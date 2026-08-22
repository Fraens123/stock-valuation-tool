from __future__ import annotations

import os
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
from stock_valuation.companies.provider_symbols import get_provider_symbol, upsert_provider_symbol
from stock_valuation.data.audit import run_deterministic_audit
from stock_valuation.data.providers.alphavantage import AlphaVantageProvider
from stock_valuation.data.providers.base import ProviderError
from stock_valuation.data.resolution import load_preferred_financial_facts
from stock_valuation.data.snapshot_service import (
    sync_alphavantage_estimates,
    sync_alphavantage_financials,
)
from stock_valuation.database.models import AnalysisStatus, EstimateSnapshot, FinancialFactSnapshot
from stock_valuation.database.session import get_session, init_database
from stock_valuation.ui.navigation import render_navigation


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


st.title("Finanzdaten")
st.caption(
    "Normaler Ablauf: Alpha Vantage laden → lokal plausibilisieren → optional mit ChatGPT gegen "
    "offizielle Quellen prüfen → Abweichungen selbst übernehmen oder verwerfen."
)

with get_session() as session:
    analyses = list_analyses(session, include_archived=True)
    options = {_analysis_label(a): a.id for a in analyses}

if not options:
    st.info("Zuerst unter **Unternehmen** eine Aktie auswählen und eine Analyse anlegen.")
    st.stop()

selected_label = st.selectbox("Analyse", list(options))
analysis_id = options[selected_label]

with get_session() as session:
    analysis = get_analysis(session, analysis_id)
    if analysis is None:
        st.error("Analyse nicht gefunden.")
        st.stop()
    alpha_identifier = get_provider_symbol(
        session,
        analysis.company,
        provider="alphavantage",
        purpose="fundamentals",
    )
    editable = analysis.status in {AnalysisStatus.DRAFT, AnalysisStatus.IN_PROGRESS}
    analysis_as_of_date = analysis.as_of_date
    company_ticker = analysis.company.ticker

alpha_symbol = alpha_identifier.symbol if alpha_identifier else company_ticker
alpha_key_available = bool(os.getenv("ALPHA_VANTAGE_API_KEY"))

header = st.columns(5)
header[0].metric("Unternehmen", analysis.company.name)
header[1].metric("Ticker", company_ticker)
header[2].metric("Fundamentals-Symbol", alpha_symbol or "—")
header[3].metric("Revision", f"R{analysis.revision_number}")
header[4].metric("Status", STATUS_LABELS.get(analysis.status, analysis.status.value))

# -----------------------------------------------------------------------------
# 1. Import
# -----------------------------------------------------------------------------
st.subheader("1. Daten laden")
if not alpha_key_available:
    st.warning("ALPHA_VANTAGE_API_KEY fehlt in der lokalen `.env`.")
elif not editable:
    st.info(
        "Diese Analyse ist abgeschlossen und eingefroren. Für aktuelle Daten zuerst eine neue "
        "Revision anlegen."
    )
