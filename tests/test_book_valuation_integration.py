from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis, get_or_create_company
from stock_valuation.book_valuation.persistence import upsert_book_assumption
from stock_valuation.book_valuation.service import BOOK_VALUATION_STAGE, build_book_valuation_for_analysis
from stock_valuation.database.models import AnalysisStageSnapshot, Base
from stock_valuation.ui.analysis_view_model import build_analysis_view_model
from stock_valuation.workflow.models import AnalysisState, StageState


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _workflow_state(analysis, *, calc_payload: dict, market_payload: dict) -> AnalysisState:
    return AnalysisState(
        analysis_id=analysis.id,
        company_name=analysis.company.name,
        ticker=analysis.company.ticker,
        as_of_date=analysis.as_of_date.isoformat(),
        revision_number=analysis.revision_number,
        analysis_status=analysis.status.value,
        market_snapshot_id=market_payload.get("snapshot_id"),
        stages={
            "FINANCIAL_DATA": StageState("FINANCIAL_DATA", "READY"),
            "CALCULATION": StageState("CALCULATION", "READY", payload=calc_payload, inputs_hash="calc-hash"),
            "HISTORICAL_ANALYSIS": StageState("HISTORICAL_ANALYSIS", "READY"),
            "BUSINESS_QUALITY": StageState("BUSINESS_QUALITY", "READY", payload={"result": {}}),
            "MARKET_DATA": StageState("MARKET_DATA", "READY", payload=market_payload, inputs_hash="market-hash", snapshot_id=market_payload.get("snapshot_id")),
            "ASSUMPTIONS": StageState(
                "ASSUMPTIONS",
                "READY",
                payload={
                    "effective_recommendations": {
                        "growth_rate": {"recommended_value": "0.03"},
                        "terminal_growth_rate": {"recommended_value": "0.02"},
                        "projection_years": {"recommended_value": "3"},
                    },
                    "recommendations": {},
                },
                inputs_hash="assumption-hash",
            ),
            "VALUATION": StageState("VALUATION", "READY_FOR_PREVIEW", payload={"multiples": [], "preview": {}}),
        },
    )


def _calc_payload() -> dict:
    def facts(year, values):
        return [
            {"metric": key, "value": str(value), "currency": "EUR", "source_status": "primary_source"}
            for key, value in values.items()
        ]

    return {
        "base_facts": {
            "2024": facts(
                2024,
                {
                    "revenue": 1000,
                    "net_income": 100,
                    "capital_expenditures": 40,
                    "intangible_purchases": 5,
                    "depreciation_amortization": 12,
                    "inventory": 20,
                    "accounts_receivable": 30,
                    "accounts_payable": 10,
                },
            ),
            "2025": facts(
                2025,
                {
                    "revenue": 1100,
                    "net_income": 130,
                    "capital_expenditures": 50,
                    "intangible_purchases": 5,
                    "depreciation_amortization": 15,
                    "inventory": 25,
                    "accounts_receivable": 35,
                    "accounts_payable": 15,
                },
            ),
        },
        "results": [],
    }


def test_book_service_computes_real_values_and_persists_snapshot() -> None:
    with _session() as session:
        company = get_or_create_company(session, name="Example", ticker="EXM", currency="EUR")
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        for key, value in {
            "base_pe": "7.5",
            "financial_stability_addon": "2",
            "market_position_addon": "2.2",
            "profitability_multiplier": "2",
            "growth_addon": "0.8",
            "individuality_addon": "2",
            "risk_free_rate": "0.032",
            "margin_of_safety": "0.5",
        }.items():
            upsert_book_assumption(session, analysis, key=key, value=Decimal(value))
        for key in ("rivalry_existing_competitors", "threat_new_entrants", "supplier_power", "buyer_power", "threat_substitutes"):
            upsert_book_assumption(session, analysis, key=key, value=Decimal("3"), unit="points")
        state = _workflow_state(
            analysis,
            calc_payload=_calc_payload(),
            market_payload={"snapshot_id": "m1", "price": "20", "shares_outstanding": "10", "payload": {"financial_statement_currency": "EUR"}, "trading_currency": "EUR"},
        )

        result = build_book_valuation_for_analysis(session, analysis, state)

        assert result.owner_earnings_history[-1].owner_earnings.value == Decimal("85")
        assert result.multiplicator_method_result.fair_pe.value == Decimal("16.7")
        assert result.multiplicator_method_result.forecast_eps.value == Decimal("13")
        assert result.multiplicator_method_result.fair_price_per_share.value == Decimal("217.1")
        assert result.discount_rate_result.cost_of_equity.value == Decimal("0.09188023952095808383233532934")
        assert result.terminal_value_result.terminal_value.value is not None
        assert result.fair_value_result.fair_value_per_share.value is not None
        assert session.query(AnalysisStageSnapshot).filter_by(stage=BOOK_VALUATION_STAGE).count() == 1


def test_book_result_is_rendered_by_view_model() -> None:
    with _session() as session:
        company = get_or_create_company(session, name="Example", ticker="EXM", currency="EUR")
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        upsert_book_assumption(session, analysis, key="fair_pe", value=Decimal("16"))
        upsert_book_assumption(session, analysis, key="risk_free_rate", value=Decimal("0.032"))
        state = _workflow_state(
            analysis,
            calc_payload=_calc_payload(),
            market_payload={"snapshot_id": "m1", "price": "20", "shares_outstanding": "10", "payload": {"financial_statement_currency": "EUR"}, "trading_currency": "EUR"},
        )
        result = build_book_valuation_for_analysis(session, analysis, state)
        vm = build_analysis_view_model(state, book_valuation_result=result)

        fair_pe = next(point for section in vm.sections for point in section.points if point.key == "fair_pe")
        owner_earnings = next(point for section in vm.sections for point in section.points if point.key == "owner_earnings")
        fair_price = next(point for section in vm.sections for point in section.points if point.key == "multiplicator_fair_price_per_share")

        assert fair_pe.latest_value != "Nicht verfügbar"
        assert owner_earnings.latest_value != "Nicht verfügbar"
        assert fair_price.latest_value != "Nicht verfügbar"
