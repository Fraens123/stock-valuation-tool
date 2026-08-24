from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_valuation.runtime_dependencies import ensure_runtime_dependencies

ensure_runtime_dependencies()

import os
from datetime import date
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import select

from stock_valuation.analyses.ai_review_service import (
    AIReviewError,
    accept_ai_review_finding,
    build_chatgpt_review_package,
    import_chatgpt_review_result,
    latest_ai_review_run,
    reject_ai_review_finding,
)
from stock_valuation.analyses.estimate_service import (
    annual_estimates,
    estimate_period_type,
    infer_fiscal_year_end_month_day,
    relevant_estimates,
)
from stock_valuation.analyses.input_service import (
    remove_manual_financial_override,
    upsert_manual_financial_override,
)
from stock_valuation.analyses.service import AnalysisFrozenError, get_analysis, list_analyses
from stock_valuation.companies.provider_symbols import get_provider_symbol
from stock_valuation.data.audit import run_deterministic_audit
from stock_valuation.data.history_mapping_audit import audit_history_mapping
from stock_valuation.data.missing_data_search import (
    is_valuation_relevant,
    metric_impacts,
    search_missing_metric_candidates,
)
from stock_valuation.data.preferred_data import load_preferred_data_states
from stock_valuation.data.providers.alphavantage import AlphaVantageProvider
from stock_valuation.data.providers.base import ProviderError
from stock_valuation.data.resolution import load_preferred_financial_facts
from stock_valuation.data.sec_history_completion import sync_sec_history_text_candidates
from stock_valuation.data.snapshot_service import sync_alphavantage_estimates
from stock_valuation.data.source_router import sync_best_available_financials
from stock_valuation.database.models import AnalysisStatus, EstimateSnapshot, FinancialFactSnapshot
from stock_valuation.database.session import get_session, init_database
from stock_valuation.ui.financial_worksheet import (
    OPEN_STATUSES,
    STATUS_DISPLAY,
    WorksheetCell,
    WorksheetCellStatus,
    build_financial_worksheet,
    open_cells,
    worksheet_candidates,
    worksheet_status_counts,
)
from stock_valuation.ui.navigation import render_navigation
from stock_valuation.workflow.service import refresh_local_analysis_stages


load_dotenv()
init_database()
st.set_page_config(page_title="Finanzdaten", layout="wide")
render_navigation()

STATUS_LABELS = {
    AnalysisStatus.DRAFT: "Entwurf",
    AnalysisStatus.IN_PROGRESS: "In Bearbeitung",
    AnalysisStatus.COMPLETED: "Abgeschlossen",
    AnalysisStatus.ARCHIVED: "Archiviert",
}
DATA_STATUS_LABELS = {
    "confirmed_override": "✅ Bestätigte Korrektur",
    "primary_source": "✅ Primärquelle",
    "primary_reviewed_pass": "✅ Primärquelle + Semantik geprüft",
    "primary_semantic_review_required": "⚠️ Semantik prüfen",
    "reviewed_pass": "✅ ChatGPT PASS",
    "legacy_primary_validated": "✅ Primärquellen-validiert",
    "provider_unverified": "🟡 Ungeprüfter Providerwert",
    "review_stale": "🟡 Prüfung veraltet",
    "unclear": "⚠️ UNKLAR",
    "review_conflict": "❌ Abweichung offen",
    "derive_required": "🔵 selbst ableiten",
}
MAPPING_STATUS_LABELS = {
    "PASS": "✅ stabil",
    "REVIEW": "⚠️ prüfen",
    "GAP": "🟡 Lücke",
}
BLOCKING_DATA_STATUSES = {
    "provider_unverified",
    "review_stale",
    "unclear",
    "review_conflict",
    "derive_required",
    "primary_semantic_review_required",
}


def _analysis_label(analysis) -> str:
    return (
        f"{analysis.company.name} · {analysis.as_of_date} · "
        f"R{analysis.revision_number} · {STATUS_LABELS.get(analysis.status, analysis.status.value)}"
    )


def _decimal(raw: str) -> Decimal:
    text = raw.strip().replace(" ", "").replace(",", ".")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Bitte einen gültigen Zahlenwert eingeben.") from exc


def _format_value(value: Decimal | None, currency: str | None) -> str:
    if value is None:
        return "—"
    return f"{float(value):,.2f} {currency or ''}".strip()


def _format_cell_value(value: Decimal | None, currency: str | None) -> str:
    if value is None:
        return ""
    return f"{float(value):,.1f} {currency or ''}".strip()


def _period_end_for_year(facts: list[FinancialFactSnapshot], fiscal_year: int):
    for fact in facts:
        if fact.period_type == "FY" and fact.period_end.year == fiscal_year:
            return fact.period_end
    return date(int(fiscal_year), 12, 31)


def _cell_option_label(cell: WorksheetCell) -> str:
    return f"{cell.fiscal_year} · {cell.label} · {STATUS_DISPLAY[cell.status]}"


def _important_open_cells(cells: tuple[WorksheetCell, ...]) -> tuple[WorksheetCell, ...]:
    return tuple(cell for cell in cells if is_valuation_relevant(cell.metric))


st.title("Finanzdaten")
st.caption(
    "Der komplette Datenworkflow läuft auf dieser Seite: **Ist-Daten laden → Quellen prüfen → "
    "10-Jahres-Abdeckung → ChatGPT-Cross-Check → Korrekturen → optionale Schätzungen**. "
    "Die Kennzahlen-Seite zeigt anschließend nur noch Analyseergebnisse."
)

