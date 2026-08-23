from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.preferred_data import (
    FIELD_DEFINITIONS,
    load_preferred_data_states,
)
from stock_valuation.database.ai_review_models import AIReviewFinding, AIReviewRun
from stock_valuation.database.models import Base, FinancialFactSnapshot
from stock_valuation.metrics.engine import MetricPoint
from stock_valuation.metrics.service import (
    MetricDataQualityError,
    calculate_and_store_phase_3a,
    calculate_ebit_margin_series,
    calculate_ebitda_margin_series,
    load_metric_series,
    replace_metric_points,
)


def _analysis(session: Session):
    company = get_or_create_company(
        session,
        name="Microsoft Corporation",
        ticker="MSFT",
        currency="USD",
        exchange="United States",
    )
    return create_analysis(session, company=company, as_of_date=date(2026, 8, 22))


def _fact(
    session: Session,
    analysis_id: int,
    metric: str,
    value: str,
    *,
    provider: str = "alphavantage",
    provider_field: str | None = None,
    source_type: str = "provider",
    period_end: date = date(2025, 6, 30),
) -> FinancialFactSnapshot:
    row = FinancialFactSnapshot(
        analysis_id=analysis_id,
        statement="income_statement",
        metric=metric,
        period_end=period_end,
        period_type="FY",
        value=Decimal(value),
        provider_value=Decimal(value),
        currency="USD",
        unit="currency",
        provider=provider,
        provider_field=provider_field or metric,
        source_type=source_type,
        is_cross_check_only=False,
    )
    session.add(row)
    session.commit()
    return row


def _review(
    session: Session,
    analysis_id: int,
    fact: FinancialFactSnapshot,
    verdict: str,
    *,
    official_value: str | None = None,
) -> AIReviewFinding:
    run = AIReviewRun(
        analysis_id=analysis_id,
        model="chatgpt_file_review",
        years_requested=1,
        status="completed",
        response_id="package-test",
        summary="test",
        completed_at=datetime.now(UTC),
    )
    session.add(run)
    session.flush()
    finding = AIReviewFinding(
        run_id=run.id,
        analysis_id=analysis_id,
        period_end=fact.period_end,
        statement=fact.statement,
        metric=fact.metric,
        imported_value=fact.value,
        official_value=Decimal(official_value) if official_value is not None else fact.value,
        currency=fact.currency,
        verdict=verdict,
        provider=fact.provider,
        provider_field=fact.provider_field,
        source_title="Official filing",
        source_url="https://example.com/filing",
        reason="test review",
    )
    session.add(finding)
    session.commit()
    return finding


def test_unverified_provider_is_preferred_but_not_calculation_ready() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        _fact(session, analysis.id, "revenue", "100", provider_field="totalRevenue")

        state = load_preferred_data_states(session, analysis.id, metrics=["revenue"])[0]
        assert state.fact.provider == "alphavantage"
        assert state.quality_status == "provider_unverified"
        assert state.calculation_ready is False


def test_chatgpt_pass_promotes_matching_provider_fact_to_calculation_ready() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        fact = _fact(session, analysis.id, "revenue", "100", provider_field="totalRevenue")
        _review(session, analysis.id, fact, "PASS")

        state = load_preferred_data_states(session, analysis.id, metrics=["revenue"])[0]
        assert state.quality_status == "reviewed_pass"
        assert state.calculation_ready is True


def test_unclear_review_blocks_calculation_and_provider_ebitda_is_never_authoritative() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        d_and_a = _fact(
            session,
            analysis.id,
            "depreciation_amortization",
            "10",
            provider_field="depreciationAndAmortization",
        )
        ebitda = _fact(session, analysis.id, "ebitda", "40", provider_field="ebitda")
        _review(session, analysis.id, d_and_a, "UNKLAR", official_value=None)
        _review(session, analysis.id, ebitda, "PASS")

        states = {
            state.fact.metric: state
            for state in load_preferred_data_states(
                session,
                analysis.id,
                metrics=["depreciation_amortization", "ebitda"],
            )
        }
        assert states["depreciation_amortization"].quality_status == "unclear"
        assert states["depreciation_amortization"].calculation_ready is False
        assert states["ebitda"].quality_status == "derive_required"
        assert states["ebitda"].calculation_ready is False


def test_primary_source_and_manual_override_are_calculation_ready() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        _fact(
            session,
            analysis.id,
            "revenue",
            "100",
            provider="sec_companyfacts",
            source_type="primary_source",
        )
        _fact(session, analysis.id, "ppe_net", "120", provider_field="propertyPlantEquipment")
        _fact(
            session,
            analysis.id,
            "ppe_net",
            "105",
            provider="manual_override",
            source_type="manual",
        )

        states = {
            state.fact.metric: state
            for state in load_preferred_data_states(session, analysis.id, metrics=["revenue", "ppe_net"])
        }
        assert states["revenue"].quality_status == "primary_source"
        assert states["revenue"].calculation_ready is True
        assert states["ppe_net"].fact.value == Decimal("105")
        assert states["ppe_net"].quality_status == "confirmed_override"
        assert states["ppe_net"].calculation_ready is True


