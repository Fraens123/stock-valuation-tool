from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st

from stock_valuation.analyses.comparison import compare_analyses
from stock_valuation.analyses.service import (
    AnalysisFrozenError,
    InvalidAnalysisTransition,
    complete_analysis,
    create_revision,
    get_analysis,
    list_analyses,
    mark_in_progress,
    update_analysis_metadata,
)
from stock_valuation.companies.service import list_companies
from stock_valuation.database.models import AnalysisStatus
from stock_valuation.database.session import get_session, init_database
from stock_valuation.reports.pdf import build_snapshot_report, snapshot_report_filename
from stock_valuation.ui.navigation import render_navigation


st.set_page_config(page_title="Übersicht", layout="wide")
init_database()
render_navigation()

STATUS_LABELS = {
    AnalysisStatus.DRAFT: "Entwurf",
    AnalysisStatus.IN_PROGRESS: "In Bearbeitung",
    AnalysisStatus.COMPLETED: "Abgeschlossen",
    AnalysisStatus.ARCHIVED: "Archiviert",
}


def status_label(status: AnalysisStatus) -> str:
    return STATUS_LABELS.get(status, status.value)


def analysis_label(analysis) -> str:
    return (
        f"{analysis.company.name} · {analysis.as_of_date} · "
        f"R{analysis.revision_number} · {status_label(analysis.status)}"
    )


def parse_optional_decimal(raw: str) -> Decimal | None:
    value = raw.strip().replace(" ", "").replace(",", ".")
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Aktienkurs ist keine gültige Zahl.") from exc


st.title("Übersicht")
st.caption(
    "Alle Unternehmen und Analyse-Snapshots an einem Ort. Neue Aktien werden unter **Unternehmen** "
    "angelegt; Finanzdaten werden danach unter **Finanzdaten** mit einem Klick geladen."
)

with get_session() as session:
    companies = list_companies(session)
    analyses = list_analyses(session, include_archived=True)

summary = st.columns(4)
summary[0].metric("Unternehmen", len(companies))
summary[1].metric("Analysen", len(analyses))
summary[2].metric(
    "Offen",
    sum(item.status in {AnalysisStatus.DRAFT, AnalysisStatus.IN_PROGRESS} for item in analyses),
)
summary[3].metric(
    "Abgeschlossen",
    sum(item.status == AnalysisStatus.COMPLETED for item in analyses),
)

st.subheader("Analysen")
if not analyses:
    st.info("Noch keine Analyse vorhanden. Links **Unternehmen** öffnen und eine Aktie auswählen.")
else:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Unternehmen": item.company.name,
                    "Ticker": item.company.ticker,
                    "Stichtag": item.as_of_date,
                    "Revision": f"R{item.revision_number}",
                    "Status": status_label(item.status),
                    "Aktienkurs": float(item.market_price) if item.market_price is not None else None,
                    "Währung": item.market_price_currency or item.company.currency,
                }
                for item in analyses
            ]
        ),
        width="stretch",
        hide_index=True,
    )

manage_tab, compare_tab = st.tabs(["Analyse verwalten", "Revisionen vergleichen"])

