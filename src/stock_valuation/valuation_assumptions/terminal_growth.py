from __future__ import annotations

from decimal import Decimal

from stock_valuation.database.models import ValuationAssumption
from stock_valuation.valuation_assumptions.models import (
    INVALID_ASSUMPTION,
    LOW,
    PROJECT_POLICY_ID,
    RECOMMENDED,
    REVIEW_REQUIRED,
    ASSUMPTION_POLICY_VERSION,
    AssumptionRecommendation,
)
from stock_valuation.valuation_assumptions.policy import (
    DEFAULT_TERMINAL_GROWTH,
)


def terminal_growth_recommendation(
    discount_rate: Decimal,
    manual: ValuationAssumption | None = None,
) -> AssumptionRecommendation:
    if manual is not None and manual.value is not None and manual.source_type == "MANUAL_APPROVED":
        value = Decimal(manual.value)
        if value >= discount_rate:
            return AssumptionRecommendation(
                "terminal_growth_rate",
                value,
                manual.unit or "decimal_ratio",
                INVALID_ASSUMPTION,
                PROJECT_POLICY_ID,
                ASSUMPTION_POLICY_VERSION,
                (f"valuation_assumption:{manual.id}",),
                "Manual terminal growth is invalid because terminal_growth >= discount_rate.",
                LOW,
                ("TERMINAL_GROWTH_NOT_BELOW_DISCOUNT_RATE",),
                True,
                "MANUAL_APPROVED",
                approved_value=value,
            )
        return AssumptionRecommendation(
            "terminal_growth_rate",
            value,
            manual.unit or "decimal_ratio",
            RECOMMENDED,
            PROJECT_POLICY_ID,
            ASSUMPTION_POLICY_VERSION,
            (f"valuation_assumption:{manual.id}",),
            "Manual approved long-term terminal growth is used.",
            "HIGH",
            (),
            False,
            "MANUAL_APPROVED",
            approved_value=value,
            primary_anchor="manual approved terminal growth",
        )
    return AssumptionRecommendation(
        "terminal_growth_rate",
        DEFAULT_TERMINAL_GROWTH,
        "decimal_ratio",
        REVIEW_REQUIRED,
        PROJECT_POLICY_ID,
        ASSUMPTION_POLICY_VERSION,
        (),
        "Terminal growth uses generic V1 project policy; it is not copied from short-term company CAGR.",
        LOW,
        ("TERMINAL_GROWTH_GENERIC",),
        True,
        "PROJECT_POLICY_V1",
        primary_anchor="generic long-term nominal growth policy",
    )
