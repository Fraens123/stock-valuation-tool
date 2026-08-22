from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import AnalysisFrozenError, complete_analysis, create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.snapshot_service import replace_estimates, replace_financial_facts
from stock_valuation.data.types import NormalizedEstimate, NormalizedFinancialFact
from stock_valuation.database.models import Base, EstimateSnapshot, FinancialFactSnapshot


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


def test_replace_financial_facts_is_repeatable_inside_draft() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)

    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        first = NormalizedFinancialFact(
            statement="income_statement",
            metric="revenue",
            period_end=date(2025, 12, 31),
            period_type="FY",
            value=Decimal("32700"),
            provider_value=Decimal("32700"),
            currency="EUR",
            unit="currency",
            provider="eodhd",
            provider_field="totalRevenue",
            retrieved_at=now,
        )
        replace_financial_facts(session, analysis, [first], provider="eodhd")

        corrected = NormalizedFinancialFact(
            statement="income_statement",
            metric="revenue",
            period_end=date(2025, 12, 31),
            period_type="FY",
            value=Decimal("32750"),
            provider_value=Decimal("32750"),
            currency="EUR",
            unit="currency",
            provider="eodhd",
            provider_field="totalRevenue",
            retrieved_at=now,
        )
        replace_financial_facts(session, analysis, [corrected], provider="eodhd")

        rows = session.scalars(
            select(FinancialFactSnapshot).where(FinancialFactSnapshot.analysis_id == analysis.id)
        ).all()
        assert len(rows) == 1
        assert rows[0].value == Decimal("32750")
        assert rows[0].provider_field == "totalRevenue"


def test_completed_analysis_rejects_provider_refresh() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        complete_analysis(session, analysis)
        with pytest.raises(AnalysisFrozenError):
            replace_financial_facts(session, analysis, [], provider="eodhd")


def test_estimates_keep_source_metadata() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)

    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        estimate = NormalizedEstimate(
            metric="revenue",
            period="2027-12-31",
            low=Decimal("39000"),
            average=Decimal("42000"),
            high=Decimal("45000"),
            analyst_count=28,
            provider="eodhd",
            currency="EUR",
            unit="currency",
            retrieved_at=now,
        )
        replace_estimates(session, analysis, [estimate], provider="eodhd")

        row = session.scalar(
            select(EstimateSnapshot).where(EstimateSnapshot.analysis_id == analysis.id)
        )
        assert row is not None
        assert row.average == Decimal("42000")
        assert row.analyst_count == 28
        assert row.provider == "eodhd"
