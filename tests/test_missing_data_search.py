from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from stock_valuation.analyses.input_service import (
    remove_manual_financial_override,
    upsert_manual_financial_override,
)
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.missing_data_search import (
    MissingDataSearchStatus,
    search_missing_metric_candidates,
)
from stock_valuation.data.preferred_data import load_preferred_data_states
from stock_valuation.database.models import Analysis, Base, FinancialFactSnapshot
from stock_valuation.workflow.service import refresh_local_analysis_stages


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def _analysis(session: Session) -> Analysis:
    company = get_or_create_company(
        session,
        name="Example Inc.",
        ticker="EXM",
        currency="USD",
        exchange="NASDAQ",
    )
    analysis = Analysis(company_id=company.id, as_of_date=date(2025, 12, 31))
    session.add(analysis)
    session.commit()
    return analysis


def _fact(
    analysis: Analysis,
    metric: str,
    year: int,
    value: str | None,
    provider_field: str,
    *,
    statement: str = "balance_sheet",
    provider: str = "sec_companyfacts",
) -> FinancialFactSnapshot:
    decimal_value = Decimal(value) if value is not None else None
    return FinancialFactSnapshot(
        analysis_id=analysis.id,
        statement=statement,
        metric=metric,
        period_end=date(year, 12, 31),
        period_type="FY",
        value=decimal_value,
        provider_value=decimal_value,
        currency="USD",
        unit="currency",
        provider=provider,
        provider_field=provider_field,
        source_type="primary_source",
        source_url="https://www.sec.gov/example",
    )


def test_search_classifies_safe_exact_candidate() -> None:
    engine = _engine()
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        session.add(_fact(analysis, "short_term_debt", 2025, "100", "us-gaap:DebtCurrent"))
        session.commit()

        result = search_missing_metric_candidates(
            session,
            analysis,
            metric="short_term_debt",
            fiscal_year=2025,
        )

        assert result.status == MissingDataSearchStatus.FOUND_SAFE
        assert result.candidates[0].semantic_status == "SAFE_STANDARD_MAPPING"
        assert result.candidates[0].input_refs


def test_search_classifies_semantic_uncertain_candidate() -> None:
    engine = _engine()
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        session.add(_fact(analysis, "short_term_debt", 2025, "100", "us-gaap:LongTermDebtCurrent"))
        session.commit()

        result = search_missing_metric_candidates(
            session,
            analysis,
            metric="short_term_debt",
            fiscal_year=2025,
        )

        assert result.status == MissingDataSearchStatus.FOUND_REVIEW_REQUIRED
        assert result.candidates[0].semantic_status == "REVIEW_REQUIRED"


def test_search_classifies_multiple_candidates_and_not_found() -> None:
    engine = _engine()
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        session.add(_fact(analysis, "ppe_net", 2025, "100", "us-gaap:PropertyPlantAndEquipmentNet"))
        session.add(_fact(analysis, "ppe_net", 2025, "99", "ifrs-full:PropertyPlantAndEquipment"))
        session.commit()

        multiple = search_missing_metric_candidates(session, analysis, metric="ppe_net", fiscal_year=2025)
        missing = search_missing_metric_candidates(session, analysis, metric="ppe_net", fiscal_year=2024)

        assert multiple.status == MissingDataSearchStatus.MULTIPLE_CANDIDATES
        assert missing.status == MissingDataSearchStatus.NOT_FOUND


def test_search_classifies_not_separately_reported_evidence() -> None:
    engine = _engine()
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        session.add(_fact(analysis, "intangible_purchases", 2025, None, "not_separately_reported"))
        session.commit()

        result = search_missing_metric_candidates(
            session,
            analysis,
            metric="intangible_purchases",
            fiscal_year=2025,
        )

        assert result.status == MissingDataSearchStatus.NOT_SEPARATELY_REPORTED


def test_d_and_a_complete_aggregate_and_incomplete_component() -> None:
    engine = _engine()
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        session.add(
            _fact(
                analysis,
                "depreciation_amortization",
                2025,
                "70",
                "us-gaap:Depreciation",
                statement="cash_flow",
            )
        )
        session.add(
            _fact(
                analysis,
                "depreciation_amortization",
                2025,
                "30",
                "us-gaap:AmortizationOfIntangibleAssets",
                statement="cash_flow",
            )
        )
        session.add(
            _fact(
                analysis,
                "depreciation_amortization",
                2024,
                "70",
                "us-gaap:Depreciation",
                statement="cash_flow",
            )
        )
        session.commit()

        complete = search_missing_metric_candidates(
            session,
            analysis,
            metric="depreciation_amortization",
            fiscal_year=2025,
        )
        incomplete = search_missing_metric_candidates(
            session,
            analysis,
            metric="depreciation_amortization",
            fiscal_year=2024,
        )

        assert any(candidate.candidate_type == "DERIVED" and candidate.value == Decimal("100.00000000") for candidate in complete.candidates)
        assert complete.status == MissingDataSearchStatus.FOUND_SAFE
        assert incomplete.status == MissingDataSearchStatus.FOUND_REVIEW_REQUIRED
        assert any("Nur eine D&A-Komponente" in candidate.semantic_reason for candidate in incomplete.candidates)