with get_session() as session:
    analyses = list_analyses(session, include_archived=True)
    options = {_analysis_label(a): a.id for a in analyses}

if not options:
    st.info("Zuerst unter **Unternehmen** eine Aktie auswählen und eine Analyse anlegen.")
    st.stop()

current_id = st.session_state.get("selected_analysis_id")
option_ids = list(options.values())
selected_label = st.selectbox(
    "Analyse",
    list(options),
    index=option_ids.index(current_id) if current_id in option_ids else 0,
)
analysis_id = options[selected_label]
st.session_state["selected_analysis_id"] = analysis_id

with get_session() as session:
    analysis = get_analysis(session, analysis_id)
    if analysis is None:
        st.error("Analyse nicht gefunden.")
        st.stop()
    alpha_identifier = get_provider_symbol(
        session, analysis.company, provider="alphavantage", purpose="fundamentals"
    )
    sec_identifier = get_provider_symbol(session, analysis.company, provider="sec", purpose="cik")
    lei_identifier = get_provider_symbol(session, analysis.company, provider="gleif", purpose="lei")
    editable = analysis.status in {AnalysisStatus.DRAFT, AnalysisStatus.IN_PROGRESS}
    analysis_as_of_date = analysis.as_of_date
    company_ticker = analysis.company.ticker
    company_currency = analysis.company.currency
    company_name = analysis.company.name
    revision_number = analysis.revision_number
    analysis_status = analysis.status

alpha_symbol = alpha_identifier.symbol if alpha_identifier else company_ticker
alpha_key_available = bool(os.getenv("ALPHA_VANTAGE_API_KEY"))
sec_user_agent_available = bool(os.getenv("SEC_USER_AGENT"))

header = st.columns(5)
header[0].metric("Unternehmen", company_name)
header[1].metric("Ticker", company_ticker)
header[2].metric("Währung", company_currency or "—")
header[3].metric("Revision", f"R{revision_number}")
header[4].metric("Status", STATUS_LABELS.get(analysis_status, analysis_status.value))

with st.expander("Automatisch erkannte Daten-Identitäten", expanded=False):
    st.write(f"**SEC CIK:** {sec_identifier.symbol if sec_identifier else 'noch nicht erkannt'}")
    st.write(f"**LEI:** {lei_identifier.symbol if lei_identifier else 'noch nicht erkannt'}")
    st.write(
        f"**Alpha-Vantage-Symbol:** "
        f"{alpha_symbol if alpha_identifier else 'nicht benötigt / noch nicht hinterlegt'}"
    )

# -----------------------------------------------------------------------------
# 1. Import
# -----------------------------------------------------------------------------
st.subheader("1. Finanzdaten laden")
if not editable:
    st.info(
        "Diese Analyse ist abgeschlossen und eingefroren. Für aktuelle Daten zuerst eine neue "
        "Revision anlegen."
    )
else:
    st.write(
        "Der Import sucht automatisch die beste offizielle strukturierte Quelle. Bei SEC wird nach "
        "Company Facts und Original-XBRL bei Bedarf auch die **offizielle Berichtstabelle** nach "
        "fehlenden historischen Werten durchsucht. Solche Tabellenkandidaten werden niemals still "
        "freigegeben, sondern landen automatisch im normalen ChatGPT-Prüfpaket."
    )
    if not sec_user_agent_available:
        st.caption(
            "SEC ist derzeit übersprungen, weil `SEC_USER_AGENT` in `.env` fehlt. ESEF/GLEIF wird "
            "trotzdem versucht."
        )

    allow_alpha_fallback = st.checkbox(
        "Alpha Vantage nur als Fallback verwenden",
        value=False,
        help="Nur aktivieren, wenn SEC/ESEF keine brauchbaren historischen Ist-Daten liefern.",
    )

    if st.button("Finanzdaten laden / aktualisieren", type="primary"):
        try:
            with get_session() as session:
                current = get_analysis(session, analysis_id)
                if current is None:
                    raise ValueError("Analyse wurde nicht gefunden.")
                with st.spinner("Lade und vervollständige offizielle Finanzdaten …"):
                    result = sync_best_available_financials(
                        session,
                        current,
                        allow_alpha_fallback=allow_alpha_fallback,
                    )
                    completion = None
                    if result.selected_source == "SEC":
                        completion = sync_sec_history_text_candidates(session, current)

            attempts = [
                {
                    "Quelle": attempt.source,
                    "Status": attempt.status,
                    "Fakten": attempt.fact_count,
                    "Identifikator": attempt.identifier,
                    "Hinweis": attempt.message,
                }
                for attempt in result.attempts
            ]
            if completion is not None:
                attempts.append(
                    {
                        "Quelle": "SEC Tabellen-/Text-Fallback",
                        "Status": (
                            "candidates_found" if completion.candidate_count else "checked"
                        ),
                        "Fakten": completion.candidate_count,
                        "Identifikator": sec_identifier.symbol if sec_identifier else None,
                        "Hinweis": completion.message,
                    }
                )
            st.session_state[f"source-router-{analysis_id}"] = {
                "selected_source": result.selected_source,
                "fact_count": result.fact_count + (completion.candidate_count if completion else 0),
                "report_currency": result.report_currency,
                "attempts": attempts,
                "completion_message": completion.message if completion else None,
            }
            if result.success:
                st.success("Finanzdaten wurden aktualisiert und die historischen Lücken geprüft.")
                st.rerun()
            else:
                st.error(
                    "Keine ausreichend strukturierte Quelle konnte automatisch importiert werden. "
                    "Die technischen Details stehen im Importprotokoll."
                )
        except (ValueError, AnalysisFrozenError, ProviderError) as exc:
            st.error(str(exc))

