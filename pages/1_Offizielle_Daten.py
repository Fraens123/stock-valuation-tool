from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import select

from stock_valuation.analyses.service import AnalysisFrozenError, get_analysis, list_analyses
from stock_valuation.companies.provider_symbols import get_provider_symbol, upsert_provider_symbol
from stock_valuation.data.providers.sec import SECCompanyFactsProvider, SECProviderError
from stock_valuation.data.snapshot_service import sync_sec_companyfacts
from stock_valuation.database.models import AnalysisStatus, FinancialFactSnapshot
from stock_valuation.database.session import get_session, init_database


load_dotenv()
init_database()
st.set_page_config(page_title="Offizielle Daten", layout="wide")

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


st.title("Offizielle Unternehmensdaten")
st.caption(
    "Diese Seite ergänzt automatische Providerdaten um offizielle/regulatorische Primärquellen. "
    "Erster generischer Adapter: SEC EDGAR Company Facts/XBRL für Unternehmen, die bei der SEC berichten."
)

with get_session() as session:
    analyses = list_analyses(session, include_archived=True)
    options = {_analysis_label(item): item.id for item in analyses}

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
    sec_identifier = get_provider_symbol(
        session,
        analysis.company,
        provider="sec",
        purpose="companyfacts",
    )
    editable = analysis.status in {AnalysisStatus.DRAFT, AnalysisStatus.IN_PROGRESS}
    ticker = analysis.company.ticker

header = st.columns(4)
header[0].metric("Unternehmen", analysis.company.name)
header[1].metric("Ticker", ticker)
header[2].metric("SEC CIK", sec_identifier.symbol if sec_identifier else "noch nicht ermittelt")
header[3].metric("Status", STATUS_LABELS.get(analysis.status, analysis.status.value))

st.subheader("SEC EDGAR Company Facts")
st.write(
    "Die SEC-APIs sind kostenlos und benötigen keinen API-Key. Für automatisierte Zugriffe verlangt "
    "die SEC jedoch einen deklarierten User-Agent. Trage ihn lokal in `.env` ein, z. B. "
    "`SEC_USER_AGENT=Dein Name deine@email.at`. Die Angabe wird nicht in die Datenbank oder nach GitHub geschrieben."
)

sec_user_agent_available = bool(os.getenv("SEC_USER_AGENT"))
if sec_user_agent_available:
    st.success("SEC_USER_AGENT ist lokal vorhanden.")
else:
    st.warning("SEC_USER_AGENT fehlt in `.env`; SEC-Abrufe sind deshalb deaktiviert.")

if st.button(
    "SEC-Registrierung prüfen (1 Request)",
    disabled=not sec_user_agent_available,
):
    try:
        provider = SECCompanyFactsProvider()
        with st.spinner(f"Suche {ticker} in der offiziellen SEC-Tickerliste …"):
            resolved = provider.resolve_cik(ticker)
        if resolved is None:
            st.warning(
                "Für diesen Ticker wurde keine SEC-Registrierung gefunden. Das ist bei vielen "
                "rein europäischen/asiatischen Emittenten normal; dort wird später ESEF/XBRL bzw. "
                "Investor Relations als Primärquellen-Fallback verwendet."
            )
            st.session_state["sec_probe"] = None
        else:
            cik, title = resolved
            with get_session() as session:
                current = get_analysis(session, analysis_id)
                if current is None:
                    raise ValueError("Analyse nicht gefunden.")
                upsert_provider_symbol(
                    session,
                    current.company,
                    provider="sec",
                    purpose="companyfacts",
                    symbol=cik,
                    note=f"SEC EDGAR entity: {title}",
                )
            st.session_state["sec_probe"] = {"analysis_id": analysis_id, "cik": cik}
            st.success(f"SEC-Emittent gefunden: {title} · CIK {cik}")
            st.rerun()
    except (SECProviderError, ValueError) as exc:
        st.error(str(exc))

if sec_identifier is not None:
    st.caption(
        "Der nächste Abruf benötigt genau **1 SEC-Request** und kann in einem Aufruf viele "
        "standardisierte US-GAAP-/IFRS-XBRL-Fakten über mehrere Jahre liefern."
    )
    if not editable:
        st.info("Diese Revision ist eingefroren. Für neue offizielle Daten eine neue Revision anlegen.")
    elif st.button(
        "SEC Company Facts in Snapshot importieren (1 SEC Request)",
        type="primary",
        disabled=not sec_user_agent_available,
    ):
        try:
            provider = SECCompanyFactsProvider()
            with get_session() as session:
                current = get_analysis(session, analysis_id)
                if current is None:
                    raise ValueError("Analyse nicht gefunden.")
                with st.spinner("Lade und normalisiere offizielle SEC-XBRL-Fakten …"):
                    count = sync_sec_companyfacts(
                        session,
                        current,
                        provider,
                        cik=sec_identifier.symbol,
                    )
            st.success(
                f"{count} offizielle SEC-Finanzfakten gespeichert. Niedriger priorisierte "
                "Alpha-Vantage-Werte bleiben weiterhin auditierbar erhalten."
            )
            st.rerun()
        except (SECProviderError, AnalysisFrozenError, ValueError) as exc:
            st.error(str(exc))

st.divider()
st.subheader("Bereits gespeicherte offizielle Fakten")
with get_session() as session:
    official = session.scalars(
        select(FinancialFactSnapshot)
        .where(
            FinancialFactSnapshot.analysis_id == analysis_id,
            FinancialFactSnapshot.source_type == "primary_source",
        )
        .order_by(FinancialFactSnapshot.period_end.desc(), FinancialFactSnapshot.metric)
    ).all()

if not official:
    st.caption("Noch keine offiziellen/regulatorischen Primärquellenfakten gespeichert.")
else:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Jahr": row.period_end.year,
                    "Metrik": row.metric,
                    "Wert": float(row.value) if row.value is not None else None,
                    "Währung": row.currency,
                    "Quelle": row.provider,
                    "Originaltag": row.provider_field,
                    "Filing": row.filing_date,
                }
                for row in official
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

st.info(
    "SEC deckt nicht den gesamten Weltmarkt ab. Für europäische IFRS-Emittenten ohne SEC-Reporting "
    "folgt als nächster generischer Baustein ESEF/iXBRL. Dadurch bleibt die Architektur weltweit "
    "erweiterbar und vermeidet hart codierte Unternehmensparser."
)
