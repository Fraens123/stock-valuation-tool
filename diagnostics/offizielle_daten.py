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
st.set_page_config(page_title="Offizielle Daten – Diagnose", layout="wide")

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


st.title("Offizielle Unternehmensdaten – Diagnose")
st.caption(
    "Technische Primärquellenwerkzeuge. Im normalen Workflow nicht erforderlich; Providerdaten "
    "werden über Finanzdaten importiert."
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
        session, analysis.company, provider="sec", purpose="companyfacts"
    )
    editable = analysis.status in {AnalysisStatus.DRAFT, AnalysisStatus.IN_PROGRESS}
    ticker = analysis.company.ticker

st.subheader("SEC EDGAR Company Facts")
sec_user_agent_available = bool(os.getenv("SEC_USER_AGENT"))
if st.button("SEC-Registrierung prüfen", disabled=not sec_user_agent_available):
    try:
        provider = SECCompanyFactsProvider()
        resolved = provider.resolve_cik(ticker)
        if resolved is None:
            st.warning("Keine SEC-Registrierung gefunden.")
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
            st.success(f"{title} · CIK {cik}")
            st.rerun()
    except (SECProviderError, ValueError) as exc:
        st.error(str(exc))

if sec_identifier is not None and editable:
    if st.button("SEC Company Facts importieren", disabled=not sec_user_agent_available):
        try:
            provider = SECCompanyFactsProvider()
            with get_session() as session:
                current = get_analysis(session, analysis_id)
                if current is None:
                    raise ValueError("Analyse nicht gefunden.")
                count = sync_sec_companyfacts(
                    session, current, provider, cik=sec_identifier.symbol
                )
            st.success(f"{count} offizielle SEC-Fakten gespeichert.")
            st.rerun()
        except (SECProviderError, AnalysisFrozenError, ValueError) as exc:
            st.error(str(exc))

st.divider()
st.subheader("Europa – ESEF / Inline XBRL")
uploaded = st.file_uploader(
    "Offiziellen ESEF-Bericht auswählen",
    type=["xhtml", "html", "htm", "zip"],
    accept_multiple_files=False,
)
source_url = st.text_input("Quell-URL (optional)")
if uploaded is not None:
    content = uploaded.getvalue()
    try:
        preview_facts = parse_esef_ixbrl(content, filename=uploaded.name)
    except ESEFParseError as exc:
        st.error(str(exc))
        preview_facts = []
    if preview_facts:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Jahr": fact.period_end.year,
                        "Metrik": fact.metric,
                        "Wert": float(fact.value) if fact.value is not None else None,
                        "Währung": fact.currency,
                        "IFRS-Tag": fact.provider_field,
                    }
                    for fact in preview_facts
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
        if editable and st.button("ESEF-Fakten übernehmen"):
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
                st.success(f"{count} ESEF-Fakten gespeichert.")
                st.rerun()
            except (ESEFParseError, AnalysisFrozenError, ValueError) as exc:
                st.error(str(exc))

st.divider()
with get_session() as session:
    official = session.scalars(
        select(FinancialFactSnapshot)
        .where(
            FinancialFactSnapshot.analysis_id == analysis_id,
            FinancialFactSnapshot.source_type == "primary_source",
        )
        .order_by(FinancialFactSnapshot.period_end.desc(), FinancialFactSnapshot.metric)
    ).all()

st.subheader("Gespeicherte Primärquellenfakten")
if official:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Jahr": row.period_end.year,
                    "Metrik": row.metric,
                    "Wert": float(row.value) if row.value is not None else None,
                    "Quelle": row.provider,
                    "Originaltag": row.provider_field,
                }
                for row in official
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.caption("Keine Primärquellenfakten gespeichert.")