# Load one coherent view after possible import.
with get_session() as session:
    current = get_analysis(session, analysis_id)
    if current is None:
        st.error("Analyse nicht gefunden.")
        st.stop()
    facts = list(
        session.scalars(
            select(FinancialFactSnapshot)
            .where(FinancialFactSnapshot.analysis_id == analysis_id)
            .order_by(FinancialFactSnapshot.period_end.desc(), FinancialFactSnapshot.metric)
        ).all()
    )
    estimates = list(
        session.scalars(
            select(EstimateSnapshot)
            .where(EstimateSnapshot.analysis_id == analysis_id)
            .order_by(EstimateSnapshot.period, EstimateSnapshot.metric)
        ).all()
    )
    preferred_facts = load_preferred_financial_facts(session, analysis_id)
    preferred_states = load_preferred_data_states(session, analysis_id)
    history_audit = audit_history_mapping(session, current, years=10)
    audit_checks = run_deterministic_audit(session, current)
    latest_run = latest_ai_review_run(session, analysis_id)

# -----------------------------------------------------------------------------
# 2. Financial worksheet
# -----------------------------------------------------------------------------
st.divider()
st.subheader("2. Finanzdaten-Arbeitsblatt")
if not facts:
    st.info("Noch keine Finanzdaten geladen.")
