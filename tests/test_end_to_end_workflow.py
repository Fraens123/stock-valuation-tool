from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.database.models import AnalysisStageSnapshot, Base, FinancialFactSnapshot, ValuationSnapshotRecord
from stock_valuation.market.models import (
    ListingData,
    MarketDataSnapshot,
    NetDebtInput,
    NormalizedMarketQuote,
    NormalizedShareData,
)
from stock_valuation.market.snapshot_service import persist_market_snapshot
from stock_valuation.valuation_assumptions.approvals import approve_recommended_value, override_assumption
from stock_valuation.valuation_assumptions.models import AssumptionRecommendation
from stock_valuation.workflow.service import refresh_local_analysis_stages


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def _file_session(path):
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def _add_fact(session, analysis, metric: str, year: int, value: str, currency: str = "USD"):
    session.add(
        FinancialFactSnapshot(
            analysis_id=analysis.id,
            statement="test",
            metric=metric,
            period_end=date(year, 12, 31),
            period_type="FY",
            value=Decimal(value),
            currency=currency,
            unit="currency",
            provider="manual_override",
            provider_field=metric,
            source_type="primary_source",
            filing_date=date(year + 1, 2, 1),
        )
    )


def _seed_financials(session, analysis, *, revenue_2025: str = "1210"):
    values = {
        2023: {
            "revenue": "1000",
            "gross_profit": "600",
            "operating_income": "250",
            "net_income": "200",
            "total_assets": "2000",
            "current_assets": "800",
            "cash_and_equivalents": "300",
            "accounts_receivable": "100",
            "inventory": "150",
            "total_liabilities": "900",
            "current_liabilities": "400",
            "accounts_payable": "80",
            "short_term_debt": "100",
            "long_term_debt": "500",
            "shareholders_equity": "1100",
            "operating_cash_flow": "350",
            "capital_expenditures": "120",
            "depreciation_amortization": "50",
        },
        2024: {
            "revenue": "1100",
            "gross_profit": "660",
            "operating_income": "275",
            "net_income": "220",
            "total_assets": "2100",
            "current_assets": "820",
            "cash_and_equivalents": "320",
            "accounts_receivable": "110",
            "inventory": "155",
            "total_liabilities": "930",
            "current_liabilities": "410",
            "accounts_payable": "84",
            "short_term_debt": "95",
            "long_term_debt": "480",
            "shareholders_equity": "1170",
            "operating_cash_flow": "370",
            "capital_expenditures": "125",
            "depreciation_amortization": "52",
        },
        2025: {
            "revenue": revenue_2025,
            "gross_profit": "726",
            "operating_income": "300",
            "net_income": "240",
            "total_assets": "2200",
            "current_assets": "850",
            "cash_and_equivalents": "330",
            "accounts_receivable": "120",
            "inventory": "160",
            "total_liabilities": "950",
            "current_liabilities": "420",
            "accounts_payable": "88",
            "short_term_debt": "90",
            "long_term_debt": "460",
            "shareholders_equity": "1250",
            "operating_cash_flow": "400",
            "capital_expenditures": "130",
            "depreciation_amortization": "55",
        },
    }
    for year, rows in values.items():
        for metric, value in rows.items():
            _add_fact(session, analysis, metric, year, value)
    session.commit()


def _seed_market(session, analysis):
    snapshot = MarketDataSnapshot(
        company=analysis.company.name,
        analysis_as_of_date=analysis.as_of_date,
        listing=ListingData(
            ticker=analysis.company.ticker,
            exchange="NASDAQ",
            trading_currency="USD",
            security_type="ordinary_share",
            primary_listing=True,
            provider="test",
        ),
        quote=NormalizedMarketQuote(
            ticker=analysis.company.ticker,
            exchange="NASDAQ",
            listing_currency="USD",
            price=Decimal("100"),
            price_date=analysis.as_of_date,
            retrieved_at=datetime(2026, 8, 23, tzinfo=UTC),
            provider="test",
            provider_symbol=analysis.company.ticker,
        ),
        share_data=NormalizedShareData(
            ticker=analysis.company.ticker,
            shares_outstanding=Decimal("10"),
            diluted_weighted_average_shares=Decimal("10"),
            basic_weighted_average_shares=Decimal("10"),
            fiscal_year=2025,
            share_date=date(2025, 12, 31),
            filing_date=date(2026, 2, 1),
            provider="test",
            source="filing",
        ),
        financial_statement_currency="USD",
        net_debt=NetDebtInput(2025, Decimal("220"), "USD", "calculation", "net-debt-hash"),
    )
    return persist_market_snapshot(session, analysis, snapshot, inputs_hash="market-hash")


def _setup_analysis(session):
    company = get_or_create_company(session, name="Workflow Co", ticker="WFLW", currency="USD")
    analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
    _seed_financials(session, analysis)
    _seed_market(session, analysis)
    return analysis


