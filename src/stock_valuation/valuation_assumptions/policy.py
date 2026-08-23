from __future__ import annotations

from decimal import Decimal

from stock_valuation.valuation_assumptions.models import (
    ASSUMPTION_POLICY_VERSION,
    PROJECT_POLICY_ID,
    HIGH,
    LOW,
    MEDIUM,
    VERY_LOW,
)


MAX_SUSTAINABLE_GROWTH = Decimal("0.15")
MIN_GROWTH = Decimal("-0.05")
DEFAULT_DISCOUNT_RATE = Decimal("0.09")
DEFAULT_BEAR_DISCOUNT_RATE = Decimal("0.10")
DEFAULT_BULL_DISCOUNT_RATE = Decimal("0.08")
DEFAULT_TERMINAL_GROWTH = Decimal("0.02")
DEFAULT_BEAR_TERMINAL_GROWTH = Decimal("0.01")
DEFAULT_BULL_TERMINAL_GROWTH = Decimal("0.03")
DISCOUNT_RATE_SCENARIO_SPREAD = Decimal("0.01")
TERMINAL_GROWTH_SCENARIO_SPREAD = Decimal("0.01")
DEFAULT_PROJECTION_YEARS = 5
MIN_SCENARIO_SPREAD = Decimal("0.02")
MAX_SCENARIO_SPREAD = Decimal("0.05")
HIGH_VOLATILITY_THRESHOLD = Decimal("0.10")
STABLE_MARGIN_VOLATILITY_THRESHOLD = Decimal("0.03")


def clamp_growth(value: Decimal) -> tuple[Decimal, tuple[str, ...]]:
    warnings: list[str] = []
    if value > MAX_SUSTAINABLE_GROWTH:
        warnings.append("GROWTH_SUSTAINABILITY_REVIEW")
        return MAX_SUSTAINABLE_GROWTH, tuple(warnings)
    if value < MIN_GROWTH:
        warnings.append("NEGATIVE_GROWTH_REVIEW")
        return value, tuple(warnings)
    return value, ()


def confidence_from_history(years: int, warnings: tuple[str, ...]) -> str:
    if years >= 10 and not warnings:
        return HIGH
    if years >= 5 and len(warnings) <= 1:
        return MEDIUM
    if years >= 3:
        return LOW if warnings else MEDIUM
    return VERY_LOW


def policy_ref() -> tuple[str, str]:
    return PROJECT_POLICY_ID, ASSUMPTION_POLICY_VERSION
