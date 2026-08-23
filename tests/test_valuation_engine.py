from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.database.models import Base, MarketDataSnapshotRecord, ValuationSnapshotRecord
from stock_valuation.valuation.dcf import equity_dcf
from stock_valuation.valuation.models import (
    ASSUMPTIONS_NOT_COMPANY_SPECIFIC,
    AVAILABLE,
    GENERIC_ASSUMPTION_SOURCE,
    INVALID_ASSUMPTION,
    NOT_MEANINGFUL,
    DCFScenario,
    FinancialPoint,
    MarketSnapshotInput,
)
from stock_valuation.valuation.multiples import current_market_multiples
from stock_valuation.valuation.normalization import normalize_three_year_metric
from stock_valuation.valuation.persistence import (
    MARKET_SNAPSHOT_NOT_PERSISTED,
    SNAPSHOT_ID_COLLISION,
    list_valuation_snapshots_for_analysis,
    load_valuation_snapshot,
    payload_from_record,
    persist_valuation_snapshot,
)
from stock_valuation.valuation.snapshot import (
    assumptions_payload,
    canonical_hash,
    create_valuation_snapshot,
)
from stock_valuation.valuation.summary import dcf_summary, listed_equivalent_units


def point(metric: str, year: int, value: str | None, currency: str = "USD") -> FinancialPoint:
    return FinancialPoint(
        metric,
        year,
        Decimal(value) if value is not None else None,
        currency,
        AVAILABLE if value is not None else "UNAVAILABLE",
        f"calculation:{metric}:{year}",
        f"hash:{metric}:{year}:{value}",
    )


def market(**overrides) -> MarketSnapshotInput:
    values = {
        "ticker": "TEST",
        "company": "Test Co",
        "analysis_as_of_date": "2026-08-23",
        "market_snapshot_id": "market-snapshot-1",
        "market_data_version": "market-data-v1.0",
        "security_type": "ordinary_share",
        "price": Decimal("100"),
        "market_cap": Decimal("1000"),
        "enterprise_value": Decimal("1200"),
        "shares_outstanding": Decimal("10"),
        "share_basis": "ORDINARY_SHARES",
        "financial_currency": "USD",
        "trading_currency": "USD",
        "fx_rate": None,
        "adr_ratio": None,
        "underlying_share_ratio": None,
        "input_refs": ("market:TEST",),
        "inputs_hash": "market-hash",
    }
    values.update(overrides)
    return MarketSnapshotInput(**values)


def by_id(results):
    return {result.metric_id: result for result in results}


def test_current_market_multiples_formulas_and_yields():
    results = by_id(
        current_market_multiples(
            {
                "net_income": point("net_income", 2025, "100"),
                "operating_income": point("operating_income", 2025, "80"),
                "ebitda": point("ebitda", 2025, "120"),
                "free_cash_flow": point("free_cash_flow", 2025, "50"),
            },
            market(),
        )
    )

    assert results["latest_fy_pe"].value == Decimal("10")
    assert results["latest_fy_ev_ebit"].value == Decimal("15")
    assert results["latest_fy_ev_ebitda"].value == Decimal("10")
    assert results["latest_fy_p_fcf"].value == Decimal("20")
    assert results["earnings_yield"].value == Decimal("0.1")
    assert results["fcf_yield"].value == Decimal("0.05")


def test_negative_and_zero_denominators_are_not_meaningful():
    results = by_id(
        current_market_multiples(
            {
                "net_income": point("net_income", 2025, "-1"),
                "operating_income": point("operating_income", 2025, "0"),
                "ebitda": point("ebitda", 2025, "10"),
                "free_cash_flow": point("free_cash_flow", 2025, "-5"),
            },
            market(),
        )
    )

    assert results["latest_fy_pe"].status == NOT_MEANINGFUL
    assert results["latest_fy_ev_ebit"].status == NOT_MEANINGFUL
    assert results["latest_fy_p_fcf"].status == NOT_MEANINGFUL


def test_normalization_average_median_missing_and_outlier():
    points = (point("free_cash_flow", 2023, "100"), point("free_cash_flow", 2024, "110"), point("free_cash_flow", 2025, "500"))

    median_result = normalize_three_year_metric("free_cash_flow", points)
    average_result = normalize_three_year_metric("free_cash_flow", points, method="three_year_average")
    missing_result = normalize_three_year_metric("free_cash_flow", (point("free_cash_flow", 2025, None),))

    assert median_result.value == Decimal("110")
    assert "OUTLIER_REVIEW" in median_result.issues
    assert average_result.value == Decimal("236.6666666666666666666666667")
    assert missing_result.status == "UNAVAILABLE"


