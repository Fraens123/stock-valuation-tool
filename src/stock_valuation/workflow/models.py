from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


READY = "READY"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
BLOCKED = "BLOCKED"
NOT_RUN = "NOT_RUN"
STALE = "STALE"
UNAVAILABLE = "UNAVAILABLE"
READY_FOR_PREVIEW = "READY_FOR_PREVIEW"
APPROVED = "APPROVED"


STAGES = (
    "FINANCIAL_DATA",
    "CALCULATION",
    "HISTORICAL_ANALYSIS",
    "BUSINESS_QUALITY",
    "MARKET_DATA",
    "ASSUMPTIONS",
    "VALUATION",
)


@dataclass(frozen=True)
class StageState:
    stage: str
    status: str
    version: str | None = None
    inputs_hash: str | None = None
    snapshot_id: str | None = None
    created_at: datetime | None = None
    warnings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)
    technically_available: bool = False
    review_required: bool = False
    approved: bool = False


@dataclass(frozen=True)
class AnalysisState:
    analysis_id: int
    company_name: str
    ticker: str
    as_of_date: str
    revision_number: int
    analysis_status: str
    stages: dict[str, StageState]
    history_years: tuple[int, ...] = ()
    market_snapshot_id: str | None = None
    final_valuation_snapshot_id: str | None = None


@dataclass(frozen=True)
class FinalizationIssue:
    code: str
    category: str
    message_de: str
    severity: str
    blocking: bool
    metric: str | None = None
    fiscal_year: int | None = None
    action_label: str | None = None
    location_hint: str | None = None
