from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.data.resolution import load_preferred_financial_facts
from stock_valuation.database.models import Base, FinancialFactSnapshot


def _fact(provider: str, value: str, metric: str = "inventory") -> FinancialFactSnapshot:
    return FinancialFactSnapshot(
        analysis_id=1,
        statement="balance_sheet",
        metric=metric,
        period_end=date(2025, 12, 31),
        period_type="FY",
        value=Decimal(value),
        provider_value=Decimal(value),
        currency="EUR",
        unit="currency",
        provider=provider,
        provider_field=provider,
    )


def test_primary_source_wins_without_deleting_fallback() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all([_fact("alphavantage", "11700"), _fact("asml_primary", "11429")])
        session.commit()

        selected = load_preferred_financial_facts(session, 1, metrics=["inventory"])

        assert len(selected) == 1
        assert selected[0].provider == "asml_primary"
        assert selected[0].value == Decimal("11429")
        assert session.query(FinancialFactSnapshot).count() == 2


def test_fallback_is_used_when_no_primary_source_exists() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(_fact("alphavantage", "100", metric="revenue"))
        session.commit()

        selected = load_preferred_financial_facts(session, 1, metrics=["revenue"])

        assert len(selected) == 1
        assert selected[0].provider == "alphavantage"
        assert selected[0].value == Decimal("100")