def test_two_year_three_year_median_is_marked_partial():
    result = normalize_three_year_metric(
        "free_cash_flow",
        (point("free_cash_flow", 2024, "100"), point("free_cash_flow", 2025, "120")),
    )

    assert result.status == AVAILABLE
    assert result.value == Decimal("110")
    assert result.used_fiscal_years == (2024, 2025)
    assert "PARTIAL_NORMALIZATION_WINDOW" in result.issues


def test_dcf_projection_and_terminal_growth_validation():
    normalized = normalize_three_year_metric(
        "free_cash_flow",
        (point("free_cash_flow", 2023, "90"), point("free_cash_flow", 2024, "100"), point("free_cash_flow", 2025, "110")),
    )

    result = equity_dcf("TEST", normalized, DCFScenario("base", 2, Decimal("0.05"), Decimal("0.10"), Decimal("0.02")))
    invalid = equity_dcf("TEST", normalized, DCFScenario("bad", 5, Decimal("0.05"), Decimal("0.02"), Decimal("0.02")))

    assert result.status == AVAILABLE
    assert len(result.projected_rows) == 2
    assert result.projected_rows[0].projected_fcf == Decimal("105.00")
    assert result.terminal_value is not None
    assert ASSUMPTIONS_NOT_COMPANY_SPECIFIC in result.issues
    assert invalid.status == INVALID_ASSUMPTION
    assert "TERMINAL_GROWTH_NOT_BELOW_DISCOUNT_RATE" in invalid.issues


def test_equity_dcf_does_not_subtract_net_debt_and_summary_uses_market_units():
    normalized = normalize_three_year_metric(
        "free_cash_flow",
        (point("free_cash_flow", 2023, "100"), point("free_cash_flow", 2024, "100"), point("free_cash_flow", 2025, "100")),
    )
    dcf = equity_dcf("TEST", normalized, DCFScenario("base", 1, Decimal("0"), Decimal("0.10"), Decimal("0")))
    summary = dcf_summary(dcf, market(shares_outstanding=Decimal("10"), price=Decimal("50")))

    assert dcf.equity_value == Decimal("1000")
    assert summary.fair_value_per_unit == Decimal("100")
    assert summary.upside_downside == Decimal("1")


def test_fx_conversion_and_adr_equivalent_units():
    ordinary_backed_adr = market(
        security_type="ADR",
        financial_currency="EUR",
        trading_currency="USD",
        fx_rate=Decimal("2"),
        shares_outstanding=Decimal("1000"),
        adr_ratio=Decimal("1"),
        underlying_share_ratio=Decimal("5"),
    )
    normalized = normalize_three_year_metric(
        "free_cash_flow",
        (
            point("free_cash_flow", 2023, "100", "EUR"),
            point("free_cash_flow", 2024, "100", "EUR"),
            point("free_cash_flow", 2025, "100", "EUR"),
        ),
    )
    dcf = equity_dcf("TEST", normalized, DCFScenario("base", 1, Decimal("0"), Decimal("0.10"), Decimal("0")))
    summary = dcf_summary(dcf, ordinary_backed_adr)

    assert listed_equivalent_units(ordinary_backed_adr) == (Decimal("200"), None)
    assert summary.fair_value_per_unit == Decimal("10")


def test_inputs_hash_reproducibility():
    points = (point("free_cash_flow", 2023, "100"), point("free_cash_flow", 2024, "110"), point("free_cash_flow", 2025, "120"))

    first = normalize_three_year_metric("free_cash_flow", points)
    second = normalize_three_year_metric("free_cash_flow", tuple(reversed(points)))

    assert first.inputs_hash == second.inputs_hash


def test_outlier_and_generic_assumption_warnings_persist_to_final_result():
    normalized = normalize_three_year_metric(
        "free_cash_flow",
        (point("free_cash_flow", 2023, "100"), point("free_cash_flow", 2024, "110"), point("free_cash_flow", 2025, "500")),
    )

    dcf = equity_dcf("TEST", normalized, DCFScenario("base", 2, Decimal("0.05"), Decimal("0.10"), Decimal("0.02")))
    summary = dcf_summary(dcf, market())

    assert dcf.status == AVAILABLE
    assert "OUTLIER_REVIEW" in dcf.issues
    assert ASSUMPTIONS_NOT_COMPANY_SPECIFIC in dcf.issues
    assert "OUTLIER_REVIEW" in summary.issues
    assert ASSUMPTIONS_NOT_COMPANY_SPECIFIC in summary.issues


