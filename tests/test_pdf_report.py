from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis, update_analysis_metadata
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.database.models import Base
from stock_valuation.reports.pdf import build_snapshot_report, snapshot_report_filename


def test_snapshot_report_is_pdf_and_has_stable_filename() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(
            session,
            name="ASML Holding N.V.",
            ticker="ASML",
            isin="NL0010273215",
            exchange="Euronext Amsterdam",
            currency="EUR",
        )
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 22))
        update_analysis_metadata(
            session,
            analysis,
            title="ASML Analyse",
            notes="Snapshot report test",
            market_price=850,
        )

        pdf = build_snapshot_report(session, analysis)
        assert pdf.startswith(b"%PDF")
        assert snapshot_report_filename(analysis) == "ASML_2026-08-22_R1_Analyse.pdf"
