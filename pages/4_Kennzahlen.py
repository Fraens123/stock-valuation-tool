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
DATA_STATUS_LABELS = {
    "confirmed_override": "✅ Bestätigte Korrektur",
    "primary_source": "✅ Primärquelle",
    "reviewed_pass": "✅ ChatGPT PASS",
    "legacy_primary_validated": "✅ Primärquellen-validiert",
    "provider_unverified": "🟡 Ungeprüfter Providerwert",
    "review_stale": "🟡 Prüfung veraltet",
    "unclear": "⚠️ UNKLAR",
    "review_conflict": "❌ Abweichung offen",
    "derive_required": "🔵 selbst ableiten",
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
        use_container_width=True,
        hide_index=True,
        column_config={value_label: st.column_config.NumberColumn(value_label, format="%.2f %%")},
    )

    calculation_versions = sorted({row.calculation_version for row in series})
    st.caption(
        "Datenbasis: verifizierte Preferred Data · Basis: reported · Berechnungsversion: "
        + ", ".join(calculation_versions)
        + " · Standardanzeige: letzte 10 berechenbare Geschäftsjahre"
    )


st.title("Kennzahlenanalyse")
st.caption(
    "Kennzahlen werden ausschließlich aus dem gespeicherten Analyse-Snapshot und der verifizierten "
    "Preferred-Data-Schicht berechnet. Ein ungeprüfter Alpha-Vantage-Wert ist kein automatischer "
    "Berechnungsinput. Diese Seite verursacht keine API-Requests."
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

st.divider()
st.subheader("Berechnungsbasis – Preferred Data")
if not preferred_states:
    st.warning("Noch keine bevorzugten Finanzdaten vorhanden.")
else:
    ready_count = sum(state.calculation_ready for state in preferred_states)
    unresolved_count = sum(
        state.quality_status in {"unclear", "review_conflict", "review_stale", "derive_required"}
        for state in preferred_states
    )
    unverified_count = sum(state.quality_status == "provider_unverified" for state in preferred_states)
    source_count = sum(
        state.quality_status in {"primary_source", "confirmed_override"}
        for state in preferred_states
    )

    cols = st.columns(4)
    cols[0].metric("Berechnungsbereit", ready_count)
    cols[1].metric("Ungeprüfte Providerwerte", unverified_count)
    cols[2].metric("Unklar / blockiert", unresolved_count)
    cols[3].metric("Primärquelle / Override", source_count)

    st.caption(
        "Priorität: bestätigter Override → Primärquelle → geprüfter Providerwert. Alpha Vantage "
        "bleibt als Rohdatenquelle gespeichert, wird aber ohne Freigabe nicht still verwendet."
    )

    with st.expander("Preferred-Data-Status im Detail", expanded=False):
        recent_states = sorted(
            preferred_states,
            key=lambda state: (state.fact.period_end, state.fact.metric),
            reverse=True,
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Jahr": state.fact.period_end.year,
                        "Metrik": state.fact.metric,
                        "Verwendete Quelle": state.fact.provider,
                        "Status": DATA_STATUS_LABELS.get(state.quality_status, state.quality_status),
                        "Berechnungsbereit": "Ja" if state.calculation_ready else "Nein",
                        "Review": state.review_verdict,
                        "Entscheidung": state.review_decision,
                        "Begründung": state.reason,
                    }
                    for state in recent_states
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

st.divider()
st.subheader("Kapitel 2 – Ertrag und Rentabilität")
method_rows = [
    {
        "Kennzahl": _metric_title(state.metric_id),
        "Status": METHOD_STATUS[state.status],
        "Warum": state.reason,
    }
    for state in phase_3a_method_states()
]
st.dataframe(pd.DataFrame(method_rows), use_container_width=True, hide_index=True)

st.info(
    "EBIT- und EBITDA-Marge sind methodisch freigegeben. ROE, Umsatzrendite, Kapitalumschlag, "
    "Gesamtkapitalrendite, ROCE und Umsatzverdienstrate warten noch auf die verifizierte Buchdefinition."
)

if editable:
    if st.button("Aktive Kennzahlen aus Preferred Data berechnen", type="primary"):
        try:
            with get_session() as session:
                current = get_analysis(session, analysis_id)
                if current is None:
                    raise ValueError("Analyse nicht gefunden.")
                counts = calculate_and_store_phase_3a(session, current)
            st.success(
                "Berechnung gespeichert: "
                f"{counts.get('ebit_margin', 0)} EBIT-Margen-Jahreswerte, "
                f"{counts.get('ebitda_margin', 0)} EBITDA-Margen-Jahreswerte. "
                "Es wurden ausschließlich berechnungsbereite Preferred-Data-Inputs verwendet."
            )
            if counts.get("ebitda_margin", 0) == 0:
                st.info(
                    "EBITDA-Marge blieb blockiert, weil mindestens ein benötigter Input – typischerweise "
                    "D&A – nicht eindeutig freigegeben ist."
                )
            st.rerun()
        except (MetricDataQualityError, AnalysisFrozenError, ValueError) as exc:
            st.error(str(exc))
else:
    st.caption(
        "Diese Analyse ist eingefroren. Gespeicherte Kennzahlen können angezeigt, aber nicht "
        "mit einer neueren Berechnungsversion überschrieben werden."
    )

st.divider()
metric_heading("ebit_margin")
st.caption(
    "EBIT / Revenue aus verifizierter Preferred Data. Für ASML bleibt die validierte "
    "Operating-Income-Zuordnung als EBIT-Basis bestehen; andere Unternehmen verwenden das interne EBIT-Feld."
)
_render_percentage_series(
    analysis_id,
    "ebit_margin",
    "EBIT-Marge %",
    empty_message="Noch keine berechnungsbereite EBIT-Margen-Serie gespeichert.",
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
    empty_message="Noch keine berechnungsbereite EBITDA-Margen-Serie gespeichert.",
)

st.divider()
st.subheader("Noch offene Kennzahlen dieses Kapitels")
for state in phase_3a_method_states():
    if state.status == "implemented":
        continue
    info = get_metric_info(state.metric_id) or {}
    chapter = info.get("chapter", "—")
    kindle = info.get("kindle_page", "—")
    st.markdown(
        f"**{_metric_title(state.metric_id)}** — {METHOD_STATUS[state.status]}  "
        f"\nKapitel {chapter}, Kindle-Seite {kindle}: {state.reason}"
    )
