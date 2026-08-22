from __future__ import annotations

from typing import Iterable

from sqlalchemy import delete
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import ensure_editable
from stock_valuation.data.normalization_alphavantage import normalize_alphavantage_financials
from stock_valuation.data.providers.asml_primary import (
    ASML_2025_US_GAAP_XLSX,
    download_2025_us_gaap_workbook,
    parse_primary_source_facts,
)
from stock_valuation.data.types import NormalizedEstimate, NormalizedFinancialFact
from stock_valuation.database.models import Analysis, EstimateSnapshot, FinancialFactSnapshot


def _add_financial_fact(
    session: Session,
    analysis: Analysis,
    fact: NormalizedFinancialFact,
    *,
    source_url: str | None = None,
    source_type: str = "provider",
) -> None:
    session.add(
        FinancialFactSnapshot(
            analysis_id=analysis.id,
            statement=fact.statement,
            metric=fact.metric,
            period_end=fact.period_end,
            period_type=fact.period_type,
            value=fact.value,
            provider_value=fact.provider_value,
            currency=fact.currency,
            unit=fact.unit,
            provider=fact.provider,
            provider_field=fact.provider_field,
            source_type=source_type,
            source_url=source_url,
            filing_date=fact.filing_date,
            retrieved_at=fact.retrieved_at,
            is_restated=False,
            is_cross_check_only=fact.is_cross_check_only,
            note=fact.note,
        )
    )


def replace_financial_facts(
    session: Session,
    analysis: Analysis,
    facts: Iterable[NormalizedFinancialFact],
    *,
    provider: str,
    source_url: str | None = None,
    source_type: str = "provider",
) -> int:
    """Replace one provider/source's imported financial facts inside an editable snapshot."""
    ensure_editable(analysis)
    rows = list(facts)

    session.execute(
        delete(FinancialFactSnapshot).where(
            FinancialFactSnapshot.analysis_id == analysis.id,
            FinancialFactSnapshot.provider == provider,
        )
    )

    for fact in rows:
        _add_financial_fact(
            session,
            analysis,
            fact,
            source_url=source_url,
            source_type=source_type,
        )
    session.commit()
    return len(rows)


def replace_financial_metric(
    session: Session,
    analysis: Analysis,
    facts: Iterable[NormalizedFinancialFact],
    *,
    provider: str,
    metric: str,
    source_url: str | None = None,
    source_type: str = "provider",
) -> int:
    """Replace exactly one provider/metric series without touching other snapshot facts."""
    ensure_editable(analysis)
    rows = [fact for fact in facts if fact.metric == metric]

    session.execute(
        delete(FinancialFactSnapshot).where(
            FinancialFactSnapshot.analysis_id == analysis.id,
            FinancialFactSnapshot.provider == provider,
            FinancialFactSnapshot.metric == metric,
        )
    )
    for fact in rows:
        _add_financial_fact(
            session,
            analysis,
            fact,
            source_url=source_url,
            source_type=source_type,
        )
    session.commit()
    return len(rows)


def replace_estimates(
    session: Session,
    analysis: Analysis,
    estimates: Iterable[NormalizedEstimate],
    *,
    provider: str,
) -> int:
    ensure_editable(analysis)
    rows = list(estimates)

    session.execute(
        delete(EstimateSnapshot).where(
            EstimateSnapshot.analysis_id == analysis.id,
            EstimateSnapshot.provider == provider,
        )
    )

    for item in rows:
        session.add(
            EstimateSnapshot(
                analysis_id=analysis.id,
                metric=item.metric,
                period=item.period,
                low=item.low,
                average=item.average,
                high=item.high,
                analyst_count=item.analyst_count,
                provider=item.provider,
                currency=item.currency,
                unit=item.unit,
                retrieved_at=item.retrieved_at,
            )
        )
    session.commit()
    return len(rows)