def _force_normalized_fcf_to_100(session, analysis):
    for year in (2023, 2024, 2025):
        ocf = session.scalar(
            select(FinancialFactSnapshot).where(
                FinancialFactSnapshot.analysis_id == analysis.id,
                FinancialFactSnapshot.metric == "operating_cash_flow",
                FinancialFactSnapshot.period_end == date(year, 12, 31),
            )
        )
        capex = session.scalar(
            select(FinancialFactSnapshot).where(
                FinancialFactSnapshot.analysis_id == analysis.id,
                FinancialFactSnapshot.metric == "capital_expenditures",
                FinancialFactSnapshot.period_end == date(year, 12, 31),
            )
        )
        ocf.value = Decimal("200")
        capex.value = Decimal("100")
    session.commit()


def _recommendation(payload: dict, key: str) -> AssumptionRecommendation:
    row = payload["recommendations"][key]
    return AssumptionRecommendation(
        **{
            **row,
            "recommended_value": Decimal(str(row["recommended_value"])) if row.get("recommended_value") is not None else None,
            "approved_value": Decimal(str(row["approved_value"])) if row.get("approved_value") is not None else None,
            "warnings": tuple(row.get("warnings", ())),
            "evidence_refs": tuple(row.get("evidence_refs", ())),
        }
    )


def test_review_required_workflow_keeps_preview_available_without_diagnostics_csv():
    with _session() as session:
        analysis = _setup_analysis(session)

        state = refresh_local_analysis_stages(session, analysis)

        assert state.stages["FINANCIAL_DATA"].status == "READY"
        assert state.stages["CALCULATION"].status == "READY"
        assert state.stages["HISTORICAL_ANALYSIS"].status == "READY"
        assert state.stages["BUSINESS_QUALITY"].status == "READY"
        assert state.stages["MARKET_DATA"].status == "READY"
        assert state.stages["ASSUMPTIONS"].status == "REVIEW_REQUIRED"
        assert state.stages["VALUATION"].status == "READY_FOR_PREVIEW"
        assert state.stages["CALCULATION"].payload["diagnostics_csv_used"] is False
        assert state.history_years == (2023, 2024, 2025)


def test_approved_assumptions_create_persistent_final_valuation_after_reopen(tmp_path):
    db_path = tmp_path / "workflow.sqlite"
    with _file_session(db_path) as session:
        analysis = _setup_analysis(session)
        state = refresh_local_analysis_stages(session, analysis)
        assumptions = state.stages["ASSUMPTIONS"].payload
        for key in ("base_fcf", "growth_rate", "discount_rate", "terminal_growth_rate", "projection_years"):
            approve_recommended_value(
                session,
                analysis,
                _recommendation(assumptions, key),
                recommendation_inputs_hash=assumptions["assumption_set"]["inputs_hash"],
            )

        state = refresh_local_analysis_stages(session, analysis)

        assert state.stages["ASSUMPTIONS"].status == "READY"
        assert state.stages["VALUATION"].status == "READY"
        snapshot = session.scalar(select(ValuationSnapshotRecord).where(ValuationSnapshotRecord.analysis_id == analysis.id))
        assert snapshot is not None
        snapshot_id = snapshot.snapshot_id
        analysis_id = analysis.id

    with _file_session(db_path) as other_session:
        reopened = other_session.scalar(select(ValuationSnapshotRecord).where(ValuationSnapshotRecord.analysis_id == analysis_id))
        assert reopened is not None
        assert reopened.snapshot_id == snapshot_id


def test_changed_inputs_make_approval_stale_and_do_not_overwrite_old_final_snapshot():
    with _session() as session:
        analysis = _setup_analysis(session)
        state = refresh_local_analysis_stages(session, analysis)
        assumptions = state.stages["ASSUMPTIONS"].payload
        for key in ("base_fcf", "growth_rate", "discount_rate", "terminal_growth_rate", "projection_years"):
            approve_recommended_value(
                session,
                analysis,
                _recommendation(assumptions, key),
                recommendation_inputs_hash=assumptions["assumption_set"]["inputs_hash"],
            )
        final_state = refresh_local_analysis_stages(session, analysis)
        old_snapshot = final_state.final_valuation_snapshot_id

        fact = session.scalar(
            select(FinancialFactSnapshot).where(
                FinancialFactSnapshot.analysis_id == analysis.id,
                FinancialFactSnapshot.metric == "revenue",
                FinancialFactSnapshot.period_end == date(2025, 12, 31),
            )
        )
        fact.value = Decimal("1500")
        session.commit()

        new_state = refresh_local_analysis_stages(session, analysis)

        assert old_snapshot is not None
        assert new_state.final_valuation_snapshot_id == old_snapshot
        assert new_state.stages["ASSUMPTIONS"].status == "REVIEW_REQUIRED"
        assert any("APPROVAL_STALE" in warning for warning in new_state.stages["ASSUMPTIONS"].warnings)
        assert session.scalar(select(AnalysisStageSnapshot).where(AnalysisStageSnapshot.stage == "VALUATION").order_by(AnalysisStageSnapshot.id.desc())).status == "READY_FOR_PREVIEW"


