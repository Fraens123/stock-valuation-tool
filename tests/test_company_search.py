from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.companies.service import get_or_create_from_candidate, search_company_candidates
from stock_valuation.database.models import Base


def test_asml_reference_company_is_searchable_by_ticker_and_isin() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        by_ticker = search_company_candidates(session, "ASML")
        assert by_ticker
        assert by_ticker[0].isin == "NL0010273215"
        assert by_ticker[0].provider_symbol == "ASML.AS"

        company = get_or_create_from_candidate(session, by_ticker[0])
        by_isin = search_company_candidates(session, "NL0010273215")
        assert any(candidate.ticker == company.ticker for candidate in by_isin)
