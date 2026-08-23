from __future__ import annotations

from decimal import Decimal

from stock_valuation.valuation_assumptions.models import (
    AVAILABLE,
    INSUFFICIENT_EVIDENCE,
    LOW,
    MEDIUM,
    PROJECT_POLICY_ID,
    RECOMMENDED,
    REVIEW_REQUIRED,
    ASSUMPTION_POLICY_VERSION,
    AssumptionRecommendation,
)


def assess_fcf_base(normalized_fcf: dict) -> AssumptionRecommendation:
    value = Decimal(str(normalized_fcf["value"])) if normalized_fcf.get("value") not in (None, "") else None
    issues = tuple(normalized_fcf.get("issues", ()))
    if value is None or normalized_fcf.get("status") != AVAILABLE:
        return AssumptionRecommendation(
            "base_fcf",
            None,
            "currency",
            INSUFFICIENT_EVIDENCE,
            PROJECT_POLICY_ID,
            ASSUMPTION_POLICY_VERSION,
            tuple(normalized_fcf.get("input_refs", ())),
            "Normalized FCF is unavailable; no substitute or zero was imputed.",
            LOW,
            ("FCF_BASE_UNAVAILABLE",),
            True,
            "NORMALIZED_FINANCIALS",
        )
    warnings = tuple(issue for issue in issues if issue in {"OUTLIER_REVIEW", "PARTIAL_NORMALIZATION_WINDOW"})
    status = REVIEW_REQUIRED if warnings else RECOMMENDED
    return AssumptionRecommendation(
        "base_fcf",
        value,
        "currency",
        status,
        PROJECT_POLICY_ID,
        ASSUMPTION_POLICY_VERSION,
        tuple(normalized_fcf.get("input_refs", ())),
        "DCF base FCF uses the existing frozen normalized_fcf; Phase 7 does not recompute FCF.",
        LOW if warnings else MEDIUM,
        tuple(f"FCF_BASE_{issue}" for issue in warnings),
        bool(warnings),
        "NORMALIZED_FINANCIALS",
        primary_anchor="normalized_fcf",
    )
