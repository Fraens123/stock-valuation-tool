from __future__ import annotations

from statistics import median

import pandas as pd
import streamlit as st

from stock_valuation.analyses.service import AnalysisFrozenError, get_analysis, list_analyses
from stock_valuation.data.preferred_data import load_preferred_data_states
from stock_valuation.database.models import AnalysisStatus
from stock_valuation.database.session import get_session, init_database
from stock_valuation.knowledge.catalog import get_metric_info
from stock_valuation.metrics.service import (
    MetricDataQualityError,
    calculate_and_store_phase_3a,
    load_metric_series,
    phase_3a_method_states,
)
from stock_valuation.ui.components import metric_heading
from stock_valuation.ui.navigation import render_navigation


init_database()
st.set_page_config(page_title="Kennzahlen", layout="wide")
render_navigation()

STATUS_LABELS = {
    AnalysisStatus.DRAFT: "Entwurf",
    AnalysisStatus.IN_PROGRESS: "In Bearbeitung",
    AnalysisStatus.COMPLETED: "Abgeschlossen",
    AnalysisStatus.ARCHIVED: "Archiviert",
}
METHOD_STATUS = {
    "implemented": "✅ AKTIV",
    "methodology_blocked": "🟡 METHODIK OFFEN",
    "data_blocked": "❌ DATEN BLOCKIERT",
}


def _analysis_label(analysis) -> str:
    return (
        f"{analysis.company.name} · {analysis.as_of_date} · "
        f"R{analysis.revision_number} · {STATUS_LABELS.get(analysis.status, analysis.status.value)}"
    )


def _metric_title(metric_id: str) -> str:
    info = get_metric_info(metric_id) or {}
    title_de = info.get("title_de", metric_id)
    title_en = info.get("title_en")
    return f"{title_de} ({title_en})" if title_en else title_de


def _render_percentage_series(
    analysis_id: int,
    metric_id: str,
    value_label: str,
    *,
    empty_message: str,
) -> None:
    with get_session() as session:
        series = load_metric_series(session, analysis_id, metric_id)

    if not series:
        st.warning(empty_message)
        return

    values = [float(row.value * 100) for row in series if row.value is not None]
    years = [int(row.period) for row in series if row.value is not None]
    data = pd.DataFrame({"Jahr": years, value_label: values})
    visible = data.tail(10).copy()
    if visible.empty:
        st.warning("Keine berechenbaren Jahreswerte vorhanden.")
        return

    latest = visible.iloc[-1][value_label]
    last_five = visible.tail(5)[value_label].tolist()
    ten_values = visible[value_label].tolist()

    summary = st.columns(4)
    summary[0].metric("Aktuell", f"{latest:.2f} %")
    summary[1].metric("5J Ø", f"{sum(last_five) / len(last_five):.2f} %")
    summary[2].metric("5J Median", f"{median(last_five):.2f} %")
    summary[3].metric("10J Median", f"{median(ten_values):.2f} %")

    st.line_chart(visible.set_index("Jahr")[value_label])
    st.dataframe(
        visible.sort_values("Jahr", ascending=False),
        width="stretch",
        hide_index=True,
        column_config={
            value_label: st.column_config.NumberColumn(value_label, format="%.2f %%")
        },
    )

    calculation_versions = sorted({row.calculation_version for row in series})
    st.caption(
        "Datenbasis: verifizierte Preferred Data · Basis: reported · Berechnungsversion: "
        + ", ".join(calculation_versions)
        + " · Standardanzeige: letzte 10 berechenbare Geschäftsjahre"
    )


st.title("Kennzahlenanalyse")
st.caption(
    "Hier stehen nur die **Ergebnisse der Analyse**. Import, Quellenprüfung, 10-Jahres-Mapping, "
    "Preferred-Data-Status und Korrekturen werden vollständig unter **Finanzdaten** erledigt. "
    "Diese Seite verursacht keine externen API-Requests."
)

with get_session() as session:
    analyses = list_analyses(session, include_archived=True)
    options = {_analysis_label(a): a.id for a in analyses}

if not options:
    st.info("Zuerst eine Analyse anlegen und Fundamentaldaten importieren.")
    st.stop()

