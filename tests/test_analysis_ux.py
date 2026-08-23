from __future__ import annotations

from stock_valuation.ui.analysis_layout import ANALYSIS_SECTIONS, PRIMARY_ANALYSIS_ORDER
from stock_valuation.ui.analysis_view_model import build_analysis_view_model
from stock_valuation.ui.info_catalog import INFO_CATALOG
from stock_valuation.ui.labels_de import format_currency_compact_de, issue_label, status_label
from stock_valuation.workflow.models import AnalysisState, StageState


def _stage(stage: str, status: str, payload: dict | None = None) -> StageState:
    return StageState(stage=stage, status=status, payload=payload or {})


def _analysis_state(*, market_payload: dict, valuation_status: str = "READY_FOR_PREVIEW") -> AnalysisState:
    calc_payload = {
        "base_facts": {
            "2025": [
                {"metric": "revenue", "value": "1000000000", "currency": "EUR", "source_status": "primary_source"},
                {"metric": "net_income", "value": "200000000", "currency": "EUR", "source_status": "primary_source"},
            ]
        },
        "results": [
            {"metric_id": "free_cash_flow", "fiscal_year": 2025, "value": "150000000", "status": "AVAILABLE"},
            {"metric_id": "net_margin", "fiscal_year": 2025, "value": "0.20", "status": "AVAILABLE"},
        ],
    }
    return AnalysisState(
        analysis_id=1,
        company_name="ASML Holding N.V.",
        ticker="ASML",
        as_of_date="2026-08-23",
        revision_number=1,
        analysis_status="DRAFT",
        stages={
            "FINANCIAL_DATA": _stage("FINANCIAL_DATA", "REVIEW_REQUIRED"),
            "CALCULATION": _stage("CALCULATION", "REVIEW_REQUIRED", calc_payload),
            "HISTORICAL_ANALYSIS": _stage("HISTORICAL_ANALYSIS", "READY"),
            "BUSINESS_QUALITY": _stage("BUSINESS_QUALITY", "READY", {"result": {"overall_score": 8.1}}),
            "MARKET_DATA": _stage("MARKET_DATA", "REVIEW_REQUIRED", market_payload),
            "ASSUMPTIONS": _stage("ASSUMPTIONS", "REVIEW_REQUIRED", {"recommendations": {}}),
            "VALUATION": _stage(
                "VALUATION",
                valuation_status,
                {
                    "mode": "PREVIEW",
                    "multiples": [
                        {"metric_id": "latest_fy_pe", "fiscal_year": 2025, "value": "22.5", "status": "AVAILABLE"}
                    ],
                    "preview": {},
                },
            ),
        },
    )


def test_every_layout_metric_has_visible_info_entry() -> None:
    missing = []
    for section in ANALYSIS_SECTIONS:
        for point in section.points:
            entry = INFO_CATALOG.get(point.info_key)
            if entry is None or not entry.title.strip() or not entry.meaning.strip():
                missing.append((section.key, point.key, point.info_key))
    assert missing == []


def test_main_analysis_order_matches_excel_book_flow() -> None:
    assert PRIMARY_ANALYSIS_ORDER == (
        "Unternehmensüberblick",
        "Gewinn- und Verlustrechnung",
        "Bilanz",
        "Cashflow",
        "Ertrag und Rentabilität",
        "Finanzielle Stabilität",
        "Verschuldung",
        "Kapitalbindung / Working Capital",
        "Cashflow-Qualität / Kapitalallokation",
        "Bewertungskennzahlen",
        "DCF-Bewertung",
        "Multiplikatorenmethode",
        "Zusammenfassung",
    )
    section_titles = " ".join(section.title for section in ANALYSIS_SECTIONS)
    assert section_titles.index("Gewinn- und Verlustrechnung") < section_titles.index("Bilanz")
    assert section_titles.index("Bilanz") < section_titles.index("Cashflow")
    assert section_titles.index("Cashflow-Qualität") < section_titles.index("Bewertungskennzahlen")


def test_internal_status_codes_are_hidden_by_german_labels() -> None:
    expected = {
        "REVIEW_REQUIRED": "Prüfung erforderlich",
        "READY_FOR_PREVIEW": "Bewertungsvorschau verfügbar",
        "UNAVAILABLE": "Nicht verfügbar",
        "APPROVAL_STALE": "Frühere Freigabe ist nicht mehr aktuell",
        "EV_REVIEW_REQUIRED": "Unternehmenswert noch nicht vollständig berechenbar",
        "MISSING_NET_DEBT": "Nettoverschuldung fehlt",
    }
    for code, label in expected.items():
        translated = issue_label(code) if code.startswith(("EV_", "MISSING_", "APPROVAL_")) else status_label(code)
        assert translated == label
        assert code not in translated


def test_review_required_ev_review_required_preview_labels_are_german() -> None:
    state = _analysis_state(
        market_payload={
            "price": "600",
            "trading_currency": "EUR",
            "payload": {"financial_statement_currency": "EUR", "listing": {}},
            "availability": {"enterprise_value": "EV_REVIEW_REQUIRED", "enterprise_value_reason": ["MISSING_NET_DEBT"]},
        }
    )
    vm = build_analysis_view_model(state)
    assert vm.status_line["Daten"] == "Prüfung erforderlich"
    assert vm.status_line["Bewertung"] == "Bewertungsvorschau verfügbar"
    assert "Unternehmenswert: Nettoverschuldung fehlt" in vm.market_notes
    ev_point = next(point for section in vm.sections for point in section.points if point.key == "enterprise_value")
    assert ev_point.status_label == "Unternehmenswert noch nicht vollständig berechenbar"


def test_ev_ready_is_shown_as_available_in_german() -> None:
    state = _analysis_state(
        market_payload={
            "price": "410",
            "market_cap": "3000000000000",
            "enterprise_value": "2950000000000",
            "trading_currency": "USD",
            "payload": {"financial_statement_currency": "USD", "listing": {}},
            "availability": {"enterprise_value": "EV_READY"},
        }
    )
    vm = build_analysis_view_model(state)
    ev_point = next(point for section in vm.sections for point in section.points if point.key == "enterprise_value")
    assert ev_point.status_label == "Unternehmenswert verfügbar"
    assert ev_point.latest_value != "Nicht verfügbar"


def test_missing_values_are_never_displayed_as_zero() -> None:
    assert format_currency_compact_de(None, "EUR") == "Nicht verfügbar"
    state = _analysis_state(
        market_payload={
            "price": None,
            "trading_currency": "EUR",
            "payload": {"financial_statement_currency": "EUR", "listing": {}},
            "availability": {},
        }
    )
    vm = build_analysis_view_model(state)
    market_cap = next(point for section in vm.sections for point in section.points if point.key == "market_cap")
    assert market_cap.latest_value == "Nicht verfügbar"
    assert market_cap.latest_value != "0"