def test_custom_assumptions_do_not_emit_generic_warning():
    normalized = normalize_three_year_metric(
        "free_cash_flow",
        (point("free_cash_flow", 2023, "100"), point("free_cash_flow", 2024, "100"), point("free_cash_flow", 2025, "100")),
    )

    dcf = equity_dcf(
        "TEST",
        normalized,
        DCFScenario("custom", 2, Decimal("0.05"), Decimal("0.10"), Decimal("0.02"), "CUSTOM_EXPLICIT"),
    )

    assert dcf.status == AVAILABLE
    assert ASSUMPTIONS_NOT_COMPANY_SPECIFIC not in dcf.issues


def test_snapshot_id_and_hash_are_deterministic_and_change_with_inputs():
    scenario = DCFScenario("base", 1, Decimal("0"), Decimal("0.10"), Decimal("0"))
    assumptions = assumptions_payload(
        (scenario,),
        normalization_method="three_year_median",
        outlier_threshold="0.50",
        sensitivity_discount_rates=("0.09",),
        sensitivity_terminal_growth_rates=("0.02",),
    )
    normalized = normalize_three_year_metric(
        "free_cash_flow",
        (point("free_cash_flow", 2023, "100"), point("free_cash_flow", 2024, "100"), point("free_cash_flow", 2025, "100")),
    )
    dcf = equity_dcf("TEST", normalized, scenario)
    summary = dcf_summary(dcf, market())
    quality_context = {"overall_quality_score": "8.2", "overall_quality_assessment": "STRONG"}
    historical_context = {"revenue_growth": "0.10"}

    first = create_valuation_snapshot(
        analysis_id="analysis-1",
        market=market(),
        financial_data_reference="final_data_gate_report.csv",
        calculation_version="calc-v1.0",
        historical_analysis_version="historical-v1.0",
        quality_version="quality-v1.0",
        assumptions=assumptions,
        normalized_inputs=(normalized,),
        valuation_results=(summary,),
        quality_context=quality_context,
        historical_context=historical_context,
        created_at="2026-08-23T00:00:00+00:00",
    )
    second = create_valuation_snapshot(
        analysis_id="analysis-1",
        market=market(),
        financial_data_reference="final_data_gate_report.csv",
        calculation_version="calc-v1.0",
        historical_analysis_version="historical-v1.0",
        quality_version="quality-v1.0",
        assumptions=assumptions,
        normalized_inputs=(normalized,),
        valuation_results=(summary,),
        quality_context=quality_context,
        historical_context=historical_context,
        created_at="2026-08-23T00:00:00+00:00",
    )
    changed_market = create_valuation_snapshot(
        analysis_id="analysis-1",
        market=market(market_snapshot_id="market-snapshot-2"),
        financial_data_reference="final_data_gate_report.csv",
        calculation_version="calc-v1.0",
        historical_analysis_version="historical-v1.0",
        quality_version="quality-v1.0",
        assumptions=assumptions,
        normalized_inputs=(normalized,),
        valuation_results=(summary,),
        quality_context=quality_context,
        historical_context=historical_context,
        created_at="2026-08-23T00:00:00+00:00",
    )
    changed_assumptions = assumptions_payload(
        (DCFScenario("base", 1, Decimal("0.01"), Decimal("0.10"), Decimal("0")),),
        normalization_method="three_year_median",
        outlier_threshold="0.50",
        sensitivity_discount_rates=("0.09",),
        sensitivity_terminal_growth_rates=("0.02",),
    )
    changed_growth = create_valuation_snapshot(
        analysis_id="analysis-1",
        market=market(),
        financial_data_reference="final_data_gate_report.csv",
        calculation_version="calc-v1.0",
        historical_analysis_version="historical-v1.0",
        quality_version="quality-v1.0",
        assumptions=changed_assumptions,
        normalized_inputs=(normalized,),
        valuation_results=(summary,),
        quality_context=quality_context,
        historical_context=historical_context,
        created_at="2026-08-23T00:00:00+00:00",
    )

    assert first.snapshot_id == second.snapshot_id
    assert first.inputs_hash == second.inputs_hash
    assert first.snapshot_id != changed_market.snapshot_id
    assert first.snapshot_id != changed_growth.snapshot_id
    assert first.quality_context["overall_quality_score"] == "8.2"
    assert first.quality_context["overall_quality_assessment"] == "STRONG"


