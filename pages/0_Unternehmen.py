from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_valuation.runtime_dependencies import ensure_runtime_dependencies

ensure_runtime_dependencies()

import os
from datetime import date
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from stock_valuation.analyses.service import create_analysis, update_analysis_metadata
from stock_valuation.companies.deletion import delete_all_companies_completely, delete_company_completely
from stock_valuation.companies.discovery import CompanyDiscoveryCandidate, discover_companies
from stock_valuation.companies.provider_symbols import upsert_provider_symbol
from stock_valuation.companies.service import get_or_create_company, list_companies
from stock_valuation.data.providers.gleif import GLEIFProvider
from stock_valuation.data.providers.sec import SECCompanyFactsProvider
from stock_valuation.database.session import get_session, init_database
from stock_valuation.ui.navigation import render_navigation


load_dotenv()
init_database()
st.set_page_config(page_title="Unternehmen", layout="wide")
render_navigation()


def _optional_decimal(raw: str) -> Decimal | None:
    value = raw.strip().replace(" ", "").replace(",", ".")
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Aktienkurs ist keine gültige Zahl.") from exc


def _candidate_key(candidate: CompanyDiscoveryCandidate) -> str:
    return candidate.display_name


st.title("Unternehmen")
st.caption(
    "Unternehmen über frei zugängliche offizielle Register suchen. SEC liefert Ticker/CIK für "
    "SEC-Berichterstatter, GLEIF liefert die globale LEI-Unternehmensidentität für ESEF und andere Register."
)

sec_user_agent_available = bool(os.getenv("SEC_USER_AGENT"))
if not sec_user_agent_available:
    st.info(
        "Für SEC-Abfragen fehlt noch `SEC_USER_AGENT` in `.env`. GLEIF funktioniert trotzdem. "
        "Für SEC später z. B. `SEC_USER_AGENT=Vorname Nachname email@example.com` eintragen."
    )

query = st.text_input(
    "Unternehmen oder Ticker",
    placeholder="z. B. ASML, Microsoft, Siemens AG, LVMH",
)

if st.button("Unternehmen suchen", disabled=not query.strip(), type="primary"):
    sec_provider = None
    if sec_user_agent_available:
        try:
            sec_provider = SECCompanyFactsProvider()
        except ValueError:
            sec_provider = None
    gleif_provider = GLEIFProvider()
    with st.spinner(f"Suche {query.strip()} in SEC/GLEIF …"):
        candidates, notes = discover_companies(
            query.strip(),
            sec_provider=sec_provider,
            gleif_provider=gleif_provider,
        )
    st.session_state["official_company_candidates"] = candidates
    st.session_state["official_company_search_notes"] = notes
    if candidates:
        st.success(f"{len(candidates)} mögliche Unternehmen gefunden.")
    else:
        st.warning("In SEC/GLEIF wurde kein passender Rechtsträger gefunden.")

for note in st.session_state.get("official_company_search_notes", []):
    st.caption(note)

