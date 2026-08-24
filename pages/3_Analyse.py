from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_valuation.runtime_dependencies import ensure_runtime_dependencies

ensure_runtime_dependencies()

from datetime import date
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st

from stock_valuation.analyses.input_service import store_risk_free_rate, upsert_manual_financial_override
from stock_valuation.analyses.service import get_analysis
from stock_valuation.book_valuation.persistence import load_book_assumptions, upsert_book_assumption
from stock_valuation.book_valuation.service import build_book_valuation_for_analysis
from stock_valuation.data.providers.ecb import ECBRiskFreeRateProvider
from stock_valuation.database.models import AnalysisStatus
from stock_valuation.database.session import get_session, init_database
from stock_valuation.market.refresh_service import market_refresh_missing_reason, refresh_market_snapshot_for_analysis
from stock_valuation.ui.analysis_layout import ANALYSIS_SECTIONS
from stock_valuation.ui.analysis_view_model import available_years, build_analysis_view_model, table_rows
from stock_valuation.ui.info_catalog import INFO_CATALOG, InfoEntry
from stock_valuation.ui.labels_de import format_currency_compact_de, format_date_de, issue_label, status_label
from stock_valuation.ui.navigation import STATUS_LABELS, current_analysis_id, render_analysis_selector, render_navigation
from stock_valuation.valuation_assumptions.approvals import approve_recommended_value, override_assumption
from stock_valuation.valuation_assumptions.models import AssumptionRecommendation
from stock_valuation.workflow.service import complete_analysis_if_ready, finalization_blockers, finalization_issues, refresh_local_analysis_stages


st.set_page_config(page_title="Analyse", layout="wide")
init_database()
render_navigation()


def _info_button(info_key: str) -> None:
    entry = INFO_CATALOG.get(info_key)
    if entry is None:
        return
    with st.popover("ⓘ", use_container_width=False):
        _render_info(entry)


def _render_info(entry: InfoEntry) -> None:
    st.markdown(f"**{entry.title}**")
    parts = (
        ("Was sagt die Kennzahl aus?", entry.meaning),
        ("Wie wird sie berechnet?", entry.formula),
        ("Warum ist sie wichtig?", entry.importance),
        ("Wie kann man sie einordnen?", entry.interpretation),
        ("Worauf muss man achten?", entry.watch_out),
        ("Wie sollte die Entwicklung betrachtet werden?", entry.history),
        ("Welche Daten verwendet die App?", entry.data_basis),
        ("Einschränkungen / Methodik", entry.methodology_note),
    )
    for heading, text in parts:
        if text:
            st.markdown(f"**{heading}**")
            st.write(text)
    st.markdown("**Buchbezug**")
    if entry.reference_status == "KNOWN" and (entry.book_chapter or entry.book_page):
        st.write(f"Kapitel: {entry.book_chapter or 'nicht angegeben'}")
        st.write(f"Seite: {entry.book_page or 'nicht angegeben'}")
    else:
        st.write("Buchseite: noch nicht zugeordnet")
    st.markdown("**Excel-Bezug**")
    st.write(entry.excel_location or "noch nicht zugeordnet")


def _point_label(label: str, info_key: str) -> None:
    left, right = st.columns([0.92, 0.08])
    left.markdown(f"**{label}**")
    with right:
        _info_button(info_key)


def _section_by_key(key: str):
    return next(section for section in ANALYSIS_SECTIONS if section.key == key)


def _recommendation_from_payload(payload: dict) -> AssumptionRecommendation:
    return AssumptionRecommendation(
        **{
            **payload,
            "recommended_value": Decimal(str(payload["recommended_value"])) if payload.get("recommended_value") is not None else None,
            "approved_value": Decimal(str(payload["approved_value"])) if payload.get("approved_value") is not None else None,
            "warnings": tuple(payload.get("warnings", ())),
            "evidence_refs": tuple(payload.get("evidence_refs", ())),
        }
    )


def _parse_decimal(raw: str) -> Decimal:
    try:
        return Decimal(raw.strip().replace(",", "."))
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError("Bitte einen gültigen Zahlenwert eingeben.") from exc


def _source_fields(prefix: str, *, default_source: str = "Aktienfinder") -> tuple[str, str]:
    source_choice = st.selectbox(
        "Quelle",
        ["Aktienfinder", "Geschäftsbericht", "Unternehmenswebsite", "andere"],
        index=0,
        key=f"{prefix}-source-choice",
    )
    source_free = st.text_input(
        "Freie Quellenbezeichnung",
        value="" if source_choice != "andere" else default_source,
        key=f"{prefix}-source-free",
    )
    source = source_free.strip() or source_choice
    note = st.text_area("Kommentar / Begruendung", key=f"{prefix}-note")
    return source, note


