from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis, get_or_create_company, update_analysis_metadata
from stock_valuation.database.models import Base, MarketDataSnapshotRecord
from stock_valuation.market.models import ListingData, MarketDataSnapshot, NetDebtInput, NormalizedMarketQuote, NormalizedShareData
from stock_valuation.market.refresh_service import refresh_market_snapshot_for_analysis
from stock_valuation.market.snapshot_service import persist_market_snapshot
from stock_valuation.workflow.persistence import persist_stage_snapshot
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


def test_market_refresh_reuses_existing_shares_and_calculation_net_debt() -> None:
    with _session() as session:
        company = get_or_create_company(session, name="Example AG", ticker="EXM", currency="EUR", provider_symbol="exm.de")
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        previous = MarketDataSnapshot(
            company=company.name,
            analysis_as_of_date=analysis.as_of_date,
            listing=ListingData("EXM", "XETRA", "EUR", "ordinary_share", True),
            quote=NormalizedMarketQuote("EXM", "XETRA", "EUR", Decimal("9"), analysis.as_of_date, datetime.now(UTC), "manual", "exm.de"),
            share_data=NormalizedShareData("EXM", Decimal("100"), None, None, 2026, analysis.as_of_date, None, "manual", "user_confirmed"),
            financial_statement_currency="EUR",
            net_debt=NetDebtInput(2025, None, "EUR", "missing"),
        )
        persist_market_snapshot(session, analysis, previous, inputs_hash="previous-market")
        persist_stage_snapshot(
            session,
            analysis,
            stage="CALCULATION",
            engine_version="test",
            inputs_hash="calc",
            status="READY",
            payload={"base_facts": {}, "results": [{"metric_id": "net_debt", "fiscal_year": 2025, "value": "50", "status": "AVAILABLE", "inputs_hash": "net-debt-hash"}]},
        )

        refresh_market_snapshot_for_analysis(
            session,
            analysis,
            manual_price=Decimal("10"),
            provider_symbol="exm.de",
            trading_currency="EUR",
        )
        state = refresh_local_analysis_stages(session, analysis)

        assert Decimal(str(state.stages["MARKET_DATA"].payload["market_cap"])) == Decimal("1000")
        assert Decimal(str(state.stages["MARKET_DATA"].payload["enterprise_value"])) == Decimal("1050")
        assert state.stages["MARKET_DATA"].payload["availability"]["enterprise_value"] == "EV_READY"
