from __future__ import annotations

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
