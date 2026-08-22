from stock_valuation.companies.selection import (
    choose_recommended_listing,
    group_company_candidates,
    resolve_fundamentals_symbol,
)
from stock_valuation.companies.service import CompanyCandidate


class FakeProvider:
    def __init__(self, valid_symbol: str):
        self.valid_symbol = valid_symbol
        self.calls: list[str] = []

    def probe_income_statement(self, symbol: str) -> dict[str, object]:
        self.calls.append(symbol)
        if symbol == self.valid_symbol:
            return {
                "annual_report_count": 20,
                "reported_currency": "EUR",
                "latest_fiscal_date": "2025-12-31",
            }
        return {
            "annual_report_count": 0,
            "reported_currency": None,
            "latest_fiscal_date": None,
        }


def _candidate(name: str, ticker: str, exchange: str, currency: str) -> CompanyCandidate:
    return CompanyCandidate(
        name=name,
        ticker=ticker,
        isin=None,
        exchange=exchange,
        country=exchange,
        currency=currency,
        provider_symbol=ticker,
        provider="alphavantage",
    )


def _asml_candidates() -> list[CompanyCandidate]:
    return [
        _candidate("ASML Holding NV", "ASML", "United States", "USD"),
        _candidate("ASML Holding NV", "ASMLF", "United States", "USD"),
        _candidate("ASML Holding N.V.", "ASML.AMS", "Amsterdam", "EUR"),
        _candidate("ASML CDR (CAD Hedged)", "ASML.TRT", "Toronto", "CAD"),
        _candidate("ASML Holding NV", "ASME.FRK", "Frankfurt", "EUR"),
        _candidate("ASML Holding NV", "ASME.DEX", "XETRA", "EUR"),
    ]


def test_asml_listings_are_grouped_as_one_issuer_despite_punctuation() -> None:
    groups = group_company_candidates(_asml_candidates())
    asml_groups = [group for group in groups if group.key == "asml holding nv"]

    assert len(asml_groups) == 1
    assert len(asml_groups[0].candidates) == 5
    assert asml_groups[0].name == "ASML Holding N.V."


def test_fundamentals_resolver_prefers_plain_symbol_and_verifies_it() -> None:
    group = [group for group in group_company_candidates(_asml_candidates()) if group.key == "asml holding nv"][0]
    provider = FakeProvider(valid_symbol="ASML")

    resolution = resolve_fundamentals_symbol(provider, group.candidates, max_attempts=3)

    assert resolution.symbol == "ASML"
    assert resolution.reported_currency == "EUR"
    assert resolution.annual_report_count == 20
    assert provider.calls == ["ASML"]


def test_listing_resolution_uses_report_currency_and_prefers_amsterdam_for_asml() -> None:
    group = [group for group in group_company_candidates(_asml_candidates()) if group.key == "asml holding nv"][0]

    listing = choose_recommended_listing(group.candidates, reported_currency="EUR")

    assert listing.ticker == "ASML.AMS"
    assert listing.exchange == "Amsterdam"
    assert listing.currency == "EUR"
