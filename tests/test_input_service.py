from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.input_service import (
    store_risk_free_rate,
    upsert_guidance,
    upsert_manual_input,
)
from stock_valuation.analyses.service import AnalysisFrozenError, complete_analysis, create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.providers.ecb import FULL_SERIES_KEY, RiskFreeRateObservation
from stock_valuation.database.models import Base


def _analysis(session: Session):
    company = get_or_create_company(
        session,
        name="ASML Holding N.V.",
        ticker="ASML",
        isin="NL0010273215",
        currency="EUR",
        provider_symbol="ASML.AS",
    )
    return create_analysis(session, company=company, as_of_date=date(2026, 8, 22))


def test_manual_input_upserts_same_source_metric_period() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        row = upsert_manual_input(
            session,
            analysis,
            metric="eps_estimate",
            period="FY2027",
            value="30.5",
            source_name="Aktienfinder",
            unit="currency_per_share",
            currency="EUR",
        )
        same = upsert_manual_input(
            session,
            analysis,
            metric="eps_estimate",
            period="FY2027",
            value="31.2",
            source_name="Aktienfinder",
            unit="currency_per_share",
            currency="EUR",
        )
        assert same.id == row.id
        assert same.value == Decimal("31.2")


def test_guidance_keeps_low_point_high_separate() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        row = upsert_guidance(
            session,
            analysis,
            metric="revenue",
            period="FY2026",
            low="34",
            point_estimate=None,
            high="39",
            currency="EUR",
            unit="EUR_bn",
        )
        assert row.low == Decimal("34")
        assert row.point_estimate is None
        assert row.high == Decimal("39")


def test_ecb_rate_stores_decimal_and_original_percent() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        obs = RiskFreeRateObservation(
            series_key=FULL_SERIES_KEY,
            observation_date=date(2026, 8, 20),
            percent_per_annum=Decimal("3.125"),
            rate_decimal=Decimal("0.03125"),
            retrieved_at=datetime.now(timezone.utc),
        )
        row = store_risk_free_rate(session, analysis, obs)
        assert row.value == Decimal("0.03125")
        assert row.provider_value == Decimal("3.125")
        assert row.provider == "ecb"


def test_manual_data_cannot_modify_completed_snapshot() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        complete_analysis(session, analysis)
        with pytest.raises(AnalysisFrozenError):
            upsert_manual_input(
                session,
                analysis,
                metric="eps_estimate",
                period="FY2027",
                value="31.2",
            )
