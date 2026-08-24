from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from stock_valuation.analyses.input_service import (
    remove_manual_financial_override,
    upsert_manual_financial_override,
)
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.preferred_data import load_preferred_data_states
from stock_valuation.database.models import Analysis, Base, FinancialFactSnapshot
from stock_valuation.ui.financial_worksheet import (
    WorksheetCellStatus,
    build_financial_worksheet,
    is_short_term_debt_candidate_field,
    open_cells,
    worksheet_candidates,
)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def _analysis(session: Session) -> Analysis:
    company = get_or_create_company(
        session,
        name="Example Inc.",
        ticker="EXM",
        currency="USD",
        exchange="NASDAQ",
    )
    analysis = Analysis(company_id=company.id, as_of_date=date(2025, 12, 31))
    session.add(analysis)
    session.commit()
    return analysis


def _fact(
    analysis: Analysis,
    metric: str,
    year: int,
    value: str,
    *,
    provider: str = "sec_companyfacts",
    provider_field: str | None = None,
) -> FinancialFactSnapshot:
    statement = "balance_sheet" if metric not in {"revenue", "net_income"} else "income_statement"
    return FinancialFactSnapshot(
        analysis_id=analysis.id,
        statement=statement,
        metric=metric,
        period_end=date(year, 12, 31),
        period_type="FY",
        value=Decimal(value),
        provider_value=Decimal(value),
        currency="USD",
        unit="currency",
        provider=provider,
        provider_field=provider_field or f"us-gaap:{metric}",
        source_type="primary_source",
        source_url="https://www.sec.gov/example",
    )


def test_financial_worksheet_groups_excel_like_sections_and_year_modes() -> None:
    with _session() as session:
        analysis = _analysis(session)
        for year in range(2015, 2026):
            session.add(_fact(analysis, "revenue", year, str(year)))
        session.commit()

        states = load_preferred_data_states(session, analysis.id)
        worksheet_5y = build_financial_worksheet(session, analysis.id, states, year_mode="5 Jahre")
        worksheet_10y = build_financial_worksheet(session, analysis.id, states, year_mode="10 Jahre")
        worksheet_all = build_financial_worksheet(session, analysis.id, states, year_mode="Alle")

        assert tuple(worksheet_5y.sections) == (
            "Gewinn- und Verlustrechnung",
            "Bilanz",
            "Cashflow",
        )
        assert worksheet_5y.years == (2021, 2022, 2023, 2024, 2025)
        assert worksheet_10y.years == tuple(range(2016, 2026))
        assert worksheet_all.years == tuple(range(2015, 2026))


def test_missing_and_review_cells_are_actionable() -> None:
    with _session() as session:
        analysis = _analysis(session)
        session.add(
            _fact(
                analysis,
                "short_term_debt",
                2025,
                "100",
                provider_field="us-gaap:LongTermDebtCurrent",
            )
        )
        session.commit()

        states = load_preferred_data_states(session, analysis.id)
        worksheet = build_financial_worksheet(session, analysis.id, states, year_mode="5 Jahre")

        short_debt = worksheet.cells[("short_term_debt", 2025)]
        missing_revenue = worksheet.cells[("revenue", 2025)]

        assert short_debt.status in {
            WorksheetCellStatus.OFFICIAL_CANDIDATE_FOUND,
            WorksheetCellStatus.PRESENT_REVIEW_REQUIRED,
            WorksheetCellStatus.REVIEW_REQUIRED,
            WorksheetCellStatus.CANDIDATE_FOUND,
        }
        assert missing_revenue.status in {WorksheetCellStatus.NOT_FOUND, WorksheetCellStatus.MISSING}
        assert short_debt in open_cells(worksheet)
        assert missing_revenue in open_cells(worksheet)