else:
    year_mode = st.segmented_control(
        "Zeitraum",
        ["5 Jahre", "10 Jahre", "Alle"],
        default="5 Jahre",
        key=f"financial-worksheet-years-{analysis_id}",
    )
    with get_session() as session:
        worksheet = build_financial_worksheet(
            session,
            analysis_id,
            preferred_states,
            year_mode=str(year_mode or "5 Jahre"),
        )
    counts = worksheet_status_counts(worksheet)
    compact = st.columns(4)
    confirmed = (
        counts[WorksheetCellStatus.PRESENT_RELEASED]
        + counts[WorksheetCellStatus.AUTOMATIC_CONFIRMED]
        + counts[WorksheetCellStatus.MANUAL_CONFIRMED]
    )
    open_review = (
        counts[WorksheetCellStatus.PRESENT_REVIEW_REQUIRED]
        + counts[WorksheetCellStatus.OFFICIAL_CANDIDATE_FOUND]
        + counts[WorksheetCellStatus.DERIVABLE]
        + counts[WorksheetCellStatus.REVIEW_REQUIRED]
        + counts[WorksheetCellStatus.CANDIDATE_FOUND]
    )
    compact[0].metric("bestätigte Werte", confirmed)
    compact[1].metric("zu prüfen", open_review)
    compact[2].metric("fehlt", counts[WorksheetCellStatus.NOT_FOUND] + counts[WorksheetCellStatus.MISSING])
    compact[3].metric("manuelle Korrekturen", counts[WorksheetCellStatus.MANUAL_OVERRIDE])

    important_only = st.toggle(
        "Nur für Bewertung relevante offene Werte",
        value=True,
        key=f"financial-worksheet-important-open-{analysis_id}",
    )
    filter_open = st.toggle(
        "Alle offenen historischen Werte anzeigen",
        value=False,
        key=f"financial-worksheet-open-{analysis_id}",
    )

    if editable and st.button("Alle wichtigen fehlenden Werte suchen"):
        try:
            with get_session() as session:
                current = get_analysis(session, analysis_id)
                if current is None:
                    raise ValueError("Analyse nicht gefunden.")
                open_now = open_cells(worksheet)
                if important_only:
                    open_now = _important_open_cells(open_now)
                before = len(open_now)
                completion = sync_sec_history_text_candidates(session, current)
                refresh_local_analysis_stages(session, current)
            st.session_state[f"source-router-{analysis_id}"] = {
                **st.session_state.get(f"source-router-{analysis_id}", {}),
                "completion_message": completion.message,
            }
            st.success(
                f"Suche abgeschlossen: {completion.candidate_count} Kandidat(en) gefunden; "
                f"{before} offene Zelle(n) wurden geprüft."
            )
            st.rerun()
        except (ValueError, AnalysisFrozenError, ProviderError) as exc:
            st.error(str(exc))

    worksheet_tabs = st.tabs(list(worksheet.sections))
    for tab, (section_name, section_rows) in zip(worksheet_tabs, worksheet.sections.items()):
        with tab:
            rows = []
            for row in section_rows:
                row_cells = [
                    worksheet.cells[(row.metric, year)]
                    for year in worksheet.years
                    if (row.metric, year) in worksheet.cells
                ]
                if important_only and filter_open and not is_valuation_relevant(row.metric):
                    continue
                if filter_open and not any(cell.status in OPEN_STATUSES for cell in row_cells):
                    continue
                table_row = {"Kennzahl": row.label}
                for year, cell in zip(worksheet.years, row_cells):
                    table_row[str(year)] = cell.display
                rows.append(table_row)
            if rows:
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            else:
                st.caption("Keine offenen Werte in diesem Bereich.")

    detail_cells = open_cells(worksheet) if filter_open or important_only else tuple(
        cell for key, cell in sorted(worksheet.cells.items(), key=lambda item: (item[0][1], item[0][0]), reverse=True)
    )
    if important_only:
        detail_cells = _important_open_cells(detail_cells)
    if detail_cells:
        st.markdown("#### Zelle prüfen oder korrigieren")
        labels = {_cell_option_label(cell): cell for cell in detail_cells}
        selected_cell = labels[
            st.selectbox(
                "Zelle",
                list(labels),
                key=f"financial-worksheet-selected-cell-{analysis_id}",
            )
        ]
        detail = st.columns(4)
        detail[0].metric("Kennzahl", selected_cell.label)
        detail[1].metric("Geschäftsjahr", selected_cell.fiscal_year)
        detail[2].metric("Status", STATUS_DISPLAY[selected_cell.status])
        detail[3].metric("Kandidaten", selected_cell.candidate_count)

        with st.expander("Woher kommt der Wert?", expanded=True):
            st.write(f"**Verwendeter Wert:** {_format_value(selected_cell.value, selected_cell.currency)}")
            st.write(f"**Originalwert:** {_format_value(selected_cell.value, selected_cell.currency)}")
            st.write(f"**Quelle:** {selected_cell.provider or '—'}")
            st.write(f"**Provider Field:** {selected_cell.provider_field or '—'}")
            st.write(f"**Filing Date:** {selected_cell.filing_date or '—'}")
            st.write(f"**Abrufdatum:** {selected_cell.retrieved_at or '—'}")
            st.write(f"**Begründung:** {selected_cell.reason or '—'}")
            st.caption(f"Technischer Schlüssel: `{selected_cell.metric}`")
            if selected_cell.source_url:
                st.link_button("Quelle öffnen", selected_cell.source_url)
            impacts = metric_impacts(selected_cell.metric)
            if impacts:
                st.write("**Wird verwendet für:** " + ", ".join(impacts))

        candidates = ()
        with get_session() as session:
            current = get_analysis(session, analysis_id)
            search_result = (
                search_missing_metric_candidates(
                    session,
                    current,
                    metric=selected_cell.metric,
                    fiscal_year=selected_cell.fiscal_year,
                )
                if current is not None
                else None
            )
            candidates = worksheet_candidates(
                session,
                analysis_id,
                selected_cell.metric,
                selected_cell.fiscal_year,
            )
        if search_result is not None:
            st.info(f"{search_result.status.value}: {search_result.message}")
        action_cols = st.columns(2)
        if selected_cell.status in {
            WorksheetCellStatus.PRESENT_REVIEW_REQUIRED,
            WorksheetCellStatus.OFFICIAL_CANDIDATE_FOUND,
            WorksheetCellStatus.DERIVABLE,
            WorksheetCellStatus.NOT_FOUND,
            WorksheetCellStatus.MISSING,
            WorksheetCellStatus.REVIEW_REQUIRED,
            WorksheetCellStatus.CANDIDATE_FOUND,
        }:
            if action_cols[0].button(
                "Fehlenden Wert suchen" if selected_cell.status == WorksheetCellStatus.MISSING else "Kandidaten suchen",
                disabled=not editable,
                key=f"search-cell-{selected_cell.metric}-{selected_cell.fiscal_year}",
            ):
                try:
                    with get_session() as session:
                        current = get_analysis(session, analysis_id)
                        if current is None:
                            raise ValueError("Analyse nicht gefunden.")
                        completion = sync_sec_history_text_candidates(session, current)
                        refresh_local_analysis_stages(session, current)
                    st.success(completion.message)
                    st.rerun()
                except (ValueError, AnalysisFrozenError, ProviderError) as exc:
                    st.error(str(exc))

        manual_overridden = selected_cell.provider == "manual_override"
        if manual_overridden and action_cols[1].button(
            "Override entfernen",
            disabled=not editable,
            key=f"remove-override-{selected_cell.metric}-{selected_cell.fiscal_year}",
        ):
            try:
                with get_session() as session:
                    current = get_analysis(session, analysis_id)
                    if current is None:
                        raise ValueError("Analyse nicht gefunden.")
                    remove_manual_financial_override(
                        session,
                        current,
                        metric=selected_cell.metric,
                        period_end=_period_end_for_year(facts, selected_cell.fiscal_year),
                    )
                    refresh_local_analysis_stages(session, current)
                st.rerun()
            except (ValueError, AnalysisFrozenError) as exc:
                st.error(str(exc))

        if candidates:
            st.markdown("#### Automatische Kandidaten")
            for candidate in candidates:
                title = (
                    f"{_format_value(candidate.value, candidate.currency)} · "
                    f"{candidate.provider or 'Quelle'} · {candidate.semantic_decision}"
                )
                with st.expander(title, expanded=not candidate.selectable_without_review):
                    st.write(f"**Kandidatentyp:** {candidate.candidate_type or '—'}")
                    st.write(f"**Confidence:** {candidate.confidence if candidate.confidence is not None else '—'}")
                    if candidate.formula:
                        st.write(f"**Formel:** {candidate.formula}")
                    if candidate.input_refs:
                        st.write("**Input-Refs:** " + ", ".join(candidate.input_refs))
                    st.write(f"**Concept / Provider Field:** {candidate.provider_field or '—'}")
                    st.write(f"**Filing:** {candidate.filing_date or '—'}")
                    st.write(f"**Semantik:** {candidate.semantic_reason}")
                    if candidate.source_url:
                        st.link_button("Offizielle Quelle öffnen", candidate.source_url)
                    if not candidate.selectable_without_review:
                        if st.button(
                            "Mit ChatGPT prüfen",
                            key=f"review-candidate-{candidate.fact_id}-{candidate.metric}-{candidate.fiscal_year}",
                        ):
                            st.info("Das ChatGPT-Prüfpaket kann unten im Abschnitt ChatGPT-Prüfung erzeugt werden.")
                    if candidate.rejected_reason:
                        st.warning(candidate.rejected_reason)
                    elif st.button(
                        "Automatischen Wert bestätigen",
                        disabled=not editable or candidate.value is None,
                        key=f"accept-candidate-{candidate.fact_id}-{candidate.metric}-{candidate.fiscal_year}",
                    ):
                        try:
                            with get_session() as session:
                                current = get_analysis(session, analysis_id)
                                fact = session.get(FinancialFactSnapshot, candidate.fact_id) if candidate.fact_id else None
                                if current is None or candidate.value is None:
                                    raise ValueError("Kandidat nicht mehr verfügbar.")
                                upsert_manual_financial_override(
                                    session,
                                    current,
                                    metric=candidate.metric,
                                    period_end=fact.period_end if fact is not None else _period_end_for_year(facts, candidate.fiscal_year),
                                    value=candidate.value,
                                    currency=candidate.currency,
                                    unit=fact.unit if fact is not None else "currency",
                                    statement=fact.statement if fact is not None else selected_cell.statement,
                                    source_name=f"Bestätigter Kandidat: {candidate.provider or 'Quelle'}",
                                    source_url=candidate.source_url,
                                    note=(
                                        f"Vom Nutzer im Finanzdaten-Arbeitsblatt bestätigt. "
                                        f"Original Provider Field: {candidate.provider_field or '—'}. "
                                        f"Input-Refs: {', '.join(candidate.input_refs) or '—'}."
                                    ),
                                )
                                refresh_local_analysis_stages(session, current)
                            st.rerun()
                        except (ValueError, AnalysisFrozenError) as exc:
                            st.error(str(exc))
        else:
            st.caption("Für diese Zelle ist noch kein automatischer Kandidat gespeichert.")

        with st.form(f"worksheet-manual-override-{selected_cell.metric}-{selected_cell.fiscal_year}"):
            st.markdown("#### Eigenen Wert verwenden")
            manual_value = st.text_input(
                "Wert",
                value=str(selected_cell.value) if selected_cell.value is not None else "",
            )
            manual_currency = st.text_input("Währung", value=selected_cell.currency or company_currency or "")
            manual_source_choice = st.selectbox(
                "Quelle",
                ["Aktienfinder", "Geschäftsbericht", "Unternehmenswebsite", "Andere"],
                key=f"worksheet-manual-source-{selected_cell.metric}-{selected_cell.fiscal_year}",
            )
            manual_source_other = st.text_input("Quelle genau", value="" if manual_source_choice != "Aktienfinder" else "Aktienfinder")
            manual_url = st.text_input("Quellen-URL")
            manual_note = st.text_area("Kommentar / Begründung")
            save_manual_cell = st.form_submit_button("Override speichern", disabled=not editable)
        if save_manual_cell:
            try:
                manual_source = manual_source_other.strip() or manual_source_choice
                if not manual_source.strip():
                    raise ValueError("Quelle ist erforderlich.")
                with get_session() as session:
                    current = get_analysis(session, analysis_id)
                    if current is None:
                        raise ValueError("Analyse nicht gefunden.")
                    upsert_manual_financial_override(
                        session,
                        current,
                        metric=selected_cell.metric,
                        period_end=_period_end_for_year(facts, selected_cell.fiscal_year),
                        value=_decimal(manual_value),
                        currency=manual_currency.strip() or None,
                        unit="currency",
                        statement=selected_cell.statement,
                        source_name=manual_source,
                        source_url=manual_url,
                        note=manual_note,
                    )
                    refresh_local_analysis_stages(session, current)
                st.rerun()
            except (ValueError, AnalysisFrozenError) as exc:
                st.error(str(exc))

