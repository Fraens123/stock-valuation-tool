from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import select

from stock_valuation.analyses.estimate_service import relevant_estimates
from stock_valuation.analyses.service import AnalysisFrozenError, get_analysis, list_analyses
from stock_valuation.data.providers.alphavantage import AlphaVantageProvider
from stock_valuation.data.providers.base import ProviderError
from stock_valuation.data.providers.eodhd import EODHDProvider
from stock_valuation.data.snapshot_service import sync_alphavantage_snapshot, sync_eodhd_snapshot
from stock_valuation.database.models import AnalysisStatus, EstimateSnapshot, FinancialFactSnapshot
from stock_valuation.database.session import get_session, init_database
from stock_valuation.validation.service import validate_asml_primary_source, validation_summary


load_dotenv()
init_database()
st.set_page_config(page_title="Datenimport", layout="wide")

STATUS_LABELS = {
    AnalysisStatus.DRAFT: "Entwurf",
    AnalysisStatus.IN_PROGRESS: "In Bearbeitung",
    AnalysisStatus.COMPLETED: "Abgeschlossen",
    AnalysisStatus.ARCHIVED: "Archiviert",
}
VALIDATION_STATUS = {
    "pass": "✅ PASS",
    "warn": "⚠️ WARN",
    "fail": "❌ FAIL",
    "missing": "⬜ MISSING",
}


def _analysis_label(analysis) -> str:
    return (
        f"{analysis.company.name} · {analysis.as_of_date} · "
        f"R{analysis.revision_number} · {STATUS_LABELS.get(analysis.status, analysis.status.value)}"
    )


def _default_alpha_symbol(analysis) -> str:
    # For fundamentals, Alpha Vantage can expose statement data under a different
    # symbol than the local market-price listing. ASML.AMS is known for market data,
    # but the fundamentals endpoint returned an empty statement payload. The NASDAQ/
    # ADR symbol ASML returns the consolidated ASML Holding statements in EUR.
    if analysis.company.ticker.upper() == "ASML":
        return "ASML"
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
    analysis_as_of_date = analysis.as_of_date
    analysis_ticker = analysis.company.ticker

st.divider()
st.subheader("Automatischer Fundamentaldaten-Import")

