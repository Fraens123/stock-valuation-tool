from __future__ import annotations

import os
from datetime import date
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from stock_valuation.analyses.service import create_analysis, update_analysis_metadata
from stock_valuation.companies.deletion import (
    delete_all_companies_completely,
    delete_company_completely,
)
from stock_valuation.companies.provider_symbols import upsert_provider_symbol
from stock_valuation.companies.selection import (
    choose_recommended_listing,
    resolve_fundamentals_symbol,
    standard_issuer_groups,
)
from stock_valuation.companies.service import (
    alpha_vantage_company_candidates,
    get_or_create_from_candidate,
    list_companies,
)
from stock_valuation.data.offline_replay import OfflineReplayError, replay_review_files
from stock_valuation.data.providers.alphavantage import AlphaVantageProvider
from stock_valuation.data.providers.base import ProviderError
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


st.title("Unternehmen")
st.caption(
    "Suche nur nach dem Unternehmen. Börsenplatz und Alpha-Vantage-Symbol für Fundamentaldaten "
    "werden beim Anlegen automatisch getrennt bestimmt."
)

api_key_available = bool(os.getenv("ALPHA_VANTAGE_API_KEY"))
if not api_key_available:
    st.warning("ALPHA_VANTAGE_API_KEY fehlt in der lokalen `.env`.")

with st.expander("Offline-Entwicklung – vorhandenes ChatGPT-Prüfpaket wiederherstellen", expanded=False):
    st.write(
        "Damit kann ein zuvor exportiertes **Prüfpaket zusammen mit der zugehörigen JSON-Ergebnisdatei** "
        "ohne Alpha-Vantage-Request als Entwicklungs-Snapshot wiederhergestellt werden. "
        "Es werden nur die im Prüfpaket enthaltenen Jahre/Fakten rekonstruiert; vollständige 20-Jahres-Historie "
        "und Analystenschätzungen lassen sich daraus nicht zurückholen."
    )
    replay_package = st.file_uploader(
        "ChatGPT-Prüfpaket (.md)",
        type=["md"],
        key="offline-replay-package",
    )
    replay_result = st.file_uploader(
        "Zugehöriges ChatGPT-Prüfergebnis (.json)",
        type=["json"],
        key="offline-replay-result",
    )
    if st.button(
        "Offline-Snapshot wiederherstellen",
        disabled=replay_package is None or replay_result is None,
        key="offline-replay-button",
    ):
        try:
            with get_session() as session:
                summary = replay_review_files(
                    session,
                    replay_package.getvalue(),
                    replay_result.getvalue(),
                )
            st.session_state.pop("company_search_candidates", None)
            st.success(
                f"{summary.ticker} offline wiederhergestellt: {summary.fact_count} Finanzfakten und "
                f"{summary.review_finding_count} Prüfergebnisse. Kein Alpha-Vantage-Request verwendet."
            )
            st.rerun()
        except OfflineReplayError as exc:
            st.error(str(exc))

query = st.text_input(
    "Unternehmen oder Ticker",
    placeholder="z. B. ASML, Microsoft, Siemens, LVMH, Novo Nordisk",
)

if st.button(
    "Unternehmen suchen (Cache oder 1 Request)",
    disabled=not api_key_available or not query.strip(),
):
    try:
        provider = AlphaVantageProvider()
        with st.spinner(f"Suche nach {query.strip()} …"):
            raw_matches = provider.search_companies(query.strip())
        candidates = alpha_vantage_company_candidates(raw_matches)
        st.session_state["company_search_candidates"] = candidates
        source = "lokalem Cache" if provider.cache_hits else "Alpha Vantage"
        if candidates:
            groups = standard_issuer_groups(candidates)
            if groups:
                st.success(
                    f"{len(groups)} Unternehmen aus {len(candidates)} Börsen-/Instrumenttreffern erkannt · Quelle: {source}."
                )
            else:
                st.warning("Die Treffer enthalten kein eindeutig auswählbares Unternehmen.")
        else:
            st.warning("Alpha Vantage hat für diese Suche keine Treffer geliefert.")
    except ProviderError as exc:
        st.error(str(exc))

