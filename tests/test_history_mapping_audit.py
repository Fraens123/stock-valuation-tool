from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.history_mapping_audit import audit_history_mapping
from stock_valuation.database.models import Base, FinancialFactSnapshot


def _analysis(session: Session):
    company = get_or_create_company(
        session,
        name="Generic Industrial Corp",
        ticker="GEN",
        currency="EUR",
    )
    return create_analysis(session, company=company, as_of_date=date(2026, 8, 23))


def _fact(
    session: Session,
    analysis_id: int,
    year: int,
    *,
    metric: str = "revenue",
    provider_field: str = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
    provider: str = "sec_companyfacts",
    currency: str = "EUR",
    period_end: date | None = None,
) -> None:
    session.add(
        FinancialFactSnapshot(
            analysis_id=analysis_id,
            statement="income_statement",
            metric=metric,
            period_end=period_end or date(year, 12, 31),
            period_type="FY",
            value=Decimal(str(year * 100)),
            provider_value=Decimal(str(year * 100)),
            currency=currency,
            unit="currency",
            provider=provider,
            provider_field=provider_field,
            source_type="primary_source",
            is_cross_check_only=False,
        )
    )


def test_ten_year_series_with_unchanged_mapping_is_pass() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        for year in range(2016, 2026):
            _fact(session, analysis.id, year)
        session.commit()

        audit = audit_history_mapping(session, analysis)
        row = next(row for row in audit.rows if row.metric == "revenue")

        assert audit.first_year == 2016
        assert audit.last_year == 2025
        assert row.status == "PASS"
        assert row.coverage_label == "10/10"
        assert row.missing_years == ()
        assert row.change_years == ()
        assert len(row.provider_fields) == 1


def test_provider_field_change_is_review_not_automatic_error() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        for year in range(2016, 2019):
            _fact(session, analysis.id, year, provider_field="us-gaap:SalesRevenueNet")
        for year in range(2019, 2026):
            _fact(
                session,
                analysis.id,
                year,
                provider_field="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            )
        session.commit()

        row = next(row for row in audit_history_mapping(session, analysis).rows if row.metric == "revenue")

        assert row.status == "REVIEW"
        assert row.coverage_label == "10/10"
        assert row.change_years == (2019,)
        assert len(row.provider_fields) == 2
        assert "Originalfeld wechselte" in row.reason
        assert "2016–2018" in row.mapping_sequence
        assert "2019–2025" in row.mapping_sequence


def test_missing_history_year_is_gap() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        for year in range(2016, 2026):
            if year != 2020:
                _fact(session, analysis.id, year)
        session.commit()

        row = next(row for row in audit_history_mapping(session, analysis).rows if row.metric == "revenue")

        assert row.status == "GAP"
        assert row.coverage_label == "9/10"
        assert row.missing_years == (2020,)


def test_currency_or_taxonomy_change_requires_review() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        for year in range(2016, 2021):
            _fact(session, analysis.id, year)
        for year in range(2021, 2026):
            _fact(
                session,
                analysis.id,
                year,
                provider="esef_xbrl_json",
                provider_field="ifrs-full:Revenue",
                currency="USD",
            )
        session.commit()

        row = next(row for row in audit_history_mapping(session, analysis).rows if row.metric == "revenue")

        assert row.status == "REVIEW"
        assert row.coverage_label == "10/10"
        assert row.providers == ("esef_xbrl_json", "sec_companyfacts")
        assert row.currencies == ("EUR", "USD")
        assert row.taxonomies == ("ifrs-full", "us-gaap")
        assert "Quellenfamilie wechselte" in row.reason
        assert "Währung wechselte" in row.reason
        assert "Taxonomie wechselte" in row.reason


def test_manual_override_does_not_hide_underlying_mapping_continuity() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        for year in range(2016, 2026):
            _fact(session, analysis.id, year)
        session.add(
            FinancialFactSnapshot(
                analysis_id=analysis.id,
                statement="income_statement",
                metric="revenue",
                period_end=date(2025, 12, 31),
                period_type="FY",
                value=Decimal("999"),
                provider_value=Decimal("999"),
                currency="EUR",
                unit="currency",
                provider="manual_override",
                provider_field="manual_override",
                source_type="manual_override",
                is_cross_check_only=False,
            )
        )
        session.commit()

        row = next(row for row in audit_history_mapping(session, analysis).rows if row.metric == "revenue")

        assert row.status == "PASS"
        assert row.providers == ("sec_companyfacts",)
        assert row.provider_fields == ("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",)


def test_only_latest_requested_years_are_evaluated() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        _fact(session, analysis.id, 2015, provider_field="us-gaap:OldRevenueTag")
        for year in range(2016, 2026):
            _fact(session, analysis.id, year)
        session.commit()

        row = next(row for row in audit_history_mapping(session, analysis, years=10).rows if row.metric == "revenue")

        assert row.status == "PASS"
        assert "OldRevenueTag" not in row.mapping_sequence
