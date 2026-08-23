from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.database.models import Base, EstimateSnapshot, GuidanceSnapshot, ValuationAssumption
from stock_valuation.valuation.models import MarketSnapshotInput
from stock_valuation.valuation_assumptions.approvals import (
    APPROVAL_STALE,
    approve_recommended_value,
    load_current_approvals,
    override_assumption,
    validate_approvals,
)
from stock_valuation.valuation_assumptions.cashflow import assess_fcf_base
from stock_valuation.valuation_assumptions.discount_rate import discount_rate_recommendation
from stock_valuation.valuation_assumptions.evidence import collect_forward_evidence
from stock_valuation.valuation_assumptions.growth import growth_recommendation
from stock_valuation.valuation_assumptions.models import LOOKAHEAD_BLOCKED, REVIEW_REQUIRED
from stock_valuation.valuation_assumptions.service import build_assumption_set, build_assumption_set_for_analysis, preview_scenarios
from stock_valuation.valuation_assumptions.terminal_growth import terminal_growth_recommendation


def normalized_fcf(**overrides):
    values = {
        "metric_id": "free_cash_flow",
        "method": "three_year_median",
        "value": "100",
        "currency": "USD",
        "status": "AVAILABLE",
        "issues": [],
        "input_refs": ["calculation:fcf:2023", "calculation:fcf:2024", "calculation:fcf:2025"],
        "inputs_hash": "normalized-hash",
        "used_fiscal_years": [2023, 2024, 2025],
        "input_values": ["90", "100", "110"],
    }
    values.update(overrides)
    return values


def historical_context(**overrides):
    values = {
        "historical_analysis_version": "historical-v1.0",
        "historical_window": ["2023", "2024", "2025"],
        "revenue_growth": [
            {"fiscal_year": "2024", "value": "0.10"},
            {"fiscal_year": "2025", "value": "0.10"},
        ],
        "earnings_growth": [{"fiscal_year": "2025", "value": "0.30"}],
        "fcf_growth": [{"fiscal_year": "2025", "value": "-0.05"}],
        "cagr": {"revenue": {"3Y_CAGR": "0.10"}},
        "margin_trend": {"free_cash_flow_margin": "0.01"},
        "volatility": {"free_cash_flow": "0.03", "revenue": "0.01", "free_cash_flow_margin": "0.01"},
        "negative_years": {"free_cash_flow": "0"},
        "missing_years": {"free_cash_flow": "0"},
        "input_refs": ["historical:ref"],
        "context_hash": "historical-hash",
    }
    values.update(overrides)
    return values


def quality_context(score="8.2"):
    return {
        "overall_quality_score": score,
        "overall_quality_assessment": "STRONG",
        "quality_version": "quality-v1.0",
        "context_hash": f"quality:{score}",
    }


def market():
    return MarketSnapshotInput(
        ticker="TEST",
        company="Test Co",
        analysis_as_of_date="2026-08-23",
        market_snapshot_id="market-snapshot",
        market_data_version="market-data-v1.0",
        security_type="ordinary_share",
        price=Decimal("100"),
        market_cap=Decimal("1000"),
        enterprise_value=Decimal("1200"),
        shares_outstanding=Decimal("10"),
        share_basis="ORDINARY_SHARES",
        financial_currency="USD",
        trading_currency="USD",
        fx_rate=None,
        adr_ratio=None,
        underlying_share_ratio=None,
        input_refs=("market:ref",),
        inputs_hash="market-hash",
    )


def test_fcf_base_outlier_and_partial_require_review_without_discarding_value():
    outlier = assess_fcf_base(normalized_fcf(issues=["OUTLIER_REVIEW"]))
    partial = assess_fcf_base(normalized_fcf(issues=["PARTIAL_NORMALIZATION_WINDOW"], used_fiscal_years=[2024, 2025]))

    assert outlier.recommended_value == Decimal("100")
    assert outlier.requires_review is True
    assert "FCF_BASE_OUTLIER_REVIEW" in outlier.warnings
    assert partial.requires_review is True
    assert "FCF_BASE_PARTIAL_NORMALIZATION_WINDOW" in partial.warnings