def _save_financial_override_form(
    *,
    label: str,
    metric: str,
    fiscal_year: int,
    statement: str,
    unit: str = "currency",
    default_value: str = "",
    button_label: str = "Speichern",
) -> None:
    editable = analysis.status in {AnalysisStatus.DRAFT, AnalysisStatus.IN_PROGRESS}
    with st.form(f"financial-override-{metric}-{fiscal_year}-{button_label}"):
        st.write(f"**{label} {fiscal_year}**")
        value_raw = st.text_input("Wert", value=default_value)
        currency = st.text_input("Währung", value=analysis.company.currency)
        source, note = _source_fields(f"financial-override-{metric}-{fiscal_year}-{button_label}")
        submitted = st.form_submit_button(button_label, disabled=not editable)
    if submitted:
        try:
            value = _parse_decimal(value_raw)
            with get_session() as session:
                fresh = get_analysis(session, current_analysis_id() or analysis.id)
                if fresh is not None:
                    upsert_manual_financial_override(
                        session,
                        fresh,
                        metric=metric,
                        period_end=date(fiscal_year, 12, 31),
                        value=value,
                        currency=currency.strip() or fresh.company.currency,
                        unit=unit,
                        statement=statement,
                        source_name=source,
                        note=note,
                    )
            st.success("Wert gespeichert.")
            st.rerun()
        except (ValueError, InvalidOperation) as exc:
            st.error(str(exc))


def _save_book_assumption_form(
    *,
    label: str,
    key: str,
    unit: str,
    scenario: str = "base",
    suggestion: Decimal | None = None,
    saved_value: str = "",
    saved_note: str = "",
    button_label: str = "Speichern",
) -> None:
    editable = analysis.status in {AnalysisStatus.DRAFT, AnalysisStatus.IN_PROGRESS}
    with st.form(f"book-assumption-{scenario}-{key}"):
        st.write(f"**{label}**")
        if suggestion is not None and not saved_value:
            st.caption(f"Vorschlag: {suggestion}. Status: noch nicht bestätigt.")
        value = st.text_input("Wert", value=saved_value)
        source, note = _source_fields(f"book-assumption-{scenario}-{key}", default_source="Eigene Annahme")
        if saved_note:
            st.caption(f"Gespeicherter Kommentar: {saved_note}")
        submitted = st.form_submit_button(button_label, disabled=not editable)
    if submitted:
        try:
            with get_session() as session:
                fresh = get_analysis(session, current_analysis_id() or analysis.id)
                if fresh is not None:
                    upsert_book_assumption(
                        session,
                        fresh,
                        key=key,
                        value=_parse_decimal(value),
                        note=f"Quelle: {source}. {note.strip() or 'Manuell bestätigt.'}",
                        unit=unit,
                        scenario=scenario,
                        source_type="MANUALLY_CONFIRMED",
                    )
            st.success("Annahme gespeichert.")
            st.rerun()
        except (ValueError, InvalidOperation) as exc:
            st.error(str(exc))


def _render_metric_table(section_key: str, years: list[int]) -> None:
    section = next(item for item in vm.sections if item.key == section_key)
    st.header(section.title)
    st.caption(section.intro)
    if not years:
        st.info("Für diese Analyse sind noch keine historischen Werte verfügbar.")
        return
    rows = table_rows(section, years)
    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", hide_index=True)
    with st.expander("Kennzahlen erklären"):
        for point in section.points:
            _point_label(point.label, point.info_key)
            if point.reason:
                st.caption(point.reason)


