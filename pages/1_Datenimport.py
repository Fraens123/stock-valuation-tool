from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import select

from stock_valuation.analyses.estimate_service import relevant_estimates
from stock_valuation.analyses.service import AnalysisFrozenError, get_analysis, list_analyses
from stock_valuation.companies.provider_symbols import get_provider_symbol, upsert_provider_symbol
from stock_valuation.data.providers.alphavantage import AlphaVantageProvider
from stock_valuation.data.providers.base import ProviderError
from stock_valuation.data.providers.eodhd import EODHDProvider
from stock_valuation.data.snapshot_service import sync_alphavantage_snapshot, sync_eodhd_snapshot
from stock_valuation.database.models import AnalysisStatus, EstimateSnapshot, FinancialFactSnapshot
from stock_valuation.database.session import get_session, init_database


load_dotenv()
init_database()
st.set_page_config(page_title="Datenimport", layout="wide")

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


st.title("Datenimport")
st.caption(
    "Der automatische Import ist unternehmensunabhängig. Für jede neue Aktie wird zuerst ein "
    "Provider-Symbol geprüft und anschließend als Teil der Unternehmenskonfiguration gespeichert. "
    "ASML ist nur der Referenzfall für zusätzliche Primärquellen-Validierung."
)

with get_session() as session:
    analyses = list_analyses(session, include_archived=True)
    options = {_analysis_label(a): a.id for a in analyses}

if not options:
    st.info("Zuerst unter **Unternehmen** eine Aktie suchen und eine Analyse anlegen.")
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

    cols = st.columns(5)
    cols[0].metric("Unternehmen", analysis.company.name)
    cols[1].metric("Ticker", analysis.company.ticker)
    cols[2].metric(
        "Alpha-Vantage-Symbol",
        alpha_identifier.symbol if alpha_identifier else "noch nicht gespeichert",
    )
    cols[3].metric("Revision", f"R{analysis.revision_number}")
    cols[4].metric("Status", STATUS_LABELS.get(analysis.status, analysis.status.value))

    editable = analysis.status in {AnalysisStatus.DRAFT, AnalysisStatus.IN_PROGRESS}
    analysis_as_of_date = analysis.as_of_date
    company_ticker = analysis.company.ticker
    company_currency = analysis.company.currency
    legacy_eodhd_symbol = analysis.company.provider_symbol

st.divider()
st.subheader("Automatischer Fundamentaldaten-Import")
provider_choice = st.radio(
    "Datenprovider",
    ["Alpha Vantage", "EODHD"],
    horizontal=True,
    help=(
        "Alpha Vantage ist der kostenlose automatische V1-Provider. EODHD bleibt als optionaler "
        "Adapter erhalten; beim getesteten Free-Tarif waren Fundamentals nicht freigeschaltet."
    ),
)

