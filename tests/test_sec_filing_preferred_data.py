from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.preferred_data import load_preferred_data_states
from stock_valuation.data.resolution import load_preferred_financial_facts
from stock_valuation.database.models import Base, FinancialFactSnapshot


def _add(
    session: Session,
    analysis_id: int,
    metric: str,
    provider: str,
    value: str,
    *,
    provider_field: str,
) -> None:
    session.add(
        FinancialFactSnapshot(
            analysis_id=analysis_id,
            statement="balance_sheet" if metric == "short_term_debt" else "cash_flow",
            metric=metric,
            period_end=date(2025, 12, 31),
            period_type="FY",
            value=Decimal(value),
            provider_value=Decimal(value),
            currency="EUR",
            unit="currency",
            provider=provider,
            provider_field=provider_field,
            source_type="primary_source",
            is_cross_check_only=False,
        )
    )


def test_original_filing_supplement_is_primary_but_debt_keeps_semantic_gate() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(
            session,
            name="Example Corp",
            ticker="EXM",
            currency="EUR",
        )
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        _add(
            session,
            analysis.id,
            "operating_cash_flow",
            "sec_filing_xbrl",
            "100",
            provider_field="us-gaap:NetCashProvidedByUsedInOperatingActivities",
        )
        _add(
            session,
            analysis.id,
            "short_term_debt",
            "sec_filing_xbrl",
            "25",
            provider_field="us-gaap:LongTermDebtCurrent",
        )
        session.commit()

        states = {
            state.fact.metric: state
            for state in load_preferred_data_states(session, analysis.id)
        }

        assert states["operating_cash_flow"].quality_status == "primary_source"
        assert states["operating_cash_flow"].calculation_ready is True
        assert states["short_term_debt"].quality_status == "primary_semantic_review_required"
        assert states["short_term_debt"].calculation_ready is False


def test_safe_short_term_debt_and_ppe_standard_mappings_are_calculation_ready() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(
            session,
            name="Example Corp",
            ticker="EXM",
            currency="EUR",
        )
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        _add(
            session,
            analysis.id,
            "short_term_debt",
            "sec_companyfacts",
            "25",
            provider_field="us-gaap:DebtCurrent",
        )
        _add(
            session,
            analysis.id,
            "ppe_net",
            "sec_companyfacts",
            "100",
            provider_field="us-gaap:PropertyPlantAndEquipmentNet",
        )
        session.commit()

        states = {
            state.fact.metric: state
            for state in load_preferred_data_states(session, analysis.id)
        }

        assert states["short_term_debt"].quality_status == "safe_standard_mapping"
        assert states["short_term_debt"].calculation_ready is True
        assert states["ppe_net"].quality_status == "safe_standard_mapping"
        assert states["ppe_net"].calculation_ready is True


def test_companyfacts_wins_when_same_period_also_exists_in_filing_supplement() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(
            session,
            name="Example Corp",
            ticker="EXM",
            currency="EUR",
        )
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        _add(
            session,
            analysis.id,
            "operating_cash_flow",
            "sec_filing_xbrl",
            "99",
            provider_field="us-gaap:NetCashProvidedByUsedInOperatingActivities",
        )
        _add(
            session,
            analysis.id,
            "operating_cash_flow",
            "sec_companyfacts",
            "100",
            provider_field="us-gaap:NetCashProvidedByUsedInOperatingActivities",
        )
        session.commit()

        preferred = load_preferred_financial_facts(session, analysis.id)
        fact = next(row for row in preferred if row.metric == "operating_cash_flow")

        assert fact.provider == "sec_companyfacts"
        assert fact.value == Decimal("100")