def _render_market_and_multiples(years: list[int]) -> None:
    section = next(item for item in vm.sections if item.key == "valuation_multiples")
    st.header(section.title)
    st.caption(section.intro)
    market_keys = {"market_cap", "enterprise_value"}
    market_points = [point for point in section.points if point.key in market_keys]
    cols = st.columns(2)
    for idx, point in enumerate(market_points):
        with cols[idx % 2]:
            _point_label(point.label, point.info_key)
            st.metric(point.label, point.latest_value)
            if point.reason:
                st.warning(point.reason)
    for note in vm.market_notes:
        st.caption(note)
    with st.expander("Enterprise Value Ansatz prüfen"):
        st.write("Enterprise Value = Marktkapitalisierung + kurzfristige Finanzschulden + langfristige Finanzschulden - liquide Mittel.")
        st.write("Wenn Nettoverschuldung nicht freigegeben ist, fehlen EV, EV/EBIT, EV/EBITDA, EV/Umsatz und EV/FCF bewusst.")
        market_payload = state.stages["MARKET_DATA"].payload
        st.dataframe(
            pd.DataFrame(
                [
                    {"Baustein": "Aktienkurs", "Wert": market_payload.get("price") or "Nicht verfuegbar", "Status": "Information"},
                    {"Baustein": "Anzahl Aktien", "Wert": market_payload.get("shares_outstanding") or "Nicht verfuegbar", "Status": "Information"},
                    {"Baustein": "Marktkapitalisierung", "Wert": market_payload.get("market_cap") or "Nicht verfuegbar", "Status": status_label("AVAILABLE") if market_payload.get("market_cap") else status_label("UNAVAILABLE")},
                    {"Baustein": "Nettoverschuldung", "Wert": market_payload.get("net_debt") or "Nicht verfuegbar", "Status": issue_label("MISSING_NET_DEBT") if not market_payload.get("enterprise_value") else status_label("AVAILABLE")},
                    {"Baustein": "Enterprise Value", "Wert": market_payload.get("enterprise_value") or "Nicht verfuegbar", "Status": issue_label("MISSING_NET_DEBT") if not market_payload.get("enterprise_value") else status_label("AVAILABLE")},
                ]
            ),
            width="stretch",
            hide_index=True,
        )
        if not market_payload.get("enterprise_value"):
            latest_years = available_years(vm, default=1)
            fiscal_year = latest_years[-1] if latest_years else analysis.as_of_date.year
            _save_financial_override_form(
                label="Kurzfristige Finanzschulden",
                metric="short_term_debt",
                fiscal_year=fiscal_year,
                statement="balance_sheet",
                button_label="Kurzfristige Finanzschulden speichern",
            )
    if state.stages["MARKET_DATA"].status in {"UNAVAILABLE", "NOT_RUN"}:
        st.info("Marktdaten wurden für diese Analyse noch nicht geladen.")
    with st.expander("Marktdaten aktualisieren"):
        _info_button("market_cap")
        st.write("Diese Aktion lädt Marktdaten nur nach deinem Klick und speichert danach einen Market Snapshot für diese Analyse.")
        provider_symbol = st.text_input("Handelssymbol / Börsenplatz", value=analysis.company.provider_symbol or analysis.company.ticker)
        trading_currency = st.text_input("Handelswährung", value=analysis.market_price_currency or analysis.company.currency)
        manual_price_raw = st.text_input("Aktienkurs manuell verwenden (optional)", value=str(analysis.market_price or ""))
        manual_shares_raw = st.text_input("Anzahl Aktien zum Stichtag", help="Pflicht für Marktkapitalisierung, wenn kein geprüfter Aktienzahl-Provider vorhanden ist.")
        if st.button("Marktdaten aktualisieren", disabled=not provider_symbol.strip()):
            try:
                manual_price = Decimal(manual_price_raw.replace(",", ".")) if manual_price_raw.strip() else None
                manual_shares = Decimal(manual_shares_raw.replace(",", ".")) if manual_shares_raw.strip() else None
                with get_session() as session:
                    fresh = get_analysis(session, current_analysis_id() or analysis.id)
                    if fresh is not None:
                        refresh_market_snapshot_for_analysis(
                            session,
                            fresh,
                            manual_price=manual_price,
                            manual_shares_outstanding=manual_shares,
                            provider_symbol=provider_symbol,
                            trading_currency=trading_currency,
                        )
                st.rerun()
            except (ValueError, InvalidOperation) as exc:
                st.error("Bitte Kurs und Aktienzahl als gültige Zahlen eingeben.")
            except Exception as exc:
                st.error(market_refresh_missing_reason(exc))
    multiple_points = [point for point in section.points if point.key not in market_keys]
    rows = []
    for point in multiple_points:
        rows.append(
            {
                "Kennzahl": point.label,
                "Aktueller Wert": point.latest_value,
                "Status": point.status_label,
                "Hinweis": point.reason or "",
            }
        )
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    with st.expander("Bewertungskennzahlen erklären"):
        for point in multiple_points:
            _point_label(point.label, point.info_key)
            if point.reason:
                st.caption(point.reason)


