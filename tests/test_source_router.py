from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.provider_symbols import get_provider_symbol
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.resolution import load_preferred_financial_facts
from stock_valuation.data.source_router import sync_best_available_financials
from stock_valuation.data.types import NormalizedFinancialFact
from stock_valuation.database.models import Base, FinancialFactSnapshot


def _facts(provider: str, currency: str = "USD"):
    output = []
    for year in (2024, 2025):
        for statement, metric, value in (
            ("income_statement", "revenue", 1000 + year),
            ("income_statement", "net_income", 100 + year),
            ("balance_sheet", "total_assets", 5000 + year),
            ("balance_sheet", "shareholders_equity", 2500 + year),
            ("cash_flow", "operating_cash_flow", 300 + year),
        ):
            output.append(
                NormalizedFinancialFact(
                    statement=statement,
                    metric=metric,
                    period_end=date(year, 12, 31),
                    period_type="FY",
                    value=Decimal(value),
                    provider_value=Decimal(value),
                    currency=currency,
                    unit="currency",
                    provider=provider,
                    provider_field=f"test:{metric}",
                )
            )
    return output


class FakeSEC:
    def __init__(self, facts):
        self.facts = facts
        self.calls = 0

    def resolve_company(self, ticker: str, name: str | None = None):
        return SimpleNamespace(cik="0000123456", name=name or ticker)

    def get_normalized_financials(self, cik: str):
        self.calls += 1
        assert cik == "0000123456"
        return list(self.facts)


class FakeEdgarTools:
    def __init__(self, facts):
        self.facts = facts
        self.calls = 0

    def get_normalized_financials(self, ticker_or_cik: str):
        self.calls += 1
        assert ticker_or_cik == "EXM"
        return list(self.facts)


class FakeGLEIF:
    def __init__(self):
        self.calls = 0

    def resolve_lei(self, legal_name: str, *, country: str | None = None):
        self.calls += 1
        return SimpleNamespace(lei="52990000000000000000", legal_name=legal_name)


class FakeESEF:
    def __init__(self, facts):
        self.facts = facts
        self.calls = 0

    def get_normalized_financials(self, lei: str, *, filing_limit: int = 8):
        self.calls += 1
        return list(self.facts)


def _analysis(session: Session):
    company = get_or_create_company(
        session,
        name="Example Corp",
        ticker="EXM",
        currency="USD",
        country="US",
    )
    return create_analysis(session, company=company, as_of_date=date(2026, 8, 23))


def test_router_selects_sec_and_does_not_mix_esef() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        sec = FakeSEC(_facts("sec_companyfacts"))
        gleif = FakeGLEIF()
        esef = FakeESEF(_facts("esef_xbrl_json", "EUR"))

        result = sync_best_available_financials(
            session,
            analysis,
            sec_provider=sec,
            gleif_provider=gleif,
            esef_provider=esef,
            allow_alpha_fallback=False,
        )

        assert result.selected_source == "SEC"
        assert result.fact_count == 10
        assert sec.calls == 1
        assert gleif.calls == 0
        assert esef.calls == 0
        assert get_provider_symbol(session, analysis.company, provider="sec", purpose="cik") is not None
        providers = set(
            session.scalars(
                select(FinancialFactSnapshot.provider).where(
                    FinancialFactSnapshot.analysis_id == analysis.id
                )
            ).all()
        )
        assert providers == {"sec_companyfacts"}


def test_router_imports_edgartools_and_uses_existing_sec_as_field_fallback() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        edgar_rows = [
            fact
            for fact in _facts("edgartools")
            if not (fact.metric == "operating_cash_flow" and fact.period_end.year == 2024)
        ]
        edgar = FakeEdgarTools(edgar_rows)
        sec = FakeSEC(_facts("sec_companyfacts"))
        gleif = FakeGLEIF()
        esef = FakeESEF(_facts("esef_xbrl_json", "EUR"))

        result = sync_best_available_financials(
            session,
            analysis,
            edgartools_provider=edgar,
            sec_provider=sec,
            gleif_provider=gleif,
            esef_provider=esef,
            allow_alpha_fallback=False,
        )

        assert result.selected_source == "SEC"
        assert result.fact_count == 19
        assert edgar.calls == 1
        assert sec.calls == 1
        assert gleif.calls == 0
        assert esef.calls == 0

        providers = set(
            session.scalars(
                select(FinancialFactSnapshot.provider).where(
                    FinancialFactSnapshot.analysis_id == analysis.id
                )
            ).all()
        )
        assert providers == {"edgartools", "sec_companyfacts"}

        preferred = {
            (fact.metric, fact.period_end.year): fact
            for fact in load_preferred_financial_facts(session, analysis.id)
        }
        assert preferred[("revenue", 2025)].provider == "edgartools"
        assert preferred[("operating_cash_flow", 2024)].provider == "sec_companyfacts"


def test_router_falls_back_from_insufficient_sec_to_esef() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        sec = FakeSEC([])
        gleif = FakeGLEIF()
        esef = FakeESEF(_facts("esef_xbrl_json", "EUR"))

        result = sync_best_available_financials(
            session,
            analysis,
            sec_provider=sec,
            gleif_provider=gleif,
            esef_provider=esef,
            allow_alpha_fallback=False,
        )

        assert result.selected_source == "ESEF"
        assert result.report_currency == "EUR"
        assert gleif.calls == 1
        assert esef.calls == 1
        lei = get_provider_symbol(session, analysis.company, provider="gleif", purpose="lei")
        assert lei is not None
        assert lei.symbol == "52990000000000000000"
        assert analysis.company.currency == "EUR"


def test_router_returns_clean_failure_when_no_official_source_is_usable() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        sec = FakeSEC([])
        gleif = FakeGLEIF()
        esef = FakeESEF([])

        result = sync_best_available_financials(
            session,
            analysis,
            sec_provider=sec,
            gleif_provider=gleif,
            esef_provider=esef,
            allow_alpha_fallback=False,
        )

        assert result.selected_source is None
        assert result.fact_count == 0
        assert [attempt.source for attempt in result.attempts] == ["SEC", "ESEF"]