def test_no_dangerous_short_term_debt_derivation_from_current_liabilities_minus_payables() -> None:
    engine = _engine()
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        session.add(_fact(analysis, "short_term_debt", 2025, "500", "us-gaap:LiabilitiesCurrent"))
        session.add(_fact(analysis, "accounts_payable", 2025, "200", "us-gaap:AccountsPayableCurrent"))
        session.commit()

        result = search_missing_metric_candidates(
            session,
            analysis,
            metric="short_term_debt",
            fiscal_year=2025,
        )

        assert result.status == MissingDataSearchStatus.NOT_FOUND
        assert result.candidates == ()


def test_manual_override_persists_original_and_reopen_restores_after_remove() -> None:
    engine = _engine()
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        session.add(_fact(analysis, "short_term_debt", 2025, "100", "us-gaap:DebtCurrent"))
        session.commit()
        upsert_manual_financial_override(
            session,
            analysis,
            metric="short_term_debt",
            period_end=date(2025, 12, 31),
            value=Decimal("125"),
            currency="USD",
            unit="currency",
            statement="balance_sheet",
            source_name="Aktienfinder",
            note="Manual test",
        )

    with Session(engine, expire_on_commit=False) as reopened:
        analysis = reopened.scalar(select(Analysis))
        assert analysis is not None
        preferred = load_preferred_data_states(reopened, analysis.id, metrics=["short_term_debt"])
        assert preferred[0].fact.provider == "manual_override"
        assert preferred[0].fact.value == Decimal("125.00000000")
        originals = reopened.scalars(
            select(FinancialFactSnapshot).where(FinancialFactSnapshot.provider == "sec_companyfacts")
        ).all()
        assert len(originals) == 1
        assert originals[0].value == Decimal("100.00000000")
        remove_manual_financial_override(
            reopened,
            analysis,
            metric="short_term_debt",
            period_end=date(2025, 12, 31),
        )
        preferred_after = load_preferred_data_states(reopened, analysis.id, metrics=["short_term_debt"])
        assert preferred_after[0].fact.provider == "sec_companyfacts"


def test_short_term_debt_override_makes_net_debt_available_after_recalculation() -> None:
    engine = _engine()
    with Session(engine, expire_on_commit=False) as session:
        analysis = _analysis(session)
        for year in (2024, 2025):
            for metric, value in {
                "cash_and_equivalents": "20",
                "long_term_debt": "200",
                "total_assets": "1000",
                "shareholders_equity": "600",
                "revenue": "500",
                "gross_profit": "300",
                "operating_income": "100",
                "net_income": "80",
                "current_assets": "400",
                "current_liabilities": "150",
                "accounts_receivable": "50",
                "accounts_payable": "40",
                "operating_cash_flow": "120",
                "capital_expenditures": "30",
                "depreciation_amortization": "25",
            }.items():
                statement = "income_statement" if metric in {"revenue", "gross_profit", "operating_income", "net_income"} else "balance_sheet"
                if metric in {"operating_cash_flow", "capital_expenditures", "depreciation_amortization"}:
                    statement = "cash_flow"
                session.add(_fact(analysis, metric, year, value, f"us-gaap:{metric}", statement=statement))
        session.commit()
        state_before = refresh_local_analysis_stages(session, analysis)
        results_before = state_before.stages["CALCULATION"].payload.get("results", [])
        assert next(item for item in results_before if item["metric_id"] == "net_debt")["status"] != "AVAILABLE"

        upsert_manual_financial_override(
            session,
            analysis,
            metric="short_term_debt",
            period_end=date(2025, 12, 31),
            value=Decimal("50"),
            currency="USD",
            unit="currency",
            statement="balance_sheet",
            source_name="Aktienfinder",
        )
        state_after = refresh_local_analysis_stages(session, analysis)
        results_after = state_after.stages["CALCULATION"].payload.get("results", [])

        net_debt = next(
            item
            for item in results_after
            if item["metric_id"] == "net_debt" and item["fiscal_year"] == 2025
        )
        assert net_debt["status"] == "AVAILABLE"
        assert Decimal(str(net_debt["value"])) == Decimal("230.00000000")
