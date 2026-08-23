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
from stock_valuation.data.providers.edgartools_provider import (
    EdgarToolsProvider,
    EdgarToolsProviderError,
)
from stock_valuation.data.providers.sec import SECCompanyFactsProvider, SECProviderError
from stock_valuation.data.providers.sec_extension import (
    SECCompanyExtensionProvider,
    SECCompanyExtensionResult,
)
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


class EdgarToolsProviderLike(Protocol):
    def get_normalized_financials(self, ticker_or_cik: str) -> list[NormalizedFinancialFact]: ...


class SECFilingProviderLike(Protocol):
    def gap_facts(
        self,
        cik: str,
        base_facts: list[NormalizedFinancialFact],
        *,
        years: int = 10,
    ) -> SECFilingFallbackResult: ...


class SECExtensionProviderLike(Protocol):
    def candidate_facts(
        self,
        cik: str,
        gaps,
        base_facts,
    ) -> SECCompanyExtensionResult: ...


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
    extension_provider: SECExtensionProviderLike | None,
    attempts: list[SourceAttempt],
) -> int:
    """Fill SEC Company-Facts gaps without silently guessing company-extension semantics.

    Stage 1 imports only supported standard XBRL concepts from the original 10-K/20-F/40-F.
    Stage 2 may store a best company-extension candidate, but that candidate is blocked by the
    Preferred-Data layer until the existing ChatGPT semantic review returns PASS (or a reviewed
    correction is explicitly accepted as an override).
    """
    result = provider.gap_facts(cik, base_facts, years=10)
    standard_rows = list(result.facts)
    standard_count = replace_financial_facts(
        session,
        analysis,
        standard_rows,
        provider="sec_filing_xbrl",
        source_url="https://www.sec.gov/Archives/edgar/data/",
        source_type="primary_source",
    )

    if standard_count:
        standard_status = "supplemented"
        standard_message = (
            f"{standard_count} fehlende Standard-XBRL-Fakten aus "
            f"{result.filings_checked} Originalfiling(s) ergänzt."
        )
    else:
        standard_status = "checked_no_standard_fill"
        standard_message = (
            "Originalfilings geprüft; keine zusätzliche sichere Standard-XBRL-Zuordnung gefunden."
        )
    if result.unresolved:
        standard_message += (
            f" {len(result.unresolved)} Feld/Jahr-Kombination(en) benötigen noch eine "
            "Company-Extension-/Textprüfung."
        )
    attempts.append(
        SourceAttempt(
            "SEC Original-Filing",
            standard_status,
            standard_count,
            str(cik),
            standard_message,
        )
    )

    candidate_rows: list[NormalizedFinancialFact] = []
    remaining_unresolved = tuple(result.unresolved)
    checked = 0
    if result.unresolved and extension_provider is not None:
        extension_result = extension_provider.candidate_facts(cik, result.unresolved, base_facts)
        candidate_rows = list(extension_result.facts)
        remaining_unresolved = tuple(extension_result.unresolved)
        checked = extension_result.filings_checked

    candidate_count = replace_financial_facts(
        session,
        analysis,
        candidate_rows,
        provider="sec_filing_extension",
        source_url="https://www.sec.gov/Archives/edgar/data/",
        source_type="primary_source",
    )

    if candidate_count:
        extension_status = "candidates_found"
        extension_message = (
            f"{candidate_count} firmeneigene XBRL-Kandidat(en) aus {checked} Filing-Prüfung(en) "
            "gefunden. Sie bleiben bis zum semantischen PASS blockiert."
        )
    elif result.unresolved:
        extension_status = "checked_no_candidate"
        extension_message = "Keine ausreichend plausiblen firmeneigenen XBRL-Kandidaten gefunden."
    else:
        extension_status = "not_needed"
        extension_message = "Keine offenen Standard-XBRL-Lücken für eine Extension-Prüfung."
    if remaining_unresolved:
        extension_message += (
            f" {len(remaining_unresolved)} Feld/Jahr-Kombination(en) bleiben weiterhin offen."
        )
    attempts.append(
        SourceAttempt(
            "SEC Extension-Mapping",
            extension_status,
            candidate_count,
            str(cik),
            extension_message,
        )
    )
    return standard_count + candidate_count