def test_growth_does_not_average_revenue_net_income_and_fcf_growth():
    assumption_set = build_assumption_set(
        ticker="TEST",
        analysis_as_of_date="2026-08-23",
        normalized_fcf=normalized_fcf(),
        historical_context=historical_context(),
        quality_context=quality_context(),
    )

    assert assumption_set.growth_recommendation.recommended_value == Decimal("0.10")
    assert assumption_set.growth_recommendation.recommended_value != Decimal("0.1166666666666666666666666667")
    assert assumption_set.growth_recommendation.primary_anchor == "historical revenue CAGR"


def test_quality_score_does_not_directly_change_growth_or_preview_fair_value():
    first = build_assumption_set(
        ticker="TEST",
        analysis_as_of_date="2026-08-23",
        normalized_fcf=normalized_fcf(),
        historical_context=historical_context(),
        quality_context=quality_context("8.2"),
    )
    second = build_assumption_set(
        ticker="TEST",
        analysis_as_of_date="2026-08-23",
        normalized_fcf=normalized_fcf(),
        historical_context=historical_context(),
        quality_context=quality_context("2.0"),
    )

    assert first.growth_recommendation.recommended_value == second.growth_recommendation.recommended_value
    assert first.discount_rate_recommendation.recommended_value == second.discount_rate_recommendation.recommended_value
    assert preview_scenarios(first, market(), normalized_fcf())["base"]["fair_value_per_unit"] == preview_scenarios(second, market(), normalized_fcf())["base"]["fair_value_per_unit"]


def test_discount_rate_modes_and_beta_missing_is_not_imputed():
    fallback = discount_rate_recommendation()
    manual = ValuationAssumption(
        id=1,
        analysis_id=1,
        method="equity_dcf",
        scenario="base",
        key="discount_rate",
        value=Decimal("0.11"),
        unit="decimal_ratio",
        source_type="MANUAL_APPROVED",
    )
    approved = discount_rate_recommendation(manual)

    assert fallback.recommended_value == Decimal("0.09")
    assert fallback.requires_review is True
    assert "DISCOUNT_RATE_NOT_COMPANY_SPECIFIC" in fallback.warnings
    assert approved.recommended_value == Decimal("0.11")
    assert approved.requires_review is False


def test_terminal_growth_not_copied_from_high_company_cagr_and_invalid_manual_rejected():
    generic = terminal_growth_recommendation(Decimal("0.09"))
    invalid_manual = ValuationAssumption(
        id=1,
        analysis_id=1,
        method="equity_dcf",
        scenario="base",
        key="terminal_growth_rate",
        value=Decimal("0.09"),
        unit="decimal_ratio",
        source_type="MANUAL_APPROVED",
    )
    invalid = terminal_growth_recommendation(Decimal("0.09"), invalid_manual)

    assert generic.recommended_value == Decimal("0.02")
    assert "TERMINAL_GROWTH_GENERIC" in generic.warnings
    assert invalid.status == "INVALID_ASSUMPTION"


def test_scenario_ordering_and_preview_uses_frozen_valuation_engine():
    assumption_set = build_assumption_set(
        ticker="TEST",
        analysis_as_of_date="2026-08-23",
        normalized_fcf=normalized_fcf(),
        historical_context=historical_context(),
        quality_context=quality_context(),
    )
    scenarios = {item.scenario: item for item in assumption_set.scenarios}
    preview = preview_scenarios(assumption_set, market(), normalized_fcf())

    assert scenarios["bear"].annual_growth_rate <= scenarios["base"].annual_growth_rate <= scenarios["bull"].annual_growth_rate
    assert scenarios["bear"].discount_rate >= scenarios["base"].discount_rate >= scenarios["bull"].discount_rate
    assert preview["bear"]["fair_value_per_unit"] <= preview["base"]["fair_value_per_unit"] <= preview["bull"]["fair_value_per_unit"]
    assert preview["base"]["status"] == "ASSUMPTION_PREVIEW"


def test_high_volatility_reduces_confidence_and_requires_cyclicity_review():
    assumption_set = build_assumption_set(
        ticker="TEST",
        analysis_as_of_date="2026-08-23",
        normalized_fcf=normalized_fcf(),
        historical_context=historical_context(volatility={"free_cash_flow": "0.20", "free_cash_flow_margin": "0.01"}),
        quality_context=quality_context(),
    )

    assert "CYCLICALITY_REVIEW" in assumption_set.warnings
    assert assumption_set.requires_review is True