# -----------------------------------------------------------------------------
# 3. Extended data status
# -----------------------------------------------------------------------------
st.divider()
with st.container(border=True):
    st.markdown("### 3. Erweiterte Datenprüfung")
    st.subheader("Datenstatus")
    if not facts:
        st.info("Noch keine Finanzdaten geladen.")
    else:
        pass
    ready_count = sum(state.calculation_ready for state in preferred_states)
    blocked_states = [
        state for state in preferred_states if state.quality_status in BLOCKING_DATA_STATUSES
    ]
    blocked_count = len(blocked_states)
    mapping_open = history_audit.review_count + history_audit.gap_count
    audit_open = sum(item.status != "PASS" for item in audit_checks)
    total_mapping = len(history_audit.rows)

    status_cols = st.columns(4)
    status_cols[0].metric(
        "10-Jahres-Reihen",
        f"{history_audit.stable_count}/{total_mapping}" if total_mapping else "—",
    )
    status_cols[1].metric("Historisch offen", mapping_open)
    status_cols[2].metric("Berechnungsbereit", f"{ready_count}/{len(preferred_states)}")
    status_cols[3].metric("Plausibilität offen", audit_open)

    data_ready = bool(preferred_states) and mapping_open == 0 and blocked_count == 0 and audit_open == 0
    if data_ready:
        st.success("✅ **Datenbasis bereit für die Analyse.** Es ist kein weiterer Import-Schritt nötig.")
    else:
        messages: list[str] = []
        if history_audit.gap_count:
            messages.append(
                f"{history_audit.gap_count} historische Reihe(n) sind noch nicht vollständig abgedeckt"
            )
        if history_audit.review_count:
            messages.append(f"{history_audit.review_count} Mapping-Reihe(n) brauchen noch Prüfung")
        if blocked_count:
            messages.append(f"{blocked_count} gespeicherte Werte sind noch nicht freigegeben")
        if audit_open:
            messages.append(f"{audit_open} Plausibilitätscheck(s) sind offen")
        st.warning("⚠️ **Noch nicht vollständig bereit:** " + "; ".join(messages) + ".")
        if not history_audit.gap_count and (history_audit.review_count or blocked_count):
            st.info(
                "**Nächste Aktion:** unten das normale ChatGPT-Prüfpaket herunterladen. Ältere "
                "SEC-Filing-Kandidaten werden automatisch zusätzlich zu den ausgewählten aktuellen "
                "Jahren aufgenommen."
            )
        elif history_audit.gap_count:
            st.info(
                "Die automatischen SEC/ESEF-Stufen haben für mindestens einen historischen Wert "
                "noch keinen belastbaren Kandidaten gefunden. Die betroffenen Reihen bleiben sichtbar "
                "offen; vorhandene Daten und Kennzahlen werden dadurch nicht erfunden oder ersetzt."
            )

    with st.expander("10-Jahres-Abdeckung im Detail", expanded=bool(mapping_open)):
        show_stable = st.checkbox(
            "Auch stabile Reihen anzeigen",
            value=not bool(mapping_open),
            key=f"show-stable-history-{analysis_id}",
        )
        rows = list(history_audit.rows)
        if not show_stable:
            rows = [row for row in rows if row.status != "PASS"]
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Status": MAPPING_STATUS_LABELS.get(row.status, row.status),
                        "Interner Schlüssel": row.metric,
                        "Abdeckung": row.coverage_label,
                        "Fehlende Jahre": ", ".join(str(year) for year in row.missing_years) or "—",
                        "Wechsel ab": ", ".join(str(year) for year in row.change_years) or "—",
                        "Quelle": ", ".join(row.providers),
                        "Währung": ", ".join(row.currencies),
                        "Taxonomie": ", ".join(row.taxonomies),
                        "Mapping-Verlauf": row.mapping_sequence,
                        "Hinweis": row.reason,
                    }
                    for row in rows
                ]
            ),
            width="stretch",
            hide_index=True,
        )

    with st.expander("Berechnungsbasis / Preferred Data im Detail", expanded=False):
        st.caption(
            f"{ready_count} von {len(preferred_states)} gespeicherten Preferred-Data-Werten sind "
            f"berechnungsbereit; {blocked_count} sind blockiert oder ungeklärt."
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Jahr": state.fact.period_end.year,
                        "Metrik": state.fact.metric,
                        "Quelle": state.fact.provider,
                        "Status": DATA_STATUS_LABELS.get(state.quality_status, state.quality_status),
                        "Berechnungsbereit": "Ja" if state.calculation_ready else "Nein",
                        "Review": state.review_verdict,
                        "Begründung": state.reason,
                    }
                    for state in sorted(
                        preferred_states,
                        key=lambda item: (item.fact.period_end, item.fact.metric),
                        reverse=True,
                    )
                ]
            ),
            width="stretch",
            hide_index=True,
        )

    with st.expander("Lokale Plausibilitätsprüfung", expanded=bool(audit_open)):
        st.caption(
            f"{sum(item.status == 'PASS' for item in audit_checks)} von {len(audit_checks)} "
            "Plausibilitätschecks sind PASS."
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Jahr": item.year,
                        "Status": "✅ PASS" if item.status == "PASS" else "⚠️ PRÜFEN",
                        "Check": item.label,
                        "Abweichung %": (
                            float(item.deviation_pct) if item.deviation_pct is not None else None
                        ),
                        "Details": item.detail,
                    }
                    for item in audit_checks
                ]
            ),
            width="stretch",
            hide_index=True,
        )

    with st.expander("Technische Importdetails und Rohdaten", expanded=False):
        years = sorted({fact.period_end.year for fact in facts if fact.period_type == "FY"})
        providers = sorted({fact.provider or "—" for fact in facts})
        overrides = [fact for fact in facts if fact.provider == "manual_override"]
        empty_stored = sum(1 for fact in facts if fact.value is None)
        tech = st.columns(5)
        tech[0].metric("Datenpunkte", len(facts))
        tech[1].metric("Geschäftsjahre", len(years))
        tech[2].metric("Leere gespeicherte Werte", empty_stored)
        tech[3].metric("Quellen", len(providers))
        tech[4].metric("Bestätigte Korrekturen", len(overrides))
        st.caption("Gespeicherte Quellen: " + ", ".join(providers))

        router_state = st.session_state.get(f"source-router-{analysis_id}")
        if router_state and router_state.get("attempts"):
            st.markdown("**Letzter Quellenlauf**")
            st.dataframe(pd.DataFrame(router_state["attempts"]), width="stretch", hide_index=True)

        st.markdown("**Rohdaten**")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Periode": fact.period_end,
                        "Quelle": fact.provider,
                        "Statement": fact.statement,
                        "Interner Schlüssel": fact.metric,
                        "Wert": float(fact.value) if fact.value is not None else None,
                        "Währung": fact.currency,
                        "Provider-Feld": fact.provider_field,
                        "Source Type": fact.source_type,
                    }
                    for fact in facts
                ]
            ),
            width="stretch",
            hide_index=True,
        )

