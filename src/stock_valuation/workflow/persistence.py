from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_valuation.database.models import Analysis, AnalysisStageSnapshot
from stock_valuation.valuation.models import stable_hash


def json_default(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, tuple):
        return list(value)
    if is_dataclass(value):
        return asdict(value)
    return str(value)


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, default=json_default, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_hash(payload: Any) -> str:
    return stable_hash((canonical_json(payload),))


def latest_stage_snapshot(
    session: Session,
    analysis: Analysis | int,
    stage: str,
) -> AnalysisStageSnapshot | None:
    analysis_id = analysis if isinstance(analysis, int) else analysis.id
    return session.scalar(
        select(AnalysisStageSnapshot)
        .where(
            AnalysisStageSnapshot.analysis_id == analysis_id,
            AnalysisStageSnapshot.stage == stage,
        )
        .order_by(AnalysisStageSnapshot.created_at.desc(), AnalysisStageSnapshot.id.desc())
        .limit(1)
    )


def persist_stage_snapshot(
    session: Session,
    analysis: Analysis,
    *,
    stage: str,
    engine_version: str,
    inputs_hash: str,
    status: str,
    payload: dict[str, Any],
) -> AnalysisStageSnapshot:
    payload_json = canonical_json(payload)
    existing = latest_stage_snapshot(session, analysis, stage)
    if (
        existing is not None
        and existing.engine_version == engine_version
        and existing.inputs_hash == inputs_hash
        and existing.status == status
        and existing.payload_json == payload_json
    ):
        return existing
    snapshot_id = stable_hash((str(analysis.id), stage, engine_version, inputs_hash, payload_json))
    existing_by_id = session.scalar(
        select(AnalysisStageSnapshot).where(AnalysisStageSnapshot.snapshot_id == snapshot_id)
    )
    if existing_by_id is not None:
        if (
            existing_by_id.analysis_id == analysis.id
            and existing_by_id.stage == stage
            and existing_by_id.engine_version == engine_version
            and existing_by_id.inputs_hash == inputs_hash
            and existing_by_id.status == status
            and existing_by_id.payload_json == payload_json
        ):
            return existing_by_id
        raise ValueError("STAGE_SNAPSHOT_ID_COLLISION")
    row = AnalysisStageSnapshot(
        analysis_id=analysis.id,
        stage=stage,
        snapshot_id=snapshot_id,
        engine_version=engine_version,
        inputs_hash=inputs_hash,
        status=status,
        payload_json=payload_json,
    )
    session.add(row)
    session.commit()
    return row


def payload_from_stage(row: AnalysisStageSnapshot | None) -> dict[str, Any]:
    if row is None:
        return {}
    return json.loads(row.payload_json)
