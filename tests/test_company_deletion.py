from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.deletion import (
    delete_all_companies_completely,
    delete_company_completely,
)
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.database.ai_review_models import AIReviewFinding, AIReviewRun
from stock_valuation.database.models import (
    Analysis,
    Base,
    Company,
    CompanyProviderSymbol,
    EstimateSnapshot,
    FinancialFactSnapshot,
    InvestmentThesis,
    MetricSnapshot,
)


def _company(session: Session, ticker: str) -> Company:
    return get_or_create_company(
        session,
        name=f"{ticker} Test Company",
        ticker=ticker,
        currency="USD",
        exchange="United States",
    )


def _populate_company(session: Session, ticker: str) -> tuple[Company, Analysis]:
    company = _company(session, ticker)
    analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 22))

    session.add(
        CompanyProviderSymbol(
            company_id=company.id,
            provider="alphavantage",
            purpose="fundamentals",
            symbol=ticker,
        )
    )
    fact = FinancialFactSnapshot(
        analysis_id=analysis.id,
        statement="income_statement",
        metric="revenue",
        period_end=date(2026, 6, 30),
        period_type="FY",
        value=Decimal("100"),
        provider_value=Decimal("100"),
        currency="USD",
        unit="currency",
        provider="alphavantage",
        provider_field="totalRevenue",
        source_type="provider",
        is_cross_check_only=False,
    )
    session.add(fact)
    session.add(
        EstimateSnapshot(
            analysis_id=analysis.id,
            metric="revenue",
            period="2027-06-30",
            average=Decimal("110"),
            provider="alphavantage",
            currency="USD",
            unit="currency",
        )
    )
    session.add(
        MetricSnapshot(
            analysis_id=analysis.id,
            metric_id="ebit_margin",
            period="2026",
            value=Decimal("0.30"),
            unit="decimal_ratio",
            calculation_version="test",
        )
    )
    session.add(
        InvestmentThesis(
            analysis_id=analysis.id,
            thesis_summary="test",
        )
    )
    session.flush()

    run = AIReviewRun(
        analysis_id=analysis.id,
        model="chatgpt_file_review",
        years_requested=1,
        status="completed",
        response_id="package-test",
    )
    session.add(run)
    session.flush()
    session.add(
        AIReviewFinding(
            run_id=run.id,
            analysis_id=analysis.id,
            period_end=date(2026, 6, 30),
            statement="income_statement",
            metric="revenue",
            imported_value=Decimal("100"),
            official_value=Decimal("100"),
            currency="USD",
            verdict="PASS",
            provider="alphavantage",
            provider_field="totalRevenue",
        )
    )
    session.commit()
    return company, analysis


def _count(session: Session, model) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def test_delete_one_company_removes_all_its_analysis_data_but_keeps_other_company() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        first, first_analysis = _populate_company(session, "AAA")
        second, second_analysis = _populate_company(session, "BBB")

        summary = delete_company_completely(session, first.id)

        assert summary.companies == 1
        assert summary.analyses == 1
        assert session.get(Company, first.id) is None
        assert session.get(Analysis, first_analysis.id) is None
        assert session.get(Company, second.id) is not None
        assert session.get(Analysis, second_analysis.id) is not None

        assert session.scalar(
            select(FinancialFactSnapshot.id).where(
                FinancialFactSnapshot.analysis_id == first_analysis.id
            )
        ) is None
        assert session.scalar(
            select(AIReviewRun.id).where(AIReviewRun.analysis_id == first_analysis.id)
        ) is None
        assert session.scalar(
            select(AIReviewFinding.id).where(
                AIReviewFinding.analysis_id == first_analysis.id
            )
        ) is None
        assert session.scalar(
            select(CompanyProviderSymbol.id).where(
                CompanyProviderSymbol.company_id == first.id
            )
        ) is None


def test_delete_company_handles_revision_self_references() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        company = _company(session, "REV")
        first = create_analysis(session, company=company, as_of_date=date(2025, 8, 22))
        second = create_analysis(
            session,
            company=company,
            as_of_date=date(2026, 8, 22),
            previous_analysis=first,
        )

        summary = delete_company_completely(session, company.id)

        assert summary.companies == 1
        assert summary.analyses == 2
        assert session.get(Analysis, first.id) is None
        assert session.get(Analysis, second.id) is None
        assert session.get(Company, company.id) is None


def test_delete_all_companies_leaves_database_schema_empty_and_reusable() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        _populate_company(session, "AAA")
        _populate_company(session, "BBB")

        summary = delete_all_companies_completely(session)

        assert summary.companies == 2
        assert summary.analyses == 2
        assert _count(session, Company) == 0
        assert _count(session, Analysis) == 0
        assert _count(session, FinancialFactSnapshot) == 0
        assert _count(session, EstimateSnapshot) == 0
        assert _count(session, MetricSnapshot) == 0
        assert _count(session, AIReviewRun) == 0
        assert _count(session, AIReviewFinding) == 0
        assert _count(session, CompanyProviderSymbol) == 0

        fresh = _company(session, "ASML")
        fresh_analysis = create_analysis(
            session,
            company=fresh,
            as_of_date=date(2026, 8, 22),
        )
        assert fresh.ticker == "ASML"
        assert fresh_analysis.revision_number == 1
