from __future__ import annotations

import streamlit as st

from stock_valuation.analyses.service import get_analysis, list_analyses
from stock_valuation.database.models import AnalysisStatus


STATUS_LABELS = {
    AnalysisStatus.DRAFT: "Entwurf",
    AnalysisStatus.IN_PROGRESS: "In Bearbeitung",
    AnalysisStatus.COMPLETED: "Abgeschlossen",
    AnalysisStatus.ARCHIVED: "Archiviert",
}


def render_navigation() -> None:
    """Render the user-facing navigation without technical diagnostics pages."""
    with st.sidebar:
        st.markdown("### Aktienanalyse")
        st.page_link("app.py", label="Uebersicht")
        st.page_link("pages/0_Unternehmen.py", label="Unternehmen")
        st.page_link("pages/1_Datenimport.py", label="Finanzdaten")
        st.page_link("pages/3_Analyse.py", label="Analyse")
        st.page_link("pages/2_Manuelle_Daten.py", label="Manuelle Daten")
        st.page_link("pages/4_Kennzahlen.py", label="Kennzahlen-Details")


def analysis_label(analysis) -> str:
    return (
        f"{analysis.company.name} · {analysis.as_of_date} · "
        f"R{analysis.revision_number} · {STATUS_LABELS.get(analysis.status, analysis.status.value)}"
    )


def current_analysis_id() -> int | None:
    value = st.session_state.get("selected_analysis_id")
    return int(value) if value is not None else None


def render_analysis_selector(
    session,
    *,
    include_archived: bool = True,
    key: str = "global-analysis-selector",
):
    analyses = list_analyses(session, include_archived=include_archived)
    if not analyses:
        st.session_state.pop("selected_analysis_id", None)
        return None
    valid_ids = {item.id for item in analyses}
    if st.session_state.get("selected_analysis_id") not in valid_ids:
        st.session_state["selected_analysis_id"] = analyses[0].id
    labels = {analysis_label(item): item.id for item in analyses}
    current_id = st.session_state["selected_analysis_id"]
    index = next((idx for idx, item in enumerate(labels.values()) if item == current_id), 0)
    selected_label = st.selectbox("Analyse", list(labels), index=index, key=key)
    selected_id = labels[selected_label]
    st.session_state["selected_analysis_id"] = selected_id
    return get_analysis(session, selected_id)