# -----------------------------------------------------------------------------
# 3. Review
# -----------------------------------------------------------------------------
st.divider()
st.subheader("3. ChatGPT-Prüfung")
if not preferred_facts:
    st.caption("Für die Prüfung müssen zuerst Finanzdaten importiert werden.")
else:
    st.write(
        "Die ausgewählten **2, 3 oder 5 aktuellen Jahre** werden vollständig geprüft. Ältere "
        "offene SEC-Filing-Kandidaten aus dem 10-Jahres-Fenster werden automatisch angehängt. "
        "Du musst deshalb nicht 10 Jahre auswählen."
    )
    review_years = st.selectbox(
        "Aktuelle Geschäftsjahre tief prüfen",
        [2, 3, 5],
        index=1,
        help="3 Jahre ist der normale Standard. Historische Mappingkandidaten werden zusätzlich automatisch aufgenommen.",
    )

    try:
        with get_session() as session:
            current = get_analysis(session, analysis_id)
            if current is None:
                raise ValueError("Analyse nicht gefunden.")
            review_package = build_chatgpt_review_package(session, current, years=int(review_years))

        package_cols = st.columns([1, 2])
        with package_cols[0]:
            st.download_button(
                "1. Prüfpaket herunterladen",
                data=review_package.content,
                file_name=review_package.filename,
                mime="text/markdown",
                type="primary",
            )
        with package_cols[1]:
            st.caption(
                f"{review_package.fact_count} Fakten · Package-ID `{review_package.package_id[:12]}…` · "
                f"Ergebnisdatei: `{review_package.result_filename}`"
            )

        st.info(
            "**In ChatGPT:** Datei hochladen und schreiben: „Führe die Prüfung aus und erstelle die "
            "angeforderte JSON-Ergebnisdatei.“ Danach die `.json`-Datei hier wieder hochladen."
        )

        uploaded_review = st.file_uploader(
            "2. Prüfergebnis hochladen",
            type=["json"],
            accept_multiple_files=False,
            key=f"chatgpt-review-result-{analysis_id}",
        )
        if uploaded_review is not None and st.button(
            "3. Prüfergebnis einlesen",
            disabled=not editable,
        ):
            try:
                with get_session() as session:
                    current = get_analysis(session, analysis_id)
                    if current is None:
                        raise ValueError("Analyse nicht gefunden.")
                    run = import_chatgpt_review_result(
                        session,
                        current,
                        uploaded_review.getvalue(),
                    )
                st.success(
                    f"Prüfung eingelesen: {len(run.findings)} Fakten wurden dem Snapshot zugeordnet."
                )
                st.rerun()
            except (AIReviewError, AnalysisFrozenError, ValueError) as exc:
                st.error(str(exc))
    except (AIReviewError, ValueError) as exc:
        st.error(str(exc))

    if latest_run is not None:
        findings = list(latest_run.findings)
        counts = {
            status: sum(row.verdict == status for row in findings)
            for status in ["PASS", "WARN", "FAIL", "UNKLAR"]
        }
        st.markdown("#### Letztes Prüfergebnis")
        result_cols = st.columns(4)
        result_cols[0].metric("PASS", counts["PASS"])
        result_cols[1].metric("WARN", counts["WARN"])
        result_cols[2].metric("FAIL", counts["FAIL"])
        result_cols[3].metric("UNKLAR", counts["UNKLAR"])
        if latest_run.summary:
            st.info(latest_run.summary)

        visible = [row for row in findings if row.verdict != "PASS"]
        with st.expander(
            "Prüffunde im Detail",
            expanded=bool(visible),
        ):
            show_pass = st.checkbox(
                "Auch PASS-Zeilen anzeigen",
                value=False,
                key=f"show-pass-review-{analysis_id}",
            )
            table_rows = findings if show_pass else visible
            if table_rows:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Jahr": row.period_end.year,
                                "Status": row.verdict,
                                "Metrik": row.metric,
                                "Importiert": (
                                    float(row.imported_value)
                                    if row.imported_value is not None
                                    else None
                                ),
                                "Offiziell": (
                                    float(row.official_value)
                                    if row.official_value is not None
                                    else None
                                ),
                                "Währung": row.currency,
                                "Offizielle Bezeichnung": row.official_label,
                                "Quelle": row.source_title,
                                "Entscheidung": row.decision,
                                "Begründung": row.reason,
                            }
                            for row in table_rows
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.success("Keine offenen Abweichungen in der letzten Prüfung.")

        pending = [
            row
            for row in findings
            if row.decision == "pending"
            and row.verdict in {"WARN", "FAIL"}
            and row.official_value is not None
        ]
        if pending:
            st.markdown("#### Korrekturvorschläge entscheiden")
            for finding in sorted(
                pending,
                key=lambda row: (row.period_end, row.metric),
                reverse=True,
            ):
                label = f"{finding.verdict} · {finding.period_end.year} · {finding.metric}"
                with st.expander(label, expanded=finding.verdict == "FAIL"):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Importiert", _format_value(finding.imported_value, finding.currency))
                    c2.metric("Offiziell", _format_value(finding.official_value, finding.currency))
                    c3.metric(
                        "Abweichung",
                        f"{float(finding.deviation_pct):.3f} %"
                        if finding.deviation_pct is not None
                        else "—",
                    )
                    st.write(f"**Offizielle Bezeichnung:** {finding.official_label or '—'}")
                    st.write(f"**Begründung:** {finding.reason or '—'}")
                    if finding.source_url:
                        st.link_button("Offizielle Quelle öffnen", finding.source_url)
                    accept_col, reject_col = st.columns(2)
                    if accept_col.button(
                        "Übernehmen",
                        key=f"accept-ai-{finding.id}",
                        type="primary",
                    ):
                        with get_session() as session:
                            current = get_analysis(session, analysis_id)
                            if current is not None:
                                accept_ai_review_finding(session, current, finding.id)
                        st.rerun()
                    if reject_col.button("Verwerfen", key=f"reject-ai-{finding.id}"):
                        with get_session() as session:
                            current = get_analysis(session, analysis_id)
                            if current is not None:
                                reject_ai_review_finding(session, current, finding.id)
                        st.rerun()

