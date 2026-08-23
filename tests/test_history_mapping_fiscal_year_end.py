from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.history_mapping_audit import audit_history_mapping
from stock_valuation.database.models import Base, FinancialFactSnapshot


def _add_fact(session: Session, analysis_id: int, period_end: date, provider: str = "sec_companyfacts") -> None:
    session.add(
        FinancialFactSnapshot(
            analysis_id=analysis_id,
            statement="balance_sheet",
            metric="shareholders_equity",
            period_end=period_end,
            period_type="FY",
            value=Decimal("100"),
            provider_value=Decimal("100"),
            currency="EUR",
            unit="currency",
            provider=provider,
            provider_field="us-gaap:StockholdersEquity",
            source_type="primary_source",
            is_cross_check_only=False,
        )
    )


def test_opening_balance_in_same_calendar_year_is_not_a_second_fiscal_year() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(
            session,
            name="Calendar Year Corp",
            ticker="CYC",
            currency="EUR",
        )
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        for year in range(2016, 2026):
            _add_fact(session, analysis.id, date(year, 12, 31))
        _add_fact(session, analysis.id, date(2018, 1, 1))
        session.commit()

        row = next(
            row
            for row in audit_history_mapping(session, analysis).rows
            if row.metric == "shareholders_equity"
        )

        assert row.status == "PASS"
        assert row.coverage_label == "10/10"
        assert row.duplicate_years == ()


def test_sec_companyfacts_and_original_filing_are_one_source_family() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(
            session,
            name="Calendar Year Corp",
            ticker="CYC",
            currency="EUR",
        )
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        for year in range(2016, 2026):
            provider = "sec_filing_xbrl" if year == 2016 else "sec_companyfacts"
            _add_fact(session, analysis.id, date(year, 12, 31), provider=provider)
        session.commit()

        row = next(
            row
            for row in audit_history_mapping(session, analysis).rows
            if row.metric == "shareholders_equity"
        )

        assert row.status == "PASS"
        assert row.providers == ("sec_companyfacts", "sec_filing_xbrl")
        assert "Quellenfamilie wechselte" not in row.reason
