from __future__ import annotations

from decimal import Decimal

from stock_valuation.valuation.models import DCFScenario


DEFAULT_DCF_SCENARIOS: tuple[DCFScenario, ...] = (
    DCFScenario("bear", 5, Decimal("0.02"), Decimal("0.10"), Decimal("0.01")),
    DCFScenario("base", 5, Decimal("0.05"), Decimal("0.09"), Decimal("0.02")),
    DCFScenario("bull", 5, Decimal("0.08"), Decimal("0.08"), Decimal("0.03")),
)

DEFAULT_SENSITIVITY_DISCOUNT_RATES: tuple[Decimal, ...] = (
    Decimal("0.07"),
    Decimal("0.08"),
    Decimal("0.09"),
    Decimal("0.10"),
)

DEFAULT_SENSITIVITY_TERMINAL_GROWTH_RATES: tuple[Decimal, ...] = (
    Decimal("0.01"),
    Decimal("0.02"),
    Decimal("0.03"),
)

NORMALIZATION_METHOD = "three_year_median"
OUTLIER_DEVIATION_THRESHOLD = Decimal("0.50")
