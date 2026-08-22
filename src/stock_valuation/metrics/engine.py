from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


CALCULATION_VERSION = "3a-0.2"


@dataclass(frozen=True)
class MetricPoint:
    metric_id: str
    period_end: date
    value: Decimal | None
    unit: str
    basis: str = "reported"
    calculation_version: str = CALCULATION_VERSION
    inputs_hash: str | None = None


def safe_ratio(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    """Return numerator/denominator without inventing values for missing or zero inputs."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def calculate_ebit_margin(
    operating_income: Decimal | None,
    revenue: Decimal | None,
) -> Decimal | None:
    """Calculate EBIT/operating margin as a decimal fraction."""
    return safe_ratio(operating_income, revenue)


def calculate_ebitda_margin(
    operating_income: Decimal | None,
    depreciation_amortization: Decimal | None,
    revenue: Decimal | None,
) -> Decimal | None:
    """Calculate EBITDA margin as (operating income + D&A) / revenue."""
    if operating_income is None or depreciation_amortization is None:
        return None
    return safe_ratio(operating_income + depreciation_amortization, revenue)
