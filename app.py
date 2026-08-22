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
    create_analysis,
    create_revision,
    get_analysis,
    list_analyses,
    mark_in_progress,
    update_analysis_metadata,
)
from stock_valuation.companies.service import (
    CompanyCandidate,
    get_or_create_company,
    get_or_create_from_candidate,
    list_companies,
    search_company_candidates,
)
from stock_valuation.database.models import AnalysisStatus
from stock_valuation.database.session import get_session, init_database
from stock_valuation.reports.pdf import build_snapshot_report, snapshot_report_filename


st.set_page_config(page_title="Aktienanalyse & Unternehmensbewertung", layout="wide")
init_database()

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


def candidate_details(candidate: CompanyCandidate) -> None:
    cols = st.columns(4)
    cols[0].metric("Ticker", candidate.ticker)
    cols[1].metric("ISIN", candidate.isin or "—")
    cols[2].metric("Börse", candidate.exchange or "—")
    cols[3].metric("Währung", candidate.currency)
    if candidate.provider_symbol:
        st.caption(f"Provider-Symbol: `{candidate.provider_symbol}`")


st.title("Aktienanalyse & Unternehmensbewertung")
st.caption("Geführte Analyse nach der bestehenden Excel-/Schmidlin-Methodik")

mode = st.sidebar.radio(
    "Arbeitsbereich",
    ["Start", "Neue Analyse", "Analyse öffnen", "Analysen vergleichen"],
)