def test_canonical_hash_is_independent_of_dict_insertion_order():
    first = {"a": 1, "b": {"x": Decimal("1.20"), "y": [2, 3]}}
    second = {"b": {"y": [2, 3], "x": Decimal("1.20")}, "a": 1}

    assert canonical_hash(first) == canonical_hash(second)


def test_quality_and_historical_context_do_not_change_dcf_math():
    normalized = normalize_three_year_metric(
        "free_cash_flow",
        (point("free_cash_flow", 2023, "100"), point("free_cash_flow", 2024, "100"), point("free_cash_flow", 2025, "100")),
    )
    scenario = DCFScenario("base", 1, Decimal("0"), Decimal("0.10"), Decimal("0"), GENERIC_ASSUMPTION_SOURCE)

    weak_context_result = dcf_summary(equity_dcf("TEST", normalized, scenario), market())
    strong_context_result = dcf_summary(equity_dcf("TEST", normalized, scenario), market())

    assert weak_context_result.fair_value_per_unit == strong_context_result.fair_value_per_unit


def _assumptions(growth: str = "0", discount: str = "0.10"):
    return assumptions_payload(
        (DCFScenario("base", 1, Decimal(growth), Decimal(discount), Decimal("0")),),
        normalization_method="three_year_median",
        outlier_threshold="0.50",
        sensitivity_discount_rates=("0.09",),
        sensitivity_terminal_growth_rates=("0.02",),
    )


def _valuation_snapshot(analysis_id: int, market_snapshot_id: str = "market-snapshot-1", **overrides):
    assumptions = overrides.pop("assumptions", _assumptions())
    quality_context = overrides.pop(
        "quality_context",
        {
            "overall_quality_score": "8.2",
            "overall_quality_assessment": "STRONG",
            "quality_version": "quality-v1.0",
            "quality_inputs_hash": "quality-hash",
            "components": {"profitability": {"score": "8"}},
        },
    )
    historical_context = overrides.pop(
        "historical_context",
        {
            "historical_analysis_version": "historical-v1.0",
            "historical_window": ["2023", "2024", "2025"],
            "revenue_growth": [{"fiscal_year": "2025", "value": "0.10"}],
            "input_refs": ["historical:TEST:revenue:2025"],
            "context_hash": "historical-hash",
        },
    )
    normalized = overrides.pop(
        "normalized",
        normalize_three_year_metric(
            "free_cash_flow",
            (
                point("free_cash_flow", 2023, "100"),
                point("free_cash_flow", 2024, "110"),
                point("free_cash_flow", 2025, "500"),
            ),
        ),
    )
    scenario = DCFScenario("base", 1, Decimal("0"), Decimal("0.10"), Decimal("0"))
    dcf = equity_dcf("TEST", normalized, scenario)
    summary = dcf_summary(dcf, market(market_snapshot_id=market_snapshot_id))
    return create_valuation_snapshot(
        analysis_id=str(analysis_id),
        market=market(market_snapshot_id=market_snapshot_id),
        financial_data_reference="final_data_gate_report.csv",
        calculation_version="calc-v1.0",
        historical_analysis_version="historical-v1.0",
        quality_version="quality-v1.0",
        assumptions=assumptions,
        normalized_inputs=(normalized,),
        valuation_results=(summary,),
        quality_context=quality_context,
        historical_context=historical_context,
        created_at="2026-08-23T00:00:00+00:00",
    )


def _add_market_record(session: Session, analysis_id: int, snapshot_id: str = "market-snapshot-1"):
    session.add(
        MarketDataSnapshotRecord(
            analysis_id=analysis_id,
            snapshot_id=snapshot_id,
            analysis_as_of_date=date(2026, 8, 23),
            ticker="TEST",
            price=Decimal("100"),
            shares_outstanding=Decimal("10"),
            inputs_hash="market-hash",
            payload_json='{"snapshot":"market"}',
            retrieved_at=datetime(2026, 8, 23, tzinfo=UTC),
        )
    )
    session.commit()


