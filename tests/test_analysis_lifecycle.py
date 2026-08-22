from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import (
    AnalysisFrozenError,
    complete_analysis,
    create_analysis,
    create_revision,
    mark_in_progress,
    update_analysis_metadata,
)
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.database.models import AnalysisStatus, Base, QualitativeAssessment


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def make_asml(session: Session):
    return get_or_create_company(
        session,
        name="ASML Holding N.V.",
        ticker="ASML",
        isin="NL0010273215",
        exchange="Euronext Amsterdam",
        country="Netherlands",
        currency="EUR",
        provider_symbol="ASML.AS",
    )


def test_analysis_can_be_created_edited_completed_and_frozen() -> None:
    with make_session() as session:
        company = make_asml(session)
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 22))
        assert analysis.status == AnalysisStatus.DRAFT
        assert analysis.revision_number == 1

        update_analysis_metadata(
            session,
            analysis,
            title="ASML Basisanalyse",
            notes="Erste These",
            market_price=Decimal("850.00"),
            market_price_currency="EUR",
        )
        mark_in_progress(session, analysis)
        assert analysis.status == AnalysisStatus.IN_PROGRESS

        complete_analysis(session, analysis)
        assert analysis.status == AnalysisStatus.COMPLETED
        assert analysis.completed_at is not None

        with pytest.raises(AnalysisFrozenError):
            update_analysis_metadata(
                session,
                analysis,
                title="Darf nicht geändert werden",
                notes="",
                market_price=900,
            )


def test_new_revision_links_to_completed_snapshot_and_does_not_copy_market_data() -> None:
    with make_session() as session:
        company = make_asml(session)
        old = create_analysis(session, company=company, as_of_date=date(2026, 8, 22))
        update_analysis_metadata(
            session,
            old,
            title="ASML",
            notes="These bleibt als Ausgangspunkt erhalten.",
            market_price=850,
        )
        session.add(
            QualitativeAssessment(
                analysis_id=old.id,
                criterion_id="market_position",
                rating_key="very_strong",
                comment="Dominante Marktstellung.",
            )
        )
        session.commit()
        complete_analysis(session, old)

        new = create_revision(
            session,
            source=old,
            as_of_date=date(2027, 2, 15),
            copy_qualitative=True,
        )

        assert new.revision_number == 2
        assert new.previous_analysis_id == old.id
        assert new.status == AnalysisStatus.DRAFT
        assert new.market_price is None
        assert new.notes == old.notes

        copied = session.query(QualitativeAssessment).filter_by(analysis_id=new.id).one()
        assert copied.criterion_id == "market_position"
        assert copied.rating_key == "very_strong"