def test_overrides_are_effective_in_preview_final_scenarios_and_persisted_snapshot(tmp_path):
    db_path = tmp_path / "override-workflow.sqlite"
    with _file_session(db_path) as session:
        analysis = _setup_analysis(session)
        _force_normalized_fcf_to_100(session, analysis)
        base_state = refresh_local_analysis_stages(session, analysis)
        base_preview = Decimal(str(base_state.stages["VALUATION"].payload["preview"]["base"]["fair_value_per_unit"]))
        assumptions = base_state.stages["ASSUMPTIONS"].payload

        overrides = {
            "base_fcf": Decimal("150"),
            "growth_rate": Decimal("0.02"),
            "discount_rate": Decimal("0.11"),
            "terminal_growth_rate": Decimal("0.025"),
            "projection_years": Decimal("7"),
        }
        for key, value in overrides.items():
            override_assumption(
                session,
                analysis,
                _recommendation(assumptions, key),
                approved_value=value,
                recommendation_inputs_hash=assumptions["recommendation_inputs_hash"],
                note=f"test override {key}",
            )

        final_state = refresh_local_analysis_stages(session, analysis)
        valuation = final_state.stages["VALUATION"].payload
        scenarios = {row["scenario"]: row for row in valuation["effective_scenarios"]}
        final_preview = valuation["preview"]

        assert final_state.stages["ASSUMPTIONS"].status == "READY"
        assert final_state.stages["VALUATION"].status == "READY"
        assert Decimal(str(assumptions["normalized_fcf"]["value"])) == Decimal("100")
        assert Decimal(str(valuation["effective_base_fcf"]["value"])) == Decimal("150")
        assert Decimal(str(scenarios["base"]["annual_growth_rate"])) == Decimal("0.02")
        assert Decimal(str(scenarios["base"]["discount_rate"])) == Decimal("0.11")
        assert Decimal(str(scenarios["bear"]["discount_rate"])) > Decimal("0.11")
        assert Decimal(str(scenarios["bull"]["discount_rate"])) < Decimal("0.11")
        assert Decimal(str(scenarios["base"]["terminal_growth_rate"])) == Decimal("0.025")
        assert Decimal(str(scenarios["bear"]["terminal_growth_rate"])) < Decimal("0.025")
        assert Decimal(str(scenarios["bull"]["terminal_growth_rate"])) > Decimal("0.025")
        assert {row["projection_years"] for row in scenarios.values()} == {7}
        assert scenarios["bear"] != scenarios["base"] != scenarios["bull"]
        assert Decimal(str(final_preview["bear"]["fair_value_per_unit"])) <= Decimal(str(final_preview["base"]["fair_value_per_unit"])) <= Decimal(str(final_preview["bull"]["fair_value_per_unit"]))
        assert Decimal(str(final_preview["base"]["fair_value_per_unit"])) != base_preview
        assert all("assumption_approval:" in ref for ref in valuation["effective_base_fcf"]["input_refs"] if "assumption_approval:" in ref)

        record = session.scalar(select(ValuationSnapshotRecord).where(ValuationSnapshotRecord.analysis_id == analysis.id))
        assert record is not None
        record_id = record.snapshot_id
        payload = json.loads(record.payload_json)
        effective = payload["assumptions"]["effective_recommendations"]
        assert effective["base_fcf"]["approved_value"] == "150.00000000"
        assert effective["growth_rate"]["approved_value"] == "0.02000000"
        assert effective["discount_rate"]["approved_value"] == "0.11000000"
        assert effective["terminal_growth_rate"]["approved_value"] == "0.02500000"
        assert effective["projection_years"]["approved_value"] == "7.00000000"

    with _file_session(db_path) as reopened:
        persisted = reopened.scalar(select(ValuationSnapshotRecord).where(ValuationSnapshotRecord.snapshot_id == record_id))
        assert persisted is not None
        payload = json.loads(persisted.payload_json)
        assert payload["normalized_inputs"]["free_cash_flow"]["value"] == "150.00000000"


def test_partial_approval_preview_uses_approved_discount_and_recommendations_for_rest():
    with _session() as session:
        analysis = _setup_analysis(session)
        state = refresh_local_analysis_stages(session, analysis)
        assumptions = state.stages["ASSUMPTIONS"].payload
        override_assumption(
            session,
            analysis,
            _recommendation(assumptions, "discount_rate"),
            approved_value=Decimal("0.11"),
            recommendation_inputs_hash=assumptions["recommendation_inputs_hash"],
            note="discount review",
        )

        state = refresh_local_analysis_stages(session, analysis)
        scenarios = {row["scenario"]: row for row in state.stages["VALUATION"].payload["effective_scenarios"]}

        assert state.stages["ASSUMPTIONS"].status == "REVIEW_REQUIRED"
        assert state.stages["VALUATION"].status == "READY_FOR_PREVIEW"
        assert Decimal(str(scenarios["base"]["discount_rate"])) == Decimal("0.11")
        assert Decimal(str(scenarios["base"]["annual_growth_rate"])) == Decimal(str(state.stages["ASSUMPTIONS"].payload["raw_recommendations"]["growth_rate"]["recommended_value"]))
