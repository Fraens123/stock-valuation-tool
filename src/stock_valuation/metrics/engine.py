from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


CALCULATION_VERSION = "3a-0.3"


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
    ebit: Decimal | None,
    revenue: Decimal | None,
) -> Decimal | None:
    """Calculate EBIT margin as a decimal fraction from already approved inputs."""
    return safe_ratio(ebit, revenue)


def calculate_ebitda_margin(
    ebit: Decimal | None,
    depreciation_amortization: Decimal | None,
    revenue: Decimal | None,
) -> Decimal | None:
    """Calculate EBITDA margin as (EBIT + D&A) / revenue from already approved inputs."""
    if ebit is None or depreciation_amortization is None:
        return None
    return safe_ratio(ebit + depreciation_amortization, revenue)
