from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from statistics import pstdev
from typing import Mapping


HISTORICAL_ANALYSIS_VERSION = "historical-v1.0"


@dataclass(frozen=True)
class HistoricalPoint:
    metric_id: str
    fiscal_year: int
    value: Decimal | None
    unit: str
    status: str = "AVAILABLE"
    issue: str | None = None


@dataclass(frozen=True)
class HistoricalSeries:
    metric_id: str
    points: tuple[HistoricalPoint, ...]


@dataclass(frozen=True)
class HistoricalResult:
    metric_id: str
    fiscal_year: int | None
    window: str
    value: Decimal | None
    unit: str
    status: str
    issue: str | None = None
    calculation_version: str = HISTORICAL_ANALYSIS_VERSION


GROWTH_METRICS = (
    "revenue",
    "operating_income",
    "net_income",
    "ebitda",
    "operating_cash_flow",
    "free_cash_flow",
)
MARGIN_METRICS = (
    "gross_margin",
    "operating_margin",
    "net_margin",
    "ebitda_margin",
    "free_cash_flow_margin",
)
CAPITAL_STRUCTURE_METRICS = (
    "equity_ratio",
    "debt",
    "net_debt",
    "debt_to_equity",
)
WORKING_CAPITAL_METRICS = (
    "working_capital",
    "working_capital_to_revenue",
    "receivables_days",
    "payables_days",
    "inventory_intensity",
    "inventory_days",
)


def series_from_points(points: list[HistoricalPoint]) -> HistoricalSeries:
    if not points:
        raise ValueError("series requires at least one point")
    return HistoricalSeries(points[0].metric_id, tuple(sorted(points, key=lambda item: item.fiscal_year)))


def yoy_growth(series: HistoricalSeries) -> tuple[HistoricalResult, ...]:
    by_year = {point.fiscal_year: point for point in series.points}
    results: list[HistoricalResult] = []
    for point in series.points:
        previous = by_year.get(point.fiscal_year - 1)
        if previous is None:
            results.append(_unavailable(series.metric_id, point.fiscal_year, "YoY", "MISSING_PRIOR_YEAR"))
            continue
        results.append(_growth_between(series.metric_id, previous, point, "YoY"))
    return tuple(results)


def cagr(series: HistoricalSeries, years: int) -> HistoricalResult:
    if years not in {3, 5, 10}:
        raise ValueError("CAGR window must be 3, 5, or 10 years")
    points = sorted(series.points, key=lambda item: item.fiscal_year)
    if len(points) < years:
        return _unavailable(series.metric_id, None, f"{years}Y_CAGR", "INSUFFICIENT_HISTORY")
    end = points[-1]
    start_year = end.fiscal_year - (years - 1)
    start = next((point for point in points if point.fiscal_year == start_year), None)
    if start is None:
        return _unavailable(series.metric_id, end.fiscal_year, f"{years}Y_CAGR", "MISSING_START_YEAR")
    if _has_bad_point(start) or _has_bad_point(end):
        return _unavailable(series.metric_id, end.fiscal_year, f"{years}Y_CAGR", "UNAVAILABLE_ENDPOINT")
    if start.value is None or end.value is None or start.value <= 0 or end.value <= 0:
        return _unavailable(series.metric_id, end.fiscal_year, f"{years}Y_CAGR", "NON_POSITIVE_ENDPOINT")
    exponent = Decimal("1") / Decimal(years - 1)
    try:
        value = (end.value / start.value) ** exponent - Decimal("1")
    except (InvalidOperation, ZeroDivisionError):
        return _unavailable(series.metric_id, end.fiscal_year, f"{years}Y_CAGR", "CALCULATION_ERROR")
    return HistoricalResult(series.metric_id, end.fiscal_year, f"{years}Y_CAGR", value, "decimal_ratio", "AVAILABLE")


