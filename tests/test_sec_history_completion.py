from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.provider_symbols import upsert_provider_symbol
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.providers.sec_text import SECFilingTextResult
from stock_valuation.data.sec_history_completion import sync_sec_history_text_candidates
from stock_valuation.data.types import NormalizedFinancialFact
from stock_valuation.database.models import Base, FinancialFactSnapshot


class FakeTextProvider:
    def candidate_facts(self, cik, gaps, base_facts):
        rows = []
        for gap in gaps:
            rows.append(
                NormalizedFinancialFact(
                    statement="cash_flow",
                    metric=gap.metric,
                    period_end=date(gap.year, 12, 31),
                    period_type="FY",
                    value=Decimal("100"),
                    provider_value=Decimal("100"),
                    currency="EUR",
                    unit="currency",
                    provider="sec_filing_text_candidate",
                    provider_field=f"text-table:{gap.metric}",
                    source_url="https://www.sec.gov/example/report.htm",
                )
            )
        return SECFilingTextResult(tuple(rows), (), 1)


def _fact(analysis_id: int, metric: str, year: int) -> FinancialFactSnapshot:
    return FinancialFactSnapshot(
        analysis_id=analysis_id,
        statement="cash_flow" if metric == "dividends_paid" else "income_statement",
        metric=metric,
        period_end=date(year, 12, 31),
        period_type="FY",
        value=Decimal("100"),
        provider_value=Decimal("100"),
        currency="EUR",
        unit="currency",
        provider="sec_companyfacts",
        provider_field=("us-gaap:PaymentsOfDividends" if metric == "dividends_paid" else "us-gaap:Revenue"),
        source_type="primary_source",
        is_cross_check_only=False,
    )


def test_completion_routes_table_rows_into_existing_semantic_review_provider() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(session, name="Example NV", ticker="EXM", currency="EUR")
        upsert_provider_symbol(session, company, provider="sec", purpose="cik", symbol="0000000001")
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        for year in range(2016, 2026):
            session.add(_fact(analysis.id, "revenue", year))
        for year in range(2016, 2019):
            session.add(_fact(analysis.id, "dividends_paid", year))
        session.commit()

        result = sync_sec_history_text_candidates(
            session,
            analysis,
            text_provider=FakeTextProvider(),  # type: ignore[arg-type]
        )

        assert result.candidate_count == 7
        stored = session.scalars(
            select(FinancialFactSnapshot).where(
                FinancialFactSnapshot.analysis_id == analysis.id,
                FinancialFactSnapshot.provider == "sec_filing_extension",
                FinancialFactSnapshot.metric == "dividends_paid",
            )
        ).all()
        assert len(stored) == 7
        assert all((row.provider_field or "").startswith("text-table:") for row in stored)
