from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import select

from stock_valuation.analyses.service import AnalysisFrozenError, get_analysis, list_analyses
from stock_valuation.data.providers.alphavantage import AlphaVantageProvider
from stock_valuation.data.providers.asml_primary import (
    ASMLPrimarySourceError,
    download_2025_us_gaap_workbook,
    parse_primary_source_facts,
    scan_financial_statement_workbook,
)
from stock_valuation.data.providers.base import ProviderError
from stock_valuation.data.snapshot_service import (
    sync_alphavantage_depreciation_amortization,
    sync_asml_primary_source_2024_2025,
)
from stock_valuation.database.models import AnalysisStatus, FinancialFactSnapshot
from stock_valuation.database.session import get_session, init_database
from stock_valuation.validation.asml_reference import ASML_US_GAAP_REFERENCES
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


def _decimal(value) -> Decimal | None:
    if value in (None, "", "None", "null"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _enrich_candidate_rows(rows: list[dict]) -> list[dict]:
    references = {
        (item.metric, item.period_end.year): item.value for item in ASML_US_GAAP_REFERENCES
    }
    enriched: list[dict] = []
    for row in rows:
        candidate = str(row.get("candidate_for") or "")
        fiscal_date = str(row.get("fiscal_date") or "")
        try:
            year = int(fiscal_date[:4])
        except ValueError:
            year = 0
        raw = _decimal(row.get("value"))
        reference = references.get((candidate, year))
        relative = None
        if raw is not None and reference not in (None, Decimal("0")):
            relative = abs(raw - reference) / abs(reference) * Decimal("100")
        enriched.append(
            {
                "Kandidat für": candidate,
                "Statement": row.get("statement"),
                "Jahr": year or None,
                "Provider-Feld": row.get("field"),
                "Alpha Vantage Mio. €": float(raw / Decimal("1000000")) if raw is not None else None,
                "ASML offiziell Mio. €": (
                    float(reference / Decimal("1000000")) if reference is not None else None
                ),
                "Abweichung %": float(relative) if relative is not None else None,
            }
        )
    return enriched


def _primary_preview_rows(facts) -> list[dict]:
    return [
        {
            "Jahr": fact.period_end.year,
            "Statement": fact.statement,
            "Interner Schlüssel": fact.metric,
            "Wert Mio. €": float(fact.value / Decimal("1000000")) if fact.value is not None else None,
            "Original Mio. €": (
                float(fact.provider_value) if fact.provider_value is not None else None
            ),
            "ASML-Zeile": fact.provider_field,
        }
        for fact in facts
    ]


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
    primary_facts_saved = session.scalars(
        select(FinancialFactSnapshot).where(
            FinancialFactSnapshot.analysis_id == analysis_id,
            FinancialFactSnapshot.provider == "asml_primary",
        )
    ).all()

if analysis.company.ticker.upper() != "ASML":
    st.info("Der automatische Primärquellen-Gate ist derzeit für den ASML-Referenzfall implementiert.")
    st.stop()

if not results:
    st.warning("Für diese Analyse wurden noch keine validierbaren Fundamentaldaten gefunden.")
    st.stop()

gates = metric_validation_gates(results)
readiness = phase_3a_data_readiness(gates)

approved = sum(gate.status == "approved" for gate in gates)
review = sum(gate.status == "review" for gate in gates)
blocked = sum(gate.status == "blocked" for gate in gates)

cols = st.columns(4)
cols[0].metric("Felder freigegeben", approved)
cols[1].metric("Felder prüfen", review)
cols[2].metric("Felder gesperrt", blocked)
cols[3].metric("ASML-Primärfakten", len(primary_facts_saved))

st.subheader("Feldfreigabe")
st.write(
    "Ein Feld wird nur freigegeben, wenn **alle vorhandenen 2024/2025-Primärquellenchecks PASS** "
    "sind. Für jedes Feld/Jahr gilt die Quellenpriorität **ASML-Primärquelle > Alpha Vantage**. "
    "Die schlechtere Providerzahl wird nicht gelöscht, sondern bleibt auditierbar gespeichert."
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
    "Working-Capital- und DCF-Kennzahlen bleiben gesperrt, solange die jeweils benötigte Historie "
    "noch nicht zuverlässig aus Primärquelle oder validiertem Provider vorliegt."
)

st.divider()
st.subheader("D&A-Rohfelddiagnose")
st.caption(
    "Für ASML ist `INCOME_STATEMENT.depreciationAndAmortization` validiert. Das Cashflow-D&A-Feld "
    "bleibt nur Cross-Check."
)

api_key_available = bool(os.getenv("ALPHA_VANTAGE_API_KEY"))
if not api_key_available:
    st.warning("Für optionale Alpha-Vantage-Diagnosen fehlt `ALPHA_VANTAGE_API_KEY` in `.env`.")

button_cols = st.columns(2)
with button_cols[0]:
    if st.button("D&A-Rohfelder prüfen (2 Requests)", disabled=not api_key_available):
        try:
            provider = AlphaVantageProvider()
            with st.spinner("Prüfe D&A-Rohfelder für ASML …"):
                rows = provider.probe_depreciation_fields("ASML")
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        except ProviderError as exc:
            st.error(str(exc))

with button_cols[1]:
    if st.button(
        "D&A-Mapping anwenden (1 Request)",
        disabled=not api_key_available or not editable,
    ):
        try:
            provider = AlphaVantageProvider()
            with get_session() as session:
                current = get_analysis(session, analysis_id)
                if current is None:
                    raise ValueError("Analyse nicht gefunden.")
                count = sync_alphavantage_depreciation_amortization(
                    session, current, provider, symbol="ASML"
                )
            st.success(f"D&A-Mapping aktualisiert: {count} Jahreswerte gespeichert.")
            st.rerun()
        except (ProviderError, AnalysisFrozenError, ValueError) as exc:
            st.error(str(exc))

st.divider()
st.subheader("Gesperrte Alpha-Vantage-Rohfelder diagnostizieren")
st.caption(
    "Optionaler Diagnoseabruf mit genau **2 Alpha-Vantage-Requests**. Er verändert den Snapshot nicht."
)

if st.button("Gesperrte Felder prüfen (2 Requests)", disabled=not api_key_available):
    try:
        provider = AlphaVantageProvider()
        with st.spinner("Prüfe Balance-Sheet- und Cashflow-Rohfelder für ASML …"):
            rows = provider.probe_blocked_field_candidates("ASML")
        enriched = _enrich_candidate_rows(rows)
        st.dataframe(
            pd.DataFrame(enriched),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Alpha Vantage Mio. €": st.column_config.NumberColumn(format="%.1f"),
                "ASML offiziell Mio. €": st.column_config.NumberColumn(format="%.1f"),
                "Abweichung %": st.column_config.NumberColumn(format="%.3f"),
            },
        )
    except ProviderError as exc:
        st.error(str(exc))

