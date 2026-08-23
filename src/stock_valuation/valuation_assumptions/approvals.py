from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import ensure_editable
from stock_valuation.database.models import Analysis, AssumptionApprovalRecord
from stock_valuation.valuation_assumptions.models import (
    ASSUMPTION_ENGINE_VERSION,
    ASSUMPTION_POLICY_VERSION,
    APPROVED,
    AssumptionRecommendation,
)


APPROVAL_STALE = "APPROVAL_STALE"
MANUAL_APPROVED = "MANUAL_APPROVED"
MANUAL_APPROVED_OVERRIDE = "MANUAL_APPROVED_OVERRIDE"


def approve_recommended_value(
    session: Session,
    analysis: Analysis,
    recommendation: AssumptionRecommendation,
    *,
    scenario: str = "base",
    method: str = "equity_dcf",
    recommendation_inputs_hash: str,
    note: str | None = None,
) -> AssumptionApprovalRecord:
    ensure_editable(analysis)
    if recommendation.recommended_value is None:
        raise ValueError("Cannot approve an unavailable recommendation.")
    return _append_approval(
        session,
        analysis,
        method=method,
        scenario=scenario,
        key=recommendation.assumption_key,
        recommended_value=recommendation.recommended_value,
        approved_value=recommendation.recommended_value,
        unit=recommendation.unit,
        source_type=MANUAL_APPROVED,
        note=note,
        recommendation_inputs_hash=recommendation_inputs_hash,
    )


def override_assumption(
    session: Session,
    analysis: Analysis,
    recommendation: AssumptionRecommendation,
    *,
    approved_value: Decimal,
    scenario: str = "base",
    method: str = "equity_dcf",
    recommendation_inputs_hash: str,
    note: str,
) -> AssumptionApprovalRecord:
    ensure_editable(analysis)
    if not note or not note.strip():
        raise ValueError("Manual approved override requires a note.")
    return _append_approval(
        session,
        analysis,
        method=method,
        scenario=scenario,
        key=recommendation.assumption_key,
        recommended_value=recommendation.recommended_value,
        approved_value=approved_value,
        unit=recommendation.unit,
        source_type=MANUAL_APPROVED_OVERRIDE,
        note=note,
        recommendation_inputs_hash=recommendation_inputs_hash,
    )


def load_current_approvals(
    session: Session,
    analysis: Analysis,
    *,
    method: str = "equity_dcf",
) -> dict[tuple[str, str], AssumptionApprovalRecord]:
    rows = session.scalars(
        select(AssumptionApprovalRecord)
        .where(
            AssumptionApprovalRecord.analysis_id == analysis.id,
            AssumptionApprovalRecord.method == method,
        )
        .order_by(AssumptionApprovalRecord.approved_at.asc(), AssumptionApprovalRecord.id.asc())
    ).all()
    current: dict[tuple[str, str], AssumptionApprovalRecord] = {}
    for row in rows:
        current[(row.scenario, row.key)] = row
    return current


def validate_approvals(
    approvals: dict[tuple[str, str], AssumptionApprovalRecord],
    *,
    recommendation_inputs_hash: str,
) -> tuple[dict[tuple[str, str], AssumptionApprovalRecord], tuple[str, ...]]:
    valid: dict[tuple[str, str], AssumptionApprovalRecord] = {}
    warnings: list[str] = []
    for key, row in approvals.items():
        if (
            row.recommendation_inputs_hash != recommendation_inputs_hash
            or row.policy_version != ASSUMPTION_POLICY_VERSION
            or row.engine_version != ASSUMPTION_ENGINE_VERSION
        ):
            warnings.append(f"{APPROVAL_STALE}:{row.scenario}:{row.key}")
            continue
        valid[key] = row
    return valid, tuple(warnings)


def apply_approval(
    recommendation: AssumptionRecommendation,
    approval: AssumptionApprovalRecord | None,
) -> AssumptionRecommendation:
    if approval is None:
        return recommendation
    return AssumptionRecommendation(
        assumption_key=recommendation.assumption_key,
        recommended_value=recommendation.recommended_value,
        unit=recommendation.unit,
        status=APPROVED,
        policy_id=recommendation.policy_id,
        policy_version=recommendation.policy_version,
        evidence_refs=recommendation.evidence_refs + (f"assumption_approval:{approval.id}",),
        reasoning_summary=recommendation.reasoning_summary,
        confidence=recommendation.confidence,
        warnings=(),
        requires_review=False,
        source_type=approval.source_type,
        approved_value=Decimal(approval.approved_value) if approval.approved_value is not None else None,
        primary_anchor=recommendation.primary_anchor,
    )


def _append_approval(
    session: Session,
    analysis: Analysis,
    *,
    method: str,
    scenario: str,
    key: str,
    recommended_value: Decimal | None,
    approved_value: Decimal,
    unit: str,
    source_type: str,
    note: str | None,
    recommendation_inputs_hash: str,
) -> AssumptionApprovalRecord:
    row = AssumptionApprovalRecord(
        analysis_id=analysis.id,
        method=method,
        scenario=scenario,
        key=key,
        recommended_value=recommended_value,
        approved_value=approved_value,
        unit=unit,
        source_type=source_type,
        note=note.strip() if note else None,
        recommendation_inputs_hash=recommendation_inputs_hash,
        policy_version=ASSUMPTION_POLICY_VERSION,
        engine_version=ASSUMPTION_ENGINE_VERSION,
    )
    session.add(row)
    session.commit()
    return row