def sync_best_available_financials(
    session: Session,
    analysis: Analysis,
    *,
    sec_provider: SECProviderLike | None = None,
    edgartools_provider: EdgarToolsProviderLike | None = None,
    sec_filing_provider: SECFilingProviderLike | None = None,
    sec_extension_provider: SECExtensionProviderLike | None = None,
    gleif_provider: GLEIFProviderLike | None = None,
    esef_provider: ESEFProviderLike | None = None,
    alpha_provider: AlphaVantageProvider | None = None,
    allow_alpha_fallback: bool = True,
    esef_filing_limit: int = 8,
) -> FinancialSourceResult:
    """Load one coherent historical dataset from the best available source.

    Routing order is source-level to avoid silently mixing accounting bases:

    1. SEC Company Facts for SEC-reporting issuers, with targeted original-filing fallbacks inside
       the same SEC reporting basis. Standard tags can fill gaps automatically; company-extension
       candidates remain blocked until semantic review.
    2. ESEF via GLEIF LEI for issuers not sufficiently covered by SEC.
    3. Alpha Vantage only as a fallback when no official structured source is usable.

    Lower-level provider errors are recorded as attempts. Analyst estimates remain outside this
    function.
    """
    ensure_editable(analysis)
    attempts: list[SourceAttempt] = []

    # --- SEC -----------------------------------------------------------------
    edgar_facts: list[NormalizedFinancialFact] = []
    edgar_count = 0
    edgar = edgartools_provider
    if edgar is None and sec_provider is None and os.getenv("SEC_USER_AGENT"):
        try:
            edgar = EdgarToolsProvider()
        except (ValueError, EdgarToolsProviderError) as exc:
            attempts.append(SourceAttempt("EdgarTools", "unavailable", message=str(exc)))

    if edgar is not None:
        try:
            facts = edgar.get_normalized_financials(analysis.company.ticker)
            if _usable(facts):
                edgar_facts = facts
                edgar_count = _store_primary(
                    session,
                    analysis,
                    facts,
                    provider="edgartools",
                    source_url="https://www.sec.gov/edgar/search/",
                )
                attempts.append(
                    SourceAttempt(
                        "EdgarTools",
                        "selected_candidate",
                        edgar_count,
                        analysis.company.ticker,
                        (
                            "EdgarTools SEC/XBRL-Daten importiert. Bestehende SEC Company Facts "
                            "bleiben als Fallback/Ergänzung aktiv."
                        ),
                    )
                )
            else:
                attempts.append(
                    SourceAttempt(
                        "EdgarTools",
                        "insufficient",
                        len(facts),
                        analysis.company.ticker,
                        "EdgarTools lieferte nicht genug nutzbare strukturierte Fakten.",
                    )
                )
        except (EdgarToolsProviderError, ValueError) as exc:
            attempts.append(
                SourceAttempt(
                    "EdgarTools",
                    "error",
                    identifier=analysis.company.ticker,
                    message=str(exc),
                )
            )

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
                        note=(
                            "Automatisch über SEC-Ticker/CIK-Verzeichnis aufgelöst "
                            f"({sec_match_name or analysis.company.name})."
                        ),
                    )
                    count = _store_primary(
                        session,
                        analysis,
                        facts,
                        provider="sec_companyfacts",
                        source_url=(
                            "https://data.sec.gov/api/xbrl/companyfacts/"
                            f"CIK{str(cik).zfill(10)}.json"
                        ),
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

                    extension = sec_extension_provider
                    if extension is None and isinstance(filing, SECFilingFallbackProvider):
                        extension = SECCompanyExtensionProvider(filing)

                    filing_count = 0
                    if filing is not None:
                        try:
                            filing_count = _supplement_sec_filing_gaps(
                                session,
                                analysis,
                                cik=str(cik),
                                base_facts=facts,
                                provider=filing,
                                extension_provider=extension,
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
                        edgar_count + count + filing_count,
                        tuple(attempts),
                        _report_currency([*edgar_facts, *facts]) or currency,
                    )
                attempts.append(
                    SourceAttempt(
                        "SEC",
                        "insufficient",
                        len(facts),
                        str(cik),
                        (
                            "SEC-Daten vorhanden, aber für einen kohärenten Standardimport zu wenig "
                            "unterstützte Fakten."
                        ),
                    )
                )
            else:
                attempts.append(SourceAttempt("SEC", "not_found", message="Kein sicherer SEC-CIK-Treffer."))
        except (SECProviderError, ProviderError, ValueError) as exc:
            attempts.append(SourceAttempt("SEC", "error", message=str(exc)))

    if edgar_count:
        return FinancialSourceResult(
            "SEC",
            edgar_count,
            tuple(attempts),
            _report_currency(edgar_facts),
        )

    # --- ESEF ----------------------------------------------------------------
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
                    (
                        "ESEF-Filings gefunden, aber zu wenig standardisierte IFRS-Fakten für den "
                        "automatischen Import."
                    ),
                )
            )
        else:
            attempts.append(SourceAttempt("ESEF", "not_found", message="Kein eindeutiger LEI-Treffer über GLEIF."))
    except (GLEIFProviderError, ESEFRegistryError, ProviderError, ValueError) as exc:
        attempts.append(SourceAttempt("ESEF", "error", message=str(exc)))

    # --- Alpha Vantage fallback ---------------------------------------------
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
