from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from statistics import pstdev


def d(value: str) -> Decimal:
    return Decimal(value)


@dataclass(frozen=True)
class QualityScoringConfig:
    component_weights: dict[str, Decimal] = field(
        default_factory=lambda: {
            "profitability": d("0.18"),
            "margin_quality": d("0.14"),
            "cashflow_quality": d("0.16"),
            "growth": d("0.14"),
            "balance_sheet": d("0.14"),
            "capital_efficiency": d("0.14"),
            "stability": d("0.10"),
        }
    )
    ratio_high_quality: Decimal = d("0.30")
    ratio_solid: Decimal = d("0.15")
    ratio_weak: Decimal = d("0.03")
    liquidity_solid: Decimal = d("1.00")
    liquidity_strong: Decimal = d("1.50")
    leverage_low: Decimal = d("1.00")
    leverage_high: Decimal = d("3.00")
    volatility_low: Decimal = d("0.03")
    volatility_high: Decimal = d("0.15")
    growth_solid: Decimal = d("0.05")
    growth_high: Decimal = d("0.12")


def clamp_score(score: Decimal) -> Decimal:
    return max(Decimal("0"), min(Decimal("10"), score))


def assessment_from_score(score: Decimal | None) -> str:
    if score is None:
        return "NOT_SCORED"
    if score >= Decimal("8"):
        return "STRONG"
    if score >= Decimal("6"):
        return "SOLID"
    if score >= Decimal("4"):
        return "MIXED"
    return "WEAK"


def score_positive_ratio(value: Decimal, config: QualityScoringConfig) -> Decimal:
    if value < 0:
        return Decimal("1")
    if value >= config.ratio_high_quality:
        return Decimal("9")
    if value >= config.ratio_solid:
        return Decimal("7")
    if value >= config.ratio_weak:
        return Decimal("5")
    return Decimal("3")


def score_growth(value: Decimal, config: QualityScoringConfig) -> Decimal:
    if value < Decimal("-0.10"):
        return Decimal("2")
    if value < Decimal("0"):
        return Decimal("4")
    if value >= config.growth_high:
        return Decimal("9")
    if value >= config.growth_solid:
        return Decimal("7")
    return Decimal("5")


def score_lower_is_better(value: Decimal, low: Decimal, high: Decimal) -> Decimal:
    if value <= low:
        return Decimal("9")
    if value >= high:
        return Decimal("2")
    span = high - low
    return clamp_score(Decimal("9") - ((value - low) / span * Decimal("7")))


def score_liquidity(value: Decimal, config: QualityScoringConfig) -> Decimal:
    if value >= config.liquidity_strong:
        return Decimal("8")
    if value >= config.liquidity_solid:
        return Decimal("6")
    if value >= Decimal("0.5"):
        return Decimal("4")
    return Decimal("2")


def score_volatility(value: Decimal, config: QualityScoringConfig) -> Decimal:
    return score_lower_is_better(value.copy_abs(), config.volatility_low, config.volatility_high)


def population_volatility(values: list[Decimal]) -> Decimal | None:
    if len(values) < 2:
        return None
    return Decimal(str(pstdev(values)))


def weighted_average(items: list[tuple[Decimal, Decimal]]) -> Decimal | None:
    if not items:
        return None
    total_weight = sum(weight for _, weight in items)
    if total_weight == 0:
        return None
    return sum(score * weight for score, weight in items) / total_weight
