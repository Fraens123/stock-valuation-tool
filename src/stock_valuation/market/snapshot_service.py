from __future__ import annotations

import hashlib
import json

from sqlalchemy.orm import Session

from stock_valuation.analyses.service import ensure_editable
from stock_valuation.database.models import Analysis, MarketDataSnapshotRecord
from stock_valuation.market.models import MarketDataSnapshot


class ImmutableMarketSnapshotStore:
    """Small append-only store used by tests and diagnostics.

    The production DB can persist the same frozen payload later. The important V1 contract is that
    adding a newer quote creates a new snapshot id and never mutates an older analysis snapshot.
    """

    def __init__(self) -> None:
        self._rows: dict[str, MarketDataSnapshot] = {}

    def add(self, snapshot: MarketDataSnapshot) -> str:
        snapshot_id = snapshot.snapshot_id or (
            f"{snapshot.company}:{snapshot.analysis_as_of_date}:"
            f"{snapshot.quote.provider_symbol}:{snapshot.quote.price_date}:{len(self._rows) + 1}"
        )
        if snapshot_id in self._rows:
            raise ValueError(f"Market snapshot already exists: {snapshot_id}")
        frozen = MarketDataSnapshot(
            company=snapshot.company,
            analysis_as_of_date=snapshot.analysis_as_of_date,
            listing=snapshot.listing,
            quote=snapshot.quote,
            share_data=snapshot.share_data,
            financial_statement_currency=snapshot.financial_statement_currency,
            net_debt=snapshot.net_debt,
            fx_rate=snapshot.fx_rate,
            snapshot_id=snapshot_id,
        )
        self._rows[snapshot_id] = frozen
        return snapshot_id

    def get(self, snapshot_id: str) -> MarketDataSnapshot:
        return self._rows[snapshot_id]


def persist_market_snapshot(
    session: Session,
    analysis: Analysis,
    snapshot: MarketDataSnapshot,
    *,
    inputs_hash: str,
) -> str:
    ensure_editable(analysis)
    snapshot_id = snapshot.snapshot_id or stable_snapshot_id(analysis.id, snapshot, inputs_hash)
    existing = (
        session.query(MarketDataSnapshotRecord)
        .filter(MarketDataSnapshotRecord.snapshot_id == snapshot_id)
        .one_or_none()
    )
    if existing is not None:
        raise ValueError(f"Market snapshot already exists: {snapshot_id}")
    payload = _snapshot_payload(snapshot)
    session.add(
        MarketDataSnapshotRecord(
            analysis_id=analysis.id,
            snapshot_id=snapshot_id,
            analysis_as_of_date=snapshot.analysis_as_of_date,
            provider=snapshot.quote.provider,
            provider_symbol=snapshot.quote.provider_symbol,
            ticker=snapshot.listing.ticker,
            exchange=snapshot.listing.exchange,
            security_type=snapshot.listing.security_type,
            trading_currency=snapshot.listing.trading_currency,
            financial_currency=snapshot.financial_statement_currency,
            price=snapshot.quote.price,
            price_date=snapshot.quote.price_date,
            shares_outstanding=snapshot.share_data.shares_outstanding,
            share_date=snapshot.share_data.share_date,
            share_basis=snapshot.share_data.share_basis,
            filing_date=snapshot.share_data.filing_date,
            fx_rate=snapshot.fx_rate.rate if snapshot.fx_rate else None,
            fx_date=snapshot.fx_rate.fx_date if snapshot.fx_rate else None,
            net_debt_ref=(
                f"{snapshot.net_debt.source}:{snapshot.net_debt.fiscal_year}:"
                f"{snapshot.net_debt.inputs_hash or ''}"
                if snapshot.net_debt
                else None
            ),
            inputs_hash=inputs_hash,
            payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            retrieved_at=snapshot.quote.retrieved_at,
        )
    )
    session.commit()
    return snapshot_id


def stable_snapshot_id(analysis_id: int, snapshot: MarketDataSnapshot, inputs_hash: str) -> str:
    payload = (
        f"{analysis_id}:{snapshot.analysis_as_of_date}:{snapshot.quote.provider_symbol}:"
        f"{snapshot.quote.price_date}:{snapshot.share_data.share_date}:{inputs_hash}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _snapshot_payload(snapshot: MarketDataSnapshot) -> dict[str, object]:
    return {
        "company": snapshot.company,
        "analysis_as_of_date": snapshot.analysis_as_of_date.isoformat(),
        "listing": {
            **snapshot.listing.__dict__,
            "adr_ratio": str(snapshot.listing.adr_ratio) if snapshot.listing.adr_ratio is not None else None,
            "underlying_share_ratio": str(snapshot.listing.underlying_share_ratio) if snapshot.listing.underlying_share_ratio is not None else None,
        },
        "quote": {
            **snapshot.quote.__dict__,
            "price": str(snapshot.quote.price) if snapshot.quote.price is not None else None,
            "original_value": str(snapshot.quote.original_value) if snapshot.quote.original_value is not None else None,
            "price_date": snapshot.quote.price_date.isoformat() if snapshot.quote.price_date else None,
            "retrieved_at": snapshot.quote.retrieved_at.isoformat(),
        },
        "shares": {
            **snapshot.share_data.__dict__,
            "shares_outstanding": str(snapshot.share_data.shares_outstanding) if snapshot.share_data.shares_outstanding is not None else None,
            "diluted_weighted_average_shares": str(snapshot.share_data.diluted_weighted_average_shares) if snapshot.share_data.diluted_weighted_average_shares is not None else None,
            "basic_weighted_average_shares": str(snapshot.share_data.basic_weighted_average_shares) if snapshot.share_data.basic_weighted_average_shares is not None else None,
            "share_date": snapshot.share_data.share_date.isoformat() if snapshot.share_data.share_date else None,
            "filing_date": snapshot.share_data.filing_date.isoformat() if snapshot.share_data.filing_date else None,
        },
        "financial_statement_currency": snapshot.financial_statement_currency,
        "net_debt": {
            **snapshot.net_debt.__dict__,
            "value": str(snapshot.net_debt.value) if snapshot.net_debt.value is not None else None,
        }
        if snapshot.net_debt
        else None,
        "fx": {
            **snapshot.fx_rate.__dict__,
            "rate": str(snapshot.fx_rate.rate) if snapshot.fx_rate and snapshot.fx_rate.rate is not None else None,
            "fx_date": snapshot.fx_rate.fx_date.isoformat() if snapshot.fx_rate and snapshot.fx_rate.fx_date else None,
        }
        if snapshot.fx_rate
        else None,
    }