def test_override_persists_and_original_fact_remains_unchanged_after_reopen() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        original = _fact(
            analysis,
            "short_term_debt",
            2025,
            "100",
            provider_field="us-gaap:DebtCurrent",
        )
        session.add(original)
        session.commit()
        upsert_manual_financial_override(
            session,
            analysis,
            metric="short_term_debt",
            period_end=date(2025, 12, 31),
            value=Decimal("123"),
            currency="USD",
            unit="currency",
            statement="balance_sheet",
            source_name="Aktienfinder",
            note="User correction",
        )

    with Session(engine, expire_on_commit=False) as reopened:
        facts = reopened.scalars(
            select(FinancialFactSnapshot).where(FinancialFactSnapshot.metric == "short_term_debt")
        ).all()
        assert sorted((fact.provider, fact.value) for fact in facts) == [
            ("manual_override", Decimal("123.00000000")),
            ("sec_companyfacts", Decimal("100.00000000")),
        ]
        analysis = reopened.scalar(select(Analysis))
        assert analysis is not None
        states = load_preferred_data_states(reopened, analysis.id)
        worksheet = build_financial_worksheet(reopened, analysis.id, states, year_mode="Alle")
        assert worksheet.cells[("short_term_debt", 2025)].status == WorksheetCellStatus.MANUAL_OVERRIDE
        assert worksheet.cells[("short_term_debt", 2025)].value == Decimal("123.00000000")


def test_override_removal_restores_automatic_preferred_value() -> None:
    with _session() as session:
        analysis = _analysis(session)
        session.add(
            _fact(
                analysis,
                "short_term_debt",
                2025,
                "100",
                provider_field="us-gaap:DebtCurrent",
            )
        )
        session.commit()
        upsert_manual_financial_override(
            session,
            analysis,
            metric="short_term_debt",
            period_end=date(2025, 12, 31),
            value=Decimal("123"),
            currency="USD",
            unit="currency",
            statement="balance_sheet",
            source_name="Aktienfinder",
        )
        remove_manual_financial_override(
            session,
            analysis,
            metric="short_term_debt",
            period_end=date(2025, 12, 31),
        )

        states = load_preferred_data_states(session, analysis.id)
        worksheet = build_financial_worksheet(session, analysis.id, states, year_mode="Alle")

        assert worksheet.cells[("short_term_debt", 2025)].value == Decimal("100.00000000")
        assert worksheet.cells[("short_term_debt", 2025)].provider == "sec_companyfacts"


def test_missing_data_search_candidate_semantics() -> None:
    with _session() as session:
        analysis = _analysis(session)
        session.add(
            _fact(
                analysis,
                "short_term_debt",
                2025,
                "100",
                provider_field="us-gaap:DebtCurrent",
            )
        )
        session.add(
            _fact(
                analysis,
                "short_term_debt",
                2024,
                "90",
                provider_field="us-gaap:LongTermDebtCurrent",
            )
        )
        session.add(
            _fact(
                analysis,
                "short_term_debt",
                2023,
                "80",
                provider_field="us-gaap:AccountsPayableCurrent",
            )
        )
        session.commit()

        safe = worksheet_candidates(session, analysis.id, "short_term_debt", 2025)
        review = worksheet_candidates(session, analysis.id, "short_term_debt", 2024)
        rejected = worksheet_candidates(session, analysis.id, "short_term_debt", 2023)
        none = worksheet_candidates(session, analysis.id, "short_term_debt", 2022)

        assert safe[0].selectable_without_review is True
        assert review[0].selectable_without_review is False
        assert review[0].semantic_decision == "REVIEW_REQUIRED"
        assert rejected == ()
        assert none == ()


def test_short_term_debt_regression_rejects_non_debt_fields() -> None:
    assert is_short_term_debt_candidate_field("us-gaap:DebtCurrent")[0] is True
    assert is_short_term_debt_candidate_field("us-gaap:CurrentPortionOfLongTermDebt")[0] is True
    assert is_short_term_debt_candidate_field("us-gaap:AccountsPayableCurrent")[0] is False
    assert is_short_term_debt_candidate_field("us-gaap:LiabilitiesCurrent")[0] is False
    assert is_short_term_debt_candidate_field("ifrs-full:LeaseLiabilityCurrent")[0] is False