def _render_dcf() -> None:
    section = next(item for item in vm.sections if item.key == "dcf")
    st.header(section.title)
    st.subheader("Equity-Methode")
    st.write(section.intro)
    if state.stages["ASSUMPTIONS"].status == "REVIEW_REQUIRED":
        st.warning("Diese Bewertung verwendet noch nicht vollständig freigegebene Annahmen.")
    st.subheader("1. Bestimmung Owner Earnings")
    for key in ("owner_earnings", "owner_earnings_capex", "operating_working_capital", "change_in_operating_working_capital"):
        _info_button(key)
    owner_rows = []
    for row in book_valuation.owner_earnings_history[-(len(years) or 5):]:
        owner_rows.append(
            {
                "Jahr": row.fiscal_year,
                "Jahresüberschuss": _book_text(row.net_income),
                "Umsatz": _book_text(row.revenue),
                "Owner-Earnings-CAPEX": _book_text(row.owner_earnings_capex),
                "Abschreibungen": _book_text(row.depreciation_amortization),
                "Operating Working Capital": _book_text(row.operating_working_capital),
                "Δ Operating Working Capital": _book_text(row.change_in_operating_working_capital),
                "Owner Earnings": _book_text(row.owner_earnings),
                "Status": _book_status(row.owner_earnings),
            }
        )
    if owner_rows:
        st.dataframe(pd.DataFrame(owner_rows), width="stretch", hide_index=True)
    else:
        st.info("Für Owner Earnings fehlen noch ausreichend historische Eingabewerte.")
    with st.expander("Fehlende immaterielle Investitionen bestätigen"):
        st.caption("Nur hier darf ein fehlender Wert ausdrücklich als 0 oder als eigener Wert bestätigt werden. Ohne Bestätigung wird nichts als 0 behandelt.")
        for row in book_valuation.owner_earnings_history[-5:]:
            key = f"intangible_purchases_{row.fiscal_year}"
            saved = book_valuation.manual_inputs.get(key, {})
            cols = st.columns([0.25, 0.25, 0.35, 0.15])
            cols[0].write(str(row.fiscal_year))
            value = cols[1].text_input("Wert", value=saved.get("value") or "", key=f"book-{key}")
            note = cols[2].text_input("Begründung", value=saved.get("note") or "", key=f"book-note-{key}")
            if cols[3].button("Speichern", key=f"book-save-{key}", disabled=not value.strip()):
                with get_session() as session:
                    fresh = get_analysis(session, current_analysis_id() or analysis.id)
                    if fresh is not None:
                        upsert_book_assumption(session, fresh, key=key, value=Decimal(value.replace(",", ".")), note=note or "Manuell bestätigt.", unit="currency")
                st.rerun()
    with st.expander("Owner-Earnings-Werte direkt am Verwendungsort ergaenzen"):
        st.caption("Gespeichert wird erst nach Klick auf Speichern oder Bestätigen. Eingetippte, aber nicht gespeicherte Werte gehen beim Schließen verloren.")
        for owner_row in book_valuation.owner_earnings_history[-5:]:
            st.markdown(f"**Geschäftsjahr {owner_row.fiscal_year}**")
            if "MISSING_INTANGIBLE_PURCHASES" in owner_row.owner_earnings_capex.issues or "MISSING_OWNER_EARNINGS_CAPEX" in owner_row.owner_earnings.issues:
                st.write("Käufe immaterieller Anlagewerte fehlen. Wenn die Quelle keinen separaten Wert ausweist, kann für genau dieses Jahr 0 bestätigt werden.")
                _save_financial_override_form(
                    label="Käufe immaterieller Anlagewerte",
                    metric="intangible_purchases",
                    fiscal_year=owner_row.fiscal_year,
                    statement="cash_flow",
                    default_value="0",
                    button_label=f"Wert für {owner_row.fiscal_year} speichern",
                )
            if "MISSING_DEPRECIATION_AMORTIZATION" in owner_row.depreciation_amortization.issues or "MISSING_DEPRECIATION_AMORTIZATION" in owner_row.owner_earnings.issues:
                st.write("Abschreibungen fehlen oder müssen geprüft werden.")
                _save_financial_override_form(
                    label="Abschreibungen und Amortisation",
                    metric="depreciation_amortization",
                    fiscal_year=owner_row.fiscal_year,
                    statement="cash_flow",
                    button_label=f"Abschreibungen für {owner_row.fiscal_year} speichern",
                )
    st.subheader("2. Bestimmung des Diskontierungsfaktors")
    for key in ("fair_pe", "cost_of_equity"):
        _info_button(key)
    row = next((item for item in vm.assumption_rows if item["key"] == "discount_rate"), None)
    if row:
        st.write(f"Diskontierungszins nach aktueller Annahme: **{row['Empfehlung']}** · Status: **{row['Status']}**")
        st.caption("Die Excel-/Buchmethode nutzt zusätzlich: Risikoaufschlag = 1 / faires KGV plus risikofreier Zins und Mindestverzinsung.")
    discount_rows = [
        ("Faires KGV", book_valuation.discount_rate_result.fair_pe, "fair_pe"),
        ("Risikoaufschlag", book_valuation.discount_rate_result.risk_premium, "cost_of_equity"),
        ("Risikofreier Zins", book_valuation.discount_rate_result.risk_free_rate, "cost_of_equity"),
        ("Mindestaufschlag", book_valuation.discount_rate_result.minimum_return_addon, "cost_of_equity"),
        ("Eigenkapitalkosten", book_valuation.discount_rate_result.cost_of_equity, "cost_of_equity"),
    ]
    st.dataframe(pd.DataFrame({"Kennzahl": label, "Wert": _book_text(value), "Status": _book_status(value)} for label, value, _ in discount_rows), width="stretch", hide_index=True)
    with st.expander("Risikofreien Zins hier laden oder überschreiben"):
        st.write("Bei EUR-Bewertungen wird der ECB Euro-area AAA 10Y Zinssatz verwendet. Bei anderer Bewertungswährung muss der Zins manuell geprüft werden.")
        if st.button("ECB 10Y AAA Zins laden", disabled=analysis.company.currency != "EUR"):
            try:
                observation = ECBRiskFreeRateProvider().get_latest_eur_aaa_10y()
                with get_session() as session:
                    fresh = get_analysis(session, current_analysis_id() or analysis.id)
                    if fresh is not None:
                        store_risk_free_rate(session, fresh, observation)
                st.success("ECB-Zins gespeichert.")
                st.rerun()
            except Exception as exc:
                st.error(f"ECB-Zins konnte nicht geladen werden: {exc}")
        saved_risk_free = book_valuation.manual_inputs.get("risk_free_rate", {})
        _save_book_assumption_form(
            label="Eigenen risikofreien Zins verwenden",
            key="risk_free_rate",
            unit="decimal_ratio",
            saved_value=saved_risk_free.get("value") or "",
            saved_note=saved_risk_free.get("note") or "",
            button_label="Risikofreien Zins speichern",
        )
    st.subheader("3. Bestimmung der Ewigen Rente")
    _info_button("terminal_value")
    row = next((item for item in vm.assumption_rows if item["key"] == "terminal_growth_rate"), None)
    if row:
        st.write(f"Ewige Wachstumsrate: **{row['Empfehlung']}**")
    st.caption("Orientierung aus Excel-/Buchvorlage: konservativ wählen; Erfahrungsbereich ungefähr 0 bis 4 Prozent; Wachstum muss unter Diskontierungszins liegen.")
    terminal_rows = [
        {"Kennzahl": "Ewige Wachstumsrate", "Wert": _book_text(book_valuation.terminal_value_result.terminal_growth_rate), "Status": _book_status(book_valuation.terminal_value_result.terminal_growth_rate)},
        {"Kennzahl": "Terminal Value", "Wert": _book_text(book_valuation.terminal_value_result.terminal_value), "Status": _book_status(book_valuation.terminal_value_result.terminal_value)},
        {"Kennzahl": "Barwert Terminal Value", "Wert": _book_text(book_valuation.terminal_value_result.present_value_terminal_value), "Status": _book_status(book_valuation.terminal_value_result.present_value_terminal_value)},
    ]
    st.dataframe(pd.DataFrame(terminal_rows), width="stretch", hide_index=True)
    st.subheader("4. Fairen Aktienkurs bestimmen")
    for key in ("fair_value", "margin_of_safety"):
        _info_button(key)
    fair_rows = [
        ("Summe Barwerte Owner Earnings", book_valuation.fair_value_result.present_value_owner_earnings_sum),
        ("Barwert Ewige Rente", book_valuation.fair_value_result.present_value_terminal_value),
        ("Wert des Eigenkapitals", book_valuation.fair_value_result.equity_value),
        ("Anzahl Aktien", book_valuation.fair_value_result.shares_outstanding),
        ("Fairer Aktienkurs", book_valuation.fair_value_result.fair_value_per_share),
        ("Sicherheitsmarge", book_valuation.fair_value_result.margin_of_safety),
        ("Fairer Aktienkurs nach Sicherheitsmarge", book_valuation.fair_value_result.fair_value_after_safety_margin),
        ("Aktueller Kurs", book_valuation.fair_value_result.market_price),
        ("Abweichung", book_valuation.fair_value_result.valuation_gap),
    ]
    st.dataframe(pd.DataFrame({"Kennzahl": label, "Wert": _book_text(value), "Status": _book_status(value)} for label, value in fair_rows), width="stretch", hide_index=True)
    st.subheader("Szenarien")
    if vm.scenario_rows:
        st.dataframe(pd.DataFrame(vm.scenario_rows), width="stretch", hide_index=True)
    else:
        st.info("Noch keine Bewertungsvorschau verfügbar.")
    st.subheader("Annahmen prüfen")
    _render_assumption_actions()

    st.subheader("Excel-/Buch-DCF-Szenarien")
    if book_valuation.scenario_results:
        labels = {key: item.label for key, item in book_valuation.scenario_results.items()}
        scenario_table = []
        scenario_metrics = [
            ("Owner Earnings Basis", "owner_earnings_base"),
            ("Wachstum", "growth_rate"),
            ("Diskontierungszins", "discount_rate"),
            ("Ewiges Wachstum", "terminal_growth_rate"),
            ("PV Owner Earnings", "present_value_owner_earnings_sum"),
            ("PV Ewige Rente", "present_value_terminal_value"),
            ("Fairer Aktienkurs", "fair_value_per_share"),
            ("Wert nach Sicherheitsmarge", "fair_value_after_safety_margin"),
            ("Aktueller Kurs", "market_price"),
        ]
        for label, attr in scenario_metrics:
            row_data = {"Kennzahl": label}
            for scenario_key, scenario in book_valuation.scenario_results.items():
                row_data[labels[scenario_key]] = _book_text(getattr(scenario, attr))
            scenario_table.append(row_data)
        st.dataframe(pd.DataFrame(scenario_table), width="stretch", hide_index=True)
    with st.expander("Excel-/Buch-Szenarien bearbeiten"):
        scenario_labels = {"bear": "Pessimistisch", "base": "Basis", "bull": "Optimistisch"}
        for scenario_key, scenario_label in scenario_labels.items():
            st.markdown(f"**{scenario_label}**")
            cols = st.columns(3)
            with cols[0]:
                _save_book_assumption_form(label="Owner Earnings Basis", key="base_owner_earnings", unit="currency", scenario=scenario_key)
                _save_book_assumption_form(label="Wachstumsrate", key="growth_rate", unit="decimal_ratio", scenario=scenario_key, suggestion=Decimal("0.03"))
            with cols[1]:
                _save_book_assumption_form(label="Planungszeitraum", key="projection_years", unit="years", scenario=scenario_key, suggestion=Decimal("5"))
                _save_book_assumption_form(label="Ewige Wachstumsrate", key="terminal_growth_rate", unit="decimal_ratio", scenario=scenario_key, suggestion=Decimal("0.02"))
            with cols[2]:
                _save_book_assumption_form(label="Faires KGV", key="fair_pe", unit="multiple", scenario=scenario_key)
                _save_book_assumption_form(label="Sicherheitsmarge", key="margin_of_safety", unit="decimal_ratio", scenario=scenario_key, suggestion=Decimal("0.5"))


