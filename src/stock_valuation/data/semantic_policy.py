from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from stock_valuation.data.metric_requirements import metric_policy


SEMANTIC_POLICY_VERSION = "semantic-policy-v1.0"


class SemanticMappingDecision(str, Enum):
    SAFE_STANDARD_MAPPING = "SAFE_STANDARD_MAPPING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class SemanticMappingPolicy:
    provider: str
    provider_field: str
    internal_metric: str
    decision: SemanticMappingDecision
    reason: str
    policy_version: str = SEMANTIC_POLICY_VERSION


_SAFE_STANDARD_MAPPINGS: dict[tuple[str, str, str], str] = {
    (
        "sec_companyfacts",
        "us-gaap:DepreciationAndAmortization",
        "depreciation_amortization",
    ): "US-GAAP combined depreciation and amortization concept without depletion or catch-all wording.",
    (
        "sec_companyfacts",
        "ifrs-full:DepreciationAndAmortisationExpense",
        "depreciation_amortization",
    ): "IFRS combined depreciation and amortisation expense concept.",
    (
        "sec_companyfacts",
        "aggregation:us-gaap:Depreciation+us-gaap:AmortizationOfIntangibleAssets",
        "depreciation_amortization",
    ): "Complete US-GAAP component aggregate: tangible depreciation plus intangible amortization.",
    (
        "sec_companyfacts",
        "aggregation:ifrs-full:DepreciationExpense+ifrs-full:AmortisationExpense",
        "depreciation_amortization",
    ): "Complete IFRS component aggregate: depreciation expense plus amortisation expense.",
    (
        "sec_companyfacts",
        "us-gaap:DebtCurrent",
        "short_term_debt",
    ): "US-GAAP current debt total; excludes trade payables by taxonomy definition.",
    (
        "sec_companyfacts",
        "ifrs-full:CurrentBorrowings",
        "short_term_debt",
    ): "IFRS current borrowings total; interest-bearing current financing by taxonomy definition.",
    (
        "sec_companyfacts",
        "aggregation:us-gaap:ShortTermBorrowings+us-gaap:LongTermDebtCurrent",
        "short_term_debt",
    ): "Complete US-GAAP short-term debt aggregate: short-term borrowings plus current long-term debt.",
    (
        "sec_companyfacts",
        "us-gaap:PropertyPlantAndEquipmentNet",
        "ppe_net",
    ): "US-GAAP net property, plant and equipment standard concept.",
    (
        "sec_companyfacts",
        "ifrs-full:PropertyPlantAndEquipment",
        "ppe_net",
    ): "IFRS property, plant and equipment carrying amount; ROU assets stay separately tagged when separately reported.",
}


_EQUIVALENT_PROVIDER_SAFE_FIELDS = {
    "edgartools": "sec_companyfacts",
    "sec_filing_xbrl": "sec_companyfacts",
    "esef_xbrl_json": "sec_companyfacts",
    "esef_ixbrl": "sec_companyfacts",
}


def semantic_mapping_policy(provider: str | None, provider_field: str | None, internal_metric: str) -> SemanticMappingPolicy:
    normalized_provider = (provider or "").strip()
    normalized_field = (provider_field or "").strip()
    if not normalized_provider or not normalized_field:
        return SemanticMappingPolicy(
            provider=normalized_provider,
            provider_field=normalized_field,
            internal_metric=internal_metric,
            decision=SemanticMappingDecision.REVIEW_REQUIRED,
            reason="Provider or provider_field missing; semantic mapping cannot be proven generically.",
        )

    key = (normalized_provider, normalized_field, internal_metric)
    reason = _SAFE_STANDARD_MAPPINGS.get(key)
    if reason is None and normalized_provider in _EQUIVALENT_PROVIDER_SAFE_FIELDS:
        equivalent_key = (
            _EQUIVALENT_PROVIDER_SAFE_FIELDS[normalized_provider],
            normalized_field,
            internal_metric,
        )
        reason = _SAFE_STANDARD_MAPPINGS.get(equivalent_key)

    if reason is not None:
        return SemanticMappingPolicy(
            provider=normalized_provider,
            provider_field=normalized_field,
            internal_metric=internal_metric,
            decision=SemanticMappingDecision.SAFE_STANDARD_MAPPING,
            reason=reason,
        )

    try:
        policy = metric_policy(internal_metric)
    except KeyError:
        needs_gate = False
    else:
        needs_gate = policy.needs_semantic_gate

    return SemanticMappingPolicy(
        provider=normalized_provider,
        provider_field=normalized_field,
        internal_metric=internal_metric,
        decision=SemanticMappingDecision.REVIEW_REQUIRED if needs_gate else SemanticMappingDecision.SAFE_STANDARD_MAPPING,
        reason=(
            "Metric requires semantic gate and this provider_field is not in the versioned safe standard mapping registry."
            if needs_gate
            else "Metric does not require the semantic gate in metric_requirements.py."
        ),
    )


def safe_standard_mappings() -> tuple[SemanticMappingPolicy, ...]:
    return tuple(
        SemanticMappingPolicy(provider, provider_field, metric, SemanticMappingDecision.SAFE_STANDARD_MAPPING, reason)
        for (provider, provider_field, metric), reason in sorted(_SAFE_STANDARD_MAPPINGS.items())
    )
