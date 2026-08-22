from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis, get_or_create_company
from stock_valuation.database.models import Base, FinancialFactSnapshot
from stock_valuation.validation.asml_reference import PrimarySourceReference
from stock_valuation.validation.service import validate_asml_primary_source, validation_summary


def test_asml_validation_flags_match_mismatch_and_missing() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(
            session,
            name="ASML Holding N.V.",
            ticker="ASML",
            currency="EUR",
            provider_symbol="ASML.AS",
        )
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 22))
        session.add_all(
            [
                FinancialFactSnapshot(
                    analysis_id=analysis.id,
                    statement="income_statement",
                    metric="revenue",
                    period_end=date(2025, 12, 31),
                    period_type="FY",
                    value=Decimal("1000"),
                    provider_value=Decimal("1000"),
                    provider="alphavantage",
                    provider_field="totalRevenue",
                ),
                FinancialFactSnapshot(
                    analysis_id=analysis.id,
                    statement="balance_sheet",
                    metric="accounts_receivable",
                    period_end=date(2025, 12, 31),
                    period_type="FY",
                    value=Decimal("1400"),
                    provider_value=Decimal("1400"),
                    provider="alphavantage",
                    provider_field="currentNetReceivables",
                ),
            ]
        )
        session.commit()

        refs = (
            PrimarySourceReference(
                metric="revenue",
                period_end=date(2025, 12, 31),
                value=Decimal("1000"),
                label="Revenue",
                source_url="https://example.com",
            ),
            PrimarySourceReference(
                metric="accounts_receivable",
                period_end=date(2025, 12, 31),
                value=Decimal("1000"),
                label="Receivables",
                source_url="https://example.com",
            ),
            PrimarySourceReference(
                metric="inventory",
                period_end=date(2025, 12, 31),
                value=Decimal("1000"),
                label="Inventory",
                source_url="https://example.com",
            ),
        )

        results = validate_asml_primary_source(session, analysis, references=refs)
        by_metric = {row.metric: row for row in results}

        assert by_metric["revenue"].status == "pass"
        assert by_metric["accounts_receivable"].status == "fail"
        assert by_metric["inventory"].status == "missing"

        summary = validation_summary(results)
        assert summary["critical_fail"] == 1
        assert summary["critical_missing"] == 1
        assert summary["provider_gate_passed"] is False
