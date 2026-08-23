from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.history_mapping_audit import audit_history_mapping
from stock_valuation.database.ai_review_models import AIReviewFinding, AIReviewRun
from stock_valuation.database.models import Base, FinancialFactSnapshot


def _fact(session: Session, analysis_id: int, year: int, provider: str) -> FinancialFactSnapshot:
    extension = provider == "sec_filing_extension"
    row = FinancialFactSnapshot(
        analysis_id=analysis_id,
        statement="cash_flow",
        metric="dividends_paid",
        period_end=date(year, 12, 31),
        period_type="FY",
        value=Decimal(year),
        provider_value=Decimal(year),
        currency="EUR",
        unit="currency",
        provider=provider,
        provider_field=(
            "company-extension:DividendsPaidToShareholders"
            if extension
            else "us-gaap:PaymentsOfDividends"
        ),
        source_type="primary_source",
        is_cross_check_only=False,
    )
    session.add(row)
    session.flush()
    return row


def test_extension_transition_is_review_until_matching_pass_then_stable() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(
            session,
            name="Example NV",
            ticker="EXM",
            currency="EUR",
        )
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        candidate = None
        for year in range(2016, 2026):
            row = _fact(
                session,
                analysis.id,
                year,
                "sec_filing_extension" if year == 2019 else "sec_companyfacts",
            )
            if year == 2019:
                candidate = row
        session.commit()

        before = next(
            row
            for row in audit_history_mapping(session, analysis).rows
            if row.metric == "dividends_paid"
        )
        assert before.status == "REVIEW"
        assert candidate is not None

        run = AIReviewRun(
            analysis_id=analysis.id,
            model="chatgpt_file_review",
            years_requested=3,
            status="completed",
            response_id="test",
        )
        session.add(run)
        session.flush()
        session.add(
            AIReviewFinding(
                run_id=run.id,
                analysis_id=analysis.id,
                period_end=candidate.period_end,
                statement=candidate.statement,
                metric=candidate.metric,
                imported_value=candidate.value,
                official_value=candidate.value,
                currency="EUR",
                verdict="PASS",
                provider=candidate.provider,
                provider_field=candidate.provider_field,
                reason="Extension concept semantically confirmed.",
            )
        )
        session.commit()

        after = next(
            row
            for row in audit_history_mapping(session, analysis).rows
            if row.metric == "dividends_paid"
        )
        assert after.status == "PASS"
        assert after.coverage_label == "10/10"
        assert "semantisch bestätigt" in after.reason
