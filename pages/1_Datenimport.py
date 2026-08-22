from __future__ import annotations

import os

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
from stock_valuation.analyses.service import AnalysisFrozenError, get_analysis, list_analyses
from stock_valuation.companies.provider_symbols import get_provider_symbol, upsert_provider_symbol
from stock_valuation.data.providers.alphavantage import AlphaVantageProvider
from stock_valuation.data.providers.base import ProviderError
from stock_valuation.data.providers.eodhd import EODHDProvider
from stock_valuation.data.snapshot_service import (
    sync_alphavantage_estimates,
    sync_alphavantage_financials,
    sync_eodhd_snapshot,
)
from stock_valuation.database.models import AnalysisStatus, EstimateSnapshot, FinancialFactSnapshot
from stock_valuation.database.session import get_session, init_database


load_dotenv()
init_database()
st.set_page_config(page_title="Finanzdaten", layout="wide")

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


st.title("Finanzdaten")
st.caption(
    "Im normalen Workflow genügt ein Klick. Alpha Vantage lädt GuV, Bilanz, Cashflow und "
    "Analystenschätzungen; alle Daten werden im ausgewählten Analyse-Snapshot gespeichert."
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
    company_currency = analysis.company.currency
    legacy_eodhd_symbol = analysis.company.provider_symbol

alpha_symbol = alpha_identifier.symbol if alpha_identifier else company_ticker
api_key_available = bool(os.getenv("ALPHA_VANTAGE_API_KEY"))

header = st.columns(5)
header[0].metric("Unternehmen", analysis.company.name)
header[1].metric("Ticker", company_ticker)
header[2].metric("Fundamentals-Symbol", alpha_symbol or "—")
header[3].metric("Revision", f"R{analysis.revision_number}")
header[4].metric("Status", STATUS_LABELS.get(analysis.status, analysis.status.value))

if not api_key_available:
    st.warning("ALPHA_VANTAGE_API_KEY fehlt in der lokalen `.env`.")
elif not editable:
    st.info(
        "Diese Analyse ist abgeschlossen und eingefroren. Für aktuelle Daten zuerst eine neue "
        "Revision anlegen."
    )
else:
    st.subheader("Automatischer Import")
    st.write(
        "Der Button verwendet normalerweise **4 Alpha-Vantage-Requests**: GuV, Bilanz, "
        "Cashflow und Analystenschätzungen. Die Finanzabschlüsse werden zuerst gespeichert. "
        "Falls nur die Estimates fehlen, bleiben die bereits geladenen Abschlüsse erhalten."
    )

    if st.button(
        "Daten laden / aktualisieren",
        type="primary",
        disabled=not alpha_symbol,
        help="Ein Klick: 3 Requests Finanzabschlüsse + 1 Request Analystenschätzungen.",
    ):
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
                st.info(
                    "Finanzabschlüsse wurden gespeichert; Alpha Vantage lieferte für dieses "
                    "Unternehmen derzeit keine Analystenschätzungen."
                )
        except (ValueError, AnalysisFrozenError, ProviderError) as exc:
            st.warning(
                "Die Finanzabschlüsse wurden erfolgreich gespeichert, aber die "
                "Analystenschätzungen konnten nicht aktualisiert werden: " + str(exc)
            )

with st.expander("Erweitert / Diagnose", expanded=False):
    st.caption(
        "Diese Funktionen sind für Fehlersuche und Sonderfälle gedacht. Im normalen Workflow "
        "werden sie nicht benötigt."
    )
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
            with st.spinner(f"Teste {diagnostic_symbol} …"):
                result = provider.probe_income_statement(diagnostic_symbol)
            if result["annual_report_count"]:
                with get_session() as session:
                    current = get_analysis(session, analysis_id)
                    if current is None:
                        raise ValueError("Analyse nicht gefunden.")
                    upsert_provider_symbol(
                        session,
                        current.company,
                        provider="alphavantage",
                        purpose="fundamentals",
                        symbol=diagnostic_symbol,
                        currency=result.get("reported_currency") or company_currency,
                        note="Fundamentals-Symbol durch INCOME_STATEMENT-Probe bestätigt.",
                    )
                st.success(
                    f"{result['annual_report_count']} Jahresberichte und "
                    f"{result['quarterly_report_count']} Quartalsberichte gefunden."
                )
            else:
                st.warning("Für dieses Symbol wurden keine Jahresabschlüsse gefunden.")
            st.json(result)
        except (ProviderError, ValueError) as exc:
            st.error(str(exc))

    separate = st.columns(2)
    with separate[0]:
        if st.button(
            "Nur Finanzabschlüsse importieren (3 Requests)",
            disabled=not editable or not api_key_available or not diagnostic_symbol,
        ):
            try:
                provider = AlphaVantageProvider()
                with get_session() as session:
                    current = get_analysis(session, analysis_id)
                    if current is None:
                        raise ValueError("Analyse nicht gefunden.")
                    count = sync_alphavantage_financials(
                        session, current, provider, symbol=diagnostic_symbol
                    )
                st.success(f"{count} Finanzdatenpunkte gespeichert.")
            except (ProviderError, AnalysisFrozenError, ValueError) as exc:
                st.error(str(exc))

    with separate[1]:
        if st.button(
            "Nur Analystenschätzungen importieren (1 Request)",
            disabled=not editable or not api_key_available or not diagnostic_symbol,
        ):
            try:
                provider = AlphaVantageProvider()
                with get_session() as session:
                    current = get_analysis(session, analysis_id)
                    if current is None:
                        raise ValueError("Analyse nicht gefunden.")
                    count = sync_alphavantage_estimates(
                        session, current, provider, symbol=diagnostic_symbol
                    )
                st.success(f"{count} Schätzdatensätze gespeichert.")
            except (ProviderError, AnalysisFrozenError, ValueError) as exc:
                st.error(str(exc))

    st.divider()
    st.caption("Optionaler EODHD-Adapter")
    if legacy_eodhd_symbol and os.getenv("EODHD_API_KEY") and editable:
        if st.button("EODHD importieren"):
            try:
                provider = EODHDProvider()
                with get_session() as session:
                    current = get_analysis(session, analysis_id)
                    if current is None:
                        raise ValueError("Analyse nicht gefunden.")
                    fact_count, estimate_count = sync_eodhd_snapshot(session, current, provider)
                st.success(
                    f"EODHD: {fact_count} Finanzdatenpunkte und {estimate_count} Estimates gespeichert."
                )
            except (ProviderError, AnalysisFrozenError, ValueError) as exc:
                st.error(str(exc))
    else:
        st.caption("EODHD ist für diese Analyse derzeit nicht aktiv/verfügbar.")

st.divider()
st.subheader("Gespeicherter Datenstand")
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

if not facts:
    st.caption("Noch keine Finanzdaten in diesem Snapshot.")
else:
    missing_count = sum(1 for fact in facts if fact.value is None)
    cross_check_count = sum(1 for fact in facts if fact.is_cross_check_only)
    years = sorted({fact.period_end.year for fact in facts})
    providers = sorted({fact.provider or "—" for fact in facts})

    summary = st.columns(5)
    summary[0].metric("Datenpunkte", len(facts))
    summary[1].metric("Geschäftsjahre", len(years))
    summary[2].metric("Missing", missing_count)
    summary[3].metric("Cross-Check", cross_check_count)
    summary[4].metric("Quellen", len(providers))

    with st.expander("Rohdaten anzeigen", expanded=False):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Periode": fact.period_end,
                        "Quelle": fact.provider,
                        "Source Type": fact.source_type,
                        "Statement": fact.statement,
                        "Interner Schlüssel": fact.metric,
                        "Wert": float(fact.value) if fact.value is not None else None,
                        "Währung": fact.currency,
                        "Provider-Feld": fact.provider_field,
                        "Originalwert": (
                            float(fact.provider_value) if fact.provider_value is not None else None
                        ),
                        "Cross-Check": fact.is_cross_check_only,
                    }
                    for fact in facts
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

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
    if not show_quarters:
        hidden_quarters = len(base_estimates) - len(visible_estimates)
        st.caption(f"{hidden_quarters} Quartalsdatensätze ausgeblendet.")

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Typ": estimate_period_type(
                        item.period,
                        fiscal_year_end=fiscal_year_end,
                    ),
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

st.info(
    "Für die spätere Bewertung werden nur gespeicherte Snapshot-Daten verwendet. Offizielle "
    "Primärquellen können einzelne Werte zusätzlich absichern, sind aber kein notwendiger "
    "manueller Schritt für den normalen Alpha-Vantage-Import."
)