else:
    st.write(
        "Ein Klick lädt GuV, Bilanz, Cashflow und Analystenschätzungen. "
        "Das sind intern normalerweise **4 Alpha-Vantage-Requests**."
    )
    if st.button("Daten laden / aktualisieren", type="primary", disabled=not alpha_symbol):
        provider = AlphaVantageProvider()
        try:
            with get_session() as session:
                current = get_analysis(session, analysis_id)
                if current is None:
                    raise ValueError("Analyse wurde nicht gefunden.")
                with st.spinner(f"Lade Finanzabschlüsse für {alpha_symbol} …"):
                    fact_count = sync_alphavantage_financials(
                        session,
                        current,
                        provider,
                        symbol=alpha_symbol,
                    )
                upsert_provider_symbol(
                    session,
                    current.company,
                    provider="alphavantage",
                    purpose="fundamentals",
                    symbol=alpha_symbol,
                    note="Erfolgreicher automatischer Finanzabschlussimport.",
                )
            st.success(f"Finanzabschlüsse geladen: {fact_count} Datenpunkte gespeichert.")
        except (ValueError, AnalysisFrozenError, ProviderError) as exc:
            st.error(str(exc))
            st.stop()

        try:
            with get_session() as session:
                current = get_analysis(session, analysis_id)
                if current is None:
                    raise ValueError("Analyse wurde nicht gefunden.")
                with st.spinner("Lade Analystenschätzungen …"):
                    estimate_count = sync_alphavantage_estimates(
                        session,
                        current,
                        provider,
                        symbol=alpha_symbol,
                    )
            if estimate_count:
                st.success(f"Analystenschätzungen geladen: {estimate_count} Datensätze gespeichert.")
            else:
                st.info("Finanzabschlüsse gespeichert; aktuell keine Estimates geliefert.")
        except (ValueError, AnalysisFrozenError, ProviderError) as exc:
            st.warning(
                "Finanzabschlüsse wurden gespeichert, die Analystenschätzungen aber nicht: " + str(exc)
            )
        st.rerun()

with get_session() as session:
    facts = session.scalars(
        select(FinancialFactSnapshot)
        .where(FinancialFactSnapshot.analysis_id == analysis_id)
        .order_by(FinancialFactSnapshot.period_end.desc(), FinancialFactSnapshot.metric)
    ).all()
    estimates = session.scalars(
        select(EstimateSnapshot)
        .where(EstimateSnapshot.analysis_id == analysis_id)
        .order_by(EstimateSnapshot.period, EstimateSnapshot.metric)
    ).all()
    preferred = load_preferred_financial_facts(session, analysis_id)

# -----------------------------------------------------------------------------
# 2. Stored data
# -----------------------------------------------------------------------------
st.divider()
st.subheader("2. Gespeicherter Datenstand")
if not facts:
    st.caption("Noch keine Finanzdaten in diesem Snapshot.")
else:
    missing_count = sum(1 for fact in facts if fact.value is None)
    years = sorted({fact.period_end.year for fact in facts if fact.period_type == "FY"})
    providers = sorted({fact.provider or "—" for fact in facts})
    overrides = [fact for fact in facts if fact.provider == "manual_override"]

    summary = st.columns(5)
    summary[0].metric("Datenpunkte", len(facts))
    summary[1].metric("Geschäftsjahre", len(years))
    summary[2].metric("Missing", missing_count)
    summary[3].metric("Quellen", len(providers))
    summary[4].metric("Bestätigte Korrekturen", len(overrides))

    with st.expander("Rohdaten anzeigen", expanded=False):
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
            use_container_width=True,
            hide_index=True,
        )

# -----------------------------------------------------------------------------
# 3. Review
# -----------------------------------------------------------------------------
st.divider()
st.subheader("3. Daten prüfen")
if not preferred:
    st.caption("Für die Prüfung müssen zuerst Finanzdaten importiert werden.")
