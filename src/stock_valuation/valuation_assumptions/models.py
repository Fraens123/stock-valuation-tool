from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


ASSUMPTION_ENGINE_VERSION = "assumption-engine-v1.0"
ASSUMPTION_POLICY_VERSION = "assumption-policy-v1.0"
PROJECT_POLICY_ID = "PROJECT_POLICY_V1"

AVAILABLE = "AVAILABLE"
RECOMMENDED = "RECOMMENDED"
APPROVED = "APPROVED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
NOT_APPLICABLE = "NOT_APPLICABLE"
UNAVAILABLE = "UNAVAILABLE"
LOOKAHEAD_BLOCKED = "LOOKAHEAD_BLOCKED"
INVALID_ASSUMPTION = "INVALID_ASSUMPTION"

HIGH = "HIGH"
MEDIUM = "MEDIUM"
LOW = "LOW"
VERY_LOW = "VERY_LOW"


@dataclass(frozen=True)
class AssumptionEvidence:
    evidence_id: str
    metric: str
    value: Decimal | None
    unit: str
    period: str
    window: str
    source_type: str
    source_ref: str
    source_date: str | None
    status: str
    confidence: str
    note: str = ""


@dataclass(frozen=True)
class AssumptionRecommendation:
    assumption_key: str
    recommended_value: Decimal | None
    unit: str
    status: str
    policy_id: str
    policy_version: str
    evidence_refs: tuple[str, ...]
    reasoning_summary: str
    confidence: str
    warnings: tuple[str, ...]
    requires_review: bool
    source_type: str
    approved_value: Decimal | None = None
    primary_anchor: str = ""


@dataclass(frozen=True)
class ScenarioAssumptionRecommendation:
    scenario: str
    projection_years: int
    base_fcf: Decimal | None
    annual_growth_rate: Decimal | None
    discount_rate: Decimal | None
    terminal_growth_rate: Decimal | None
    status: str
    confidence: str
    warnings: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    sources: dict[str, str]


@dataclass(frozen=True)
class AssumptionSetRecommendation:
    ticker: str
    analysis_as_of_date: str
    normalized_fcf: Decimal | None
    fcf_base_assessment: AssumptionRecommendation
    growth_recommendation: AssumptionRecommendation
    discount_rate_recommendation: AssumptionRecommendation
    terminal_growth_recommendation: AssumptionRecommendation
    projection_years_recommendation: AssumptionRecommendation
    scenarios: tuple[ScenarioAssumptionRecommendation, ...]
    evidence: tuple[AssumptionEvidence, ...]
    quality_context: dict
    historical_context: dict
    status: str
    confidence: str
    warnings: tuple[str, ...]
    requires_review: bool
    inputs_hash: str
    assumption_engine_version: str = ASSUMPTION_ENGINE_VERSION
    policy_version: str = ASSUMPTION_POLICY_VERSION