def test_persistent_valuation_snapshot_survives_new_db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'valuation.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(session, name="Test Co", ticker="TEST", currency="USD")
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        _add_market_record(session, analysis.id)
        snapshot = _valuation_snapshot(analysis.id)
        record = persist_valuation_snapshot(session, analysis, snapshot)
        record_id = record.id

    with Session(engine, expire_on_commit=False) as session:
        record = session.get(ValuationSnapshotRecord, record_id)
        loaded = load_valuation_snapshot(session, snapshot.snapshot_id)
        payload = payload_from_record(loaded)

        assert record is not None
        assert loaded is not None
        assert loaded.payload_json == record.payload_json
        assert payload["snapshot_id"] == snapshot.snapshot_id
        assert payload["inputs_hash"] == snapshot.inputs_hash
        assert "OUTLIER_REVIEW" in payload["valuation_results"]["ValuationSummary:0"]["issues"]
        assert ASSUMPTIONS_NOT_COMPANY_SPECIFIC in payload["valuation_results"]["ValuationSummary:0"]["issues"]


def test_persist_valuation_snapshot_linkage_idempotency_and_immutability():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(session, name="Test Co", ticker="TEST", currency="USD")
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        other_analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 24))
        _add_market_record(session, analysis.id)
        _add_market_record(session, other_analysis.id, "other-market-snapshot")
        snapshot = _valuation_snapshot(analysis.id)

        first = persist_valuation_snapshot(session, analysis, snapshot)
        second = persist_valuation_snapshot(session, analysis, snapshot)
        rows = list_valuation_snapshots_for_analysis(session, analysis)

        assert first.id == second.id
        assert len(rows) == 1
        assert payload_from_record(first)["snapshot_id"] == snapshot.snapshot_id

        with pytest.raises(ValueError, match=SNAPSHOT_ID_COLLISION):
            persist_valuation_snapshot(
                session,
                analysis,
                replace(snapshot, inputs_hash="changed", payload_json="invalid") if False else replace(snapshot, inputs_hash="changed"),
            )
        with pytest.raises(ValueError, match=MARKET_SNAPSHOT_NOT_PERSISTED):
            persist_valuation_snapshot(session, analysis, _valuation_snapshot(analysis.id, "missing-market"))
        with pytest.raises(ValueError, match="MARKET_SNAPSHOT_ANALYSIS_MISMATCH"):
            persist_valuation_snapshot(session, analysis, _valuation_snapshot(analysis.id, "other-market-snapshot"))


def test_changed_inputs_create_new_snapshot_ids_but_do_not_change_existing_payload():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(session, name="Test Co", ticker="TEST", currency="USD")
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        _add_market_record(session, analysis.id)
        _add_market_record(session, analysis.id, "market-snapshot-2")
        original = _valuation_snapshot(analysis.id)
        original_record = persist_valuation_snapshot(session, analysis, original)
        original_payload = original_record.payload_json

        changed_growth = _valuation_snapshot(analysis.id, assumptions=_assumptions(growth="0.01"))
        changed_discount = _valuation_snapshot(analysis.id, assumptions=_assumptions(discount="0.11"))
        changed_market = _valuation_snapshot(analysis.id, "market-snapshot-2")
        changed_normalized = _valuation_snapshot(
            analysis.id,
            normalized=normalize_three_year_metric(
                "free_cash_flow",
                (
                    point("free_cash_flow", 2023, "101"),
                    point("free_cash_flow", 2024, "110"),
                    point("free_cash_flow", 2025, "500"),
                ),
            ),
        )
        changed_quality = _valuation_snapshot(
            analysis.id,
            quality_context={"overall_quality_score": "2.0", "overall_quality_assessment": "WEAK"},
        )
        changed_historical = _valuation_snapshot(
            analysis.id,
            historical_context={
                "historical_analysis_version": "historical-v1.0",
                "historical_window": ["2023", "2024", "2025"],
                "revenue_growth": [{"fiscal_year": "2025", "value": "0.99"}],
                "input_refs": ["historical:TEST:revenue:2025"],
                "context_hash": "changed-history",
            },
        )

        assert original.snapshot_id != changed_growth.snapshot_id
        assert original.snapshot_id != changed_discount.snapshot_id
        assert original.snapshot_id != changed_market.snapshot_id
        assert original.snapshot_id != changed_normalized.snapshot_id
        assert original.inputs_hash != changed_quality.inputs_hash
        assert original.inputs_hash != changed_historical.inputs_hash
        assert original.valuation_results["ValuationSummary:0"]["fair_value_per_unit"] == changed_quality.valuation_results["ValuationSummary:0"]["fair_value_per_unit"]
        assert original.valuation_results["ValuationSummary:0"]["fair_value_per_unit"] == changed_historical.valuation_results["ValuationSummary:0"]["fair_value_per_unit"]
        assert original_record.payload_json == original_payload
