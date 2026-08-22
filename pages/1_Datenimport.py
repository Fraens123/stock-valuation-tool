from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import select

from stock_valuation.analyses.service import AnalysisFrozenError, get_analysis, list_analyses
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


def _default_alpha_symbol(analysis) -> str:
    # ASML is the reference case. Productive provider-specific symbol resolution follows
    # later through company search / identifiers instead of hard-coding all exchanges.
    if analysis.company.ticker.upper() == "ASML":
        return "ASML.AMS"
    return analysis.company.ticker


st.title("Datenimport")
st.caption(
    "Rohdaten werden in den ausgewählten Analyse-Snapshot geschrieben. "
    "Kennzahlen werden hier noch nicht berechnet."
)

with get_session() as session:
    analyses = list_analyses(session, include_archived=True)
    options = {_analysis_label(a): a.id for a in analyses}

if not options:
    st.info("Zuerst auf der Startseite eine Analyse anlegen.")
    st.stop()

selected_label = st.selectbox("Analyse", list(options))
analysis_id = options[selected_label]

with get_session() as session:
    analysis = get_analysis(session, analysis_id)
    if analysis is None:
        st.error("Analyse nicht gefunden.")
        st.stop()

    cols = st.columns(5)
    cols[0].metric("Unternehmen", analysis.company.name)
    cols[1].metric("Ticker", analysis.company.ticker)
    cols[2].metric("EODHD-Symbol", analysis.company.provider_symbol or "—")
    cols[3].metric("Revision", f"R{analysis.revision_number}")
    cols[4].metric("Status", STATUS_LABELS.get(analysis.status, analysis.status.value))

    editable = analysis.status in {AnalysisStatus.DRAFT, AnalysisStatus.IN_PROGRESS}

st.divider()
st.subheader("Automatischer Fundamentaldaten-Import")

provider_choice = st.radio(
    "Datenprovider",
    ["Alpha Vantage", "EODHD"],
    horizontal=True,
    help=(
        "Alpha Vantage wird zuerst getestet, weil der Free-Tier laut Anbieter viele "
        "Fundamental-Endpunkte umfasst. EODHD Fundamentals erfordern beim getesteten Free-Key "
        "für ASML einen kostenpflichtigen Tarif."
    ),
)

if provider_choice == "Alpha Vantage":
    st.write(
        "Ein vollständiger Import verwendet vier getrennte Requests: GuV, Bilanz, Cashflow "
        "und Analystenschätzungen. Der Provider wartet im Free-Tier konservativ mindestens "
        "2 Sekunden zwischen Requests. Das Tageslimit von 25 Requests bleibt davon unabhängig."
    )
    api_key_available = bool(os.getenv("ALPHA_VANTAGE_API_KEY"))
    if api_key_available:
        st.success("ALPHA_VANTAGE_API_KEY ist in der lokalen Umgebung vorhanden.")
    else:
        st.warning(
            "ALPHA_VANTAGE_API_KEY fehlt. Kostenlosen Alpha-Vantage-Key anlegen und in `.env` "
            "als `ALPHA_VANTAGE_API_KEY=...` eintragen. API-Keys niemals committen."
        )

    alpha_symbol = st.text_input(
        "Alpha-Vantage-Symbol",
        value=_default_alpha_symbol(analysis),
        help="Für die ASML-Aktie in Amsterdam verwenden wir beim Test `ASML.AMS`.",
    )

    st.markdown("#### Verbindungstest")
    st.caption(
        "Dieser Test verwendet genau **einen** API-Request (`INCOME_STATEMENT`) und speichert "
        "noch keine Daten. Erst wenn dieser Test erfolgreich ist, sollte der vollständige "
        "4-Request-Import gestartet werden."
    )
    if st.button(
        "Alpha Vantage testen (1 Request)",
        disabled=not api_key_available,
    ):
        try:
            provider = AlphaVantageProvider()
            with st.spinner(f"Teste INCOME_STATEMENT für {alpha_symbol} …"):
                result = provider.probe_income_statement(alpha_symbol)
            st.success(
                "Einzeltest erfolgreich: "
                f"{result['annual_report_count']} Jahresberichte und "
                f"{result['quarterly_report_count']} Quartalsberichte wurden vom Endpoint erkannt."
            )
            st.session_state["alpha_probe_ok"] = True
        except ProviderError as exc:
            st.session_state["alpha_probe_ok"] = False
            st.error(str(exc))
            st.info(
                "Wenn bereits dieser einzelne Request dieselbe Limitmeldung liefert, liegt das "
                "Problem nicht an den Abständen innerhalb unseres 4-Request-Imports. Dann heute "
                "keine weiteren Alpha-Vantage-Requests verbrauchen und den Einzeltest später bzw. "
                "nach Rücksetzung des Tageslimits erneut ausführen."
            )
        except Exception as exc:
            st.session_state["alpha_probe_ok"] = False
            st.exception(exc)

    if not editable:
        st.info(
            "Diese Analyse ist abgeschlossen/archiviert und eingefroren. "
            "Für neue Daten zuerst eine neue Revision erzeugen."
        )
    elif st.button(
        "Alpha-Vantage-Finanzdaten und Schätzungen aktualisieren",
        type="primary",
        disabled=not api_key_available,
        help=(
            "Bitte zuerst den 1-Request-Verbindungstest ausführen. Der vollständige Import "
            "benötigt vier API-Requests."
        ),
    ):
        try:
            provider = AlphaVantageProvider()
            with get_session() as session:
                current = get_analysis(session, analysis_id)
                if current is None:
                    raise ValueError("Analyse wurde nicht gefunden.")
                with st.spinner(
                    f"Lade {alpha_symbol} von Alpha Vantage … "
                    "Der Free-Tier-Import dauert wegen der Request-Abstände einige Sekunden."
                ):
                    fact_count, estimate_count = sync_alphavantage_snapshot(
                        session,
                        current,
                        provider,
                        symbol=alpha_symbol,
                    )
            st.success(
                f"Import abgeschlossen: {fact_count} Finanzdatenzeilen, "
                f"{estimate_count} Schätzdatensätze gespeichert."
            )
            st.rerun()
        except (ValueError, AnalysisFrozenError, ProviderError) as exc:
            st.error(str(exc))
            st.caption(
                "Bei einer Limitmeldung nicht mehrfach erneut klicken. Zuerst den einzelnen "
                "Verbindungstest verwenden, damit wir das Tageskontingent nicht unnötig verbrauchen."
            )
        except Exception as exc:
            st.exception(exc)