def test_missing_growth_history_requires_review():
    assumption_set = build_assumption_set(
        ticker="TEST",
        analysis_as_of_date="2026-08-23",
        normalized_fcf=normalized_fcf(),
        historical_context=historical_context(revenue_growth=[], earnings_growth=[], fcf_growth=[], cagr={}),
        quality_context=quality_context(),
    )

    assert assumption_set.growth_recommendation.status == "INSUFFICIENT_EVIDENCE"
    assert assumption_set.requires_review is True


def test_forward_evidence_point_in_time_blocks_late_guidance_and_estimates():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(session, name="Test Co", ticker="TEST", currency="USD")
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        session.add_all(
            [
                EstimateSnapshot(
                    analysis_id=analysis.id,
                    metric="revenue",
                    period="2027",
                    average=Decimal("100"),
                    retrieved_at=datetime(2026, 8, 24, tzinfo=UTC),
                    analyst_count=10,
                ),
                GuidanceSnapshot(
                    analysis_id=analysis.id,
                    metric="revenue",
                    period="2027",
                    point_estimate=Decimal("100"),
                    publication_date=date(2026, 8, 24),
                ),
            ]
        )
        session.commit()

        evidence = collect_forward_evidence(session, analysis)

    assert evidence
    assert all(item.status == LOOKAHEAD_BLOCKED for item in evidence)


def test_annual_forward_estimate_levels_are_converted_to_growth_and_quarters_not_used():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(session, name="Test Co", ticker="TEST", currency="USD")
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        session.add_all(
            [
                EstimateSnapshot(
                    analysis_id=analysis.id,
                    metric="revenue",
                    period="FY2027",
                    low=Decimal("105"),
                    average=Decimal("110"),
                    high=Decimal("120"),
                    unit="currency",
                    currency="USD",
                    retrieved_at=datetime(2026, 8, 22, tzinfo=UTC),
                    analyst_count=10,
                ),
                EstimateSnapshot(
                    analysis_id=analysis.id,
                    metric="revenue",
                    period="2027-03-31",
                    average=Decimal("30"),
                    unit="currency",
                    currency="USD",
                    retrieved_at=datetime(2026, 8, 22, tzinfo=UTC),
                    analyst_count=10,
                ),
            ]
        )
        session.commit()

        evidence = collect_forward_evidence(
            session,
            analysis,
            latest_actuals={"revenue": {"value": Decimal("100"), "unit": "currency", "currency": "USD"}},
        )

    values = {item.metric: item.value for item in evidence if item.status == "AVAILABLE"}
    quarterly = [item for item in evidence if item.period == "2027-03-31"]
    assert values["forward_revenue_growth_low"] == Decimal("0.05")
    assert values["forward_revenue_growth_average"] == Decimal("0.1")
    assert values["forward_revenue_growth_high"] == Decimal("0.2")
    assert quarterly
    assert all(item.status in {"NOT_USED_FOR_ANNUAL_DCF_GROWTH", "FORWARD_PERIOD_TYPE_UNCERTAIN"} for item in quarterly)


def test_forward_evidence_is_used_in_productive_service_and_conflict_is_reviewed():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(session, name="Test Co", ticker="TEST", currency="USD")
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        session.add(
            EstimateSnapshot(
                analysis_id=analysis.id,
                metric="revenue",
                period="FY2027",
                average=Decimal("102"),
                unit="currency",
                currency="USD",
                retrieved_at=datetime(2026, 8, 22, tzinfo=UTC),
                analyst_count=10,
            )
        )
        session.commit()
        assumption_set = build_assumption_set_for_analysis(
            session,
            analysis,
            ticker="TEST",
            normalized_fcf=normalized_fcf(),
            historical_context=historical_context(cagr={"revenue": {"5Y_CAGR": "0.15"}}),
            quality_context=quality_context(),
            latest_actuals={"revenue": {"value": Decimal("100"), "unit": "currency", "currency": "USD"}},
        )

    assert assumption_set.growth_recommendation.primary_anchor == "forward analyst revenue growth average"
    assert assumption_set.growth_recommendation.recommended_value == Decimal("0.02")
    assert "FORWARD_HISTORICAL_CONFLICT_REVIEW" in assumption_set.growth_recommendation.warnings


