from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


QUALITY_ENGINE_VERSION = "quality-v1.0"

AVAILABLE = "AVAILABLE"
UNAVAILABLE = "UNAVAILABLE"
NOT_APPLICABLE = "NOT_APPLICABLE"
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"

UPSTREAM_NON_PENALTY_STATUSES = {
    "NOT_SEPARATELY_REPORTED",
    "NEGATIVE_BASE",
    "MISSING_PRIOR_YEAR",
    "INSUFFICIENT_HISTORY",
    "MISSING_START_YEAR",
    "UNAVAILABLE_POINT",
}


@dataclass(frozen=True)
class QualityInput:
    metric_id: str
    fiscal_year: int | None
    window: str
    value: Decimal | None
    unit: str
    status: str
    issue: str | None
    source: str
    input_provenance: str = ""
    inputs_hash: str = ""
    source_version: str = ""


@dataclass(frozen=True)
class QualityMetricDefinition:
    metric_id: str
    name: str
    category: str
    formula: str
    inputs: tuple[str, ...]
    unit: str
    meaning: str
    availability_rule: str
    interpretation: str
    limitations: str
    suitable_business_models: str
    unsuitable_business_models: str
    source_category: str
    threshold_rationale: str


@dataclass(frozen=True)
class QualityMetricResult:
    metric_id: str
    name: str
    category: str
    fiscal_year: int | None
    window: str
    value: Decimal | None
    unit: str
    trend: str
    assessment: str
    score: Decimal | None
    status: str
    issue: str | None
    source_category: str
    input_metrics: tuple[str, ...]
    input_refs: tuple[str, ...]
    inputs_hash: str
    rule_version: str = QUALITY_ENGINE_VERSION


@dataclass(frozen=True)
class QualityScoreComponent:
    component_id: str
    score: Decimal | None
    weight: Decimal
    status: str
    contributing_metrics: tuple[str, ...]
    issue: str | None = None


@dataclass(frozen=True)
class QualityCompanyResult:
    ticker: str
    years: tuple[int, ...]
    metrics: tuple[QualityMetricResult, ...]
    component_scores: tuple[QualityScoreComponent, ...]
    overall_score: Decimal | None
    assessment: str
    positive_factors: tuple[str, ...]
    negative_factors: tuple[str, ...]
    unavailable_factors: tuple[str, ...]
    not_applicable_factors: tuple[str, ...]
    quality_version: str = QUALITY_ENGINE_VERSION