def _render_assumption_actions() -> None:
    editable = analysis.status in {AnalysisStatus.DRAFT, AnalysisStatus.IN_PROGRESS}
    if not vm.assumption_rows:
        st.info("Bewertungsannahmen sind noch nicht berechenbar.")
        return
    for row in vm.assumption_rows:
        with st.expander(row["Annahme"]):
            _info_button(row["key"])
            st.write(f"Empfehlung: **{row['Empfehlung']}**")
            st.write(f"Freigegeben: **{row['Freigegeben']}**")
            st.write(f"Status: **{row['Status']}**")
            st.caption(row["Begründung"])
            actions = st.columns(2)
            if actions[0].button("Empfehlung übernehmen", key=f"approve-{row['key']}", disabled=not editable or row["raw"].get("recommended_value") is None):
                with get_session() as session:
                    fresh = get_analysis(session, current_analysis_id() or analysis.id)
                    if fresh is not None:
                        approve_recommended_value(
                            session,
                            fresh,
                            _recommendation_from_payload(row["raw"]),
                            recommendation_inputs_hash=state.stages["ASSUMPTIONS"].payload["assumption_set"]["inputs_hash"],
                        )
                        st.rerun()
            with actions[1].form(f"override-{row['key']}"):
                value = st.text_input("Eigener Wert")
                note = st.text_input("Begründung")
                submitted = st.form_submit_button("Speichern", disabled=not editable)
                if submitted:
                    if not note.strip():
                        st.error("Begründung ist Pflicht.")
                    else:
                        try:
                            parsed = _parse_decimal(value)
                            with get_session() as session:
                                fresh = get_analysis(session, current_analysis_id() or analysis.id)
                                if fresh is not None:
                                    override_assumption(
                                        session,
                                        fresh,
                                        _recommendation_from_payload(row["raw"]),
                                        approved_value=parsed,
                                        note=note,
                                        recommendation_inputs_hash=state.stages["ASSUMPTIONS"].payload["assumption_set"]["inputs_hash"],
                                    )
                                    st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))


