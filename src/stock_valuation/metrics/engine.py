from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


CALCULATION_VERSION = "3a-0.1"


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
    """Calculate EBIT/operating margin as a decimal fraction.

    For the ASML reference case the validated provider input `operating_income` maps to
    ASML's `Income from operations`. The generic target definition remains EBIT / Revenue.
    Provider-specific semantics must be validated before this function is used for another
    company/provider combination.
    """
    return safe_ratio(operating_income, revenue)
