from __future__ import annotations

from decimal import Decimal
from statistics import median

from stock_valuation.valuation.assumptions import OUTLIER_DEVIATION_THRESHOLD
from stock_valuation.valuation.models import AVAILABLE, UNAVAILABLE, FinancialPoint, NormalizedValue, stable_hash


def normalize_three_year_metric(
    metric_id: str,
    points: tuple[FinancialPoint, ...],
    *,
    method: str = "three_year_median",
) -> NormalizedValue:
    usable = tuple(
        point
        for point in sorted(points, key=lambda item: item.fiscal_year)[-3:]
        if point.status == "AVAILABLE" and point.value is not None
    )
    input_refs = tuple(point.input_ref for point in usable)
    used_fiscal_years = tuple(point.fiscal_year for point in usable)
    input_values = tuple(point.value for point in usable if point.value is not None)
    if len(usable) < 2:
        return NormalizedValue(
            metric_id,
            method,
            None,
            points[-1].currency if points else "",
            UNAVAILABLE,
            ("INSUFFICIENT_HISTORY",),
            input_refs,
            stable_hash(tuple(point.inputs_hash for point in usable)),
            used_fiscal_years,
            input_values,
        )
    currencies = {point.currency for point in usable}
    if len(currencies) != 1:
        return NormalizedValue(
            metric_id,
            method,
            None,
            "",
            UNAVAILABLE,
            ("CURRENCY_MISMATCH",),
            input_refs,
            stable_hash(tuple(point.inputs_hash for point in usable)),
            used_fiscal_years,
            input_values,
        )
    values = input_values
    if method == "three_year_average":
        value = sum(values) / Decimal(len(values))
    elif method == "weighted_recent_average":
        weights = tuple(Decimal(index + 1) for index, _ in enumerate(values))
        value = sum(item * weight for item, weight in zip(values, weights)) / sum(weights)
    else:
        value = Decimal(str(median(values)))
        method = "three_year_median"
    issues = _outlier_issues(values)
    if method == "three_year_median" and len(usable) == 2:
        issues = issues + ("PARTIAL_NORMALIZATION_WINDOW",)
    return NormalizedValue(
        metric_id,
        method,
        value,
        usable[-1].currency,
        AVAILABLE,
        issues,
        input_refs,
        stable_hash(tuple(point.inputs_hash for point in usable)),
        used_fiscal_years,
        input_values,
    )


def _outlier_issues(values: tuple[Decimal, ...]) -> tuple[str, ...]:
    if len(values) < 3:
        return ()
    center = Decimal(str(median(values)))
    if center == 0:
        return ()
    for value in values:
        if abs(value - center) / abs(center) > OUTLIER_DEVIATION_THRESHOLD:
            return ("OUTLIER_REVIEW",)
    return ()