# -----------------------------------------------------------------------------
# Start
# -----------------------------------------------------------------------------
if mode == "Start":
    st.header("Unternehmen auswählen")
    st.write(
        "Suche nach Unternehmen, Ticker oder ISIN. In Phase 0 ist ASML als "
        "Referenzunternehmen hinterlegt; eine externe Symbolsuche folgt in Phase 2."
    )
    query = st.text_input("Unternehmen, Ticker oder ISIN", value="ASML")

    with get_session() as session:
        candidates = search_company_candidates(session, query)
        if candidates:
            options = {candidate.display_name: candidate for candidate in candidates}
            label = st.selectbox("Treffer", list(options))
            candidate = options[label]
            st.subheader(candidate.name)
            candidate_details(candidate)
            st.info("Zum Anlegen eines Analyse-Snapshots links **Neue Analyse** wählen.")
        else:
            st.warning("Kein lokaler Treffer. Eine externe Unternehmenssuche wird in Phase 2 ergänzt.")

        st.divider()
        st.subheader("Zuletzt bearbeitete Analysen")
        recent = list_analyses(session)[:8]
        if not recent:
            st.caption("Noch keine Analysen gespeichert.")
        else:
            rows = [
                {
                    "Unternehmen": a.company.name,
                    "Stichtag": a.as_of_date,
                    "Revision": a.revision_number,
                    "Status": status_label(a.status),
                    "Aktienkurs": float(a.market_price) if a.market_price is not None else None,
                    "Währung": a.market_price_currency or a.company.currency,
                }
                for a in recent
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# New analysis
# -----------------------------------------------------------------------------
elif mode == "Neue Analyse":
    st.header("Neue Analyse starten")

    company_mode = st.radio(
        "Unternehmen",
        ["Unternehmen suchen", "Stammdaten manuell eingeben"],
        horizontal=True,
    )

    selected_candidate: CompanyCandidate | None = None
    if company_mode == "Unternehmen suchen":
        search_query = st.text_input("Unternehmen / Ticker / ISIN", value="ASML")
        with get_session() as session:
            candidates = search_company_candidates(session, search_query)
        if candidates:
            options = {candidate.display_name: candidate for candidate in candidates}
            selected_candidate = options[st.selectbox("Treffer", list(options))]
            candidate_details(selected_candidate)
        else:
            st.warning("Kein Treffer. Verwende alternativ die manuelle Eingabe.")

    with st.form("new-analysis"):
        if company_mode == "Stammdaten manuell eingeben":
            name = st.text_input("Unternehmensname")
            ticker = st.text_input("Ticker")
            isin = st.text_input("ISIN")
            provider_symbol = st.text_input("Provider-Symbol")
            exchange = st.text_input("Börse")
            country = st.text_input("Land")
            currency = st.text_input("Währung", value="EUR")
        else:
            name = ticker = isin = provider_symbol = exchange = country = currency = ""

        analysis_date = st.date_input("Analyse-Stichtag", value=date.today())
        market_price_raw = st.text_input("Aktienkurs am Analyse-Stichtag (optional)")
        title = st.text_input("Titel (optional)")
        notes = st.text_area("Notizen / erste Investmentthese (optional)", height=120)
        submitted = st.form_submit_button("Analyse anlegen", type="primary")

    if submitted:
        try:
            market_price = parse_optional_decimal(market_price_raw)
            with get_session() as session:
                if company_mode == "Unternehmen suchen":
                    if selected_candidate is None:
                        raise ValueError("Bitte zuerst ein Unternehmen auswählen.")
                    company = get_or_create_from_candidate(session, selected_candidate)
                else:
                    if not name.strip() or not ticker.strip():
                        raise ValueError("Unternehmensname und Ticker sind Pflichtfelder.")
                    company = get_or_create_company(
                        session,
                        name=name,
                        ticker=ticker,
                        isin=isin or None,
                        exchange=exchange or None,
                        country=country or None,
                        currency=currency or "EUR",
                        provider_symbol=provider_symbol or None,
                    )

                analysis = create_analysis(session, company=company, as_of_date=analysis_date)
                update_analysis_metadata(
                    session,
                    analysis,
                    title=title or None,
                    notes=notes or None,
                    market_price=market_price,
                    market_price_currency=company.currency,
                )
                st.success(
                    f"{company.name}: Analyse R{analysis.revision_number} wurde als Entwurf angelegt."
                )
                st.caption("Die Analyse kann jetzt unter **Analyse öffnen** weiterbearbeitet werden.")
        except ValueError as exc:
            st.error(str(exc))

# -----------------------------------------------------------------------------
# Open/edit/revise/report analysis
# -----------------------------------------------------------------------------
elif mode == "Analyse öffnen":
    st.header("Bestehende Analyse öffnen")

    with get_session() as session:
        analyses = list_analyses(session, include_archived=True)
        analysis_options = {analysis_label(a): a.id for a in analyses}

    if not analysis_options:
        st.info("Noch keine Analysen gespeichert.")
    else:
        selected_label = st.selectbox("Analyse", list(analysis_options))
        selected_id = analysis_options[selected_label]

        with get_session() as session:
            selected = get_analysis(session, selected_id)
            if selected is None:
                st.error("Analyse wurde nicht gefunden.")
                st.stop()

            st.subheader(selected.company.name)
            cols = st.columns(5)
            cols[0].metric("Ticker", selected.company.ticker)
            cols[1].metric("Stichtag", str(selected.as_of_date))
            cols[2].metric("Revision", f"R{selected.revision_number}")
            cols[3].metric("Status", status_label(selected.status))
            cols[4].metric(
                "Aktienkurs",
                (
                    f"{float(selected.market_price):,.2f} {selected.market_price_currency or selected.company.currency}"
                    if selected.market_price is not None
                    else "—"
                ),
            )
            if selected.previous_analysis_id:
                st.caption(f"Vorherige Revision: Analyse-ID {selected.previous_analysis_id}")

            is_editable = selected.status in {AnalysisStatus.DRAFT, AnalysisStatus.IN_PROGRESS}

            st.divider()
            st.subheader("Analyse-Metadaten")
            if is_editable:
                with st.form(f"edit-analysis-{selected.id}"):
                    edit_title = st.text_input("Titel", value=selected.title or "")
                    edit_market = st.text_input(
                        "Aktienkurs am Stichtag",
                        value=(str(selected.market_price) if selected.market_price is not None else ""),
                    )
                    edit_notes = st.text_area(
                        "Notizen / Investmentthese",
                        value=selected.notes or "",
                        height=180,
                    )
                    save = st.form_submit_button("Änderungen speichern")
                if save:
                    try:
                        update_analysis_metadata(
                            session,
                            selected,
                            title=edit_title,
                            notes=edit_notes,
                            market_price=parse_optional_decimal(edit_market),
                            market_price_currency=selected.company.currency,
                        )
                        st.success("Änderungen gespeichert.")
                        st.rerun()
                    except (ValueError, AnalysisFrozenError) as exc:
                        st.error(str(exc))

                action_cols = st.columns(2)
                if selected.status == AnalysisStatus.DRAFT:
                    if action_cols[0].button("Als 'In Bearbeitung' markieren"):
                        mark_in_progress(session, selected)
                        st.rerun()
                if action_cols[1].button("Analyse abschließen und einfrieren", type="primary"):
                    try:
                        complete_analysis(session, selected)
                        st.success("Analyse abgeschlossen. Dieser Snapshot ist nun schreibgeschützt.")
                        st.rerun()
                    except (AnalysisFrozenError, InvalidAnalysisTransition) as exc:
                        st.error(str(exc))
            else:
                st.info(
                    "Dieser Snapshot ist abgeschlossen/archiviert und wird nicht mehr verändert. "
                    "Für aktuelle Daten eine neue Revision anlegen."
                )
                st.write(f"**Titel:** {selected.title or '—'}")
                st.write("**Notizen / Investmentthese:**")
                st.write(selected.notes or "—")

            if selected.status == AnalysisStatus.COMPLETED:
                st.divider()
                st.subheader("Neue Revision")
                with st.form(f"revision-{selected.id}"):
                    revision_date = st.date_input("Neuer Analyse-Stichtag", value=date.today())
                    copy_qualitative = st.checkbox(
                        "Qualitative Einschätzungen als Ausgangspunkt übernehmen",
                        value=True,
                    )
                    copy_assumptions = st.checkbox(
                        "Eigene Bewertungsannahmen übernehmen",
                        value=False,
                        help="Später müssen übernommene Annahmen bewusst erneut geprüft werden.",
                    )
                    revision_submit = st.form_submit_button("Neue Revision erstellen")
                if revision_submit:
                    try:
                        revision = create_revision(
                            session,
                            source=selected,
                            as_of_date=revision_date,
                            copy_qualitative=copy_qualitative,
                            copy_valuation_assumptions=copy_assumptions,
                        )
                        st.success(
                            f"Revision R{revision.revision_number} wurde als neuer Entwurf angelegt. "
                            "Markt-/Finanzdaten werden bewusst nicht aus der alten Analyse kopiert."
                        )
                        st.rerun()
                    except InvalidAnalysisTransition as exc:
                        st.error(str(exc))

            st.divider()
            st.subheader("PDF-Snapshot")
            pdf_bytes = build_snapshot_report(session, selected)
            st.download_button(
                "PDF-Report herunterladen",
                data=pdf_bytes,
                file_name=snapshot_report_filename(selected),
                mime="application/pdf",
            )
            st.caption(
                "Der PDF-Prototyp verwendet ausschließlich Daten dieser Revision und keine Live-Daten."
            )

# -----------------------------------------------------------------------------
# Compare revisions
# -----------------------------------------------------------------------------
elif mode == "Analysen vergleichen":
    st.header("Analysen vergleichen")
    st.write(
        "Verglichen werden ausschließlich gespeicherte Snapshots. Damit wird sichtbar, "
        "was sich zwischen zwei Analyse-Ständen tatsächlich geändert hat."
    )

    with get_session() as session:
        companies = [company for company in list_companies(session) if len(list_analyses(session, company.id, include_archived=True)) >= 2]
        company_options = {f"{company.name} · {company.ticker}": company.id for company in companies}

    if not company_options:
        st.info("Für einen Vergleich werden mindestens zwei Revisionen desselben Unternehmens benötigt.")
    else:
        company_label = st.selectbox("Unternehmen", list(company_options))
        company_id = company_options[company_label]

        with get_session() as session:
            analyses = list_analyses(session, company_id=company_id, include_archived=True)
            labels = {analysis_label(a): a.id for a in analyses}

        left, right = st.columns(2)
        with left:
            old_label = st.selectbox("Ältere Analyse", list(labels), index=len(labels) - 1, key="old")
        with right:
            new_label = st.selectbox("Neuere Analyse", list(labels), index=0, key="new")

        old_id = labels[old_label]
        new_id = labels[new_label]
        if old_id == new_id:
            st.warning("Bitte zwei unterschiedliche Revisionen auswählen.")
        else:
            with get_session() as session:
                old = get_analysis(session, old_id)
                new = get_analysis(session, new_id)
                if old is None or new is None:
                    st.error("Eine der ausgewählten Analysen wurde nicht gefunden.")
                    st.stop()
                changes = compare_analyses(session, old, new)

            st.subheader(f"R{old.revision_number} → R{new.revision_number}")
            summary_cols = st.columns(4)
            summary_cols[0].metric("Alt", str(old.as_of_date))
            summary_cols[1].metric("Neu", str(new.as_of_date))
            summary_cols[2].metric("Änderungen", len(changes))
            summary_cols[3].metric("Unternehmen", old.company.ticker)

            if not changes:
                st.success("Zwischen den gespeicherten Feldern wurden keine Änderungen gefunden.")
            else:
                categories = [
                    "Fundamentaldaten",
                    "Prognosen",
                    "Bewertung",
                    "Eigene Einschätzung",
                    "Analyse",
                ]
                for category in categories:
                    group = [change for change in changes if change.category == category]
                    if not group:
                        continue
                    with st.expander(f"{category} · {len(group)} Änderung(en)", expanded=True):
                        df = pd.DataFrame(
                            [
                                {
                                    "Feld": item.label,
                                    "Alt": item.old_value,
                                    "Neu": item.new_value,
                                }
                                for item in group
                            ]
                        )
                        st.dataframe(df, use_container_width=True, hide_index=True)
