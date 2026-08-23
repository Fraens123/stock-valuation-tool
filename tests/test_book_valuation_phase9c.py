from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis, get_or_create_company
from stock_valuation.book_valuation.persistence import upsert_book_assumption
from stock_valuation.book_valuation.service import build_book_valuation_for_analysis
from stock_valuation.database.models import Analysis, Base, FinancialFactSnapshot
from stock_valuation.ui.info_catalog import INFO_CATALOG
from stock_valuation.workflow.models import AnalysisState, StageState


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _facts(values: dict[str, str]) -> list[dict[str, str]]:
    return [
        {"metric": key, "value": value, "currency": "EUR", "source_status": "primary_source"}
        for key, value in values.items()
    ]


def _calc_payload() -> dict:
    return {
        "base_facts": {
            "2024": _facts(
                {
                    "revenue": "1000",
                    "net_income": "100",
                    "capital_expenditures": "40",
                    "intangible_purchases": "5",
                    "depreciation_amortization": "12",
                    "inventory": "20",
                    "accounts_receivable": "30",
                    "accounts_payable": "10",
                }
            ),
            "2025": _facts(
                {
                    "revenue": "1100",
                    "net_income": "130",
                    "capital_expenditures": "50",
                    "intangible_purchases": "5",
                    "depreciation_amortization": "15",
                    "inventory": "25",
                    "accounts_receivable": "35",
                    "accounts_payable": "15",
                }
            ),
        },
        "results": [],
    }


def _state(analysis: Analysis) -> AnalysisState:
    return AnalysisState(
        analysis_id=analysis.id,
        company_name=analysis.company.name,
        ticker=analysis.company.ticker,
        as_of_date=analysis.as_of_date.isoformat(),
        revision_number=analysis.revision_number,
        analysis_status=analysis.status.value,
        market_snapshot_id="m1",
        stages={
            "FINANCIAL_DATA": StageState("FINANCIAL_DATA", "READY"),
            "CALCULATION": StageState("CALCULATION", "READY", payload=_calc_payload(), inputs_hash="calc-hash"),
            "HISTORICAL_ANALYSIS": StageState("HISTORICAL_ANALYSIS", "READY"),
            "BUSINESS_QUALITY": StageState("BUSINESS_QUALITY", "READY", payload={"result": {}}),
            "MARKET_DATA": StageState(
                "MARKET_DATA",
                "READY",
                payload={"snapshot_id": "m1", "price": "20", "shares_outstanding": "10", "payload": {"financial_statement_currency": "EUR"}, "trading_currency": "EUR"},
                inputs_hash="market-hash",
                snapshot_id="m1",
            ),
            "ASSUMPTIONS": StageState("ASSUMPTIONS", "READY", payload={"effective_recommendations": {}, "recommendations": {}}, inputs_hash="assumption-hash"),
            "VALUATION": StageState("VALUATION", "READY_FOR_PREVIEW", payload={"multiples": [], "preview": {}}),
        },
    )


def _confirm_multiplicator_inputs(session: Session, analysis: Analysis, *, forecast: bool = True) -> None:
    for key, value in {
        "base_pe": "7.5",
        "financial_stability_addon": "0",
        "market_position_addon": "0",
        "profitability_multiplier": "1",
        "growth_addon": "0",
        "individuality_addon": "0",
    }.items():
        upsert_book_assumption(session, analysis, key=key, value=Decimal(value))
    if forecast:
        upsert_book_assumption(session, analysis, key="forecast_net_income", value=Decimal("130"))


def test_stored_ecb_risk_free_rate_is_used_by_book_service() -> None:
    with _session() as session:
        company = get_or_create_company(session, name="Example", ticker="EXM", currency="EUR")
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        _confirm_multiplicator_inputs(session, analysis)
        session.add(
            FinancialFactSnapshot(
                analysis_id=analysis.id,
                statement="market",
                metric="risk_free_rate_eur_aaa_10y",
                period_end=date(2026, 8, 20),
                period_type="D",
                value=Decimal("0.031"),
                provider_value=Decimal("3.1"),
                currency="EUR",
                unit="ratio",
                provider="ecb",
                provider_field="YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y",
                source_type="provider",
                retrieved_at=datetime(2026, 8, 23, tzinfo=UTC),
            )
        )
        session.commit()

        result = build_book_valuation_for_analysis(session, analysis, _state(analysis))

        assert result.discount_rate_result.risk_free_rate.value == Decimal("0.03100000")
        assert result.discount_rate_result.cost_of_equity.status == "AVAILABLE"


def test_missing_forecast_net_income_is_not_replaced_by_latest_actual_profit() -> None:
    with _session() as session:
        company = get_or_create_company(session, name="Example", ticker="EXM", currency="EUR")
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        _confirm_multiplicator_inputs(session, analysis, forecast=False)

        result = build_book_valuation_for_analysis(session, analysis, _state(analysis))

        assert result.multiplicator_method_result.forecast_net_income.value is None
        assert "MISSING_FORECAST_NET_INCOME" in result.multiplicator_method_result.forecast_net_income.issues


def test_book_dcf_scenarios_are_persisted_and_reopened() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        company = get_or_create_company(session, name="Example", ticker="EXM", currency="EUR")
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        for scenario, growth in {"bear": "0.01", "base": "0.03", "bull": "0.06"}.items():
            for key, value, unit in (
                ("base_owner_earnings", "100", "currency"),
                ("growth_rate", growth, "decimal_ratio"),
                ("projection_years", "3", "years"),
                ("fair_pe", "15", "multiple"),
                ("risk_free_rate", "0.03", "decimal_ratio"),
                ("terminal_growth_rate", "0.01", "decimal_ratio"),
                ("margin_of_safety", "0.5", "decimal_ratio"),
            ):
                upsert_book_assumption(session, analysis, key=key, value=Decimal(value), unit=unit, scenario=scenario)
        analysis_id = analysis.id

    with Session(engine) as session:
        analysis = session.get(Analysis, analysis_id)
        assert analysis is not None
        result = build_book_valuation_for_analysis(session, analysis, _state(analysis))

        bear = result.scenario_results["bear"].fair_value_per_share.value
        base = result.scenario_results["base"].fair_value_per_share.value
        bull = result.scenario_results["bull"].fair_value_per_share.value
        assert bear is not None and base is not None and bull is not None
        assert bear < base < bull


def test_every_info_entry_has_explicit_reference_status() -> None:
    for key, entry in INFO_CATALOG.items():
        assert entry.reference_status in {"KNOWN", "UNKNOWN"}, key
        if entry.reference_status == "KNOWN":
            assert entry.book_chapter or entry.book_page or entry.excel_location
