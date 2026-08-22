from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.comparison import compare_analyses
from stock_valuation.analyses.service import complete_analysis, create_analysis, create_revision, update_analysis_metadata
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.database.models import Base, EstimateSnapshot, QualitativeAssessment, ValuationResult


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def test_comparison_groups_market_estimate_qualitative_and_valuation_changes() -> None:
    with make_session() as session:
        company = get_or_create_company(
            session,
            name="ASML Holding N.V.",
            ticker="ASML",
            currency="EUR",
            provider_symbol="ASML.AS",
        )
        old = create_analysis(session, company=company, as_of_date=date(2026, 8, 22))
        update_analysis_metadata(session, old, title=None, notes="These A", market_price=800)
        session.add_all(
            [
                EstimateSnapshot(
                    analysis_id=old.id,
                    metric="revenue",
                    period="FY2027",
                    low=Decimal("36000"),
                    average=Decimal("38000"),
                    high=Decimal("40000"),
                    analyst_count=20,
                    provider="test",
                ),
                QualitativeAssessment(
                    analysis_id=old.id,
                    criterion_id="china_risk",
                    rating_key="medium",
                    comment="Beobachten",
                ),
                ValuationResult(
                    analysis_id=old.id,
                    method="dcf",
                    scenario="base",
                    metric="fair_value_per_share",
                    value=Decimal("900"),
                    currency="EUR",
                ),
            ]
        )
        session.commit()
        complete_analysis(session, old)

        new = create_revision(session, source=old, as_of_date=date(2027, 2, 15), copy_qualitative=False)
        update_analysis_metadata(session, new, title=None, notes="These B", market_price=850)
        session.add_all(
            [
                EstimateSnapshot(
                    analysis_id=new.id,
                    metric="revenue",
                    period="FY2027",
                    low=Decimal("37000"),
                    average=Decimal("39500"),
                    high=Decimal("42000"),
                    analyst_count=24,
                    provider="test",
                ),
                QualitativeAssessment(
                    analysis_id=new.id,
                    criterion_id="china_risk",
                    rating_key="high",
                    comment="Risiko gestiegen",
                ),
                ValuationResult(
                    analysis_id=new.id,
                    method="dcf",
                    scenario="base",
                    metric="fair_value_per_share",
                    value=Decimal("940"),
                    currency="EUR",
                ),
            ]
        )
        session.commit()

        changes = compare_analyses(session, old, new)
        categories = {change.category for change in changes}
        assert "Analyse" in categories
        assert "Prognosen" in categories
        assert "Eigene Einschätzung" in categories
        assert "Bewertung" in categories
        assert any(change.key == "market_price" for change in changes)
        assert any("fair_value_per_share" in change.key for change in changes)
