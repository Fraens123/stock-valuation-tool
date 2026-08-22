from __future__ import annotations

from datetime import date

import streamlit as st

from stock_valuation.analyses.service import create_analysis, get_or_create_company, list_analyses
from stock_valuation.database.session import get_session, init_database
from stock_valuation.ui.components import metric_heading


st.set_page_config(page_title="Aktienanalyse & Unternehmensbewertung", layout="wide")
init_database()

st.title("Aktienanalyse & Unternehmensbewertung")
st.caption("Geführte Analyse nach der bestehenden Excel-/Schmidlin-Methodik")

mode = st.sidebar.radio(
    "Arbeitsbereich",
    ["Start", "Neue Analyse", "Analyse öffnen", "Analysen vergleichen"],
)

if mode == "Start":
    st.header("Unternehmen auswählen")
    query = st.text_input("Unternehmen, Ticker oder ISIN", value="ASML")
    if query.strip().upper() == "ASML":
        st.success("ASML Holding N.V. · ASML · Euronext Amsterdam · EUR")
        c1, c2 = st.columns(2)
        with c1:
            st.info("Neue Analyse über die Seitenleiste starten.")
        with c2:
            st.info("Bestehende Analysen können später geöffnet und verglichen werden.")
    else:
        st.info("Die echte Unternehmenssuche wird in Phase 0/2 an einen Provider angebunden.")

elif mode == "Neue Analyse":
    st.header("Neue Analyse starten")
    with st.form("new-analysis"):
        name = st.text_input("Unternehmen", value="ASML Holding N.V.")
        ticker = st.text_input("Ticker", value="ASML")
        isin = st.text_input("ISIN", value="NL0010273215")
        provider_symbol = st.text_input("Provider-Symbol", value="ASML.AS")
        exchange = st.text_input("Börse", value="Euronext Amsterdam")
        currency = st.text_input("Währung", value="EUR")
        analysis_date = st.date_input("Analyse-Stichtag", value=date.today())
        submitted = st.form_submit_button("Analyse anlegen")

    if submitted:
        with get_session() as session:
            company = get_or_create_company(
                session,
                name=name,
                ticker=ticker,
                isin=isin or None,
                exchange=exchange or None,
                currency=currency,
                provider_symbol=provider_symbol or None,
            )
            analysis = create_analysis(session, company=company, as_of_date=analysis_date)
            st.success(f"Analyse #{analysis.id} · Revision {analysis.revision_number} angelegt.")

elif mode == "Analyse öffnen":
    st.header("Bestehende Analyse öffnen")
    with get_session() as session:
        analyses = list_analyses(session)
        if not analyses:
            st.info("Noch keine Analysen gespeichert.")
        else:
            options = {
                f"{a.company.name} · {a.as_of_date} · R{a.revision_number} · {a.status.value}": a
                for a in analyses
            }
            selected_label = st.selectbox("Analyse", list(options))
            selected = options[selected_label]
            st.write(f"**Unternehmen:** {selected.company.name}")
            st.write(f"**Stichtag:** {selected.as_of_date}")
            st.write(f"**Revision:** {selected.revision_number}")
            st.write(f"**Status:** {selected.status.value}")

            st.divider()
            metric_heading("roe")
            st.metric("Aktueller Wert", "—")
            st.caption("Historische Daten und Berechnung folgen in Phase 2/3.")

            st.divider()
            st.subheader("Kapitelstruktur")
            st.write(
                "Ertrag & Rentabilität · Finanzielle Stabilität · Working Capital · "
                "Geschäftsmodell · Ausschüttung · Bewertungskennzahlen · Unternehmensbewertung"
            )

elif mode == "Analysen vergleichen":
    st.header("Analysen vergleichen")
    with get_session() as session:
        analyses = list_analyses(session)
        if len(analyses) < 2:
            st.info("Mindestens zwei Analyse-Revisionen werden benötigt.")
        else:
            labels = {
                f"{a.company.name} · {a.as_of_date} · R{a.revision_number}": a for a in analyses
            }
            left, right = st.columns(2)
            with left:
                old_label = st.selectbox("Ältere Analyse", list(labels), key="old")
            with right:
                new_label = st.selectbox("Neuere Analyse", list(labels), key="new")
            st.caption("Der strukturierte Fundamentaldaten-/Prognose-/Bewertungs-Diff folgt in Phase 0.5.")