candidates = st.session_state.get("company_search_candidates", [])
if candidates:
    groups = standard_issuer_groups(candidates)
    if not groups:
        st.warning("Aus den Suchtreffern konnte kein normales Unternehmen abgeleitet werden.")
    else:
        group_labels = {
            f"{group.name} · {len(group.candidates)} gefundene Notierung(en)": group
            for group in groups
        }
        selected_group_label = st.selectbox("Unternehmen", list(group_labels))
        selected_group = group_labels[selected_group_label]

        st.info(
            "Du musst **keinen Ticker oder Börsenplatz auswählen**. Beim Anlegen prüft das Tool "
            "automatisch, welches Alpha-Vantage-Symbol echte Jahresabschlüsse liefert, und speichert "
            "dies getrennt vom Börsenplatz. Bereits bekannte Providerantworten kommen aus dem lokalen Cache."
        )

        with st.expander("Technische Details / gefundene Börsenplätze", expanded=False):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Bezeichnung": item.name,
                            "Symbol": item.provider_symbol or item.ticker,
                            "Region/Börse": item.exchange,
                            "Währung": item.currency,
                        }
                        for item in selected_group.candidates
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
            st.caption(
                "Diese Liste dient nur zur Kontrolle. Das Fundamentals-Symbol wird beim Anlegen mit "
                "einem Income-Statement-Probe automatisch verifiziert; identische Probe-Anfragen werden gecacht."
            )

        with st.form("create-analysis-from-provider"):
            analysis_date = st.date_input("Analyse-Stichtag", value=date.today())
            market_price_raw = st.text_input("Aktienkurs am Stichtag (optional)")
            title = st.text_input("Titel (optional)")
            notes = st.text_area("Notizen / erste Investmentthese (optional)")
            create = st.form_submit_button(
                "Unternehmen automatisch erkennen und Analyse anlegen",
                type="primary",
            )

        if create:
            try:
                market_price = _optional_decimal(market_price_raw)
                provider = AlphaVantageProvider()
                with st.spinner("Ermittle automatisch Fundamentaldaten-Symbol und passenden Börsenplatz …"):
                    resolution = resolve_fundamentals_symbol(
                        provider,
                        selected_group.candidates,
                        max_attempts=3,
                    )
                    listing = choose_recommended_listing(
                        selected_group.candidates,
                        reported_currency=resolution.reported_currency,
                    )

                with get_session() as session:
                    company = get_or_create_from_candidate(session, listing)
                    upsert_provider_symbol(
                        session,
                        company,
                        provider="alphavantage",
                        purpose="listing",
                        symbol=listing.provider_symbol or listing.ticker,
                        exchange=listing.exchange,
                        currency=listing.currency,
                        note="Automatisch aus den SYMBOL_SEARCH-Börsenplätzen ausgewählte Haupt-/Referenznotierung.",
                    )
                    upsert_provider_symbol(
                        session,
                        company,
                        provider="alphavantage",
                        purpose="fundamentals",
                        symbol=resolution.symbol,
                        currency=resolution.reported_currency,
                        note=(
                            "Automatisch per INCOME_STATEMENT-Probe bestätigt; "
                            f"{resolution.annual_report_count} Jahresberichte, letzter Stichtag "
                            f"{resolution.latest_fiscal_date or '—'}."
                        ),
                    )
                    analysis = create_analysis(session, company=company, as_of_date=analysis_date)
                    update_analysis_metadata(
                        session,
                        analysis,
                        title=title or None,
                        notes=notes or None,
                        market_price=market_price,
                        market_price_currency=listing.currency,
                    )

                st.session_state.pop("company_search_candidates", None)
                attempts = ", ".join(resolution.attempts)
                source = "Cache" if provider.cache_hits and provider.network_requests == 0 else "Provider/Cache"
                st.success(
                    f"{company.name}: Analyse R{analysis.revision_number} angelegt. "
                    f"Fundamentaldaten automatisch bestätigt mit `{resolution.symbol}` "
                    f"({resolution.reported_currency or 'Währung unbekannt'}); geprüft: {attempts}; Quelle: {source}. "
                    "Jetzt links **Finanzdaten** öffnen und `Daten laden / aktualisieren` drücken."
                )
                st.rerun()
            except (ValueError, ProviderError) as exc:
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
        "Revisionen, Finanzdaten, Estimates, ChatGPT-Prüfungen, Overrides, Kennzahlen und "
        "später gespeicherten Bewertungs-/Thesendaten. Der lokale Provider-Cache bleibt bewusst erhalten."
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
                st.session_state.pop("company_search_candidates", None)
                st.success(
                    f"Gelöscht: {summary.companies} Unternehmen, {summary.analyses} Analysen und "
                    f"{summary.related_rows} abhängige Datensätze."
                )
                st.rerun()

        with all_tab:
            st.write(
                "Damit wird die lokale Unternehmens-/Analysedatenbank inhaltlich geleert. "
                "Die Datenbankstruktur, Anwendung und der Provider-Cache bleiben erhalten."
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
                st.session_state.pop("company_search_candidates", None)
                st.success(
                    f"Lokale Analysedaten geleert: {summary.companies} Unternehmen, "
                    f"{summary.analyses} Analysen und {summary.related_rows} abhängige Datensätze gelöscht."
                )
                st.rerun()