else:
    with get_session() as session:
        current = get_analysis(session, analysis_id)
        audit_checks = run_deterministic_audit(session, current) if current is not None else []
        latest_run = latest_ai_review_run(session, analysis_id)

    check_count = sum(item.status == "CHECK" for item in audit_checks)
    audit_cols = st.columns(3)
    audit_cols[0].metric("Plausibilitätschecks", len(audit_checks))
    audit_cols[1].metric("PASS", sum(item.status == "PASS" for item in audit_checks))
    audit_cols[2].metric("Intern prüfen", check_count)

    if audit_checks:
        with st.expander("Kostenlose lokale Plausibilitätsprüfung", expanded=bool(check_count)):
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
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("#### ChatGPT-Prüfung gegen offizielle Quellen")
    st.write(
        "Diese Prüfung verwendet **keinen OpenAI-API-Key**. Das Tool erstellt ein Prüfpaket, "
        "das du in deinem normalen ChatGPT hochlädst. ChatGPT recherchiert die offiziellen Quellen "
        "und gibt eine JSON-Ergebnisdatei zurück, die hier wieder eingelesen wird."
    )

    review_years = st.selectbox(
        "Geschäftsjahre tief prüfen",
        [2, 3, 5],
        index=1,
        help="Für den ersten Test sind 2 oder 3 Jahre sinnvoll. Die lokale Historie bleibt vollständig gespeichert.",
    )

    try:
        with get_session() as session:
            current = get_analysis(session, analysis_id)
            if current is None:
                raise ValueError("Analyse nicht gefunden.")
            review_package = build_chatgpt_review_package(
                session,
                current,
                years=int(review_years),
            )

        package_cols = st.columns([1, 2])
        with package_cols[0]:
            st.download_button(
                "1. ChatGPT-Prüfpaket herunterladen",
                data=review_package.content,
                file_name=review_package.filename,
                mime="text/markdown",
                type="primary",
            )
        with package_cols[1]:
            st.caption(
                f"{review_package.fact_count} Fakten · Package-ID `{review_package.package_id[:12]}…` · "
                f"erwartete Ergebnisdatei: `{review_package.result_filename}`"
            )

        st.info(
            "**In ChatGPT:** Datei hochladen und schreiben: „Führe die Prüfung aus und erstelle die "
            "angeforderte JSON-Ergebnisdatei.“ Danach die von ChatGPT erzeugte `.json`-Datei hier hochladen."
        )

        uploaded_review = st.file_uploader(
            "2. ChatGPT-Prüfergebnis hochladen",
            type=["json"],
            accept_multiple_files=False,
            key=f"chatgpt-review-result-{analysis_id}",
        )
        if uploaded_review is not None:
            st.caption(f"Ausgewählt: `{uploaded_review.name}`")
            if st.button(
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
                        f"ChatGPT-Prüfung eingelesen: Lauf #{run.id} mit {len(run.findings)} Prüffunden."
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
        st.markdown("##### Letztes eingelesenes ChatGPT-Prüfergebnis")
        st.caption(
            f"Importiert: {latest_run.created_at} · {latest_run.years_requested} Geschäftsjahre · "
            f"Package-ID `{(latest_run.response_id or '—')[:12]}…`"
        )
        if latest_run.summary:
            st.info(latest_run.summary)

        result_cols = st.columns(4)
        result_cols[0].metric("PASS", counts["PASS"])
        result_cols[1].metric("WARN", counts["WARN"])
        result_cols[2].metric("FAIL", counts["FAIL"])
        result_cols[3].metric("UNKLAR", counts["UNKLAR"])

        show_pass = st.checkbox("Auch PASS-Zeilen anzeigen", value=False)
        visible = findings if show_pass else [row for row in findings if row.verdict != "PASS"]
        if visible:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Jahr": row.period_end.year,
                            "Status": row.verdict,
                            "Metrik": row.metric,
                            "Importiert": float(row.imported_value) if row.imported_value is not None else None,
                            "Offiziell": float(row.official_value) if row.official_value is not None else None,
                            "Abweichung %": float(row.deviation_pct) if row.deviation_pct is not None else None,
                            "Währung": row.currency,
                            "Offizielle Bezeichnung": row.official_label,
                            "Quelle": row.source_title,
                            "Entscheidung": row.decision,
                            "Begründung": row.reason,
                        }
                        for row in visible
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.success("Keine Abweichungen oder unklaren Positionen in der letzten ChatGPT-Prüfung.")

        pending = [
            row
            for row in findings
            if row.decision == "pending"
            and row.verdict in {"WARN", "FAIL"}
            and row.official_value is not None
        ]
        if pending:
            st.markdown("##### Korrekturvorschläge entscheiden")
            st.caption(
                "**Übernehmen** legt einen bestätigten Override an. **Verwerfen** behält den "
                "bisher verwendeten Wert. Der Alpha-Vantage-Originalwert bleibt in beiden Fällen erhalten."
            )
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
                        (
                            f"{float(finding.deviation_pct):.3f} %"
                            if finding.deviation_pct is not None
                            else "—"
                        ),
                    )
                    st.write(f"**Offizielle Bezeichnung:** {finding.official_label or '—'}")
                    st.write(f"**Begründung:** {finding.reason or '—'}")
                    if finding.source_url:
                        st.link_button("Offizielle Quelle öffnen", finding.source_url)

                    a, r = st.columns(2)
                    if a.button("Übernehmen", key=f"accept-ai-{finding.id}", type="primary"):
                        try:
                            with get_session() as session:
                                current = get_analysis(session, analysis_id)
                                if current is None:
                                    raise ValueError("Analyse nicht gefunden.")
                                accept_ai_review_finding(session, current, finding.id)
                            st.rerun()
                        except (AnalysisFrozenError, ValueError) as exc:
                            st.error(str(exc))
                    if r.button("Verwerfen", key=f"reject-ai-{finding.id}"):
                        try:
                            with get_session() as session:
                                current = get_analysis(session, analysis_id)
                                if current is None:
                                    raise ValueError("Analyse nicht gefunden.")
                                reject_ai_review_finding(session, current, finding.id)
                            st.rerun()
                        except (AnalysisFrozenError, ValueError) as exc:
                            st.error(str(exc))