selected_label = st.selectbox("Analyse", list(options))
analysis_id = options[selected_label]

with get_session() as session:
    analysis = get_analysis(session, analysis_id)
    if analysis is None:
        st.error("Analyse nicht gefunden.")
        st.stop()
    editable = analysis.status in {AnalysisStatus.DRAFT, AnalysisStatus.IN_PROGRESS}
    preferred_states = load_preferred_data_states(session, analysis_id)
    header = st.columns(4)
    header[0].metric("Unternehmen", analysis.company.name)
    header[1].metric("Stichtag", str(analysis.as_of_date))
    header[2].metric("Revision", f"R{analysis.revision_number}")
    header[3].metric("Status", STATUS_LABELS.get(analysis.status, analysis.status.value))

# Derived metrics behave like a local cache: on editable analyses they are synchronized whenever
# the page is opened/rerun. Identical input hashes cause no database rewrite.
auto_calculation_error: str | None = None
if editable and preferred_states:
    try:
        with get_session() as session:
            current = get_analysis(session, analysis_id)
            if current is None:
                raise ValueError("Analyse nicht gefunden.")
            calculate_and_store_phase_3a(session, current)
    except (MetricDataQualityError, AnalysisFrozenError, ValueError) as exc:
        auto_calculation_error = str(exc)

st.divider()
st.subheader("Kapitel 2 – Ertrag und Rentabilität")
st.caption(
    "Methodisch freigegebene Kennzahlen werden automatisch aus Preferred Data berechnet. "
    "Für Änderungen an Rohdaten oder Reviews ist kein zusätzlicher Berechnungsbutton nötig."
)

if auto_calculation_error:
    st.warning(
        auto_calculation_error
        + " Prüfe den Importstatus unter **Finanzdaten**; dort stehen alle offenen Daten-/Mappingfälle."
    )
elif not editable:
    st.caption(
        "Die Analyse ist eingefroren. Angezeigt werden die mit dieser Revision gespeicherten "
        "Kennzahlen; sie werden nicht nachträglich verändert."
    )

metric_heading("ebit_margin")
st.caption(
    "EBIT / Revenue aus verifizierter Preferred Data. Für ASML bleibt die validierte "
    "Operating-Income-Zuordnung als EBIT-Basis bestehen; andere Unternehmen verwenden das interne EBIT-Feld."
)
_render_percentage_series(
    analysis_id,
    "ebit_margin",
    "EBIT-Marge %",
    empty_message="Für die EBIT-Marge sind aktuell keine vollständig freigegebenen Jahresinputs vorhanden.",
)

st.divider()
metric_heading("ebitda_margin")
st.caption(
    "(EBIT + D&A) / Revenue aus verifizierter Preferred Data. Provider-EBITDA wird nicht direkt verwendet."
)
_render_percentage_series(
    analysis_id,
    "ebitda_margin",
    "EBITDA-Marge %",
    empty_message="Für die EBITDA-Marge sind aktuell keine vollständig freigegebenen Jahresinputs vorhanden.",
)

open_states = [state for state in phase_3a_method_states() if state.status != "implemented"]
with st.expander(
    f"Weitere Kennzahlen dieses Kapitels – Methodik noch offen ({len(open_states)})",
    expanded=False,
):
    st.caption(
        "Diese Kennzahlen werden erst aktiviert, wenn die jeweilige Buchdefinition verifiziert ist. "
        "Bis dahin wird keine Formel geraten."
    )
    method_rows = [
        {
            "Kennzahl": _metric_title(state.metric_id),
            "Status": METHOD_STATUS[state.status],
            "Warum": state.reason,
        }
        for state in open_states
    ]
    st.dataframe(pd.DataFrame(method_rows), width="stretch", hide_index=True)

    for state in open_states:
        info = get_metric_info(state.metric_id) or {}
        chapter = info.get("chapter", "—")
        kindle = info.get("kindle_page", "—")
        st.markdown(
            f"**{_metric_title(state.metric_id)}** — {METHOD_STATUS[state.status]}  "
            f"\nKapitel {chapter}, Kindle-Seite {kindle}: {state.reason}"
        )
