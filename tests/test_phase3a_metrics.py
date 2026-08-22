from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import AnalysisFrozenError, complete_analysis, create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.snapshot_service import replace_financial_facts
from stock_valuation.data.types import NormalizedFinancialFact
from stock_valuation.database.models import Base, MetricSnapshot
from stock_valuation.metrics.engine import calculate_ebit_margin, calculate_ebitda_margin, safe_ratio
from stock_valuation.metrics.service import (
    MetricDataQualityError,
    calculate_and_store_phase_3a,
    calculate_asml_ebit_margin_series,
    calculate_asml_ebitda_margin_series,
)


def _analysis(session: Session):
    company = get_or_create_company(
        session,
        name="ASML Holding N.V.",
        ticker="ASML",
        isin="NL0010273215",
        currency="EUR",
        provider_symbol="ASML.AS",
    )
    return create_analysis(session, company=company, as_of_date=date(2026, 8, 22))


def _fact(metric: str, period_end: date, value: str, field: str) -> NormalizedFinancialFact:
    return NormalizedFinancialFact(
        statement="income_statement",
        metric=metric,
        period_end=period_end,
        period_type="FY",
        value=Decimal(value),
        provider_value=Decimal(value),
        currency="EUR",
        unit="currency",
        provider="alphavantage",
        provider_field=field,
        retrieved_at=datetime.now(timezone.utc),
    )


def _validated_income_facts() -> list[NormalizedFinancialFact]:
    return [
        _fact("revenue", date(2025, 12, 31), "32667300000", "totalRevenue"),
        _fact("operating_income", date(2025, 12, 31), "11301400000", "operatingIncome"),
        _fact("depreciation_amortization", date(2025, 12, 31), "1025900000", "depreciationAndAmortization"),
        _fact("revenue", date(2024, 12, 31), "28262900000", "totalRevenue"),
        _fact("operating_income", date(2024, 12, 31), "9022600000", "operatingIncome"),
        _fact("depreciation_amortization", date(2024, 12, 31), "918600000", "depreciationAndAmortization"),
        _fact("revenue", date(2023, 12, 31), "27000000000", "totalRevenue"),
        _fact("operating_income", date(2023, 12, 31), "8500000000", "operatingIncome"),
        _fact("depreciation_amortization", date(2023, 12, 31), "850000000", "depreciationAndAmortization"),
    ]


def test_safe_ratio_and_margin_functions_do_not_invent_values() -> None:
    assert safe_ratio(Decimal("25"), Decimal("100")) == Decimal("0.25")
    assert safe_ratio(None, Decimal("100")) is None
    assert safe_ratio(Decimal("25"), Decimal("0")) is None
    assert calculate_ebit_margin(Decimal("25"), Decimal("100")) == Decimal("0.25")
    assert calculate_ebitda_margin(Decimal("25"), Decimal("5"), Decimal("100")) == Decimal("0.30")
    assert calculate_ebitda_margin(Decimal("25"), None, Decimal("100")) is None


def test_asml_margin_series_use_only_stored_snapshot_after_data_gate_passes() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        replace_financial_facts(
            session,
            analysis,
            _validated_income_facts(),
            provider="alphavantage",
        )

        ebit_points = calculate_asml_ebit_margin_series(session, analysis)
        ebitda_points = calculate_asml_ebitda_margin_series(session, analysis)

        assert [point.period_end.year for point in ebit_points] == [2023, 2024, 2025]
        assert [point.period_end.year for point in ebitda_points] == [2023, 2024, 2025]
        assert ebit_points[-1].value == Decimal("11301400000") / Decimal("32667300000")
        assert ebitda_points[-1].value == (
            Decimal("11301400000") + Decimal("1025900000")
        ) / Decimal("32667300000")
        assert ebitda_points[-1].inputs_hash is not None


def test_phase3a_persists_versioned_metric_snapshots() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        replace_financial_facts(
            session,
            analysis,
            _validated_income_facts(),
            provider="alphavantage",
        )
        result = calculate_and_store_phase_3a(session, analysis)

        rows = session.scalars(
            select(MetricSnapshot)
            .where(MetricSnapshot.analysis_id == analysis.id)
            .order_by(MetricSnapshot.metric_id, MetricSnapshot.period)
        ).all()
        assert result == {"ebit_margin": 3, "ebitda_margin": 3}
        assert len(rows) == 6
        assert all(row.calculation_version == "3a-0.2" for row in rows)
        assert all(row.inputs_hash for row in rows)


def test_phase3a_blocks_metric_if_required_field_fails_primary_source_gate() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        facts = _validated_income_facts()
        facts[1] = _fact(
            "operating_income",
            date(2025, 12, 31),
            "9000000000",
            "operatingIncome",
        )
        replace_financial_facts(session, analysis, facts, provider="alphavantage")

        with pytest.raises(MetricDataQualityError):
            calculate_asml_ebit_margin_series(session, analysis)


def test_completed_analysis_rejects_metric_snapshot_refresh() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        replace_financial_facts(
            session,
            analysis,
            _validated_income_facts(),
            provider="alphavantage",
        )
        complete_analysis(session, analysis)
        with pytest.raises(AnalysisFrozenError):
            calculate_and_store_phase_3a(session, analysis)
