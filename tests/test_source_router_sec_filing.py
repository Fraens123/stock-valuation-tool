from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.providers.sec_filing import SECFilingFallbackResult
from stock_valuation.data.source_router import sync_best_available_financials
from stock_valuation.data.types import NormalizedFinancialFact
from stock_valuation.database.models import Base, FinancialFactSnapshot


def _fact(metric: str, year: int, provider: str, value: int) -> NormalizedFinancialFact:
    statement = (
        "cash_flow"
        if metric == "operating_cash_flow"
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
        provider_field=f"us-gaap:{metric}",
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
                if year == 2024 and metric == "operating_cash_flow":
                    continue
                rows.append(_fact(metric, year, "sec_companyfacts", value + year))
        return rows


class FakeFilingFallback:
    def gap_facts(self, cik: str, base_facts, *, years: int = 10):
        assert cik == "0000123456"
        assert any(fact.metric == "operating_cash_flow" for fact in base_facts)
        return SECFilingFallbackResult(
            facts=(
                _fact("operating_cash_flow", 2024, "sec_filing_xbrl", 2324),
            ),
            unresolved=(),
            filings_checked=1,
        )


class NeverCalledGLEIF:
    def resolve_lei(self, legal_name: str, *, country: str | None = None):
        raise AssertionError("ESEF route must not run after a usable SEC import")


class NeverCalledESEF:
    def get_normalized_financials(self, lei: str, *, filing_limit: int = 8):
        raise AssertionError("ESEF route must not run after a usable SEC import")


def test_router_supplements_companyfacts_gap_from_original_sec_filing() -> None:
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
            sec_filing_provider=FakeFilingFallback(),
            gleif_provider=NeverCalledGLEIF(),
            esef_provider=NeverCalledESEF(),
            allow_alpha_fallback=False,
        )

        assert result.selected_source == "SEC"
        assert result.fact_count == 10
        assert any(
            attempt.source == "SEC Original-Filing" and attempt.status == "supplemented"
            for attempt in result.attempts
        )
        supplemental = session.scalar(
            select(FinancialFactSnapshot).where(
                FinancialFactSnapshot.analysis_id == analysis.id,
                FinancialFactSnapshot.metric == "operating_cash_flow",
                FinancialFactSnapshot.period_end == date(2024, 12, 31),
            )
        )
        assert supplemental is not None
        assert supplemental.provider == "sec_filing_xbrl"
        assert supplemental.source_type == "primary_source"
