from __future__ import annotations

from collections import Counter
from datetime import date

from stock_valuation.database.models import EstimateSnapshot, FinancialFactSnapshot


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


def infer_fiscal_year_end_month_day(
    annual_facts: list[FinancialFactSnapshot],
) -> tuple[int, int] | None:
    """Infer the company's normal fiscal year-end from stored annual financial facts.

    Providers can return estimates for both quarters and full fiscal years in the same
    endpoint. The most common month/day among annual statement dates gives us a transparent
    company-specific discriminator without hard-coding Microsoft, ASML, or calendar years.
    """
    dates = [fact.period_end for fact in annual_facts if fact.period_type == "FY"]
    if not dates:
        return None
    counts = Counter((item.month, item.day) for item in dates)
    return counts.most_common(1)[0][0]


def estimate_period_type(
    period: str,
    *,
    fiscal_year_end: tuple[int, int] | None,
) -> str:
    """Classify an estimate period as annual, quarterly, or unknown.

    Alpha Vantage documents that EARNINGS_ESTIMATES mixes annual and quarterly rows. The
    provider payload does not currently get a dedicated period-type column in our snapshot,
    so V1 classifies the display/forecast horizon against the company's observed fiscal
    year-end. Exact fiscal-year-end dates are annual; other parseable dates are quarterly.
    """
    parsed = _period_date(period)
    if parsed is None or fiscal_year_end is None:
        return "Unbekannt"
    if (parsed.month, parsed.day) == fiscal_year_end:
        return "Jahr"
    return "Quartal"


def annual_estimates(
    estimates: list[EstimateSnapshot],
    *,
    fiscal_year_end: tuple[int, int] | None,
) -> list[EstimateSnapshot]:
    """Return only full-fiscal-year estimate rows for later DCF/forecast use."""
    return [
        item
        for item in estimates
        if estimate_period_type(item.period, fiscal_year_end=fiscal_year_end) == "Jahr"
    ]
