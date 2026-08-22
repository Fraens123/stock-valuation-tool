from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import select

from stock_valuation.analyses.service import AnalysisFrozenError, get_analysis, list_analyses
from stock_valuation.companies.provider_symbols import get_provider_symbol, upsert_provider_symbol
from stock_valuation.data.providers.esef import ESEFParseError, parse_esef_ixbrl
from stock_valuation.data.providers.sec import SECCompanyFactsProvider, SECProviderError
from stock_valuation.data.snapshot_service import sync_esef_primary_source, sync_sec_companyfacts
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
    "Offizielle/regulatorische Primärquellen werden zusätzlich zu API-Providerdaten gespeichert. "
    "Die Providerhistorie bleibt auditierbar; die zentrale Source Resolution bevorzugt offizielle Fakten."
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

# -----------------------------------------------------------------------------
# SEC
# -----------------------------------------------------------------------------
st.subheader("1. SEC EDGAR Company Facts")
st.write(
    "Für US-Unternehmen und viele ausländische SEC-Emittenten. Die SEC-APIs benötigen keinen "
    "API-Key, verlangen für automatisierte Zugriffe aber einen deklarierten User-Agent. "
    "Lokal in `.env`, z. B. `SEC_USER_AGENT=Dein Name deine@email.at`."
)

sec_user_agent_available = bool(os.getenv("SEC_USER_AGENT"))
if sec_user_agent_available:
    st.success("SEC_USER_AGENT ist lokal vorhanden.")
else:
    st.warning("SEC_USER_AGENT fehlt in `.env`; SEC-Abrufe sind deshalb deaktiviert.")

if st.button("SEC-Registrierung prüfen (1 Request)", disabled=not sec_user_agent_available):
    try:
        provider = SECCompanyFactsProvider()
        with st.spinner(f"Suche {ticker} in der offiziellen SEC-Tickerliste …"):
            resolved = provider.resolve_cik(ticker)
        if resolved is None:
            st.warning(
                "Für diesen Ticker wurde keine SEC-Registrierung gefunden. Das ist bei vielen "
                "rein europäischen/asiatischen Emittenten normal. Verwende dann den ESEF/iXBRL-Block unten."
            )
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
            st.success(f"SEC-Emittent gefunden: {title} · CIK {cik}")
            st.rerun()
    except (SECProviderError, ValueError) as exc:
        st.error(str(exc))

if sec_identifier is not None:
    st.caption(
        "Der Company-Facts-Abruf benötigt genau **1 SEC-Request** und liefert in einem JSON viele "
        "standardisierte US-GAAP-/IFRS-XBRL-Fakten über mehrere Jahre."
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
            st.success(f"{count} offizielle SEC-Finanzfakten gespeichert.")
            st.rerun()
        except (SECProviderError, AnalysisFrozenError, ValueError) as exc:
            st.error(str(exc))

# -----------------------------------------------------------------------------
# ESEF
# -----------------------------------------------------------------------------
st.divider()
st.subheader("2. Europa – ESEF / Inline XBRL")
st.write(
    "Für europäische IFRS-Emittenten. Lade den offiziellen ESEF-Jahresbericht des Unternehmens "
    "oder der zuständigen Veröffentlichungsstelle als `.xhtml`, `.html`, `.htm` oder ESEF-`.zip` hoch. "
    "Der Parser verwendet standardisierte `ifrs-full`-Tags und ignoriert segmentierte/dimensionale "
    "Kontexte, damit Hauptabschlusswerte nicht mit Segmentdaten vermischt werden."
)

uploaded = st.file_uploader(
    "Offiziellen ESEF-Bericht auswählen",
    type=["xhtml", "html", "htm", "zip"],
    accept_multiple_files=False,
)
source_url = st.text_input(
    "Quell-URL des offiziellen Berichts (optional)",
    help="Nur zur Provenienz im Snapshot; der Upload selbst wird lokal verarbeitet.",
)

if uploaded is not None:
    content = uploaded.getvalue()
    try:
        preview_facts = parse_esef_ixbrl(content, filename=uploaded.name)
    except ESEFParseError as exc:
        st.error(str(exc))
        preview_facts = []

    if not preview_facts:
        st.warning(
            "Keine unterstützten standardisierten IFRS-Fakten gefunden. Mögliche Gründe: kein ESEF/iXBRL, "
            "nur unternehmensspezifische Extension-Tags oder ein noch nicht unterstütztes Zahlenformat."
        )
    else:
        years = sorted({fact.period_end.year for fact in preview_facts})
        metrics = sorted({fact.metric for fact in preview_facts})
        preview_cols = st.columns(3)
        preview_cols[0].metric("Gefundene Fakten", len(preview_facts))
        preview_cols[1].metric("Geschäftsjahre", len(years))
        preview_cols[2].metric("Interne Felder", len(metrics))

        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Jahr": fact.period_end.year,
                        "Metrik": fact.metric,
                        "Wert": float(fact.value) if fact.value is not None else None,
                        "Währung": fact.currency,
                        "IFRS-Tag": fact.provider_field,
                        "Statement": fact.statement,
                    }
                    for fact in preview_facts
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

        if not editable:
            st.info("Diese Revision ist eingefroren; ESEF-Daten können nur in eine offene Revision importiert werden.")
        elif st.button("ESEF-Fakten in Snapshot übernehmen", type="primary"):
            try:
                with get_session() as session:
                    current = get_analysis(session, analysis_id)
                    if current is None:
                        raise ValueError("Analyse nicht gefunden.")
                    count = sync_esef_primary_source(
                        session,
                        current,
                        content,
                        filename=uploaded.name,
                        source_url=source_url.strip() or None,
                    )
                st.success(f"{count} offizielle ESEF/iXBRL-Fakten gespeichert.")
                st.rerun()
            except (ESEFParseError, AnalysisFrozenError, ValueError) as exc:
                st.error(str(exc))

# -----------------------------------------------------------------------------
# Stored primary facts
# -----------------------------------------------------------------------------
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
    providers = sorted({row.provider or "—" for row in official})
    st.caption("Primärquellen im Snapshot: " + ", ".join(providers))
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
                    "Quell-URL": row.source_url,
                }
                for row in official
            ]
        ),
        use_container_width=True,
        hide_index=True,
        column_config={"Quell-URL": st.column_config.LinkColumn("Quell-URL")},
    )

st.info(
    "Damit gibt es jetzt zwei generische offizielle Datenwege: SEC Company Facts für SEC-reporting "
    "Unternehmen und ESEF/iXBRL für europäische IFRS-Berichte. Automatische ESEF-Dokument-Discovery "
    "kommt separat; das zentrale ESAP ist 2026 noch nicht öffentlich als fertiges Rechercheportal verfügbar."
)
