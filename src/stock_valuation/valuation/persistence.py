from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import ensure_editable
from stock_valuation.database.models import Analysis, MarketDataSnapshotRecord, ValuationSnapshotRecord
from stock_valuation.valuation.models import ValuationSnapshot
from stock_valuation.valuation.snapshot import canonical_json


MARKET_SNAPSHOT_NOT_PERSISTED = "MARKET_SNAPSHOT_NOT_PERSISTED"
VALUATION_NOT_READY = "VALUATION_NOT_READY"
SNAPSHOT_ID_COLLISION = "SNAPSHOT_ID_COLLISION"


def persist_valuation_snapshot(
    session: Session,
    analysis: Analysis,
    snapshot: ValuationSnapshot,
) -> ValuationSnapshotRecord:
    ensure_editable(analysis)
    _validate_analysis_identity(analysis, snapshot)
    market_record = _market_snapshot_for_valuation(session, analysis, snapshot.market_snapshot_id)
    if market_record is None:
        raise ValueError(f"{MARKET_SNAPSHOT_NOT_PERSISTED}:{VALUATION_NOT_READY}")

    payload = asdict(snapshot)
    payload_json = canonical_json(payload)
    existing = session.scalar(
        select(ValuationSnapshotRecord).where(
            ValuationSnapshotRecord.snapshot_id == snapshot.snapshot_id
        )
    )
    if existing is not None:
        if existing.inputs_hash == snapshot.inputs_hash and _idempotent_payload(existing.payload_json, payload):
            return existing
        raise ValueError(SNAPSHOT_ID_COLLISION)

    record = ValuationSnapshotRecord(
        analysis_id=analysis.id,
        snapshot_id=snapshot.snapshot_id,
        analysis_as_of_date=_parse_date(snapshot.analysis_as_of_date),
        market_snapshot_id=snapshot.market_snapshot_id,
        market_data_version=snapshot.market_data_version,
        financial_data_reference=snapshot.financial_data_reference,
        calculation_version=snapshot.calculation_version,
        historical_analysis_version=snapshot.historical_analysis_version,
        quality_version=snapshot.quality_version,
        valuation_version=snapshot.valuation_version,
        assumptions_hash=snapshot.assumptions_hash,
        inputs_hash=snapshot.inputs_hash,
        ticker=_ticker_from_payload(payload),
        base_fair_value=_base_fair_value(payload),
        trading_currency=_base_trading_currency(payload),
        assumption_source=snapshot.assumptions.get("assumption_set"),
        payload_json=payload_json,
        created_at=market_record.retrieved_at,
    )
    session.add(record)
    session.commit()
    return record


def load_valuation_snapshot(session: Session, snapshot_id: str) -> ValuationSnapshotRecord | None:
    return session.scalar(
        select(ValuationSnapshotRecord).where(ValuationSnapshotRecord.snapshot_id == snapshot_id)
    )


def list_valuation_snapshots_for_analysis(
    session: Session,
    analysis: Analysis | int,
) -> list[ValuationSnapshotRecord]:
    analysis_id = analysis if isinstance(analysis, int) else analysis.id
    return list(
        session.scalars(
            select(ValuationSnapshotRecord)
            .where(ValuationSnapshotRecord.analysis_id == analysis_id)
            .order_by(ValuationSnapshotRecord.created_at.asc(), ValuationSnapshotRecord.id.asc())
        ).all()
    )


def _validate_analysis_identity(analysis: Analysis, snapshot: ValuationSnapshot) -> None:
    if snapshot.analysis_id != str(analysis.id):
        raise ValueError(f"ANALYSIS_ID_MISMATCH:{VALUATION_NOT_READY}")


def _market_snapshot_for_valuation(
    session: Session,
    analysis: Analysis,
    market_snapshot_id: str,
) -> MarketDataSnapshotRecord | None:
    row = session.scalar(
        select(MarketDataSnapshotRecord).where(
            MarketDataSnapshotRecord.snapshot_id == market_snapshot_id
        )
    )
    if row is None:
        return None
    if row.analysis_id != analysis.id:
        raise ValueError(f"MARKET_SNAPSHOT_ANALYSIS_MISMATCH:{VALUATION_NOT_READY}")
    return row


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _ticker_from_payload(payload: dict) -> str | None:
    first = next(iter(payload.get("valuation_results", {}).values()), {})
    return first.get("ticker")


def _base_summary(payload: dict) -> dict:
    for item in payload.get("valuation_results", {}).values():
        if item.get("scenario") == "base" and "fair_value_per_unit" in item:
            return item
    return {}


def _base_fair_value(payload: dict) -> Decimal | None:
    value = _base_summary(payload).get("fair_value_per_unit")
    return Decimal(str(value)) if value is not None else None


def _base_trading_currency(payload: dict) -> str | None:
    return _base_summary(payload).get("trading_currency")


def payload_from_record(record: ValuationSnapshotRecord) -> dict:
    return json.loads(record.payload_json)


def _idempotent_payload(existing_payload_json: str, new_payload: dict) -> bool:
    existing_payload = json.loads(existing_payload_json)
    existing_payload.pop("created_at", None)
    current_payload = dict(new_payload)
    current_payload.pop("created_at", None)
    return canonical_json(existing_payload) == canonical_json(current_payload)
