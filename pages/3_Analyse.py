from __future__ import annotations

from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st

from stock_valuation.analyses.service import get_analysis
from stock_valuation.database.models import AnalysisStatus
from stock_valuation.database.session import get_session, init_database
from stock_valuation.ui.analysis_layout import ANALYSIS_SECTIONS
from stock_valuation.ui.analysis_view_model import available_years, build_analysis_view_model, table_rows
from stock_valuation.ui.info_catalog import INFO_CATALOG, InfoEntry
from stock_valuation.ui.labels_de import format_currency_compact_de, format_date_de, issue_label
from stock_valuation.ui.navigation import STATUS_LABELS, current_analysis_id, render_analysis_selector, render_navigation
from stock_valuation.valuation_assumptions.approvals import approve_recommended_value, override_assumption
from stock_valuation.valuation_assumptions.models import AssumptionRecommendation
from stock_valuation.workflow.service import complete_analysis_if_ready, finalization_blockers, refresh_local_analysis_stages


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
    st.caption("Equity-Methode")
    st.write(section.intro)
    if state.stages["ASSUMPTIONS"].status == "REVIEW_REQUIRED":
        st.warning("Diese Bewertung verwendet noch nicht vollständig freigegebene Annahmen.")
    for point in section.points[:5]:
        _point_label(point.label, point.info_key)
        row = next((item for item in vm.assumption_rows if item["key"] == point.backend_key), None)
        if row:
            st.write(f"Empfehlung: **{row['Empfehlung']}** · Status: **{row['Status']}**")
            st.caption(f"Hauptanker: {row['Hauptanker']}")
            st.caption(row["Begründung"])
    st.subheader("Szenarien")
    if vm.scenario_rows:
        st.dataframe(pd.DataFrame(vm.scenario_rows), width="stretch", hide_index=True)
    else:
        st.info("Noch keine Bewertungsvorschau verfügbar.")
    st.subheader("Annahmen prüfen")
    _render_assumption_actions()


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


def _render_quality() -> None:
    section = next(item for item in vm.sections if item.key == "quality")
    st.header(section.title)
    st.caption(section.intro)
    quality = state.stages["BUSINESS_QUALITY"].payload.get("result", {})
    cols = st.columns(2)
    with cols[0]:
        _point_label("Unternehmensqualität", "quality_summary")
        st.metric("Gesamtqualität", quality.get("overall_score") if quality.get("overall_score") is not None else "Nicht verfügbar")
        st.caption(quality.get("assessment") or "")
    with cols[1]:
        _point_label("Datenvertrauen", "data_confidence")
        st.write("Datenlage wird separat von der Unternehmensqualität betrachtet.")
    components = quality.get("component_scores", [])
    if components:
        rows = [
            {
                "Bereich": item.get("component_id", "").replace("_", " ").title(),
                "Score": item.get("score"),
                "Status": item.get("status"),
                "Einflussgrößen": ", ".join(item.get("contributing_metrics", ())),
            }
            for item in components
        ]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def _render_summary() -> None:
    st.header("13. Zusammenfassung")
    _info_button("summary")
    checks = []
    if state.stages["FINANCIAL_DATA"].status == "REVIEW_REQUIRED":
        checks.append("Einzelne Finanzdaten benötigen noch eine semantische Prüfung.")
    if vm.market_notes:
        checks.extend(vm.market_notes)
    if state.stages["ASSUMPTIONS"].status == "REVIEW_REQUIRED":
        checks.append("Bewertungsannahmen müssen noch geprüft oder freigegeben werden.")
    if checks:
        st.subheader("Was sollte geprüft werden?")
        for item in checks:
            st.write(f"- {item}")
    if vm.scenario_rows:
        st.subheader("Bewertungsbandbreite")
        st.dataframe(pd.DataFrame(vm.scenario_rows), width="stretch", hide_index=True)
    st.write("Keine Kauf-, Halte- oder Verkaufsempfehlung.")


with get_session() as session:
    analysis = render_analysis_selector(session, key="analysis-main-selector")
    if analysis is None:
        st.info("Zuerst unter Unternehmen eine Analyse anlegen.")
        st.stop()
    state = refresh_local_analysis_stages(session, analysis)

vm = build_analysis_view_model(state)

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
blockers = list(finalization_blockers(state))
if blockers:
    st.warning("Analyse kann noch nicht final eingefroren werden.")
    for blocker in blockers:
        st.write(f"- {issue_label(blocker)}")
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
