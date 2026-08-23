from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.preferred_data import load_preferred_data_states
from stock_valuation.data.providers.sec_extension import SECCompanyExtensionResult
from stock_valuation.data.providers.sec_filing import SECFilingFallbackResult, SECFilingGap
from stock_valuation.data.source_router import sync_best_available_financials
from stock_valuation.data.types import NormalizedFinancialFact
from stock_valuation.database.models import Base, FinancialFactSnapshot


def _fact(metric: str, year: int, provider: str, value: int) -> NormalizedFinancialFact:
    statement = (
        "cash_flow"
        if metric in {"operating_cash_flow", "dividends_paid"}
        else "balance_sheet"
        if metric in {"total_assets", "shareholders_equity"}
        else "income_statement"
    )
    return NormalizedFinancialFact(
        statement=statement,
        metric=metric,
        period_end=date(year, 12, 31),
        period_type="FY",
        value=Decimal(value),
        provider_value=Decimal(value),
        currency="EUR",
        unit="currency",
        provider=provider,
        provider_field=(
            "company-extension:DividendsPaidToShareholders"
            if provider == "sec_filing_extension"
            else f"us-gaap:{metric}"
        ),
        source_url="https://www.sec.gov/example.xml" if provider == "sec_filing_extension" else None,
        note="SEC Company-Extension-Kandidat; noch nicht semantisch freigegeben."
        if provider == "sec_filing_extension"
        else None,
    )


class FakeSEC:
    def resolve_company(self, ticker: str, name: str | None = None):
        return SimpleNamespace(cik="0000123456", name=name or ticker)

    def get_normalized_financials(self, cik: str):
        rows = []
        for year in (2024, 2025):
            for metric, value in (
                ("revenue", 1000),
                ("net_income", 100),
                ("total_assets", 5000),
                ("shareholders_equity", 2500),
                ("operating_cash_flow", 300),
            ):
                rows.append(_fact(metric, year, "sec_companyfacts", value + year))
        # dividends_paid exists in 2024 but is deliberately absent in 2025.
        rows.append(_fact("dividends_paid", 2024, "sec_companyfacts", 200))
        return rows


class FakeFiling:
    def gap_facts(self, cik: str, base_facts, *, years: int = 10):
        return SECFilingFallbackResult(
            facts=(),
            unresolved=(
                SECFilingGap(
                    "dividends_paid",
                    2025,
                    "semantic_review_required",
                    "Company extension required.",
                    "https://www.sec.gov/example.htm",
                ),
            ),
            filings_checked=1,
        )


class FakeExtension:
    def candidate_facts(self, cik: str, gaps, base_facts):
        return SECCompanyExtensionResult(
            facts=(_fact("dividends_paid", 2025, "sec_filing_extension", 300),),
            unresolved=(),
            filings_checked=1,
        )


class NeverCalledGLEIF:
    def resolve_lei(self, legal_name: str, *, country: str | None = None):
        raise AssertionError("ESEF route must not run")


class NeverCalledESEF:
    def get_normalized_financials(self, lei: str, *, filing_limit: int = 8):
        raise AssertionError("ESEF route must not run")


def test_router_stores_extension_candidate_but_keeps_it_blocked() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(
            session,
            name="Example Corp",
            ticker="EXM",
            currency="EUR",
            country="US",
        )
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))

        result = sync_best_available_financials(
            session,
            analysis,
            sec_provider=FakeSEC(),
            sec_filing_provider=FakeFiling(),
            sec_extension_provider=FakeExtension(),
            gleif_provider=NeverCalledGLEIF(),
            esef_provider=NeverCalledESEF(),
            allow_alpha_fallback=False,
        )

        assert result.selected_source == "SEC"
        assert any(
            attempt.source == "SEC Extension-Mapping"
            and attempt.status == "candidates_found"
            and attempt.fact_count == 1
            for attempt in result.attempts
        )
        candidate = session.scalar(
            select(FinancialFactSnapshot).where(
                FinancialFactSnapshot.analysis_id == analysis.id,
                FinancialFactSnapshot.provider == "sec_filing_extension",
                FinancialFactSnapshot.metric == "dividends_paid",
                FinancialFactSnapshot.period_end == date(2025, 12, 31),
            )
        )
        assert candidate is not None
        assert candidate.value == Decimal("300")
        state = next(
            state
            for state in load_preferred_data_states(session, analysis.id)
            if state.fact.metric == "dividends_paid" and state.fact.period_end.year == 2025
        )
        assert state.fact.provider == "sec_filing_extension"
        assert state.calculation_ready is False
        assert state.quality_status == "primary_semantic_review_required"