st.divider()
st.subheader("Offizielle ASML-Primärquelle – US-GAAP Excel")
st.caption(
    "Die offizielle ASML-Datei ist für die problematischen 2024/2025-Zeilen maßgeblich. "
    "Der Abruf benötigt **0 Alpha-Vantage-Requests**. Der Import speichert die offiziellen Werte "
    "unter `provider=asml_primary` **zusätzlich** zu Alpha Vantage; nichts wird überschrieben."
)

if st.button("Offizielle ASML-2025-US-GAAP-Excel prüfen (0 AV Requests)"):
    try:
        with st.spinner("Lade und untersuche die offizielle ASML-US-GAAP-Finanzdatei …"):
            workbook_content = download_2025_us_gaap_workbook()
            primary_matches = scan_financial_statement_workbook(workbook_content)
            primary_preview = parse_primary_source_facts(workbook_content)
        st.session_state["asml_primary_matches"] = primary_matches
        st.session_state["asml_primary_preview"] = primary_preview
        st.success(
            f"Offizielle ASML-Datei gelesen: {len(primary_matches)} relevante Zeilen gefunden; "
            f"{len(primary_preview)} deterministische 2024/2025-Fakten sind importierbar."
        )
    except ASMLPrimarySourceError as exc:
        st.error(str(exc))

primary_matches = st.session_state.get("asml_primary_matches")
primary_preview = st.session_state.get("asml_primary_preview")
if primary_matches:
    primary_rows = [
        {
            "Interner Kandidat": row["target"],
            "Tabellenblatt": row["sheet"],
            "Zeile": row["row"],
            "Treffer": row["matched_pattern"],
            "Originalzeile": row["row_values"],
            "Kopfzeile -1": row["header_minus_1"],
        }
        for row in primary_matches
    ]
    st.dataframe(pd.DataFrame(primary_rows), use_container_width=True, hide_index=True)

if primary_preview:
    st.markdown("#### Deterministischer Importvorschlag")
    st.dataframe(
        pd.DataFrame(_primary_preview_rows(primary_preview)),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Wert Mio. €": st.column_config.NumberColumn(format="%.1f"),
            "Original Mio. €": st.column_config.NumberColumn(format="%.1f"),
        },
    )
    st.caption(
        "Importiert werden ausschließlich eindeutig identifizierte Abschlusszeilen für 2024/2025. "
        "Cashflow-Bewegungszeilen mit ähnlicher Bezeichnung werden nicht als Bilanzbestände verwendet."
    )

    if st.button(
        "ASML-Primärquellenwerte 2024/2025 in Snapshot übernehmen (0 AV Requests)",
        type="primary",
        disabled=not editable,
    ):
        try:
            with get_session() as session:
                current = get_analysis(session, analysis_id)
                if current is None:
                    raise ValueError("Analyse nicht gefunden.")
                with st.spinner("Importiere offizielle ASML-Primärquellenwerte …"):
                    count = sync_asml_primary_source_2024_2025(session, current)
            st.success(
                f"{count} ASML-Primärquellenfakten gespeichert. Alpha-Vantage-Daten wurden nicht gelöscht."
            )
            st.rerun()
        except (ASMLPrimarySourceError, AnalysisFrozenError, ValueError) as exc:
            st.error(str(exc))

if primary_facts_saved:
    st.markdown("#### Bereits gespeicherte ASML-Primärquellenwerte")
    stored_rows = [
        {
            "Jahr": fact.period_end.year,
            "Statement": fact.statement,
            "Interner Schlüssel": fact.metric,
            "Wert Mio. €": float(fact.value / Decimal("1000000")) if fact.value is not None else None,
            "Quelle": fact.provider_field,
            "Source Type": fact.source_type,
        }
        for fact in sorted(primary_facts_saved, key=lambda item: (item.period_end, item.metric))
    ]
    st.dataframe(
        pd.DataFrame(stored_rows),
        use_container_width=True,
        hide_index=True,
        column_config={"Wert Mio. €": st.column_config.NumberColumn(format="%.1f")},
    )
