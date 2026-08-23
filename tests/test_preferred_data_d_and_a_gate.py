from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.preferred_data import load_preferred_data_states
from stock_valuation.database.ai_review_models import AIReviewFinding, AIReviewRun
from stock_valuation.database.models import Base, FinancialFactSnapshot


def _setup(session: Session):
    company = get_or_create_company(
        session,
        name="Example Corporation",
        ticker="EXM",
        currency="USD",
    )
    analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
    fact = FinancialFactSnapshot(
        analysis_id=analysis.id,
        statement="cash_flow",
        metric="depreciation_amortization",
        period_end=date(2025, 12, 31),
        period_type="FY",
        value=Decimal("100"),
        provider_value=Decimal("100"),
        currency="USD",
        unit="currency",
        provider="sec_companyfacts",
        provider_field="us-gaap:DepreciationDepletionAndAmortization",
        source_type="primary_source",
        is_cross_check_only=False,
    )
    session.add(fact)
    session.commit()
    return analysis, fact


def _review(session: Session, analysis_id: int, fact: FinancialFactSnapshot, verdict: str) -> None:
    run = AIReviewRun(
        analysis_id=analysis_id,
        model="chatgpt_file_review",
        years_requested=1,
        status="completed",
        response_id=f"d-and-a-{verdict.lower()}",
        summary="test",
        completed_at=datetime.now(UTC),
    )
    session.add(run)
    session.flush()
    session.add(
        AIReviewFinding(
            run_id=run.id,
            analysis_id=analysis_id,
            period_end=fact.period_end,
            statement=fact.statement,
            metric=fact.metric,
            imported_value=fact.value,
            official_value=fact.value if verdict == "PASS" else None,
            currency=fact.currency,
            verdict=verdict,
            provider=fact.provider,
            provider_field=fact.provider_field,
            source_title="Official filing",
            source_url="https://example.com/filing",
            reason="semantic review",
        )
    )
    session.commit()


def test_sec_d_and_a_requires_matching_semantic_pass() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis, fact = _setup(session)

        state = load_preferred_data_states(
            session,
            analysis.id,
            metrics=["depreciation_amortization"],
        )[0]
        assert state.quality_status == "primary_semantic_review_required"
        assert state.calculation_ready is False

        _review(session, analysis.id, fact, "UNKLAR")
        state = load_preferred_data_states(
            session,
            analysis.id,
            metrics=["depreciation_amortization"],
        )[0]
        assert state.review_verdict == "UNKLAR"
        assert state.calculation_ready is False

        _review(session, analysis.id, fact, "PASS")
        state = load_preferred_data_states(
            session,
            analysis.id,
            metrics=["depreciation_amortization"],
        )[0]
        assert state.quality_status == "primary_reviewed_pass"
        assert state.calculation_ready is True
