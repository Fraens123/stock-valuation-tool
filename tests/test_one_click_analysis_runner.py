from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.analyses.input_service import upsert_manual_financial_override
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.source_router import FinancialSourceResult
from stock_valuation.database.models import Analysis, Base, EstimateSnapshot, FinancialFactSnapshot
from stock_valuation.workflow import analysis_runner
from stock_valuation.workflow.analysis_runner import run_complete_analysis
from stock_valuation.workflow.models import AnalysisState, StageState
from stock_valuation.workflow.review_tasks import build_review_tasks


@dataclass(frozen=True)
class _HistoryCompletion:
    candidate_count: int = 0
    filings_checked: int = 0


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def _company(session):
    return get_or_create_company(session, name="One Click Co", ticker="OCC", currency="USD")


def _analysis(session, *, as_of_date: date = date(2025, 12, 31)):
    return Analysis(company_id=_company(session).id, as_of_date=as_of_date)


def _add_forward_estimate(session, analysis) -> None:
    session.add(
        EstimateSnapshot(
            analysis_id=analysis.id,
            metric="net_income",
            period=f"{analysis.as_of_date.year + 1}-12-31",
            average=Decimal("100"),
            currency="USD",
            unit="currency",
            provider="test",
        )
    )
    session.commit()


def _state(analysis, *, valuation_status: str = "READY", financial_payload: dict | None = None):
    stages = {
        "FINANCIAL_DATA": StageState("FINANCIAL_DATA", "READY", payload=financial_payload or {"review_required": ()}),
        "CALCULATION": StageState("CALCULATION", "READY", payload={"base_facts": {"2023": [], "2024": [], "2025": []}}),
        "HISTORICAL_ANALYSIS": StageState("HISTORICAL_ANALYSIS", "READY", payload={"history_years": [2023, 2024, 2025]}),
        "BUSINESS_QUALITY": StageState("BUSINESS_QUALITY", "READY", payload={"result": {"overall_score": "8"}}),
        "MARKET_DATA": StageState("MARKET_DATA", "READY", payload={"availability": {"enterprise_value": "EV_READY"}}),
        "ASSUMPTIONS": StageState("ASSUMPTIONS", "READY", payload={"recommendations": {}}),
        "VALUATION": StageState("VALUATION", valuation_status, payload={"mode": "FINAL"}),
    }
    return AnalysisState(
        analysis_id=analysis.id,
        company_name=analysis.company.name,
        ticker=analysis.company.ticker,
        as_of_date=analysis.as_of_date.isoformat(),
        revision_number=analysis.revision_number,
        analysis_status=analysis.status.value,
        stages=stages,
        history_years=(2023, 2024, 2025),
        market_snapshot_id="market-id",
    )


def _fact(analysis, metric: str, year: int, value: str | None, provider_field: str):
    decimal_value = Decimal(value) if value is not None else None
    return FinancialFactSnapshot(
        analysis_id=analysis.id,
        statement="balance_sheet",
        metric=metric,
        period_end=date(year, 12, 31),
        period_type="FY",
        value=decimal_value,
        provider_value=decimal_value,
        currency="USD",
        unit="currency",
        provider="sec_companyfacts",
        provider_field=provider_field,
        source_type="primary_source",
        source_url="https://www.sec.gov/example",
    )


def test_one_click_runner_creates_analysis_refreshes_stages_and_market(monkeypatch) -> None:
    with _session() as session:
        company = _company(session)
        analysis_seed = Analysis(company_id=company.id, as_of_date=date(2024, 12, 31))
        session.add(analysis_seed)
        session.commit()
        _add_forward_estimate(session, analysis_seed)
        calls = {"financial": 0, "market": 0}

        def financial_sync(session, analysis):
            calls["financial"] += 1
            return FinancialSourceResult("test", 12, ())

        def market_refresh(session, analysis):
            calls["market"] += 1
            return "market-id"

        def fake_state(session, analysis):
            return _state(analysis)

        monkeypatch.setattr(analysis_runner, "sync_sec_history_text_candidates", lambda session, analysis: _HistoryCompletion())
        monkeypatch.setattr(analysis_runner, "refresh_local_analysis_stages", fake_state)
        monkeypatch.setattr(analysis_runner, "build_book_valuation_for_analysis", lambda session, analysis, state: None)

        result = run_complete_analysis(
            session,
            company_id=company.id,
            as_of_date=date(2024, 12, 31),
            financial_sync=financial_sync,
            market_refresh=market_refresh,
        )

        assert result.analysis_id is not None
        assert result.market_snapshot_id == "market-id"
        assert calls == {"financial": 1, "market": 1}
        assert result.ready_for_review is True


def test_one_click_runner_marks_fully_available_analysis_ready_for_final(monkeypatch) -> None:
    with _session() as session:
        company = _company(session)
        analysis_seed = Analysis(company_id=company.id, as_of_date=date(2024, 12, 31))
        session.add(analysis_seed)
        session.commit()
        _add_forward_estimate(session, analysis_seed)
        monkeypatch.setattr(analysis_runner, "sync_sec_history_text_candidates", lambda session, analysis: _HistoryCompletion())
        monkeypatch.setattr(analysis_runner, "refresh_local_analysis_stages", lambda session, analysis: _state(analysis))
        monkeypatch.setattr(analysis_runner, "build_book_valuation_for_analysis", lambda session, analysis, state: None)

        result = run_complete_analysis(
            session,
            company_id=company.id,
            as_of_date=date(2024, 12, 31),
            financial_sync=lambda session, analysis: FinancialSourceResult("test", 12, ()),
            market_refresh=lambda session, analysis: "market-id",
        )

        assert result.review_tasks == ()
        assert result.ready_for_final is True
        assert result.status == "Analyse abgeschlossen"


def test_review_tasks_are_business_readable_and_not_technical_blockers() -> None:
    with _session() as session:
        analysis = _analysis(session)
        session.add(analysis)
        session.commit()
        session.add(_fact(analysis, "short_term_debt", 2025, "1681900000", "aggregation:us-gaap:LongTermDebtCurrent"))
        session.add(_fact(analysis, "intangible_purchases", 2025, None, "not_separately_reported"))
        session.commit()
        state = _state(
            analysis,
            valuation_status="READY_FOR_PREVIEW",
            financial_payload={"review_required": ("2025 short_term_debt: primary_semantic_review_required",)},
        )

        tasks = build_review_tasks(session, analysis, state)

        titles = [task.title_de for task in tasks]
        assert titles == [
            "Kurzfristige Finanzschulden 2025",
            "Kaeufe immaterieller Vermoegenswerte 2025",
            "Jahresueberschuss 2026e ergaenzen",
        ]
        assert all("FINANCIAL_DATA" not in task.description_de for task in tasks)
        assert all("primary_semantic_review_required" not in task.description_de for task in tasks)


def test_review_done_removes_short_term_debt_task() -> None:
    with _session() as session:
        analysis = _analysis(session)
        session.add(analysis)
        session.commit()
        upsert_manual_financial_override(
            session,
            analysis,
            metric="short_term_debt",
            period_end=date(2025, 12, 31),
            value=Decimal("50"),
            currency="USD",
            unit="currency",
            statement="balance_sheet",
            source_name="Geschaeftsbericht",
        )
        _add_forward_estimate(session, analysis)
        state = _state(analysis, financial_payload={"review_required": ()})

        tasks = build_review_tasks(session, analysis, state)

        assert all(task.metric != "short_term_debt" for task in tasks)