provider_choice = st.radio(
    "Datenprovider",
    ["Alpha Vantage", "EODHD"],
    horizontal=True,
    help=(
        "Alpha Vantage wird als V1-Kandidat validiert. EODHD Fundamentals erfordern beim "
        "getesteten Free-Key für ASML einen kostenpflichtigen Tarif."
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
        "Alpha-Vantage-Fundamentals-Symbol",
        value=_default_alpha_symbol(analysis),
        help=(
            "Für ASML verwenden wir Fundamentals mit `ASML` (NASDAQ/ADR). `ASML.AMS` kann für "
            "Kursdaten funktionieren, lieferte beim Fundamentals-Test aber 0 Reports. "
            "Marktpreis und Fundamentaldaten dürfen providerseitig unterschiedliche Symbole haben."
        ),
    )

    st.markdown("#### Verbindungstest")
    st.caption(
        "Dieser Test verwendet genau **einen** API-Request (`INCOME_STATEMENT`) und speichert "
        "noch keine Daten. Erst wenn Jahresberichte vorhanden sind, sollte der vollständige "
        "4-Request-Import gestartet werden."
    )
    if st.button("Alpha Vantage testen (1 Request)", disabled=not api_key_available):
        try:
            provider = AlphaVantageProvider()
            with st.spinner(f"Teste INCOME_STATEMENT für {alpha_symbol} …"):
                result = provider.probe_income_statement(alpha_symbol)

            if result["annual_report_count"] == 0 and result["quarterly_report_count"] == 0:
                st.warning(
                    "Der API-Request selbst war erfolgreich, aber dieses Symbol liefert keine "
                    "GuV-Berichte. Das spricht für ein Symbol-/Coverage-Problem und nicht für "
                    "einen ungültigen API-Key."
                )
                st.session_state["alpha_probe_ok"] = False
            else:
                st.success(
                    "Einzeltest erfolgreich: "
                    f"{result['annual_report_count']} Jahresberichte und "
                    f"{result['quarterly_report_count']} Quartalsberichte erkannt."
                )
                st.session_state["alpha_probe_ok"] = True

            details = {
                "Angefragt": result.get("requested_symbol"),
                "Zurückgegeben": result.get("returned_symbol"),
                "Letztes Geschäftsjahr": result.get("latest_fiscal_date") or "—",
                "Berichtswährung": result.get("reported_currency") or "—",
                "Letzter Umsatz (raw)": result.get("latest_revenue") or "—",
            }
            st.json(details)
        except ProviderError as exc:
            st.session_state["alpha_probe_ok"] = False
            st.error(str(exc))
            st.info(
                "Wenn bereits dieser einzelne Request eine Limitmeldung liefert, liegt das "
                "Problem nicht an den Abständen innerhalb unseres 4-Request-Imports. Dann keine "
                "weiteren Alpha-Vantage-Requests verbrauchen und später erneut testen."
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
        disabled=not api_key_available or not st.session_state.get("alpha_probe_ok", False),
        help=(
            "Der vollständige Import wird erst freigeschaltet, wenn der 1-Request-Test für "
            "das gewählte Fundamentals-Symbol tatsächlich Reports liefert."
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
        "Der Key ist gültig, aber der Free-Tarif schaltet diese Daten nicht frei. "
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
    elif st.button("EODHD erneut testen", disabled=not api_key_available):
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

    if analysis_ticker.upper() == "ASML" and any(fact.provider == "alphavantage" for fact in facts):
        st.divider()
        st.subheader("ASML Primärquellen-Validierung")
        st.caption(
            "Die gespeicherten Alpha-Vantage-Rohdaten für 2025 und 2024 werden gegen "
            "veröffentlichte ASML-US-GAAP-Kontrollwerte verglichen. Diese Referenzwerte dienen "
            "nur der Qualitätsprüfung und überschreiben niemals Providerdaten. Toleranz: bis "
            "0,5 % PASS, bis 2 % WARN, darüber FAIL."
        )

        with get_session() as session:
            current = get_analysis(session, analysis_id)
            validation = (
                validate_asml_primary_source(session, current)
                if current is not None
                else []
            )

        if validation:
            check = validation_summary(validation)
            check_cols = st.columns(5)
            check_cols[0].metric("PASS", check["pass"])
            check_cols[1].metric("WARN", check["warn"])
            check_cols[2].metric("FAIL", check["fail"])
            check_cols[3].metric("MISSING", check["missing"])
            check_cols[4].metric(
                "Provider-Gate",
                "BESTANDEN" if check["provider_gate_passed"] else "OFFEN",
            )

            if check["provider_gate_passed"]:
                st.success(
                    "Alle kritischen ASML-Kontrollfelder liegen innerhalb der definierten "
                    "Toleranz. Alpha Vantage kann für diese Felder freigegeben werden."
                )
            else:
                st.warning(
                    "Alpha Vantage ist noch **nicht vollständig freigegeben**. "
                    f"Kritische FAILs: {check['critical_fail']}; "
                    f"kritische Missing-Felder: {check['critical_missing']}. "
                    "Abweichende Felder werden zuerst semantisch geprüft und ggf. neu gemappt."
                )

            validation_rows = []
            for item in validation:
                validation_rows.append(
                    {
                        "Status": VALIDATION_STATUS[item.status],
                        "Jahr": item.period,
                        "Interner Schlüssel": item.metric,
                        "ASML-Bezeichnung": item.label,
                        "Alpha Vantage Mio. €": (
                            float(item.provider_value / 1_000_000)
                            if item.provider_value is not None
                            else None
                        ),
                        "ASML offiziell Mio. €": float(item.reference_value / 1_000_000),
                        "Abweichung %": (
                            float(item.relative_difference * 100)
                            if item.relative_difference is not None
                            else None
                        ),
                        "Provider-Feld": item.provider_field,
                        "Kritisch": item.critical,
                        "Hinweis": item.note,
                        "Quelle": item.source_url,
                    }
                )
            st.dataframe(
                pd.DataFrame(validation_rows),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Quelle": st.column_config.LinkColumn("Quelle"),
                    "Abweichung %": st.column_config.NumberColumn("Abweichung %", format="%.3f"),
                    "Alpha Vantage Mio. €": st.column_config.NumberColumn(
                        "Alpha Vantage Mio. €", format="%.1f"
                    ),
                    "ASML offiziell Mio. €": st.column_config.NumberColumn(
                        "ASML offiziell Mio. €", format="%.1f"
                    ),
                },
            )

st.subheader("Analystenschätzungen")
if not estimates:
    st.caption("Noch keine Analystenschätzungen gespeichert oder vom Provider geliefert.")
else:
    show_history = st.checkbox(
        "Historische Estimate-Historie anzeigen",
        value=False,
        help=(
            "Alpha Vantage liefert auch ältere Schätz-/Revisionsdaten. Sie bleiben im Snapshot "
            "erhalten, werden in der normalen Analyseansicht aber standardmäßig ausgeblendet."
        ),
    )
    visible_estimates = (
        estimates
        if show_history
        else relevant_estimates(estimates, as_of_date=analysis_as_of_date)
    )
    if not show_history:
        hidden = len(estimates) - len(visible_estimates)
        st.caption(
            f"{len(visible_estimates)} relevante Datensätze ab Analysestichtag "
            f"{analysis_as_of_date}; {hidden} historische Datensätze ausgeblendet."
        )

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
        for item in visible_estimates
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.info(
    "Erst wenn die kritischen ASML-Kontrollfelder fachlich sauber gemappt sind, beginnt Phase 3 "
    "mit der Kennzahlenengine. Providerabweichungen werden nicht durch stille Ersatzwerte kaschiert."
)