def test_manual_approved_discount_terminal_and_growth_flow_through_normal_service():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(session, name="Test Co", ticker="TEST", currency="USD")
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        session.add_all(
            [
                ValuationAssumption(analysis_id=analysis.id, method="equity_dcf", scenario="base", key="discount_rate", value=Decimal("0.11"), unit="decimal_ratio", source_type="MANUAL_APPROVED"),
                ValuationAssumption(analysis_id=analysis.id, method="equity_dcf", scenario="base", key="terminal_growth_rate", value=Decimal("0.025"), unit="decimal_ratio", source_type="MANUAL_APPROVED"),
                ValuationAssumption(analysis_id=analysis.id, method="equity_dcf", scenario="base", key="growth_rate", value=Decimal("0.04"), unit="decimal_ratio", source_type="MANUAL_APPROVED"),
            ]
        )
        session.commit()
        assumption_set = build_assumption_set_for_analysis(
            session,
            analysis,
            ticker="TEST",
            normalized_fcf=normalized_fcf(),
            historical_context=historical_context(),
            quality_context=quality_context(),
            latest_actuals={},
        )

    scenarios = {item.scenario: item for item in assumption_set.scenarios}
    assert assumption_set.discount_rate_recommendation.approved_value == Decimal("0.11000000")
    assert assumption_set.terminal_growth_recommendation.approved_value == Decimal("0.02500000")
    assert assumption_set.growth_recommendation.approved_value == Decimal("0.04000000")
    assert "DISCOUNT_RATE_NOT_COMPANY_SPECIFIC" not in assumption_set.warnings
    assert "TERMINAL_GROWTH_GENERIC" not in assumption_set.warnings
    assert scenarios["bear"].discount_rate == Decimal("0.12000000")
    assert scenarios["base"].discount_rate == Decimal("0.11000000")
    assert scenarios["bull"].discount_rate == Decimal("0.10000000")
    assert scenarios["base"].sources["growth_source"] == "MANUAL_APPROVED"


def test_approval_is_bound_to_recommendation_hash_and_stale_when_inputs_change():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(session, name="Test Co", ticker="TEST", currency="USD")
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        assumption_set = build_assumption_set(
            ticker="TEST",
            analysis_as_of_date="2026-08-23",
            normalized_fcf=normalized_fcf(),
            historical_context=historical_context(),
            quality_context=quality_context(),
        )
        approval = approve_recommended_value(
            session,
            analysis,
            assumption_set.growth_recommendation,
            recommendation_inputs_hash=assumption_set.inputs_hash,
        )
        current = load_current_approvals(session, analysis)
        valid, warnings = validate_approvals(current, recommendation_inputs_hash=assumption_set.inputs_hash)
        stale_valid, stale_warnings = validate_approvals(current, recommendation_inputs_hash="changed")

    assert approval.approved_value == assumption_set.growth_recommendation.recommended_value
    assert valid
    assert not warnings
    assert stale_valid == {}
    assert any(APPROVAL_STALE in warning for warning in stale_warnings)


def test_override_requires_note_and_preserves_recommended_value():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(session, name="Test Co", ticker="TEST", currency="USD")
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        assumption_set = build_assumption_set(
            ticker="TEST",
            analysis_as_of_date="2026-08-23",
            normalized_fcf=normalized_fcf(),
            historical_context=historical_context(),
            quality_context=quality_context(),
        )
        try:
            override_assumption(
                session,
                analysis,
                assumption_set.growth_recommendation,
                approved_value=Decimal("0.03"),
                recommendation_inputs_hash=assumption_set.inputs_hash,
                note="",
            )
            raised = False
        except ValueError:
            raised = True
        override = override_assumption(
            session,
            analysis,
            assumption_set.growth_recommendation,
            approved_value=Decimal("0.03"),
            recommendation_inputs_hash=assumption_set.inputs_hash,
            note="Manual risk adjustment",
        )

    assert raised is True
    assert override.recommended_value == assumption_set.growth_recommendation.recommended_value
    assert override.approved_value == Decimal("0.03000000")
    assert override.note == "Manual risk adjustment"