def _sync_provider_snapshot(
    session: Session,
    analysis: Analysis,
    provider,
    *,
    symbol: str,
    provider_name: str,
    source_url: str | None,
) -> tuple[int, int]:
    ensure_editable(analysis)
    facts = provider.get_normalized_financials(symbol, period_type="FY")
    estimates = provider.get_normalized_estimates(symbol)

    fact_count = replace_financial_facts(
        session,
        analysis,
        facts,
        provider=provider_name,
        source_url=source_url,
    )
    estimate_count = replace_estimates(
        session,
        analysis,
        estimates,
        provider=provider_name,
    )
    return fact_count, estimate_count


def sync_eodhd_snapshot(session: Session, analysis: Analysis, provider) -> tuple[int, int]:
    symbol = analysis.company.provider_symbol
    if not symbol:
        raise ValueError("Für das Unternehmen fehlt ein EODHD-Provider-Symbol.")
    return _sync_provider_snapshot(
        session,
        analysis,
        provider,
        symbol=symbol,
        provider_name="eodhd",
        source_url=f"https://eodhd.com/api/v1.1/fundamentals/{symbol}",
    )


def sync_alphavantage_snapshot(
    session: Session,
    analysis: Analysis,
    provider,
    *,
    symbol: str,
) -> tuple[int, int]:
    if not symbol.strip():
        raise ValueError("Für Alpha Vantage fehlt das Symbol.")
    return _sync_provider_snapshot(
        session,
        analysis,
        provider,
        symbol=symbol.strip(),
        provider_name="alphavantage",
        source_url="https://www.alphavantage.co/documentation/#fundamentals",
    )


def sync_sec_companyfacts(
    session: Session,
    analysis: Analysis,
    provider,
    *,
    cik: str,
) -> int:
    """Import standardized official SEC XBRL facts for one SEC-reporting company."""
    ensure_editable(analysis)
    normalized_cik = str(cik).strip().replace("CIK", "").zfill(10)
    facts = provider.get_normalized_financials(normalized_cik)
    if not facts:
        raise ValueError("SEC Company Facts lieferte keine unterstützten standardisierten Finanzfakten.")
    return replace_financial_facts(
        session,
        analysis,
        facts,
        provider="sec_companyfacts",
        source_url=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{normalized_cik}.json",
        source_type="primary_source",
    )


def sync_alphavantage_depreciation_amortization(
    session: Session,
    analysis: Analysis,
    provider,
    *,
    symbol: str = "ASML",
) -> int:
    """Refresh only D&A from Alpha Vantage INCOME_STATEMENT using one API request."""
    ensure_editable(analysis)
    payload = provider.get_income_statement(symbol)
    facts = normalize_alphavantage_financials(
        {"income_statement": payload},
        period_type="FY",
    )
    return replace_financial_metric(
        session,
        analysis,
        facts,
        provider="alphavantage",
        metric="depreciation_amortization",
        source_url="https://www.alphavantage.co/documentation/#income-statement",
    )


def sync_asml_primary_source_2024_2025(
    session: Session,
    analysis: Analysis,
) -> int:
    """Import validated 2024/2025 facts from ASML's official US-GAAP workbook.

    The official source is stored alongside Alpha Vantage facts under its own provider key;
    nothing from Alpha Vantage is overwritten. The imported records are marked as
    `source_type=primary_source` for later deterministic source-priority resolution.
    """
    ensure_editable(analysis)
    if analysis.company.ticker.upper() != "ASML":
        raise ValueError("Der ASML-Primärquellenimport ist nur für den ASML-Referenzfall verfügbar.")
    content = download_2025_us_gaap_workbook()
    facts = parse_primary_source_facts(content)
    if not facts:
        raise ValueError("In der offiziellen ASML-Datei wurden keine importierbaren Fakten gefunden.")
    return replace_financial_facts(
        session,
        analysis,
        facts,
        provider="asml_primary",
        source_url=ASML_2025_US_GAAP_XLSX,
        source_type="primary_source",
    )