# -----------------------------------------------------------------------------
# 4. Manual corrections
# -----------------------------------------------------------------------------
st.divider()
with st.expander("4. Manuelle Korrekturen – nur bei Bedarf", expanded=False):
    st.caption(
        "Nur verwenden, wenn eine bessere offizielle Primärquelle bekannt ist. Der importierte "
        "Originalwert bleibt immer erhalten."
    )
    selectable = [
        fact for fact in preferred_facts if fact.value is not None and fact.period_type == "FY"
    ]
    if not selectable:
        st.caption("Keine korrigierbaren Finanzwerte vorhanden.")
    else:
        labels = {
            f"{fact.period_end.year} · {fact.metric} · {fact.value} {fact.currency or ''} · {fact.provider}": fact
            for fact in selectable
        }
        selected_fact = labels[st.selectbox("Zu korrigierender Wert", list(labels))]
        with st.form("manual-financial-override"):
            corrected_raw = st.text_input("Korrigierter Wert", value=str(selected_fact.value))
            source_name = st.text_input("Quelle / Dokument", placeholder="z. B. Annual Report 2025")
            source_url = st.text_input("Offizielle Quellen-URL")
            note = st.text_area("Begründung")
            save_override = st.form_submit_button("Korrektur übernehmen", disabled=not editable)
        if save_override:
            try:
                if not source_name.strip():
                    raise ValueError("Für eine Korrektur muss eine Quelle angegeben werden.")
                with get_session() as session:
                    current = get_analysis(session, analysis_id)
                    if current is None:
                        raise ValueError("Analyse nicht gefunden.")
                    upsert_manual_financial_override(
                        session,
                        current,
                        metric=selected_fact.metric,
                        period_end=selected_fact.period_end,
                        value=_decimal(corrected_raw),
                        currency=selected_fact.currency,
                        unit=selected_fact.unit,
                        statement=selected_fact.statement,
                        source_name=source_name,
                        source_url=source_url,
                        note=note,
                    )
                st.rerun()
            except (ValueError, AnalysisFrozenError) as exc:
                st.error(str(exc))

        manual_rows = [fact for fact in facts if fact.provider == "manual_override"]
        if manual_rows:
            st.markdown("**Aktive bestätigte Korrekturen**")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Jahr": row.period_end.year,
                            "Metrik": row.metric,
                            "Wert": float(row.value) if row.value is not None else None,
                            "Währung": row.currency,
                            "Quelle": row.source_url,
                            "Begründung": row.note,
                        }
                        for row in manual_rows
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
            removal_options = {f"{row.period_end.year} · {row.metric}": row for row in manual_rows}
            remove_label = st.selectbox("Korrektur entfernen", list(removal_options))
            if st.button("Ausgewählte Korrektur entfernen", disabled=not editable):
                row = removal_options[remove_label]
                with get_session() as session:
                    current = get_analysis(session, analysis_id)
                    if current is not None:
                        remove_manual_financial_override(
                            session,
                            current,
                            metric=row.metric,
                            period_end=row.period_end,
                        )
                st.rerun()