candidates = st.session_state.get("official_company_candidates", [])
if candidates:
    labels = {_candidate_key(candidate): candidate for candidate in candidates}
    selected_label = st.selectbox("Unternehmen", list(labels))
    candidate = labels[selected_label]

    details = st.columns(4)
    details[0].metric("Unternehmen", candidate.name)
    details[1].metric("Ticker", candidate.ticker or "noch nicht bekannt")
    details[2].metric("Land", candidate.country or "—")
    details[3].metric("Identität", " + ".join(candidate.sources) or "—")

    with st.expander("Technische Identifikatoren", expanded=False):
        st.write(f"**SEC CIK:** {candidate.sec_cik or '—'}")
        st.write(f"**LEI:** {candidate.lei or '—'}")
        st.caption(
            "Diese Kennungen werden intern gespeichert, damit Finanzdaten später automatisch aus "
            "SEC bzw. ESEF gefunden werden."
        )

    with st.form("create-analysis-official"):
        if candidate.ticker:
            ticker = candidate.ticker
            st.caption(f"Verwendeter Ticker: **{ticker}**")
        else:
            ticker = st.text_input(
                "Börsenticker",
                help=(
                    "GLEIF enthält Rechtsträger, aber keine verlässliche Börsennotierung. "
                    "Hier genügt der Ticker deiner gewünschten Hauptnotierung."
                ),
            ).strip().upper()
        analysis_date = st.date_input("Analyse-Stichtag", value=date.today())
        market_price_raw = st.text_input("Aktienkurs am Stichtag (optional)")
        title = st.text_input("Titel (optional)")
        notes = st.text_area("Notizen / erste Investmentthese (optional)")
        create = st.form_submit_button("Analyse anlegen", type="primary")

    if create:
        try:
            if not ticker:
                raise ValueError("Bitte einen Börsenticker eingeben.")
            market_price = _optional_decimal(market_price_raw)
            with get_session() as session:
                company = get_or_create_company(
                    session,
                    name=candidate.name,
                    ticker=ticker,
                    currency=candidate.currency,
                    country=candidate.country,
                )
                if candidate.sec_cik:
                    upsert_provider_symbol(
                        session,
                        company,
                        provider="sec",
                        purpose="cik",
                        symbol=candidate.sec_cik,
                        note="Automatisch aus dem öffentlichen SEC-Ticker/CIK-Verzeichnis.",
                    )
                if candidate.lei:
                    upsert_provider_symbol(
                        session,
                        company,
                        provider="gleif",
                        purpose="lei",
                        symbol=candidate.lei,
                        note="Automatisch aus dem öffentlichen GLEIF-Register.",
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
            st.session_state.pop("official_company_candidates", None)
            st.session_state.pop("official_company_search_notes", None)
            st.session_state["selected_analysis_id"] = analysis.id
            st.success(
                f"{candidate.name}: Analyse R{analysis.revision_number} angelegt. "
                "Jetzt **Finanzdaten** öffnen und `Finanzdaten laden / aktualisieren` drücken."
            )
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

st.divider()
st.subheader("Gespeicherte Unternehmen")
with get_session() as session:
    companies = list_companies(session)

if companies:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Unternehmen": item.name,
                    "Ticker": item.ticker,
                    "Börse/Region": item.exchange,
                    "Land": item.country,
                    "Währung": item.currency,
                    "ISIN": item.isin,
                }
                for item in companies
            ]
        ),
        width="stretch",
        hide_index=True,
    )
else:
    st.caption("Noch keine Unternehmen gespeichert.")

with st.expander("Datenverwaltung – Unternehmen löschen", expanded=False):
    st.warning(
        "Das Löschen ist endgültig. Es entfernt das Unternehmen zusammen mit allen Analysen, "
        "Revisionen, Finanzdaten, Estimates, ChatGPT-Prüfungen, Overrides und Kennzahlen. "
        "Der lokale Provider-Cache bleibt bewusst erhalten."
    )

    if not companies:
        st.caption("Keine gespeicherten Unternehmen vorhanden.")
    else:
        single_tab, all_tab = st.tabs(["Ein Unternehmen", "Alle Unternehmen"])

        with single_tab:
            company_options = {
                f"{item.name} · {item.ticker}": (item.id, item.ticker)
                for item in companies
            }
            delete_label = st.selectbox(
                "Zu löschendes Unternehmen",
                list(company_options),
                key="delete-company-select",
            )
            delete_company_id, delete_ticker = company_options[delete_label]
            ticker_confirmation = st.text_input(
                f"Zur Bestätigung `{delete_ticker}` eingeben",
                key="delete-company-confirmation",
            )
            if st.button(
                "Unternehmen vollständig löschen",
                disabled=ticker_confirmation.strip().upper() != delete_ticker.upper(),
                key="delete-company-button",
            ):
                with get_session() as session:
                    summary = delete_company_completely(session, delete_company_id)
                st.success(
                    f"Gelöscht: {summary.companies} Unternehmen, {summary.analyses} Analysen und "
                    f"{summary.related_rows} abhängige Datensätze."
                )
                st.rerun()

        with all_tab:
            st.write(
                "Damit wird die lokale Unternehmens-/Analysedatenbank inhaltlich geleert. "
                "Datenbankstruktur, Anwendung und Provider-Cache bleiben erhalten."
            )
            all_confirmation = st.text_input(
                "Zur Bestätigung `ALLE LÖSCHEN` eingeben",
                key="delete-all-confirmation",
            )
            if st.button(
                "Alle Unternehmen und Analysen löschen",
                disabled=all_confirmation.strip() != "ALLE LÖSCHEN",
                key="delete-all-button",
            ):
                with get_session() as session:
                    summary = delete_all_companies_completely(session)
                st.success(
                    f"Lokale Analysedaten geleert: {summary.companies} Unternehmen, "
                    f"{summary.analyses} Analysen und {summary.related_rows} abhängige Datensätze gelöscht."
                )
                st.rerun()