if provider_choice == "Alpha Vantage":
    st.write(
        "Ein vollständiger Import verwendet vier Requests: GuV, Bilanz, Cashflow und "
        "Analystenschätzungen. Vorher wird mit genau einem Request geprüft, ob der gewählte "
        "Provider-Ticker tatsächlich Fundamentals liefert."
    )
    api_key_available = bool(os.getenv("ALPHA_VANTAGE_API_KEY"))
    if api_key_available:
        st.success("ALPHA_VANTAGE_API_KEY ist vorhanden.")
    else:
        st.warning("ALPHA_VANTAGE_API_KEY fehlt in der lokalen `.env`.")

    default_symbol = alpha_identifier.symbol if alpha_identifier else company_ticker
    alpha_symbol = st.text_input(
        "Alpha-Vantage-Fundamentals-Symbol",
        value=default_symbol,
        help=(
            "Normalerweise ist dies der über die Online-Unternehmenssuche gewählte Ticker. "
            "Bei Zweitnotierungen kann der Fundamentals-Ticker von der lokalen Kursnotierung "
            "abweichen. Der erfolgreiche Ticker wird dauerhaft beim Unternehmen gespeichert."
        ),
    ).strip()

    probe_key = f"{analysis_id}:{alpha_symbol.upper()}"
    st.markdown("#### Fundamentals-Verfügbarkeit prüfen")
    st.caption(
        "Genau 1 Request (`INCOME_STATEMENT`). Es werden noch keine Finanzdaten gespeichert."
    )

    if st.button(
        "Fundamentals testen (1 Request)",
        disabled=not api_key_available or not alpha_symbol,
    ):
        try:
            provider = AlphaVantageProvider()
            with st.spinner(f"Teste {alpha_symbol} …"):
                result = provider.probe_income_statement(alpha_symbol)

            if result["annual_report_count"] == 0:
                st.session_state["alpha_probe_ok_key"] = None
                st.warning(
                    "Der Provider-Ticker existiert, liefert aber keine Jahresabschlüsse. "
                    "Bitte auf **Unternehmen** einen anderen Börsen-/Provider-Treffer wählen oder "
                    "hier einen alternativen Fundamentals-Ticker eingeben."
                )
            else:
                with get_session() as session:
                    current = get_analysis(session, analysis_id)
                    if current is None:
                        raise ValueError("Analyse nicht gefunden.")
                    upsert_provider_symbol(
                        session,
                        current.company,
                        provider="alphavantage",
                        purpose="fundamentals",
                        symbol=alpha_symbol,
                        currency=result.get("reported_currency") or company_currency,
                        note="Fundamentals-Symbol durch erfolgreichen INCOME_STATEMENT-Probe bestätigt.",
                    )
                st.session_state["alpha_probe_ok_key"] = probe_key
                st.success(
                    f"Fundamentals verfügbar: {result['annual_report_count']} Jahresberichte, "
                    f"{result['quarterly_report_count']} Quartalsberichte. Symbol wurde gespeichert."
                )

            st.json(
                {
                    "Angefragt": result.get("requested_symbol"),
                    "Zurückgegeben": result.get("returned_symbol"),
                    "Letztes Geschäftsjahr": result.get("latest_fiscal_date") or "—",
                    "Berichtswährung": result.get("reported_currency") or "—",
                    "Letzter Umsatz (raw)": result.get("latest_revenue") or "—",
                }
            )
        except (ProviderError, ValueError) as exc:
            st.session_state["alpha_probe_ok_key"] = None
            st.error(str(exc))

    probe_ok = st.session_state.get("alpha_probe_ok_key") == probe_key
    if not editable:
        st.info(
            "Diese Analyse ist eingefroren. Für aktuelle Daten zuerst eine neue Revision erzeugen."
        )
    elif st.button(
        "Finanzdaten und Schätzungen importieren (4 Requests)",
        type="primary",
        disabled=not api_key_available or not probe_ok,
        help="Wird erst nach einem erfolgreichen 1-Request-Test für genau dieses Symbol freigeschaltet.",
    ):
        try:
            provider = AlphaVantageProvider()
            with get_session() as session:
                current = get_analysis(session, analysis_id)
                if current is None:
                    raise ValueError("Analyse wurde nicht gefunden.")
                with st.spinner(f"Importiere {alpha_symbol} …"):
                    fact_count, estimate_count = sync_alphavantage_snapshot(
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
                    note="Erfolgreicher Fundamentals- und Estimates-Import.",
                )
            st.success(
                f"Import abgeschlossen: {fact_count} Finanzdatenzeilen und "
                f"{estimate_count} Schätzdatensätze gespeichert."
            )
            st.rerun()
        except (ValueError, AnalysisFrozenError, ProviderError) as exc:
            st.error(str(exc))

else:
    st.warning(
        "EODHD ist derzeit nur optional. Der getestete kostenlose Account hatte keinen "
        "Fundamentals-Zugriff."
    )
    api_key_available = bool(os.getenv("EODHD_API_KEY"))
    if not editable:
        st.info("Diese Analyse ist eingefroren.")
    elif not legacy_eodhd_symbol:
        st.error("Für dieses Unternehmen ist kein EODHD-Symbol hinterlegt.")
    elif st.button("EODHD importieren", disabled=not api_key_available):
        try:
            provider = EODHDProvider()
            with get_session() as session:
                current = get_analysis(session, analysis_id)
                if current is None:
                    raise ValueError("Analyse wurde nicht gefunden.")
                fact_count, estimate_count = sync_eodhd_snapshot(session, current, provider)
            st.success(
                f"Import abgeschlossen: {fact_count} Finanzdatenzeilen, "
                f"{estimate_count} Schätzdatensätze gespeichert."
            )
            st.rerun()
        except (ValueError, AnalysisFrozenError, ProviderError) as exc:
            st.error(str(exc))

st.divider()
st.subheader("Gespeicherter Snapshot")
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

    st.caption(
        "Import und Qualitätsprüfung sind getrennt: Providerdaten werden vollständig gespeichert. "
        "Eine zusätzliche Primärquellenprüfung kann später einzelne Felder höher priorisieren, "
        "ohne die Providerhistorie zu löschen."
    )
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
    show_history = st.checkbox("Historische Estimate-Historie anzeigen", value=False)
    visible_estimates = (
        estimates if show_history else relevant_estimates(estimates, as_of_date=analysis_as_of_date)
    )
    if not show_history:
        st.caption(
            f"{len(visible_estimates)} relevante Datensätze ab Analysestichtag; "
            f"{len(estimates) - len(visible_estimates)} historische Datensätze ausgeblendet."
        )
    st.dataframe(
        pd.DataFrame(
            [
                {
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

if company_ticker.upper() == "ASML":
    st.info(
        "Für ASML existiert zusätzlich die Referenz-Primärquellenprüfung auf der Seite "
        "**Datenqualität**. Dieser Spezialcheck dient der Entwicklung der allgemeinen "
        "Qualitätsarchitektur und ist keine Voraussetzung für den Import anderer Aktien."
    )
else:
    st.info(
        "Der automatische Import dieser Aktie ist damit unabhängig von ASML. Die nächste "
        "Ausbaustufe ergänzt generische Primärquellenadapter und einen Qualitätsstatus für "
        "Unternehmen ohne speziellen Referenzadapter."
    )
