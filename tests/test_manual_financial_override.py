from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.input_service import upsert_manual_financial_override
from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.resolution import preferred_fact_index
from stock_valuation.database.models import Base, FinancialFactSnapshot


def test_manual_override_wins_without_deleting_provider_fact() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(
            session,
            name="Example Corp",
            ticker="EXM",
            currency="USD",
        )
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 22))
        session.add(
            FinancialFactSnapshot(
                analysis_id=analysis.id,
                statement="income_statement",
                metric="revenue",
                period_end=date(2025, 12, 31),
                period_type="FY",
                value=Decimal("100"),
                provider_value=Decimal("100"),
                currency="USD",
                unit="currency",
                provider="alphavantage",
                provider_field="totalRevenue",
                source_type="provider",
            )
        )
        session.commit()

        upsert_manual_financial_override(
            session,
            analysis,
            metric="revenue",
            period_end=date(2025, 12, 31),
            value=Decimal("105"),
            currency="USD",
            unit="currency",
            statement="income_statement",
            source_name="Annual Report",
            source_url="https://example.com/report",
            note="Official revenue line",
        )

        preferred = preferred_fact_index(session, analysis.id)
        selected = preferred[("revenue", date(2025, 12, 31))]
        assert selected.provider == "manual_override"
        assert selected.value == Decimal("105")

        all_rows = session.query(FinancialFactSnapshot).filter_by(
            analysis_id=analysis.id,
            metric="revenue",
        ).all()
        assert {row.provider for row in all_rows} == {"alphavantage", "manual_override"}
