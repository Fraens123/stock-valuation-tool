from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis, get_or_create_company
from stock_valuation.book_valuation.models import BOOK_VALUATION_VERSION
from stock_valuation.book_valuation.persistence import load_book_assumptions, upsert_book_assumption
from stock_valuation.database.models import Base


def test_book_manual_inputs_survive_db_reopen() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        company = get_or_create_company(session, name="Example", ticker="EXM", currency="EUR")
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        upsert_book_assumption(
            session,
            analysis,
            key="rivalry_existing_competitors",
            value=Decimal("4"),
            note="Starke Marktposition begründet.",
            unit="points",
        )
        analysis_id = analysis.id
        company_id = company.id

    with Session(engine) as session:
        from stock_valuation.database.models import Analysis, Company

        company = session.get(Company, company_id)
        analysis = session.get(Analysis, analysis_id)
        rows = load_book_assumptions(session, analysis)
        assert rows["rivalry_existing_competitors"].value == Decimal("4.00000000")
        assert rows["rivalry_existing_competitors"].note == "Starke Marktposition begründet."
        assert rows["rivalry_existing_competitors"].source_type == BOOK_VALUATION_VERSION
