from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_valuation.database.models import FinancialFactSnapshot


DEFAULT_PROVIDER_PRIORITY: tuple[str, ...] = (
    "manual_override",
    "asml_primary",
    "esef_xbrl_json",
    "esef_ixbrl",
    "sec_companyfacts",
    "alphavantage",
    "eodhd",
)


def load_preferred_financial_facts(
    session: Session,
    analysis_id: int,
    *,
    metrics: Iterable[str] | None = None,
    period_type: str = "FY",
    provider_priority: tuple[str, ...] = DEFAULT_PROVIDER_PRIORITY,
) -> list[FinancialFactSnapshot]:
    """Resolve one canonical stored fact for every metric/period pair.

    The function performs no network access and no arithmetic transformation. It only selects
    among facts already persisted in the selected analysis snapshot. Explicit manual overrides
    win, followed by official primary sources and then provider fallbacks. Lower-priority facts
    remain stored for audit and comparison.
    """
    query = select(FinancialFactSnapshot).where(
        FinancialFactSnapshot.analysis_id == analysis_id,
        FinancialFactSnapshot.period_type == period_type,
        FinancialFactSnapshot.provider.in_(provider_priority),
    )
    metric_list = list(metrics) if metrics is not None else None
    if metric_list:
        query = query.where(FinancialFactSnapshot.metric.in_(metric_list))

    facts = session.scalars(query).all()
    priority = {provider: rank for rank, provider in enumerate(provider_priority)}

    selected: dict[tuple[str, object], FinancialFactSnapshot] = {}
    for fact in facts:
        key = (fact.metric, fact.period_end)
        existing = selected.get(key)
        if existing is None:
            selected[key] = fact
            continue
        existing_rank = priority.get(existing.provider or "", len(priority))
        candidate_rank = priority.get(fact.provider or "", len(priority))
        if candidate_rank < existing_rank:
            selected[key] = fact

    return sorted(selected.values(), key=lambda fact: (fact.period_end, fact.metric))


def preferred_fact_index(
    session: Session,
    analysis_id: int,
    *,
    metrics: Iterable[str] | None = None,
    period_type: str = "FY",
    provider_priority: tuple[str, ...] = DEFAULT_PROVIDER_PRIORITY,
) -> dict[tuple[str, object], FinancialFactSnapshot]:
    """Return preferred facts indexed by `(metric, period_end)`."""
    return {
        (fact.metric, fact.period_end): fact
        for fact in load_preferred_financial_facts(
            session,
            analysis_id,
            metrics=metrics,
            period_type=period_type,
            provider_priority=provider_priority,
        )
    }