def _book_text(item) -> str:
    value = item.value
    if value is None:
        return "Nicht verfügbar"
    if item.unit == "decimal_ratio":
        return f"{Decimal(str(value)) * Decimal('100'):.1f} %"
    if item.unit in {"multiple", "factor"}:
        return f"{Decimal(str(value)):.2f}x"
    return format_currency_compact_de(value, vm.financial_currency)


def _book_status(item) -> str:
    if item.issues:
        return issue_label(item.issues[0])
    return status_label(item.status)


def _render_issue_list(issues, *, blocking: bool) -> None:
    selected = [issue for issue in issues if issue.blocking is blocking]
    if not selected:
        return
    for index, issue in enumerate(selected, start=1):
        st.write(f"**{index}. {issue.message_de}**")
        if issue.location_hint:
            st.caption(issue.location_hint)
        if issue.action_label:
            st.caption(issue.action_label)


def _render_historical_warnings(issues) -> None:
    warnings = [issue for issue in issues if issue.category == "HISTORISCHE_WARNUNG"]
    if not warnings:
        return
    st.subheader("Historische Hinweise")
    st.write(
        "Ältere Geschäftsjahre enthalten noch nicht bestätigte Detaildaten. "
        "Diese Werte blockieren die aktuelle Bewertung nicht, solange sie nicht verwendet werden."
    )
    for issue in warnings:
        st.write(f"- {issue.message_de}")
    with st.expander("Technische Datenprüfungen anzeigen"):
        for issue in warnings:
            st.write(f"{issue.message_de}: {issue.location_hint or '-'}")