# -----------------------------------------------------------------------------
# 5. Estimates
# -----------------------------------------------------------------------------
st.divider()
with st.expander("5. Analystenschätzungen – optional", expanded=False):
    st.caption(
        "SEC/ESEF liefern veröffentlichte Ist-Daten, aber keinen Analystenkonsens. Schätzungen bleiben "
        "deshalb ein separater optionaler Datenblock."
    )
    if alpha_key_available and editable:
        if st.button("Analystenschätzungen über Alpha Vantage laden"):
            try:
                provider = AlphaVantageProvider()
                with get_session() as session:
                    current = get_analysis(session, analysis_id)
                    if current is None:
                        raise ValueError("Analyse nicht gefunden.")
                    estimate_count = sync_alphavantage_estimates(
                        session,
                        current,
                        provider,
                        symbol=alpha_symbol,
                    )
                st.success(f"Analystenschätzungen geladen: {estimate_count} Datensätze.")
                st.rerun()
            except (ValueError, AnalysisFrozenError, ProviderError) as exc:
                st.warning("Analystenschätzungen konnten nicht geladen werden: " + str(exc))
    elif not alpha_key_available:
        st.caption("Kein Alpha-Vantage-Key hinterlegt; die historischen Ist-Daten sind davon unabhängig.")

    if not estimates:
        st.caption("Noch keine Analystenschätzungen gespeichert.")
    else:
        fiscal_year_end = infer_fiscal_year_end_month_day(facts)
        relevant = relevant_estimates(estimates, as_of_date=analysis_as_of_date)
        show_quarters = st.checkbox("Quartalsschätzungen anzeigen", value=False)
        show_history = st.checkbox("Historische Estimate-Historie anzeigen", value=False)
        base_estimates = estimates if show_history else relevant
        visible_estimates = (
            base_estimates
            if show_quarters
            else annual_estimates(base_estimates, fiscal_year_end=fiscal_year_end)
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Typ": estimate_period_type(item.period, fiscal_year_end=fiscal_year_end),
                        "Periode": item.period,
                        "Metrik": item.metric,
                        "Low": float(item.low) if item.low is not None else None,
                        "Konsens": float(item.average) if item.average is not None else None,
                        "High": float(item.high) if item.high is not None else None,
                        "Analysten": item.analyst_count,
                        "Quelle": item.provider,
                    }
                    for item in visible_estimates
                ]
            ),
            width="stretch",
            hide_index=True,
        )
