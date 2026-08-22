import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from stock_valuation.analyses.ai_review_service import (
    accept_ai_review_finding,
    execute_ai_review,
    reject_ai_review_finding,
)
from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.resolution import load_preferred_financial_facts
from stock_valuation.database.ai_review_models import AIReviewFinding
from stock_valuation.database.models import Base, FinancialFactSnapshot


class _FakeResponses:
    def __init__(self, payload: dict):
        self.payload = payload
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(
            id="resp_test",
            output_text=json.dumps(self.payload),
        )


class _FakeClient:
    def __init__(self, payload: dict):
        self.responses = _FakeResponses(payload)


def _analysis(session: Session):
    company = get_or_create_company(
        session,
        name="Microsoft Corporation",
        ticker="MSFT",
        currency="USD",
        exchange="United States",
    )
    return create_analysis(session, company=company, as_of_date=date(2026, 8, 22))


def _fact(session: Session, analysis_id: int) -> FinancialFactSnapshot:
    row = FinancialFactSnapshot(
        analysis_id=analysis_id,
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
    session.add(row)
    session.commit()
    return row


def test_ai_review_persists_findings_without_changing_financial_fact() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        fact = _fact(session, analysis.id)
        client = _FakeClient(
            {
                "summary": "One verified difference.",
                "findings": [
                    {
                        "fact_id": fact.id,
                        "official_value": 102,
                        "status": "WARN",
                        "official_label": "Revenue",
                        "source_title": "Microsoft Annual Report",
                        "source_url": "https://www.microsoft.com/investor/example",
                        "reason": "Official filing reports 102 in the same base unit.",
                    }
                ],
            }
        )

        run = execute_ai_review(session, analysis, years=3, client=client, model="test-model")

        assert run.response_id == "resp_test"
        assert len(run.findings) == 1
        assert run.findings[0].decision == "pending"
        assert run.findings[0].official_value == Decimal("102.00000000")
        original = session.get(FinancialFactSnapshot, fact.id)
        assert original.value == Decimal("100")
        assert client.responses.last_kwargs["tools"] == [{"type": "web_search"}]
        assert client.responses.last_kwargs["store"] is False


def test_user_acceptance_creates_priority_override_and_rejection_does_not() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        fact = _fact(session, analysis.id)
        client = _FakeClient(
            {
                "summary": "Difference found.",
                "findings": [
                    {
                        "fact_id": fact.id,
                        "official_value": 105,
                        "status": "FAIL",
                        "official_label": "Revenue",
                        "source_title": "Official Annual Report",
                        "source_url": "https://example.com/annual-report",
                        "reason": "Provider differs from the official value.",
                    }
                ],
            }
        )
        run = execute_ai_review(session, analysis, client=client, model="test-model")
        finding = run.findings[0]

        accept_ai_review_finding(session, analysis, finding.id)
        preferred = load_preferred_financial_facts(session, analysis.id, metrics=["revenue"])
        assert len(preferred) == 1
        assert preferred[0].provider == "manual_override"
        assert preferred[0].value == Decimal("105")
        stored = session.get(AIReviewFinding, finding.id)
        assert stored.decision == "accepted"

        second = AIReviewFinding(
            run_id=run.id,
            analysis_id=analysis.id,
            period_end=date(2026, 6, 30),
            statement="income_statement",
            metric="net_income",
            imported_value=Decimal("10"),
            official_value=Decimal("11"),
            currency="USD",
            verdict="FAIL",
            source_url="https://example.com/report",
            reason="test",
        )
        session.add(second)
        session.commit()
        reject_ai_review_finding(session, analysis, second.id)
        assert session.get(AIReviewFinding, second.id).decision == "rejected"
        assert session.scalars(
            select(FinancialFactSnapshot).where(
                FinancialFactSnapshot.analysis_id == analysis.id,
                FinancialFactSnapshot.metric == "net_income",
                FinancialFactSnapshot.provider == "manual_override",
            )
        ).first() is None
