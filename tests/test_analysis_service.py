from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis, get_or_create_company
from stock_valuation.database.models import Base


def test_analysis_revisions_increment() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(
            session,
            name="ASML Holding N.V.",
            ticker="ASML",
            isin="NL0010273215",
            currency="EUR",
            provider_symbol="ASML.AS",
        )
        first = create_analysis(session, company=company, as_of_date=date(2026, 8, 22))
        second = create_analysis(
            session,
            company=company,
            as_of_date=date(2027, 2, 15),
            previous_analysis=first,
        )

        assert first.revision_number == 1
        assert second.revision_number == 2
        assert second.previous_analysis_id == first.id
