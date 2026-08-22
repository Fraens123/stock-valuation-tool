from __future__ import annotations

import pandas as pd
import streamlit as st

from stock_valuation.analyses.service import get_analysis, list_analyses
from stock_valuation.database.session import get_session, init_database
from stock_valuation.validation.service import (
    metric_validation_gates,
    phase_3a_data_readiness,
    validate_asml_primary_source,
)


init_database()
st.set_page_config(page_title="ASML Datenqualität – Diagnose", layout="wide")

st.title("ASML Datenqualität – Diagnose")
st.caption(
    "Referenzfall für die Entwicklung der feldweisen Datenqualitätsarchitektur. Diese Seite ist "
    "kein normaler Arbeitsschritt für neue Aktienanalysen."
)

with get_session() as session:
    analyses = [
        item
        for item in list_analyses(session, include_archived=True)
        if item.company.ticker.upper() == "ASML"
    ]
    options = {
        f"{item.company.name} · {item.as_of_date} · R{item.revision_number}": item.id
        for item in analyses
    }

if not options:
    st.info("Keine ASML-Analyse vorhanden.")
    st.stop()

selected = st.selectbox("Analyse", list(options))
analysis_id = options[selected]

with get_session() as session:
    analysis = get_analysis(session, analysis_id)
    if analysis is None:
        st.stop()
    results = validate_asml_primary_source(session, analysis)

if not results:
    st.warning("Keine validierbaren ASML-Daten vorhanden.")
    st.stop()

gates = metric_validation_gates(results)
readiness = phase_3a_data_readiness(gates)

st.subheader("Feldfreigabe")
st.dataframe(
    pd.DataFrame(
        [
            {
                "Metrik": gate.metric,
                "Status": gate.status,
                "PASS": gate.pass_count,
                "WARN": gate.warn_count,
                "FAIL": gate.fail_count,
                "MISSING": gate.missing_count,
                "Begründung": gate.reason,
            }
            for gate in gates
        ]
    ),
    use_container_width=True,
    hide_index=True,
)

st.subheader("Phase-3A-Datenbereitschaft")
st.dataframe(pd.DataFrame(readiness), use_container_width=True, hide_index=True)
