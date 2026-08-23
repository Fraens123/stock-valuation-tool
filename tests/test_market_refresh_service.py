from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis, get_or_create_company, update_analysis_metadata
from stock_valuation.database.models import Base, MarketDataSnapshotRecord
from stock_valuation.market.refresh_service import refresh_market_snapshot_for_analysis
from stock_valuation.workflow.service import refresh_local_analysis_stages


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def test_market_refresh_requires_explicit_call_and_persists_snapshot() -> None:
    with _session() as session:
        company = get_or_create_company(session, name="Example AG", ticker="EXM", currency="EUR", provider_symbol="exm.de")
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        update_analysis_metadata(session, analysis, title=None, notes=None, market_price=Decimal("10"), market_price_currency="EUR")
        state_before = refresh_local_analysis_stages(session, analysis)
        assert state_before.stages["MARKET_DATA"].status in {"NOT_RUN", "UNAVAILABLE"}
        assert session.query(MarketDataSnapshotRecord).count() == 0

        snapshot_id = refresh_market_snapshot_for_analysis(
            session,
            analysis,
            manual_price=Decimal("10"),
            manual_shares_outstanding=Decimal("100"),
            provider_symbol="exm.de",
            trading_currency="EUR",
        )

        assert snapshot_id
        assert session.query(MarketDataSnapshotRecord).count() == 1
        state_after = refresh_local_analysis_stages(session, analysis)
        assert state_after.stages["MARKET_DATA"].payload["availability"]["market_cap"] == "MARKET_CAP_READY"
        assert Decimal(str(state_after.stages["MARKET_DATA"].payload["market_cap"])) == Decimal("1000")
