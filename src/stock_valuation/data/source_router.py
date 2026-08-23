from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from stock_valuation.analyses.service import ensure_editable
from stock_valuation.companies.provider_symbols import get_provider_symbol, upsert_provider_symbol
from stock_valuation.data.providers.alphavantage import AlphaVantageProvider
from stock_valuation.data.providers.base import ProviderError
from stock_valuation.data.providers.esef_registry import ESEFRegistryError, ESEFRegistryProvider
from stock_valuation.data.providers.gleif import GLEIFProvider, GLEIFProviderError
from stock_valuation.data.providers.sec import SECCompanyFactsProvider, SECProviderError
from stock_valuation.data.providers.sec_filing import (
    SECFilingFallbackError,
    SECFilingFallbackProvider,
    SECFilingFallbackResult,
)
from stock_valuation.data.snapshot_service import replace_financial_facts
from stock_valuation.data.types import NormalizedFinancialFact
from stock_valuation.database.models import Analysis


CORE_METRICS = {"revenue", "net_income", "total_assets", "shareholders_equity", "operating_cash_flow"}


@dataclass(frozen=True)
class SourceAttempt:
    source: str
    status: str
    fact_count: int = 0
    identifier: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class FinancialSourceResult:
    selected_source: str | None
    fact_count: int
    attempts: tuple[SourceAttempt, ...]
    report_currency: str | None = None

    @property
    def success(self) -> bool:
        return self.selected_source is not None and self.fact_count > 0


class SECProviderLike(Protocol):
    def resolve_company(self, ticker: str, name: str | None = None): ...
    def get_normalized_financials(self, cik: str) -> list[NormalizedFinancialFact]: ...


class SECFilingProviderLike(Protocol):
    def gap_facts(
        self,
        cik: str,
        base_facts: list[NormalizedFinancialFact],
        *,
        years: int = 10,
    ) -> SECFilingFallbackResult: ...


class GLEIFProviderLike(Protocol):
    def resolve_lei(self, legal_name: str, *, country: str | None = None): ...


class ESEFProviderLike(Protocol):
    def get_normalized_financials(self, lei: str, *, filing_limit: int = 8) -> list[NormalizedFinancialFact]: ...


def _usable(facts: list[NormalizedFinancialFact]) -> bool:
    if len(facts) < 8:
        return False
    years = {row.period_end.year for row in facts if row.value is not None}
    metrics = {row.metric for row in facts if row.value is not None}
    return len(years) >= 2 and bool(metrics & CORE_METRICS)


def _report_currency(facts: list[NormalizedFinancialFact]) -> str | None:
    currencies = [
        str(row.currency or "").upper()
        for row in facts
        if row.currency and row.unit == "currency"
    ]
    if not currencies:
        return None
    return Counter(currencies).most_common(1)[0][0]


def _store_primary(
    session: Session,
    analysis: Analysis,
    facts: list[NormalizedFinancialFact],
    *,
    provider: str,
    source_url: str,
) -> int:
    count = replace_financial_facts(
        session,
        analysis,
        facts,
        provider=provider,
        source_url=source_url,
        source_type="primary_source",
    )
    currency = _report_currency(facts)
    if currency:
        analysis.company.currency = currency
        session.commit()
    return count


def _supplement_sec_filing_gaps(
    session: Session,
    analysis: Analysis,
    *,
    cik: str,
    base_facts: list[NormalizedFinancialFact],
    provider: SECFilingProviderLike,
    attempts: list[SourceAttempt],
) -> int:
    """Fill only Company-Facts gaps from the original SEC XBRL filing.

    This stays inside the SEC accounting source. Standard taxonomy facts can be persisted as
    primary-source supplements. Missing fields that require a company extension remain unresolved
    and are surfaced in the router message instead of being guessed.
    """
    result = provider.gap_facts(cik, base_facts, years=10)
    supplemented = list(result.facts)
    count = replace_financial_facts(
        session,
        analysis,
        supplemented,
        provider="sec_filing_xbrl",
        source_url="https://www.sec.gov/Archives/edgar/data/",
        source_type="primary_source",
    )
    unresolved_count = len(result.unresolved)
    if count:
        status = "supplemented"
        message = (
            f"{count} fehlende Standard-XBRL-Fakten aus {result.filings_checked} Originalfiling(s) ergänzt."
        )
    else:
        status = "checked_no_standard_fill"
        message = "Originalfilings geprüft; keine zusätzliche sichere Standard-XBRL-Zuordnung gefunden."
    if unresolved_count:
        message += (
            f" {unresolved_count} Feld/Jahr-Kombination(en) bleiben offen und benötigen "
            "Extension-/Textprüfung."
        )
    attempts.append(
        SourceAttempt(
            "SEC Original-Filing",
            status,
            count,
            str(cik),
            message,
        )
    )
    return count