def margin_trend(series: HistoricalSeries) -> HistoricalResult:
    available = [point for point in series.points if not _has_bad_point(point)]
    if len(available) < 2:
        return _unavailable(series.metric_id, None, "trend", "INSUFFICIENT_HISTORY")
    change = (available[-1].value or Decimal("0")) - (available[0].value or Decimal("0"))
    return HistoricalResult(series.metric_id, available[-1].fiscal_year, "trend", change, "decimal_ratio_delta", "AVAILABLE")


def stability_profile(series: HistoricalSeries) -> tuple[HistoricalResult, ...]:
    years = [point.fiscal_year for point in series.points]
    expected_years = set(range(min(years), max(years) + 1)) if years else set()
    actual_years = set(years)
    available = [point for point in series.points if not _has_bad_point(point)]
    negative_count = sum(1 for point in available if point.value is not None and point.value < 0)
    missing_count = len(expected_years - actual_years) + sum(1 for point in series.points if _has_bad_point(point))
    values = [point.value for point in available if point.value is not None]
    volatility = Decimal(str(pstdev(values))) if len(values) > 1 else Decimal("0")
    latest_year = max(years) if years else None
    return (
        HistoricalResult(series.metric_id, latest_year, "negative_years", Decimal(negative_count), "count", "AVAILABLE"),
        HistoricalResult(series.metric_id, latest_year, "missing_years", Decimal(missing_count), "count", "AVAILABLE"),
        HistoricalResult(series.metric_id, latest_year, "volatility", volatility, series.points[0].unit if series.points else "unknown", "AVAILABLE"),
    )


def analyze_historical_series(series_by_metric: Mapping[str, HistoricalSeries]) -> dict[str, tuple[HistoricalResult, ...]]:
    output: dict[str, list[HistoricalResult]] = {
        "yoy_growth": [],
        "cagr": [],
        "margin_trends": [],
        "capital_structure": [],
        "working_capital": [],
        "stability_quality": [],
    }
    for metric in GROWTH_METRICS:
        series = series_by_metric.get(metric)
        if series is None:
            continue
        output["yoy_growth"].extend(yoy_growth(series))
        output["cagr"].extend(cagr(series, years) for years in (3, 5, 10))
        output["stability_quality"].extend(stability_profile(series))
    for metric in MARGIN_METRICS:
        series = series_by_metric.get(metric)
        if series is not None:
            output["margin_trends"].append(margin_trend(series))
            output["stability_quality"].extend(stability_profile(series))
    for metric in CAPITAL_STRUCTURE_METRICS:
        series = series_by_metric.get(metric)
        if series is not None:
            output["capital_structure"].extend(stability_profile(series))
    for metric in WORKING_CAPITAL_METRICS:
        series = series_by_metric.get(metric)
        if series is not None:
            output["working_capital"].extend(stability_profile(series))
    return {key: tuple(value) for key, value in output.items()}


def _growth_between(metric_id: str, previous: HistoricalPoint, current: HistoricalPoint, window: str) -> HistoricalResult:
    if _has_bad_point(previous) or _has_bad_point(current):
        return _unavailable(metric_id, current.fiscal_year, window, "UNAVAILABLE_POINT")
    if previous.value is None or current.value is None:
        return _unavailable(metric_id, current.fiscal_year, window, "MISSING_VALUE")
    if previous.value == 0:
        return _unavailable(metric_id, current.fiscal_year, window, "ZERO_BASE")
    if previous.value < 0:
        return _unavailable(metric_id, current.fiscal_year, window, "NEGATIVE_BASE")
    return HistoricalResult(metric_id, current.fiscal_year, window, current.value / previous.value - Decimal("1"), "decimal_ratio", "AVAILABLE")


def _has_bad_point(point: HistoricalPoint) -> bool:
    return point.status != "AVAILABLE" or point.value is None


def _unavailable(metric_id: str, fiscal_year: int | None, window: str, issue: str) -> HistoricalResult:
    return HistoricalResult(metric_id, fiscal_year, window, None, "n/a", "UNAVAILABLE", issue)
