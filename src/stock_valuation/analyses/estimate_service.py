from __future__ import annotations

from datetime import date

from stock_valuation.database.models import EstimateSnapshot


def _period_date(period: str) -> date | None:
    try:
        return date.fromisoformat(period[:10])
    except (TypeError, ValueError):
        return None


def relevant_estimates(
    estimates: list[EstimateSnapshot],
    *,
    as_of_date: date,
) -> list[EstimateSnapshot]:
    """Return estimate rows relevant at/after the analysis date for the normal UI.

    Alpha Vantage returns long estimate/revision history. We keep that history in the
    snapshot for audit purposes, but the normal analysis view should not be dominated by
    stale historical estimate rows. Unparseable provider period labels remain visible so
    potentially useful data is not silently discarded.
    """
    output: list[EstimateSnapshot] = []
    for item in estimates:
        parsed = _period_date(item.period)
        if parsed is None or parsed >= as_of_date:
            output.append(item)
    return output