def _render_quality() -> None:
    section = next(item for item in vm.sections if item.key == "quality")
    st.header(section.title)
    st.caption(section.intro)
    st.subheader("12. Multiplikatorenmethode")
    st.caption("Vorschläge sind Startwerte. Sie werden erst nach Übernehmen oder Speichern als echte Annahme verwendet.")
    mult = book_valuation.multiplicator_method_result
    mult_rows = [
        ("A. Sockel-KGV", mult.base_pe),
        ("B. Finanzielle Stabilitaet", mult.financial_stability_addon),
        ("C. Marktposition", mult.market_position_addon),
        ("D. Rentabilitaet", mult.profitability_multiplier),
        ("E. Wachstum", mult.growth_addon),
        ("F. Individualität", mult.individuality_addon),
        ("G. Faires KGV", mult.fair_pe),
        ("H. Fairer Aktienkurs", mult.fair_price_per_share),
    ]
    st.dataframe(
        pd.DataFrame({"Schritt": label, "Wert": _book_text(value), "Status": _book_status(value)} for label, value in mult_rows),
        width="stretch",
        hide_index=True,
    )
    base_state = book_valuation.assumption_states.get("base_pe")
    forecast_state = book_valuation.assumption_states.get("forecast_net_income")
    cols = st.columns(2)
    with cols[0]:
        _save_book_assumption_form(
            label="Sockel-KGV",
            key="base_pe",
            unit="multiple",
            suggestion=base_state.suggestion if base_state else Decimal("7.5"),
            saved_value=str(base_state.value) if base_state and base_state.value is not None else "",
            saved_note=base_state.note or "" if base_state else "",
            button_label="Sockel-KGV übernehmen",
        )
    with cols[1]:
        _save_book_assumption_form(
            label="Prognostizierter Jahresüberschuss",
            key="forecast_net_income",
            unit="currency",
            saved_value=str(forecast_state.value) if forecast_state and forecast_state.value is not None else "",
            saved_note=forecast_state.note or "" if forecast_state else "",
            button_label="Prognosewert speichern",
        )
    rows = [
        {
            "Baustein": point.label,
            "Wert": point.latest_value,
            "Status": point.status_label,
            "Hinweis": point.reason or "Prüfen oder manuell bestätigen.",
        }
        for point in section.points
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    with st.expander("KGV-Aufschläge und Bewertungsannahmen prüfen"):
        assumption_rows = [
            ("Sockel-KGV", "base_pe", "multiple", "base_pe"),
            ("Finanzielle Stabilität", "financial_stability_addon", "multiple_points", "financial_stability_addon"),
            ("Marktpositions-Aufschlag", "market_position_addon", "multiple_points", "market_position"),
            ("Rentabilitätsmultiplikator", "profitability_multiplier", "factor", "profitability_addon"),
            ("Wachstum", "growth_addon", "multiple_points", "growth_addon"),
            ("Individualität", "individuality_addon", "multiple_points", "individuality_addon"),
            ("Faires KGV für DCF", "fair_pe", "multiple", "fair_pe"),
            ("Risikofreier Zinssatz", "risk_free_rate", "decimal_ratio", "cost_of_equity"),
            ("Sicherheitsmarge", "margin_of_safety", "decimal_ratio", "margin_of_safety"),
            ("Prognose-Jahresüberschuss", "forecast_net_income", "currency", "multiplicator_fair_price_per_share"),
        ]
        for label, key, unit, info_key in assumption_rows:
            saved = book_valuation.manual_inputs.get(key, {})
            cols = st.columns([0.30, 0.22, 0.35, 0.13])
            with cols[0]:
                _point_label(label, info_key)
            value = cols[1].text_input("Wert", value=saved.get("value") or "", key=f"book-input-{key}")
            note = cols[2].text_input("Begründung", value=saved.get("note") or "", key=f"book-input-note-{key}")
            if cols[3].button("Speichern", key=f"book-input-save-{key}", disabled=not value.strip()):
                with get_session() as session:
                    fresh = get_analysis(session, current_analysis_id() or analysis.id)
                    if fresh is not None:
                        upsert_book_assumption(session, fresh, key=key, value=Decimal(value.replace(",", ".")), note=note or "Manuell geprüft.", unit=unit)
                st.rerun()
    with st.expander("Multiplikatorenmethode erklären"):
        for point in section.points:
            _point_label(point.label, point.info_key)
    st.subheader("Marktposition")
    with get_session() as session:
        fresh = get_analysis(session, current_analysis_id() or analysis.id)
        saved_book_inputs = load_book_assumptions(session, fresh) if fresh is not None else {}
    porter_rows = [
        ("Rivalitäten unter bestehenden Wettbewerbern", "rivalry_existing_competitors"),
        ("Bedrohung durch neue Anbieter", "threat_new_entrants"),
        ("Verhandlungsstärke der Lieferanten", "supplier_power"),
        ("Verhandlungsstärke der Abnehmer", "buyer_power"),
        ("Bedrohung durch Ersatzprodukte", "threat_substitutes"),
    ]
    for label, key in porter_rows:
        cols = st.columns([0.45, 0.15, 0.40])
        saved = saved_book_inputs.get(key)
        with cols[0]:
            _point_label(label, "market_position")
        score = cols[1].number_input("Punkte", min_value=0.0, max_value=5.0, step=0.5, value=float(saved.value) if saved and saved.value is not None else 0.0, key=f"porter-{key}")
        note = cols[2].text_input("Begründung", value=saved.note if saved and saved.note else "", key=f"porter-note-{key}")
        if st.button("Speichern", key=f"porter-save-{key}"):
            with get_session() as session:
                fresh = get_analysis(session, current_analysis_id() or analysis.id)
                if fresh is not None:
                    upsert_book_assumption(session, fresh, key=key, value=Decimal(str(score)), note=note, unit="points")
            st.rerun()
    st.caption("Diese qualitativen Punkte werden manuell begründet und persistent gespeichert; automatische KI-Bewertung wird hier bewusst nicht gesetzt.")
    quality = state.stages["BUSINESS_QUALITY"].payload.get("result", {})
    with st.expander("Zusätzliche Qualitätsanalyse"):
        _point_label("Unternehmensqualität", "quality_summary")
        st.metric("Gesamtqualität", quality.get("overall_score") if quality.get("overall_score") is not None else "Nicht verfügbar")
        _point_label("Datenvertrauen", "data_confidence")
        st.write("Datenlage wird separat von der Unternehmensqualität betrachtet.")


def _render_summary() -> None:
    st.header("13. Zusammenfassung")
    _info_button("summary")
    issues = finalization_issues(state, book_valuation)
    checks = []
    info_notes = []
    if state.stages["FINANCIAL_DATA"].status == "REVIEW_REQUIRED":
        checks.append("Einzelne Finanzdaten benötigen noch eine semantische Prüfung.")
    if vm.market_notes:
        for note in vm.market_notes:
            if "Unternehmenswert" in note or "Nettoverschuldung" in note:
                checks.append(note)
            else:
                info_notes.append(note)
    if state.stages["ASSUMPTIONS"].status == "REVIEW_REQUIRED":
        checks.append("Bewertungsannahmen müssen noch geprüft oder freigegeben werden.")
    if info_notes:
        st.subheader("Informationen")
        for item in info_notes:
            st.write(f"- {item}")
    if checks:
        st.subheader("Was sollte geprüft werden?")
        for item in checks:
            st.write(f"- {item}")
    if vm.scenario_rows:
        st.subheader("Bewertungsbandbreite")
        st.dataframe(pd.DataFrame(vm.scenario_rows), width="stretch", hide_index=True)
    hard_issues = [issue for issue in issues if issue.blocking]
    if hard_issues:
        st.subheader("Aktuelle offene Punkte")
        _render_issue_list(hard_issues, blocking=True)
    _render_historical_warnings(issues)
    st.info("Gespeichert werden alle Werte, nachdem du auf Speichern, Bestätigen oder Übernehmen geklickt hast. Nur eingetippte, aber nicht gespeicherte Werte gehen beim Schließen verloren.")
    st.write("Keine Kauf-, Halte- oder Verkaufsempfehlung.")


with get_session() as session:
    analysis = render_analysis_selector(session, key="analysis-main-selector")
    if analysis is None:
        st.info("Zuerst unter Unternehmen eine Analyse anlegen.")
        st.stop()
    state = refresh_local_analysis_stages(session, analysis)
    book_valuation = build_book_valuation_for_analysis(session, analysis, state)

vm = build_analysis_view_model(state, book_valuation_result=book_valuation)

st.title("Analyse")
st.caption("Die Analyse folgt der Excel-/Buchlogik von oben nach unten. Die Berechnungen stammen ausschließlich aus den freigegebenen Frozen Engines.")

header = st.columns(6)
header[0].metric("Unternehmen", vm.company_name)
header[1].metric("Ticker", vm.ticker)
header[2].metric("Stichtag", vm.as_of_date)
header[3].metric("Aktueller Kurs", vm.market_price)
header[4].metric("Währung", f"{vm.financial_currency} / {vm.trading_currency}")
header[5].metric("Historie", vm.history_label)

st.subheader("Status")
status_cols = st.columns(len(vm.status_line))
for col, (label, value) in zip(status_cols, vm.status_line.items()):
    with col:
        _point_label(label, vm.status_info_keys[label])
        st.write(value)

st.subheader("Inhaltsverzeichnis")
st.write(" · ".join(section.title for section in ANALYSIS_SECTIONS))

years = available_years(vm, default=5)
history_options = {"5 Jahre": 5, "10 Jahre": 10, "Alle": 1000}
selected_window = st.segmented_control("Historienanzeige", options=list(history_options), default="5 Jahre")
years = available_years(vm, default=history_options[selected_window])

for key in (
    "income_statement",
    "balance_sheet",
    "cash_flow",
    "profitability",
    "financial_stability",
    "debt",
    "working_capital",
    "cashflow_quality_allocation",
):
    _render_metric_table(key, years)

_render_market_and_multiples(years)
_render_dcf()
_render_quality()
_render_summary()

st.header("Abschluss")
completion_issues = finalization_issues(state, book_valuation)
blockers = [issue for issue in completion_issues if issue.blocking]
if blockers:
    st.warning("Analyse kann noch nicht final eingefroren werden.")
    st.write(f"Noch {len(blockers)} Punkte offen:")
    _render_issue_list(completion_issues, blocking=True)
    _render_historical_warnings(completion_issues)
else:
    st.success("Alle Pflichtstufen sind bereit.")
if st.button("Analyse abschließen und einfrieren", type="primary", disabled=bool(blockers) or analysis.status == AnalysisStatus.COMPLETED):
    with get_session() as session:
        fresh = get_analysis(session, current_analysis_id() or analysis.id)
        if fresh is not None:
            try:
                complete_analysis_if_ready(session, fresh)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

with st.expander("Technische Details anzeigen"):
    st.json(vm.technical_payload)
