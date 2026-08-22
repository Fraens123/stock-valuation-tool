import json
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from stock_valuation.analyses.ai_review_service import (
    AIReviewError,
    accept_ai_review_finding,
    build_chatgpt_review_package,
    import_chatgpt_review_result,
    reject_ai_review_finding,
)
from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.resolution import load_preferred_financial_facts
from stock_valuation.database.ai_review_models import AIReviewFinding
from stock_valuation.database.models import Base, FinancialFactSnapshot


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


def _result_payload(package, fact, *, value=102, status="WARN") -> dict:
    return {
        "schema_version": "1.0",
        "package_id": package.package_id,
        "years_requested": package.years_requested,
        "company": {
            "name": "Microsoft Corporation",
            "ticker": "MSFT",
            "analysis_as_of_date": "2026-08-22",
            "revision": 1,
        },
        "summary": "One verified difference.",
        "findings": [
            {
                "fact_id": fact.id,
                "official_value": value,
                "status": status,
                "official_label": "Revenue",
                "source_title": "Microsoft Annual Report",
                "source_url": "https://www.microsoft.com/investor/example",
                "reason": "Official filing reports a different value in the same base unit.",
            }
        ],
    }


def test_review_package_contains_snapshot_identity_and_requires_no_api() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        fact = _fact(session, analysis.id)

        package = build_chatgpt_review_package(session, analysis, years=3)
        text = package.content.decode("utf-8")

        assert package.fact_count == 1
        assert package.package_id in text
        assert str(fact.id) in text
        assert "MSFT" in package.filename
        assert package.result_filename.endswith("_chatgpt_review_result.json")
        assert "OpenAI-API" not in text


def test_imported_chatgpt_result_persists_findings_without_changing_original() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        fact = _fact(session, analysis.id)
        package = build_chatgpt_review_package(session, analysis, years=3)
        payload = _result_payload(package, fact)

        run = import_chatgpt_review_result(session, analysis, json.dumps(payload).encode("utf-8"))

        assert run.response_id == package.package_id
        assert run.model == "chatgpt_file_review"
        assert len(run.findings) == 1
        assert run.findings[0].decision == "pending"
        assert run.findings[0].official_value == Decimal("102.00000000")
        original = session.get(FinancialFactSnapshot, fact.id)
        assert original.value == Decimal("100")


def test_result_for_different_package_is_rejected() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        fact = _fact(session, analysis.id)
        package = build_chatgpt_review_package(session, analysis, years=3)
        payload = _result_payload(package, fact)
        payload["package_id"] = "wrong-package-id"

        with pytest.raises(AIReviewError, match="Package-ID"):
            import_chatgpt_review_result(session, analysis, json.dumps(payload))


def test_user_acceptance_creates_priority_override_and_rejection_does_not() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        fact = _fact(session, analysis.id)
        package = build_chatgpt_review_package(session, analysis, years=3)
        payload = _result_payload(package, fact, value=105, status="FAIL")
        run = import_chatgpt_review_result(session, analysis, json.dumps(payload))
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
