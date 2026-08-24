from __future__ import annotations

import os
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from stock_valuation.runtime_dependencies import ensure_runtime_dependencies

ensure_runtime_dependencies()

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from stock_valuation.book_valuation.service import build_book_valuation_for_analysis
from stock_valuation.analyses.service import list_analyses
from stock_valuation.companies.discovery import discover_companies
from stock_valuation.companies.provider_symbols import upsert_provider_symbol
from stock_valuation.companies.service import get_or_create_company, list_companies
from stock_valuation.data.providers.gleif import GLEIFProvider
from stock_valuation.data.providers.sec import SECCompanyFactsProvider
from stock_valuation.database.models import Analysis
from stock_valuation.database.session import get_session, init_database
from stock_valuation.ui.analysis_view_model import build_analysis_view_model
from stock_valuation.ui.navigation import render_navigation
from stock_valuation.workflow.analysis_runner import CompleteAnalysisRunResult, run_complete_analysis
from stock_valuation.workflow.service import build_analysis_state


load_dotenv()
init_database()
st.set_page_config(page_title="Aktienanalyse", layout="wide")
render_navigation()


def _company_label(company) -> str:
    return f"{company.name} · {company.ticker}"


def _result_payload(result: CompleteAnalysisRunResult) -> dict:
    return {
        "analysis_id": result.analysis_id,
        "status": result.status,
        "progress_steps": [asdict(item) for item in result.progress_steps],
        "review_tasks": [asdict(item) for item in result.review_tasks],
        "warnings": result.warnings,
        "market_snapshot_id": result.market_snapshot_id,
        "ready_for_review": result.ready_for_review,
        "ready_for_final": result.ready_for_final,
    }


def _render_progress(payload: dict) -> None:
    st.subheader("Analyse")
    for step in payload.get("progress_steps", ()):
        status = step.get("status")
        marker = "OK" if status == "OK" else "Pruefung" if status == "PRUEFUNG" else status
        st.write(f"**{marker}:** {step.get('label_de')}")
        if step.get("message_de"):
            st.caption(step["message_de"])
    for warning in payload.get("warnings", ()):
        st.warning(warning)


def _render_review_tasks(payload: dict) -> None:
    tasks = payload.get("review_tasks", ())
    priority = [task for task in tasks if task.get("severity") in {"A", "B"}]
    if not tasks:
        st.success("Analyse fertig.")
        return
    st.subheader(f"{len(priority)} Punkt(e) benoetigen deine Pruefung")
    for task in priority[:6]:
        with st.container(border=True):
            st.markdown(f"**{task['title_de']}**")
            st.write(task["description_de"])
            if task.get("suggested_value") is not None:
                st.write(f"Vorschlag: **{task['suggested_value']}**")
            if task.get("blocking_for"):
                st.caption("Relevant fuer: " + ", ".join(task["blocking_for"]))
            actions = task.get("actions", ())[:3]
            cols = st.columns(max(1, len(actions)))
            for idx, action in enumerate(actions):
                if cols[idx].button(action, key=f"task-{task['id']}-{idx}"):
                    st.session_state["selected_analysis_id"] = payload["analysis_id"]
                    if task.get("category") == "Daten pruefen":
                        st.switch_page("pages/1_Datenimport.py")
                    else:
                        st.switch_page("pages/3_Analyse.py")
    hints = [task for task in tasks if task.get("severity") not in {"A", "B"}]
    if hints:
        with st.expander("Weitere Datenhinweise", expanded=False):
            for task in hints:
                st.write(f"**{task['title_de']}**: {task['description_de']}")


def _render_analysis_report(analysis_id: int) -> None:
    with get_session() as session:
        analysis = session.get(Analysis, analysis_id)
        if analysis is None:
            st.error("Analyse wurde nicht gefunden.")
            return
        state = build_analysis_state(session, analysis)
        required = ("CALCULATION", "HISTORICAL_ANALYSIS", "MARKET_DATA", "ASSUMPTIONS", "VALUATION")
        if any(not state.stages[key].payload for key in required):
            st.info("Die Analyse ist noch nicht weit genug vorbereitet.")
            return
        book = build_book_valuation_for_analysis(session, analysis, state)
        vm = build_analysis_view_model(state, book_valuation_result=book)

    st.subheader(vm.company_name)
    st.caption(f"Analyse vom {vm.as_of_date} · {vm.history_label}")
    top = st.columns(4)
    top[0].metric("Aktueller Kurs", vm.market_price)
    top[1].metric("Datenlage", vm.status_line.get("Daten", "-"))
    top[2].metric("Markt", vm.status_line.get("Marktdaten", "-"))
    top[3].metric("Bewertung", vm.status_line.get("Bewertung", "-"))

    for index, section in enumerate(vm.sections, start=1):
        st.markdown(f"### {index}. {section.title}")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Kennzahl": point.label,
                        "Status": point.status_label,
                        "Aktuell": point.latest_value,
                    }
                    for point in section.points
                ]
            ),
            hide_index=True,
            width="stretch",
        )

    if vm.scenario_rows:
        st.markdown("### DCF")
        st.dataframe(pd.DataFrame(vm.scenario_rows), hide_index=True, width="stretch")

    with st.expander("Technische Details", expanded=False):
        st.json(vm.technical_payload)