# -----------------------------------------------------------------------------
# 4. Manual correction
# -----------------------------------------------------------------------------
st.divider()
st.subheader("4. Manuelle Korrektur")
st.caption(
    "Falls du selbst eine bessere Primärquelle kennst, kannst du einen Wert direkt korrigieren. "
    "Der importierte Originalwert wird niemals gelöscht."
)

if not preferred:
    st.caption("Noch keine importierten Werte vorhanden.")
else:
    selectable = [fact for fact in preferred if fact.value is not None and fact.period_type == "FY"]
    labels = {
        f"{fact.period_end.year} · {fact.metric} · {fact.value} {fact.currency or ''} · {fact.provider}": fact
        for fact in selectable
    }
    selected_fact = labels[st.selectbox("Zu korrigierender Wert", list(labels))]

    with st.form("manual-financial-override"):
        corrected_raw = st.text_input("Korrigierter Wert", value=str(selected_fact.value))
        source_name = st.text_input("Quelle / Dokument", placeholder="z. B. Annual Report 2026")
        source_url = st.text_input("Offizielle Quellen-URL (empfohlen)")
        note = st.text_area("Begründung der Korrektur")
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
            st.success("Korrektur gespeichert. Der importierte Originalwert bleibt erhalten.")
            st.rerun()
        except (ValueError, AnalysisFrozenError) as exc:
            st.error(str(exc))

    manual_rows = [fact for fact in facts if fact.provider == "manual_override"]
    if manual_rows:
        with st.expander("Aktive bestätigte Korrekturen", expanded=False):
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
                use_container_width=True,
                hide_index=True,
            )
            removal_options = {f"{row.period_end.year} · {row.metric}": row for row in manual_rows}
            remove_label = st.selectbox(
                "Bestätigte Korrektur entfernen",
                list(removal_options),
                key="remove-override",
            )
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
# Estimates
# -----------------------------------------------------------------------------
st.divider()
st.subheader("Analystenschätzungen")
if not estimates:
    st.caption("Noch keine Analystenschätzungen gespeichert oder vom Provider geliefert.")
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

    if fiscal_year_end:
        st.caption(
            f"Erkanntes Geschäftsjahresende: {fiscal_year_end[1]:02d}.{fiscal_year_end[0]:02d}. "
            "Standardmäßig werden nur volle Geschäftsjahresschätzungen gezeigt."
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
                    "Abruf": item.retrieved_at,
                }
                for item in visible_estimates
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
