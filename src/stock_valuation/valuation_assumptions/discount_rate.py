from __future__ import annotations

from decimal import Decimal

from stock_valuation.database.models import ValuationAssumption
from stock_valuation.valuation_assumptions.models import (
    LOW,
    PROJECT_POLICY_ID,
    RECOMMENDED,
    REVIEW_REQUIRED,
    ASSUMPTION_POLICY_VERSION,
    AssumptionRecommendation,
)
from stock_valuation.valuation_assumptions.policy import (
    DEFAULT_DISCOUNT_RATE,
)


def discount_rate_recommendation(manual: ValuationAssumption | None = None) -> AssumptionRecommendation:
    if manual is not None and manual.value is not None and manual.source_type == "MANUAL_APPROVED":
        return AssumptionRecommendation(
            "discount_rate",
            Decimal(manual.value),
            manual.unit or "decimal_ratio",
            RECOMMENDED,
            PROJECT_POLICY_ID,
            ASSUMPTION_POLICY_VERSION,
            (f"valuation_assumption:{manual.id}",),
            "Manual approved required return is used as Cost of Equity for Equity DCF.",
            "HIGH",
            (),
            False,
            "MANUAL_APPROVED",
            approved_value=Decimal(manual.value),
            primary_anchor="manual approved required return",
        )
    return AssumptionRecommendation(
        "discount_rate",
        DEFAULT_DISCOUNT_RATE,
        "decimal_ratio",
        REVIEW_REQUIRED,
        PROJECT_POLICY_ID,
        ASSUMPTION_POLICY_VERSION,
        (),
        "Required return falls back to generic V1 policy because sourced beta/ERP components are not complete; beta missing is not imputed as 1.",
        LOW,
        ("DISCOUNT_RATE_NOT_COMPANY_SPECIFIC", "REQUIRED_RETURN_REVIEW"),
        True,
        "GENERIC_FALLBACK",
        primary_anchor="generic V1 cost of equity fallback",
    )
