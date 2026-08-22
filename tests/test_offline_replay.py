from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from stock_valuation.analyses.ai_review_service import build_chatgpt_review_package
from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.offline_replay import replay_review_files
from stock_valuation.database.ai_review_models import AIReviewFinding
from stock_valuation.database.models import Base, FinancialFactSnapshot


def _source_package_and_result() -> tuple[bytes, bytes]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(
            session,
            name="Microsoft Corporation",
            ticker="MSFT",
            currency="USD",
            exchange="United States",
        )
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 22))
        fact = FinancialFactSnapshot(
            analysis_id=analysis.id,
            statement="income_statement",
            metric="revenue",
            period_end=date(2025, 6, 30),
            period_type="FY",
            value=Decimal("100"),
            provider_value=Decimal("100"),
            currency="USD",
            unit="currency",
            provider="alphavantage",
            provider_field="totalRevenue",
            source_type="provider",
            source_url="https://www.alphavantage.co/documentation/#fundamentals",
            is_cross_check_only=False,
        )
        session.add(fact)
        session.commit()

        package = build_chatgpt_review_package(session, analysis, years=1)
        result = {
            "schema_version": "1.0",
            "package_id": package.package_id,
            "years_requested": 1,
            "company": {
                "name": "Microsoft Corporation",
                "ticker": "MSFT",
                "analysis_as_of_date": "2026-08-22",
                "revision": 1,
            },
            "summary": "offline replay test",
            "findings": [
                {
                    "fact_id": fact.id,
                    "official_value": 100,
                    "status": "PASS",
                    "official_label": "Revenue",
                    "source_title": "Microsoft Annual Report",
                    "source_url": "https://www.microsoft.com/investor/example",
                    "reason": "same value",
                }
            ],
        }
        return package.content, json.dumps(result).encode("utf-8")


def test_offline_replay_remaps_fact_ids_and_imports_review() -> None:
    package_content, result_content = _source_package_and_result()

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        # Consume an analysis ID so the replay cannot accidentally rely on the original DB IDs.
        dummy_company = get_or_create_company(
            session,
            name="Dummy Corp",
            ticker="DUMMY",
            currency="USD",
        )
        create_analysis(session, company=dummy_company, as_of_date=date(2026, 1, 1))

        summary = replay_review_files(session, package_content, result_content)

        assert summary.ticker == "MSFT"
        assert summary.fact_count == 1
        assert summary.review_finding_count == 1
        assert summary.old_package_id != summary.new_package_id

        fact = session.scalar(
            select(FinancialFactSnapshot).where(
                FinancialFactSnapshot.analysis_id == summary.analysis_id,
                FinancialFactSnapshot.metric == "revenue",
            )
        )
        assert fact is not None
        assert fact.value == Decimal("100")

        finding = session.scalar(
            select(AIReviewFinding).where(AIReviewFinding.analysis_id == summary.analysis_id)
        )
        assert finding is not None
        assert finding.verdict == "PASS"
        # AIReviewFinding intentionally stores an auditable snapshot of the reviewed fact rather
        # than a foreign-key fact_id. Successful import already proves that the old fact_id was
        # remapped to a valid recreated fact. Verify the persisted semantic identity/value here.
        assert finding.metric == fact.metric
        assert finding.statement == fact.statement
        assert finding.period_end == fact.period_end
        assert finding.imported_value == fact.value
        assert finding.provider == fact.provider
        assert finding.provider_field == fact.provider_field
