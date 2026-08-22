from __future__ import annotations

from typing import Iterable

from sqlalchemy import delete
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import ensure_editable
from stock_valuation.data.types import NormalizedEstimate, NormalizedFinancialFact
from stock_valuation.database.models import Analysis, EstimateSnapshot, FinancialFactSnapshot


def replace_financial_facts(
    session: Session,
    analysis: Analysis,
    facts: Iterable[NormalizedFinancialFact],
    *,
    provider: str,
    source_url: str | None = None,
) -> int:
    """Replace one provider's imported financial facts inside an editable snapshot.

    Re-running an import while an analysis is still draft/in-progress is deterministic:
    old rows from the same provider are removed first. Completed analyses remain frozen.
    """
    ensure_editable(analysis)
    rows = list(facts)

    session.execute(
        delete(FinancialFactSnapshot).where(
            FinancialFactSnapshot.analysis_id == analysis.id,
            FinancialFactSnapshot.provider == provider,
        )
    )

    for fact in rows:
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
                source_type="provider",
                source_url=source_url,
                filing_date=fact.filing_date,
                retrieved_at=fact.retrieved_at,
                is_restated=False,
                is_cross_check_only=fact.is_cross_check_only,
                note=fact.note,
            )
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


def sync_eodhd_snapshot(session: Session, analysis: Analysis, provider) -> tuple[int, int]:
    """Load EODHD annual financials and annual estimates into an editable analysis.

    The provider argument is intentionally duck-typed so tests can inject a fake provider
    without network access or credentials.
    """
    ensure_editable(analysis)
    symbol = analysis.company.provider_symbol
    if not symbol:
        raise ValueError("Für das Unternehmen fehlt ein Provider-Symbol.")

    facts = provider.get_normalized_financials(symbol, period_type="FY")
    estimates = provider.get_normalized_estimates(symbol)
    source_url = f"https://eodhd.com/api/v1.1/fundamentals/{symbol}"

    fact_count = replace_financial_facts(
        session,
        analysis,
        facts,
        provider="eodhd",
        source_url=source_url,
    )
    estimate_count = replace_estimates(
        session,
        analysis,
        estimates,
        provider="eodhd",
    )
    return fact_count, estimate_count