with manage_tab:
    if not analyses:
        st.caption("Keine Analyse vorhanden.")
    else:
        options = {analysis_label(item): item.id for item in analyses}
        selected_label = st.selectbox("Analyse", list(options), key="manage-analysis")
        selected_id = options[selected_label]

        with get_session() as session:
            selected = get_analysis(session, selected_id)
            if selected is None:
                st.error("Analyse wurde nicht gefunden.")
                st.stop()

            cols = st.columns(5)
            cols[0].metric("Unternehmen", selected.company.name)
            cols[1].metric("Ticker", selected.company.ticker)
            cols[2].metric("Stichtag", str(selected.as_of_date))
            cols[3].metric("Revision", f"R{selected.revision_number}")
            cols[4].metric("Status", status_label(selected.status))

            editable = selected.status in {AnalysisStatus.DRAFT, AnalysisStatus.IN_PROGRESS}
            if editable:
                with st.form(f"edit-analysis-{selected.id}"):
                    title = st.text_input("Titel", value=selected.title or "")
                    market = st.text_input(
                        "Aktienkurs am Stichtag",
                        value=str(selected.market_price) if selected.market_price is not None else "",
                    )
                    notes = st.text_area(
                        "Notizen / Investmentthese",
                        value=selected.notes or "",
                        height=160,
                    )
                    save = st.form_submit_button("Änderungen speichern")
                if save:
                    try:
                        update_analysis_metadata(
                            session,
                            selected,
                            title=title or None,
                            notes=notes or None,
                            market_price=parse_optional_decimal(market),
                            market_price_currency=selected.company.currency,
                        )
                        st.success("Änderungen gespeichert.")
                        st.rerun()
                    except (ValueError, AnalysisFrozenError) as exc:
                        st.error(str(exc))

                actions = st.columns(2)
                if selected.status == AnalysisStatus.DRAFT:
                    if actions[0].button("Als 'In Bearbeitung' markieren"):
                        mark_in_progress(session, selected)
                        st.rerun()
                if actions[1].button("Analyse abschließen und einfrieren", type="primary"):
                    try:
                        complete_analysis(session, selected)
                        st.rerun()
                    except (AnalysisFrozenError, InvalidAnalysisTransition) as exc:
                        st.error(str(exc))
            else:
                st.info(
                    "Dieser Snapshot ist eingefroren. Für einen neuen Datenstand eine neue Revision erstellen."
                )
                st.write(f"**Titel:** {selected.title or '—'}")
                st.write(f"**Notizen / Investmentthese:** {selected.notes or '—'}")

            if selected.status == AnalysisStatus.COMPLETED:
                st.markdown("#### Neue Revision")
                with st.form(f"revision-{selected.id}"):
                    revision_date = st.date_input("Neuer Analyse-Stichtag", value=date.today())
                    copy_qualitative = st.checkbox(
                        "Qualitative Einschätzungen als Ausgangspunkt übernehmen",
                        value=True,
                    )
                    copy_assumptions = st.checkbox(
                        "Eigene Bewertungsannahmen übernehmen",
                        value=False,
                    )
                    create = st.form_submit_button("Neue Revision erstellen")
                if create:
                    try:
                        revision = create_revision(
                            session,
                            source=selected,
                            as_of_date=revision_date,
                            copy_qualitative=copy_qualitative,
                            copy_valuation_assumptions=copy_assumptions,
                        )
                        st.success(f"Revision R{revision.revision_number} wurde angelegt.")
                        st.rerun()
                    except InvalidAnalysisTransition as exc:
                        st.error(str(exc))

            st.markdown("#### PDF-Snapshot")
            pdf_bytes = build_snapshot_report(session, selected)
            st.download_button(
                "PDF-Report herunterladen",
                data=pdf_bytes,
                file_name=snapshot_report_filename(selected),
                mime="application/pdf",
            )

with compare_tab:
    company_options: dict[str, int] = {}
    with get_session() as session:
        for company in list_companies(session):
            company_analyses = list_analyses(session, company.id, include_archived=True)
            if len(company_analyses) >= 2:
                company_options[f"{company.name} · {company.ticker}"] = company.id

    if not company_options:
        st.info("Für einen Vergleich werden mindestens zwei Revisionen desselben Unternehmens benötigt.")
    else:
        company_label = st.selectbox("Unternehmen", list(company_options), key="compare-company")
        company_id = company_options[company_label]
        with get_session() as session:
            company_analyses = list_analyses(
                session,
                company_id=company_id,
                include_archived=True,
            )
        labels = {analysis_label(item): item.id for item in company_analyses}
        left, right = st.columns(2)
        with left:
            old_label = st.selectbox("Ältere Analyse", list(labels), index=len(labels) - 1)
        with right:
            new_label = st.selectbox("Neuere Analyse", list(labels), index=0)
        old_id = labels[old_label]
        new_id = labels[new_label]

        if old_id == new_id:
            st.warning("Bitte zwei unterschiedliche Revisionen auswählen.")
        else:
            with get_session() as session:
                old = get_analysis(session, old_id)
                new = get_analysis(session, new_id)
                if old is None or new is None:
                    st.error("Eine Analyse wurde nicht gefunden.")
                    st.stop()
                changes = compare_analyses(session, old, new)

            st.write(f"**R{old.revision_number} → R{new.revision_number}** · {len(changes)} Änderungen")
            if not changes:
                st.success("Keine gespeicherten Änderungen gefunden.")
            else:
                for category in [
                    "Fundamentaldaten",
                    "Prognosen",
                    "Bewertung",
                    "Eigene Einschätzung",
                    "Analyse",
                ]:
                    group = [item for item in changes if item.category == category]
                    if not group:
                        continue
                    with st.expander(f"{category} · {len(group)} Änderung(en)", expanded=True):
                        st.dataframe(
                            pd.DataFrame(
                                [
                                    {"Feld": item.label, "Alt": item.old_value, "Neu": item.new_value}
                                    for item in group
                                ]
                            ),
                            width="stretch",
                            hide_index=True,
                        )
