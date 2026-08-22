from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.companies.provider_symbols import get_provider_symbol, upsert_provider_symbol
from stock_valuation.companies.service import alpha_vantage_company_candidates, get_or_create_company
from stock_valuation.database.models import Base


def test_alpha_vantage_search_rows_become_generic_candidates() -> None:
    candidates = alpha_vantage_company_candidates(
        [
            {
                "1. symbol": "MSFT",
                "2. name": "Microsoft Corporation",
                "4. region": "United States",
                "8. currency": "USD",
            }
        ]
    )
    assert len(candidates) == 1
    assert candidates[0].ticker == "MSFT"
    assert candidates[0].provider == "alphavantage"
    assert candidates[0].provider_symbol == "MSFT"
    assert candidates[0].currency == "USD"


def test_provider_symbol_is_persisted_and_updated_per_company() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(
            session,
            name="Microsoft Corporation",
            ticker="MSFT",
            currency="USD",
        )
        first = upsert_provider_symbol(
            session,
            company,
            provider="alphavantage",
            purpose="fundamentals",
            symbol="MSFT",
        )
        assert first.symbol == "MSFT"

        second = upsert_provider_symbol(
            session,
            company,
            provider="alphavantage",
            purpose="fundamentals",
            symbol="MSFT_ALT",
        )
        assert second.id == first.id

        stored = get_provider_symbol(
            session,
            company,
            provider="alphavantage",
            purpose="fundamentals",
        )
        assert stored is not None
        assert stored.symbol == "MSFT_ALT"
