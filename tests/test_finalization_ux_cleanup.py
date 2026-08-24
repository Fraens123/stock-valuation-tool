from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from stock_valuation.book_valuation.models import unavailable
from stock_valuation.workflow.models import AnalysisState, StageState
from stock_valuation.workflow.service import finalization_issues


def _stage(stage: str, status: str, payload: dict | None = None, blockers: tuple[str, ...] = ()) -> StageState:
    return StageState(stage=stage, status=status, payload=payload or {}, blockers=blockers)


def _state(financial_payload: dict, *, years: tuple[int, ...] = (2021, 2022, 2023, 2024, 2025)) -> AnalysisState:
    return AnalysisState(
        analysis_id=1,
        company_name="ASML",
        ticker="ASML",
        as_of_date="2026-08-23",
        revision_number=1,
        analysis_status="DRAFT",
        history_years=years,
        stages={
            "FINANCIAL_DATA": _stage("FINANCIAL_DATA", "REVIEW_REQUIRED", financial_payload),
            "CALCULATION": _stage("CALCULATION", "READY"),
            "HISTORICAL_ANALYSIS": _stage("HISTORICAL_ANALYSIS", "READY"),
            "BUSINESS_QUALITY": _stage("BUSINESS_QUALITY", "READY"),
            "MARKET_DATA": _stage("MARKET_DATA", "READY"),
            "ASSUMPTIONS": _stage("ASSUMPTIONS", "READY"),
            "VALUATION": _stage("VALUATION", "READY"),
        },
    )


def test_old_historical_reviews_are_warnings_not_hard_blockers() -> None:
    state = _state({"review_required": ("2012 short_term_debt: primary_semantic_review_required",)})

    issues = finalization_issues(state)

    assert not [issue for issue in issues if issue.blocking]
    warning = next(issue for issue in issues if issue.category == "HISTORISCHE_WARNUNG")
    assert warning.metric == "short_term_debt"
    assert "ältere Geschäftsjahre" in warning.message_de


def test_current_used_review_value_is_hard_blocker_with_german_message() -> None:
    state = _state({"review_required": ("2025 short_term_debt: primary_semantic_review_required",)})

    issues = finalization_issues(state)
    blockers = [issue for issue in issues if issue.blocking]

    assert len(blockers) == 1
    assert blockers[0].metric == "short_term_debt"
    assert blockers[0].fiscal_year == 2025
    assert blockers[0].message_de == "Kurzfristige Finanzschulden 2025 müssen noch bestätigt werden. Relevant für Nettoverschuldung und Enterprise Value."


def test_owner_earnings_current_depreciation_review_is_hard_blocker() -> None:
    state = _state({"review_required": ("2025 depreciation_amortization: primary_semantic_review_required",)})

    blocker = next(issue for issue in finalization_issues(state) if issue.blocking)

    assert blocker.metric == "depreciation_amortization"
    assert blocker.message_de == "Abschreibungen 2025 müssen noch bestätigt werden. Relevant für EBITDA und Owner Earnings."


def test_missing_current_owner_earnings_input_is_dcf_blocker() -> None:
    state = _state({"review_required": ()})
    book = SimpleNamespace(
        values={
            "owner_earnings": unavailable("owner_earnings", "currency", ("MISSING_OWNER_EARNINGS_CAPEX",)),
            "cost_of_equity": unavailable("cost_of_equity", "decimal_ratio", ("MISSING_DISCOUNT_INPUT",)),
        },
        scenario_results={},
    )

    messages = [issue.message_de for issue in finalization_issues(state, book) if issue.blocking]

    assert "Die Investitionsbasis für Owner Earnings ist noch unvollständig." in messages
    assert "MISSING_OWNER_EARNINGS_CAPEX" not in " ".join(messages)


def test_normal_finalization_messages_do_not_contain_raw_codes() -> None:
    state = _state(
        {
            "review_required": (
                "2025 short_term_debt: primary_semantic_review_required",
                "2012 depreciation_amortization: primary_semantic_review_required",
            )
        }
    )
    forbidden = ("REVIEW_REQUIRED", "primary_semantic_review_required", "FINANCIAL_DATA", "MISSING_")

    for issue in finalization_issues(state):
        for token in forbidden:
            assert token not in issue.message_de


def test_analysis_ui_visible_text_uses_real_german_umlauts() -> None:
    text = Path("pages/3_Analyse.py").read_text(encoding="utf-8")
    forbidden = (
        "Geschaeft",
        "Kaeufe",
        "Bestaet",
        "bestaet",
        "Schliessen",
        "schliessen",
        "ueberschreib",
        "Vorschlaege",
        "Jahresueberschuss",
        "Rentabilitaets",
        "Individualitaet",
    )
    for token in forbidden:
        assert token not in text
