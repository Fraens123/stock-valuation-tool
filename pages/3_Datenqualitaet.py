from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from stock_valuation.analyses.service import AnalysisFrozenError, get_analysis, list_analyses
from stock_valuation.data.providers.alphavantage import AlphaVantageProvider
from stock_valuation.data.providers.base import ProviderError
from stock_valuation.data.snapshot_service import sync_alphavantage_depreciation_amortization
from stock_valuation.database.models import AnalysisStatus
from stock_valuation.database.session import get_session, init_database
from stock_valuation.validation.service import (
    metric_validation_gates,
    phase_3a_data_readiness,
    validate_asml_primary_source,
)


load_dotenv()
init_database()
st.set_page_config(page_title="Datenqualität", layout="wide")

GATE_LABELS = {
    "approved": "✅ FREIGEGEBEN",
    "review": "⚠️ PRÜFEN",
    "blocked": "❌ GESPERRT",
}


st.title("Datenqualität")
st.caption(
    "Provider werden nicht pauschal freigegeben. Entscheidend ist, ob ein konkretes Rohdatenfeld "
    "gegen eine Primärquelle fachlich bestanden hat. Die normalen Feld-Gates verwenden nur den "
    "gespeicherten Snapshot und benötigen keine API-Requests."
)

with get_session() as session:
    analyses = list_analyses(session, include_archived=True)
    options = {
        f"{item.company.name} · {item.as_of_date} · R{item.revision_number}": item.id
        for item in analyses
    }

if not options:
    st.info("Noch keine Analyse vorhanden.")
    st.stop()

selected = st.selectbox("Analyse", list(options))
analysis_id = options[selected]

with get_session() as session:
    analysis = get_analysis(session, analysis_id)
    if analysis is None:
        st.error("Analyse nicht gefunden.")
        st.stop()
    results = validate_asml_primary_source(session, analysis)
    editable = analysis.status in {AnalysisStatus.DRAFT, AnalysisStatus.IN_PROGRESS}

if analysis.company.ticker.upper() != "ASML":
    st.info("Der automatische Primärquellen-Gate ist derzeit für den ASML-Referenzfall implementiert.")
    st.stop()

if not results:
    st.warning("Für diese Analyse wurden noch keine validierbaren Alpha-Vantage-Daten gefunden.")
    st.stop()

gates = metric_validation_gates(results)
readiness = phase_3a_data_readiness(gates)

approved = sum(gate.status == "approved" for gate in gates)
review = sum(gate.status == "review" for gate in gates)
blocked = sum(gate.status == "blocked" for gate in gates)

cols = st.columns(3)
cols[0].metric("Felder freigegeben", approved)
cols[1].metric("Felder prüfen", review)
cols[2].metric("Felder gesperrt", blocked)

st.subheader("Feldfreigabe")
st.write(
    "Ein Feld wird nur freigegeben, wenn **alle vorhandenen 2024/2025-Primärquellenchecks PASS** "
    "sind. Ein einziges FAIL oder MISSING sperrt das Feld. Damit kann ein gutes Jahr eine "
    "problematische Historie nicht verdecken."
)

gate_rows = [
    {
        "Status": GATE_LABELS[gate.status],
        "Interner Schlüssel": gate.metric,
        "Geprüfte Jahre": gate.years_checked,
        "PASS": gate.pass_count,
        "WARN": gate.warn_count,
        "FAIL": gate.fail_count,
        "MISSING": gate.missing_count,
        "Kritisch": gate.critical,
        "Begründung": gate.reason,
    }
    for gate in gates
]
st.dataframe(pd.DataFrame(gate_rows), use_container_width=True, hide_index=True)

st.subheader("Datenbereitschaft Phase 3A")
st.caption(
    "Dies prüft nur die Rohdatenbasis. Noch offene Buch-/Methodikfragen bleiben weiterhin separat "
    "blockierend und werden durch einen grünen Datenstatus nicht automatisch entschieden."
)
readiness_rows = [
    {
        "Kennzahl": row["metric"],
        "Datenstatus": "✅ BEREIT" if row["ready"] else "❌ BLOCKIERT",
        "Benötigte Felder": row["required"],
        "Blockiert durch": row["blocked_by"] or "—",
    }
    for row in readiness
]
st.dataframe(pd.DataFrame(readiness_rows), use_container_width=True, hide_index=True)

st.info(
    "Aktueller Grundsatz: Umsatz-/Ergebniskennzahlen dürfen auf freigegebenen Feldern aufbauen. "
    "Working-Capital- und DCF-Kennzahlen bleiben gesperrt, solange z. B. Forderungen, CAPEX oder "
    "Operating Cash Flow die Primärquellenprüfung nicht bestehen."
)

st.divider()
st.subheader("D&A-Rohfelddiagnose")
st.caption(
    "Die Diagnose zeigte für ASML, dass `depreciationAndAmortization` aus dem "
    "`INCOME_STATEMENT` die offiziellen D&A-Kontrollwerte 2025 (1.025,9 Mio. €) und 2024 "
    "(918,6 Mio. €) exakt trifft. Das Cashflow-Feld weicht 2024 ab und bleibt deshalb nur "
    "Cross-Check."
)

api_key_available = bool(os.getenv("ALPHA_VANTAGE_API_KEY"))
if not api_key_available:
    st.warning("Für die optionale Diagnose/Reparatur fehlt `ALPHA_VANTAGE_API_KEY` in der lokalen `.env`.")

button_cols = st.columns(2)
with button_cols[0]:
    if st.button(
        "D&A-Rohfelder prüfen (2 Requests)",
        disabled=not api_key_available,
        help="Technische Diagnose; verändert den Snapshot nicht.",
    ):
        try:
            provider = AlphaVantageProvider()
            with st.spinner("Prüfe D&A-Rohfelder für ASML …"):
                rows = provider.probe_depreciation_fields("ASML")
            if not rows:
                st.warning("In den beiden Statements wurden keine passenden Rohfelder gefunden.")
            else:
                st.success(
                    f"Diagnose abgeschlossen: {len(rows)} passende Rohfeld-Zeilen gefunden. "
                    "Es wurden keine Snapshot-Daten verändert."
                )
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        except ProviderError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.exception(exc)

with button_cols[1]:
    if st.button(
        "D&A-Mapping anwenden (1 Request)",
        type="primary",
        disabled=not api_key_available or not editable,
        help=(
            "Lädt nur INCOME_STATEMENT und ersetzt ausschließlich die D&A-Serie im bestehenden "
            "Snapshot. Alle anderen 720 Rohdaten bleiben unverändert."
        ),
    ):
        try:
            provider = AlphaVantageProvider()
            with get_session() as session:
                current = get_analysis(session, analysis_id)
                if current is None:
                    raise ValueError("Analyse nicht gefunden.")
                with st.spinner("Aktualisiere nur die D&A-Serie aus INCOME_STATEMENT …"):
                    count = sync_alphavantage_depreciation_amortization(
                        session,
                        current,
                        provider,
                        symbol="ASML",
                    )
            st.success(
                f"D&A-Mapping aktualisiert: {count} Jahreswerte gespeichert. "
                "Verbraucht wurde genau 1 Alpha-Vantage-Request."
            )
            st.rerun()
        except (ProviderError, AnalysisFrozenError, ValueError) as exc:
            st.error(str(exc))
        except Exception as exc:
            st.exception(exc)

if not editable:
    st.caption(
        "Die ausgewählte Analyse ist abgeschlossen/archiviert. Das D&A-Mapping kann nur in einer "
        "offenen Revision geändert werden."
    )