def test_sec_short_term_debt_requires_semantic_review_even_as_primary_source() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        debt = _fact(
            session,
            analysis.id,
            "short_term_debt",
            "2999",
            provider="sec_companyfacts",
            provider_field="us-gaap:LongTermDebtCurrent",
            source_type="primary_source",
        )

        state = load_preferred_data_states(session, analysis.id, metrics=["short_term_debt"])[0]
        assert state.quality_status == "primary_semantic_review_required"
        assert state.calculation_ready is False

        _review(session, analysis.id, debt, "PASS")
        state = load_preferred_data_states(session, analysis.id, metrics=["short_term_debt"])[0]
        assert state.quality_status == "primary_reviewed_pass"
        assert state.calculation_ready is True


def test_edgartools_primary_source_imports_but_ambiguous_metrics_keep_review_gate() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        _fact(
            session,
            analysis.id,
            "revenue",
            "100",
            provider="edgartools",
            provider_field="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            source_type="primary_source",
        )
        _fact(
            session,
            analysis.id,
            "short_term_debt",
            "10",
            provider="edgartools",
            provider_field="aggregation:us-gaap:LongTermDebtCurrent",
            source_type="primary_source",
        )

        states = {
            state.fact.metric: state
            for state in load_preferred_data_states(
                session,
                analysis.id,
                metrics=["revenue", "short_term_debt"],
            )
        }

        assert states["revenue"].quality_status == "primary_source"
        assert states["revenue"].calculation_ready is True
        assert states["short_term_debt"].quality_status == "primary_semantic_review_required"
        assert states["short_term_debt"].calculation_ready is False


def test_internal_definitions_cover_microsoft_mapping_problems() -> None:
    assert "Operating-Lease-Right-of-Use-Assets" in FIELD_DEFINITIONS["ppe_net"]
    assert "Fälligkeit innerhalb von zwölf Monaten" in FIELD_DEFINITIONS["short_term_debt"]
    assert "'and other'" in FIELD_DEFINITIONS["depreciation_amortization"]
    assert "selbst" in FIELD_DEFINITIONS["ebitda"]


def test_generic_ebit_margin_uses_verified_ebit_but_ebitda_blocks_on_unclear_d_and_a() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        revenue = _fact(session, analysis.id, "revenue", "200", provider_field="totalRevenue")
        ebit = _fact(session, analysis.id, "ebit", "50", provider_field="ebit")
        d_and_a = _fact(
            session,
            analysis.id,
            "depreciation_amortization",
            "10",
            provider_field="depreciationAndAmortization",
        )
        _review(session, analysis.id, revenue, "PASS")
        _review(session, analysis.id, ebit, "PASS")
        _review(session, analysis.id, d_and_a, "UNKLAR", official_value=None)

        ebit_points = calculate_ebit_margin_series(session, analysis)
        assert len(ebit_points) == 1
        assert ebit_points[0].value == Decimal("0.25")

        with pytest.raises(MetricDataQualityError):
            calculate_ebitda_margin_series(session, analysis)


def test_metric_sync_does_not_rewrite_identical_series() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        point = MetricPoint(
            metric_id="ebit_margin",
            period_end=date(2025, 6, 30),
            value=Decimal("0.25"),
            unit="decimal_ratio",
            inputs_hash="same-inputs",
        )

        replace_metric_points(session, analysis, [point], metric_id="ebit_margin")
        first_id = load_metric_series(session, analysis.id, "ebit_margin")[0].id

        replace_metric_points(session, analysis, [point], metric_id="ebit_margin")
        second_id = load_metric_series(session, analysis.id, "ebit_margin")[0].id

        assert second_id == first_id


def test_auto_sync_removes_stale_ebitda_when_input_becomes_blocked() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        _fact(
            session,
            analysis.id,
            "revenue",
            "200",
            provider="manual_override",
            source_type="manual",
        )
        _fact(
            session,
            analysis.id,
            "ebit",
            "50",
            provider="manual_override",
            source_type="manual",
        )
        d_and_a = _fact(
            session,
            analysis.id,
            "depreciation_amortization",
            "10",
            provider="manual_override",
            source_type="manual",
        )

        counts = calculate_and_store_phase_3a(session, analysis)
        assert counts["ebitda_margin"] == 1
        assert len(load_metric_series(session, analysis.id, "ebitda_margin")) == 1

        d_and_a.provider = "alphavantage"
        d_and_a.source_type = "provider"
        d_and_a.provider_field = "depreciationAndAmortization"
        session.commit()

        counts = calculate_and_store_phase_3a(session, analysis)
        assert counts["ebit_margin"] == 1
        assert counts["ebitda_margin"] == 0
        assert load_metric_series(session, analysis.id, "ebitda_margin") == []