def sync_best_available_financials(
    session: Session,
    analysis: Analysis,
    *,
    sec_provider: SECProviderLike | None = None,
    sec_filing_provider: SECFilingProviderLike | None = None,
    gleif_provider: GLEIFProviderLike | None = None,
    esef_provider: ESEFProviderLike | None = None,
    alpha_provider: AlphaVantageProvider | None = None,
    allow_alpha_fallback: bool = True,
    esef_filing_limit: int = 8,
) -> FinancialSourceResult:
    """Load one coherent historical dataset from the best available source.

    Routing order is source-level to avoid silently mixing accounting bases:

    1. SEC Company Facts for SEC-reporting issuers, with a targeted original-filing XBRL fallback
       for missing standard concepts inside the same SEC reporting basis.
    2. ESEF via GLEIF LEI for issuers not sufficiently covered by SEC.
    3. Alpha Vantage only as a fallback when no official structured source is usable.

    Lower-level provider errors are recorded as attempts. One unavailable source does not abort the
    remaining routes. Analyst estimates are deliberately outside this function.
    """
    ensure_editable(analysis)
    attempts: list[SourceAttempt] = []

    # --- SEC -----------------------------------------------------------------
    sec = sec_provider
    if sec is None and os.getenv("SEC_USER_AGENT"):
        try:
            sec = SECCompanyFactsProvider()
        except ValueError as exc:
            attempts.append(SourceAttempt("SEC", "unavailable", message=str(exc)))

    if sec is not None:
        try:
            stored_cik = get_provider_symbol(session, analysis.company, provider="sec", purpose="cik")
            if stored_cik is not None:
                cik = stored_cik.symbol
                sec_match_name = analysis.company.name
            else:
                match = sec.resolve_company(analysis.company.ticker, analysis.company.name)
                cik = match.cik if match is not None else None
                sec_match_name = match.name if match is not None else None
            if cik:
                facts = sec.get_normalized_financials(cik)
                if _usable(facts):
                    upsert_provider_symbol(
                        session,
                        analysis.company,
                        provider="sec",
                        purpose="cik",
                        symbol=cik,
                        note=f"Automatisch über SEC-Ticker/CIK-Verzeichnis aufgelöst ({sec_match_name or analysis.company.name}).",
                    )
                    count = _store_primary(
                        session,
                        analysis,
                        facts,
                        provider="sec_companyfacts",
                        source_url=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{str(cik).zfill(10)}.json",
                    )
                    currency = _report_currency(facts)
                    attempts.append(
                        SourceAttempt(
                            "SEC Company Facts",
                            "selected",
                            count,
                            str(cik),
                            "Offizielle aggregierte SEC-XBRL-Daten.",
                        )
                    )

                    filing = sec_filing_provider
                    if filing is None and isinstance(sec, SECCompanyFactsProvider):
                        try:
                            filing = SECFilingFallbackProvider(
                                user_agent=sec.user_agent,
                                timeout=sec.timeout,
                                use_cache=sec.use_cache,
                            )
                        except ValueError as exc:
                            attempts.append(
                                SourceAttempt("SEC Original-Filing", "unavailable", message=str(exc))
                            )
                    filing_count = 0
                    if filing is not None:
                        try:
                            filing_count = _supplement_sec_filing_gaps(
                                session,
                                analysis,
                                cik=str(cik),
                                base_facts=facts,
                                provider=filing,
                                attempts=attempts,
                            )
                        except (SECFilingFallbackError, ProviderError, ValueError) as exc:
                            attempts.append(
                                SourceAttempt(
                                    "SEC Original-Filing",
                                    "error",
                                    identifier=str(cik),
                                    message=str(exc),
                                )
                            )
                    return FinancialSourceResult(
                        "SEC",
                        count + filing_count,
                        tuple(attempts),
                        currency,
                    )
                attempts.append(
                    SourceAttempt(
                        "SEC",
                        "insufficient",
                        len(facts),
                        str(cik),
                        "SEC-Daten vorhanden, aber für einen kohärenten Standardimport zu wenig unterstützte Fakten.",
                    )
                )
            else:
                attempts.append(SourceAttempt("SEC", "not_found", message="Kein sicherer SEC-CIK-Treffer."))
        except (SECProviderError, ProviderError, ValueError) as exc:
            attempts.append(SourceAttempt("SEC", "error", message=str(exc)))

    # --- ESEF ---------------------------------------------------------------
    gleif = gleif_provider or GLEIFProvider()
    esef = esef_provider or ESEFRegistryProvider()
    try:
        stored_lei = get_provider_symbol(session, analysis.company, provider="gleif", purpose="lei")
        if stored_lei is not None:
            lei = stored_lei.symbol
            lei_name = analysis.company.name
        else:
            lei_match = gleif.resolve_lei(analysis.company.name, country=analysis.company.country)
            lei = lei_match.lei if lei_match is not None else None
            lei_name = lei_match.legal_name if lei_match is not None else None
        if lei:
            facts = esef.get_normalized_financials(lei, filing_limit=esef_filing_limit)
            if _usable(facts):
                upsert_provider_symbol(
                    session,
                    analysis.company,
                    provider="gleif",
                    purpose="lei",
                    symbol=lei,
                    note=f"Automatisch über GLEIF aufgelöst ({lei_name or analysis.company.name}).",
                )
                count = _store_primary(
                    session,
                    analysis,
                    facts,
                    provider="esef_xbrl_json",
                    source_url="https://filings.xbrl.org/",
                )
                currency = _report_currency(facts)
                attempts.append(
                    SourceAttempt(
                        "ESEF",
                        "selected",
                        count,
                        lei,
                        "Offizielle ESEF/iXBRL-Daten über filings.xbrl.org.",
                    )
                )
                return FinancialSourceResult("ESEF", count, tuple(attempts), currency)
            attempts.append(
                SourceAttempt(
                    "ESEF",
                    "insufficient",
                    len(facts),
                    lei,
                    "ESEF-Filings gefunden, aber zu wenig standardisierte IFRS-Fakten für den automatischen Import.",
                )
            )
        else:
            attempts.append(SourceAttempt("ESEF", "not_found", message="Kein eindeutiger LEI-Treffer über GLEIF."))
    except (GLEIFProviderError, ESEFRegistryError, ProviderError, ValueError) as exc:
        attempts.append(SourceAttempt("ESEF", "error", message=str(exc)))

    # --- Alpha Vantage fallback --------------------------------------------
    if allow_alpha_fallback:
        alpha = alpha_provider
        if alpha is None and os.getenv("ALPHA_VANTAGE_API_KEY"):
            try:
                alpha = AlphaVantageProvider()
            except ValueError as exc:
                attempts.append(SourceAttempt("Alpha Vantage", "unavailable", message=str(exc)))
        if alpha is not None:
            alpha_symbol_row = get_provider_symbol(
                session,
                analysis.company,
                provider="alphavantage",
                purpose="fundamentals",
            )
            alpha_symbol = (
                alpha_symbol_row.symbol if alpha_symbol_row is not None else analysis.company.ticker
            )
            try:
                facts = alpha.get_normalized_financials(alpha_symbol, period_type="FY")
                if facts:
                    count = replace_financial_facts(
                        session,
                        analysis,
                        facts,
                        provider="alphavantage",
                        source_url="https://www.alphavantage.co/documentation/#fundamentals",
                        source_type="provider",
                    )
                    attempts.append(
                        SourceAttempt("Alpha Vantage", "selected_fallback", count, alpha_symbol)
                    )
                    return FinancialSourceResult(
                        "Alpha Vantage",
                        count,
                        tuple(attempts),
                        _report_currency(facts),
                    )
                attempts.append(
                    SourceAttempt("Alpha Vantage", "not_found", identifier=alpha_symbol)
                )
            except (ProviderError, ValueError) as exc:
                attempts.append(
                    SourceAttempt(
                        "Alpha Vantage",
                        "error",
                        identifier=alpha_symbol,
                        message=str(exc),
                    )
                )

    return FinancialSourceResult(None, 0, tuple(attempts), None)
