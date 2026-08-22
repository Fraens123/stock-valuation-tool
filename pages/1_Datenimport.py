from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import select

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
from stock_valuation.data.audit import build_ai_review_prompt, run_deterministic_audit
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


st.title("Finanzdaten")
st.caption(
    "Normaler Ablauf: Analyse auswählen → **Daten laden / aktualisieren**. "
    "Danach können die Daten automatisch geprüft und bei Bedarf nachvollziehbar korrigiert werden."
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
api_key_available = bool(os.getenv("ALPHA_VANTAGE_API_KEY"))

header = st.columns(5)
header[0].metric("Unternehmen", analysis.company.name)
header[1].metric("Ticker", company_ticker)
header[2].metric("Fundamentals-Symbol", alpha_symbol or "—")
header[3].metric("Revision", f"R{analysis.revision_number}")
header[4].metric("Status", STATUS_LABELS.get(analysis.status, analysis.status.value))

st.subheader("1. Daten laden")
if not api_key_available:
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

st.divider()
st.subheader("2. Gespeicherter Datenstand")
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

if not facts:
    st.caption("Noch keine Finanzdaten in diesem Snapshot.")
else:
    missing_count = sum(1 for fact in facts if fact.value is None)
    years = sorted({fact.period_end.year for fact in facts})
    providers = sorted({fact.provider or "—" for fact in facts})
    overrides = [fact for fact in facts if fact.provider == "manual_override"]

    summary = st.columns(5)
    summary[0].metric("Datenpunkte", len(facts))
    summary[1].metric("Geschäftsjahre", len(years))
    summary[2].metric("Missing", missing_count)
    summary[3].metric("Quellen", len(providers))
    summary[4].metric("Manuelle Korrekturen", len(overrides))

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

st.divider()
st.subheader("3. Daten prüfen")
if not preferred:
    st.caption("Für die Prüfung müssen zuerst Finanzdaten importiert werden.")
else:
    with get_session() as session:
        current = get_analysis(session, analysis_id)
        audit_checks = run_deterministic_audit(session, current) if current is not None else []

    check_count = sum(item.status == "CHECK" for item in audit_checks)
    audit_cols = st.columns(3)
    audit_cols[0].metric("Plausibilitätschecks", len(audit_checks))
    audit_cols[1].metric("PASS", sum(item.status == "PASS" for item in audit_checks))
    audit_cols[2].metric("Prüfen", check_count)

    if audit_checks:
        with st.expander("Automatische Plausibilitätsprüfung", expanded=bool(check_count)):
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

    with st.expander("KI-Prüfung", expanded=False):
        st.write(
            "Die KI-Prüfung soll später die importierten Zahlen mit offiziellen Annual Reports, "
            "10-K/20-F bzw. Investor-Relations-Unterlagen vergleichen. Sie darf nur "
            "Korrekturvorschläge machen; übernommen wird nichts ohne Bestätigung."
        )
        st.info(
            "Aktuell erzeugt dieser Button das vollständige Prüf-Paket. Die direkte automatische "
            "Ausführung wird als optionaler KI-Provider angebunden, damit kein kostenpflichtiger "
            "API-Dienst still vorausgesetzt wird."
        )
        if st.button("KI-Prüfprompt erstellen"):
            with get_session() as session:
                current = get_analysis(session, analysis_id)
                if current is None:
                    st.error("Analyse nicht gefunden.")
                else:
                    st.session_state[f"ai-review-prompt-{analysis_id}"] = build_ai_review_prompt(
                        session, current
                    )
        ai_prompt = st.session_state.get(f"ai-review-prompt-{analysis_id}")
        if ai_prompt:
            st.text_area(
                "Prüfprompt",
                value=ai_prompt,
                height=420,
                help="Kann bis zur direkten KI-Anbindung in einen Chat mit Webzugriff kopiert werden.",
            )

st.divider()
st.subheader("4. Werte korrigieren")
st.caption(
    "Korrekturen überschreiben Alpha Vantage **nicht**. Der Originalwert bleibt gespeichert; "
    "deine bestätigte Korrektur wird als separater `manual_override` mit höherer Priorität geführt."
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

    original_candidates = [
        fact
        for fact in facts
        if fact.metric == selected_fact.metric
        and fact.period_end == selected_fact.period_end
        and fact.provider != "manual_override"
        and fact.value is not None
    ]
    original_candidates.sort(key=lambda item: item.provider or "")
    if original_candidates:
        original = original_candidates[0]
        st.caption(
            f"Importierter Vergleichswert: **{original.value} {original.currency or ''}** · "
            f"Quelle `{original.provider}` · Feld `{original.provider_field or '—'}`"
        )

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
        st.markdown("#### Aktive manuelle Korrekturen")
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
        removal_options = {
            f"{row.period_end.year} · {row.metric}": row for row in manual_rows
        }
        remove_label = st.selectbox("Korrektur entfernen", list(removal_options), key="remove-override")
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
            "Standardmäßig werden nur Jahresschätzungen gezeigt."
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

with st.expander("Erweitert / Provider-Diagnose", expanded=False):
    st.caption("Nur für Symbol-/Providerprobleme; im normalen Workflow nicht erforderlich.")
    diagnostic_symbol = st.text_input(
        "Alpha-Vantage-Fundamentals-Symbol",
        value=alpha_symbol,
        key=f"diagnostic-symbol-{analysis_id}",
    ).strip()
    if st.button(
        "Fundamentals testen (1 Request)",
        disabled=not api_key_available or not diagnostic_symbol,
    ):
        try:
            provider = AlphaVantageProvider()
            result = provider.probe_income_statement(diagnostic_symbol)
            st.json(result)
            if result["annual_report_count"]:
                st.success("Fundamentals für dieses Symbol verfügbar.")
            else:
                st.warning("Für dieses Symbol wurden keine Jahresabschlüsse gefunden.")
        except ProviderError as exc:
            st.error(str(exc))