st.title("Aktienanalyse")
st.caption("Unternehmen auswaehlen, Analyse starten, nur echte Ausnahmen pruefen, Ergebnis lesen.")

with get_session() as session:
    companies = list_companies(session)

selected_company_id = None
if companies:
    labels = {_company_label(company): company.id for company in companies}
    selected_label = st.selectbox("Unternehmen", list(labels))
    selected_company_id = labels[selected_label]
else:
    st.info("Noch kein Unternehmen gespeichert. Suche unten eine Aktie und fuege sie hinzu.")

with st.expander("Unternehmen suchen / neu hinzufuegen", expanded=not bool(companies)):
    query = st.text_input("Name oder Ticker", placeholder="z. B. ASML, Apple, Microsoft")
    if st.button("Unternehmen suchen", disabled=not query.strip()):
        sec_provider = None
        if os.getenv("SEC_USER_AGENT"):
            try:
                sec_provider = SECCompanyFactsProvider()
            except ValueError:
                sec_provider = None
        with st.spinner("Unternehmen wird gesucht ..."):
            candidates, notes = discover_companies(
                query.strip(),
                sec_provider=sec_provider,
                gleif_provider=GLEIFProvider(),
            )
        st.session_state["start_company_candidates"] = candidates
        st.session_state["start_company_notes"] = notes

    for note in st.session_state.get("start_company_notes", ()):
        st.caption(note)

    candidates = st.session_state.get("start_company_candidates", ())
    if candidates:
        candidate_labels = {candidate.display_name: candidate for candidate in candidates}
        candidate_label = st.selectbox("Gefundene Unternehmen", list(candidate_labels))
        candidate = candidate_labels[candidate_label]
        ticker = candidate.ticker or st.text_input("Ticker", key="new-company-ticker").strip().upper()
        if st.button("Unternehmen uebernehmen", disabled=not ticker):
            with get_session() as session:
                company = get_or_create_company(
                    session,
                    name=candidate.name,
                    ticker=ticker,
                    currency=candidate.currency,
                    exchange=candidate.exchange,
                    country=candidate.country,
                )
                if candidate.sec_cik:
                    upsert_provider_symbol(session, company, provider="sec", purpose="cik", symbol=candidate.sec_cik)
                if candidate.lei:
                    upsert_provider_symbol(session, company, provider="gleif", purpose="lei", symbol=candidate.lei)
                selected_company_id = company.id
            st.session_state.pop("start_company_candidates", None)
            st.session_state.pop("start_company_notes", None)
            st.success(f"{candidate.name} wurde gespeichert.")
            st.rerun()

as_of_date = st.date_input("Analyse-Stichtag", value=date.today())
with st.expander("Erweiterte Einstellungen", expanded=False):
    refresh_market_data = st.checkbox("Marktdaten beim Start aktualisieren", value=True)
    search_missing_data = st.checkbox("Fehlende wichtige Werte automatisch suchen", value=True)

if st.button("Analyse starten / aktualisieren", type="primary", disabled=selected_company_id is None):
    with get_session() as session:
        with st.spinner("Analyse wird erstellt ..."):
            result = run_complete_analysis(
                session,
                company_id=int(selected_company_id),
                as_of_date=as_of_date,
                refresh_market_data=refresh_market_data,
                search_missing_data=search_missing_data,
            )
    st.session_state["selected_analysis_id"] = result.analysis_id
    st.session_state["one_click_result"] = _result_payload(result)
    st.rerun()

payload = st.session_state.get("one_click_result")
if payload:
    _render_progress(payload)
    _render_review_tasks(payload)
    actions = st.columns(3)
    if actions[0].button("Analyse ansehen", disabled=not payload.get("analysis_id")):
        st.session_state["show_one_click_report"] = True
    if actions[1].button("Pruefungen bearbeiten", disabled=not payload.get("review_tasks")):
        st.session_state["selected_analysis_id"] = payload["analysis_id"]
        st.switch_page("pages/1_Datenimport.py")
    if actions[2].button("Details anzeigen"):
        st.session_state["selected_analysis_id"] = payload["analysis_id"]
        st.switch_page("pages/3_Analyse.py")

if st.session_state.get("show_one_click_report") and st.session_state.get("selected_analysis_id"):
    _render_analysis_report(int(st.session_state["selected_analysis_id"]))

st.divider()
st.subheader("Analysen")
with get_session() as session:
    analyses = list_analyses(session, include_archived=True)

if analyses:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Unternehmen": analysis.company.name,
                    "Ticker": analysis.company.ticker,
                    "Stichtag": analysis.as_of_date,
                    "Revision": f"R{analysis.revision_number}",
                    "Status": analysis.status.value,
                }
                for analysis in analyses
            ]
        ),
        hide_index=True,
        width="stretch",
    )
else:
    st.caption("Noch keine Analyse vorhanden.")