else:
    st.warning(
        "Der getestete kostenlose EODHD-Key liefert für `ASML.AS` bei Fundamentals HTTP 403. "
        "Das bedeutet: Der Key ist vorhanden, aber der Free-Tarif schaltet diese Daten nicht frei. "
        "Wir kaufen vorerst keinen EODHD-Fundamentals-Tarif."
    )
    api_key_available = bool(os.getenv("EODHD_API_KEY"))
    if api_key_available:
        st.success("EODHD_API_KEY ist in der lokalen Umgebung vorhanden.")
    else:
        st.warning("EODHD_API_KEY fehlt in der lokalen `.env`.")

    if not editable:
        st.info(
            "Diese Analyse ist abgeschlossen/archiviert und eingefroren. "
            "Für neue Daten zuerst eine neue Revision erzeugen."
        )
    elif not analysis.company.provider_symbol:
        st.error("Für dieses Unternehmen ist noch kein EODHD-Provider-Symbol hinterlegt.")
    elif st.button(
        "EODHD erneut testen",
        disabled=not api_key_available,
    ):
        try:
            provider = EODHDProvider()
            with get_session() as session:
                current = get_analysis(session, analysis_id)
                if current is None:
                    raise ValueError("Analyse wurde nicht gefunden.")
                with st.spinner(f"Lade {current.company.provider_symbol} von EODHD …"):
                    fact_count, estimate_count = sync_eodhd_snapshot(session, current, provider)
            st.success(
                f"Import abgeschlossen: {fact_count} Finanzdatenzeilen, "
                f"{estimate_count} Schätzdatensätze gespeichert."
            )
            st.rerun()
        except (ValueError, AnalysisFrozenError, ProviderError) as exc:
            st.error(str(exc))
        except Exception as exc:
            st.exception(exc)

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
    st.caption("Noch keine automatischen Finanzdaten in diesem Snapshot.")
else:
    missing_count = sum(1 for fact in facts if fact.value is None)
    cross_check_count = sum(1 for fact in facts if fact.is_cross_check_only)
    years = sorted({fact.period_end.year for fact in facts})

    summary = st.columns(4)
    summary[0].metric("Datenpunkte", len(facts))
    summary[1].metric("Geschäftsjahre", len(years))
    summary[2].metric("Missing", missing_count)
    summary[3].metric("Nur Cross-Check", cross_check_count)

    st.caption(
        "Missing-Werte bleiben absichtlich sichtbar. Es werden keine stillen Ersatzwerte "
        "oder fertigen Providerkennzahlen eingesetzt."
    )

    rows = [
        {
            "Periode": fact.period_end,
            "Provider": fact.provider,
            "Statement": fact.statement,
            "Interner Schlüssel": fact.metric,
            "Wert": float(fact.value) if fact.value is not None else None,
            "Währung": fact.currency,
            "Provider-Feld": fact.provider_field,
            "Originalwert": float(fact.provider_value) if fact.provider_value is not None else None,
            "Cross-Check": fact.is_cross_check_only,
            "Filing": fact.filing_date,
        }
        for fact in facts
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.subheader("Analystenschätzungen")
if not estimates:
    st.caption("Noch keine Analystenschätzungen gespeichert oder vom Provider geliefert.")
else:
    rows = [
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
        for item in estimates
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.info(
    "Nach dem ersten erfolgreichen ASML-Import vergleichen wir Umsatz, EBIT, Gewinn, Bilanz "
    "und Cashflow stichprobenartig mit der offiziellen ASML-Berichterstattung. Erst danach "
    "wird ein Provider als Primärquelle freigegeben."
)
