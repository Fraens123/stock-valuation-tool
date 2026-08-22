from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.audit import build_ai_review_prompt, run_deterministic_audit
from stock_valuation.database.models import Base, FinancialFactSnapshot


def _fact(analysis_id: int, metric: str, value: str) -> FinancialFactSnapshot:
    return FinancialFactSnapshot(
        analysis_id=analysis_id,
        statement="test",
        metric=metric,
        period_end=date(2025, 12, 31),
        period_type="FY",
        value=Decimal(value),
        provider_value=Decimal(value),
        currency="USD",
        unit="currency",
        provider="alphavantage",
        provider_field=metric,
        source_type="provider",
    )


def test_audit_checks_basic_accounting_identities_and_builds_prompt() -> None:
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
        session.add_all(
            [
                _fact(analysis.id, "revenue", "1000"),
                _fact(analysis.id, "cost_of_revenue", "600"),
                _fact(analysis.id, "gross_profit", "400"),
                _fact(analysis.id, "total_assets", "1200"),
                _fact(analysis.id, "total_liabilities", "700"),
                _fact(analysis.id, "shareholders_equity", "500"),
                _fact(analysis.id, "current_assets", "500"),
                _fact(analysis.id, "current_liabilities", "300"),
                _fact(analysis.id, "cash_and_equivalents", "200"),
            ]
        )
        session.commit()

        checks = run_deterministic_audit(session, analysis)
        assert checks
        assert all(item.status == "PASS" for item in checks)

        prompt = build_ai_review_prompt(session, analysis)
        assert "Example Corp" in prompt
        assert "Bruttogewinn" in prompt
        assert "offiziellen Geschäftsbericht" in prompt
