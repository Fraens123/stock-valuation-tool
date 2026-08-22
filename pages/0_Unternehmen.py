from __future__ import annotations

import os
from datetime import date
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from stock_valuation.analyses.service import create_analysis, update_analysis_metadata
from stock_valuation.companies.provider_symbols import upsert_provider_symbol
from stock_valuation.companies.service import (
    alpha_vantage_company_candidates,
    get_or_create_from_candidate,
    list_companies,
)
from stock_valuation.data.providers.alphavantage import AlphaVantageProvider
from stock_valuation.data.providers.base import ProviderError
from stock_valuation.database.session import get_session, init_database


load_dotenv()
init_database()
st.set_page_config(page_title="Unternehmen", layout="wide")


def _optional_decimal(raw: str) -> Decimal | None:
    value = raw.strip().replace(" ", "").replace(",", ".")
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Aktienkurs ist keine gültige Zahl.") from exc


st.title("Unternehmen suchen")
st.caption(
    "Neue Aktien werden nicht im Code hinterlegt. Die Online-Suche fragt Alpha Vantage nur auf "
    "bewussten Klick ab (1 Request) und speichert den gewählten Provider-Ticker dauerhaft beim Unternehmen."
)

api_key_available = bool(os.getenv("ALPHA_VANTAGE_API_KEY"))
if not api_key_available:
    st.warning("ALPHA_VANTAGE_API_KEY fehlt in der lokalen `.env`.")

query = st.text_input("Unternehmen oder Ticker", placeholder="z. B. Microsoft, Siemens, LVMH, Novo Nordisk")

if st.button("Online bei Alpha Vantage suchen (1 Request)", disabled=not api_key_available or not query.strip()):
    try:
        provider = AlphaVantageProvider()
        with st.spinner(f"Suche nach {query.strip()} …"):
            raw_matches = provider.search_companies(query.strip())
        candidates = alpha_vantage_company_candidates(raw_matches)
        st.session_state["company_search_candidates"] = candidates
        st.session_state["company_search_query"] = query.strip()
        if candidates:
            st.success(f"{len(candidates)} Provider-Treffer gefunden.")
        else:
            st.warning("Alpha Vantage hat für diese Suche keine Treffer geliefert.")
    except ProviderError as exc:
        st.error(str(exc))

candidates = st.session_state.get("company_search_candidates", [])
if candidates:
    labels = {
        f"{candidate.name} · {candidate.ticker} · {candidate.exchange or '—'} · {candidate.currency}": candidate
        for candidate in candidates
    }
    selected_label = st.selectbox("Provider-Treffer", list(labels))
    candidate = labels[selected_label]

    details = st.columns(4)
    details[0].metric("Unternehmen", candidate.name)
    details[1].metric("Alpha-Vantage-Symbol", candidate.provider_symbol or candidate.ticker)
    details[2].metric("Region/Börse", candidate.exchange or "—")
    details[3].metric("Währung", candidate.currency)

    st.info(
        "Die Online-Suche bestätigt zunächst nur den Provider-Ticker. Der anschließende "
        "1-Request-Fundamentals-Test auf der Seite **Datenimport** prüft, ob für dieses Symbol "
        "tatsächlich Jahresabschlüsse verfügbar sind."
    )

    with st.form("create-analysis-from-provider"):
        analysis_date = st.date_input("Analyse-Stichtag", value=date.today())
        market_price_raw = st.text_input("Aktienkurs am Stichtag (optional)")
        title = st.text_input("Titel (optional)")
        notes = st.text_area("Notizen / erste Investmentthese (optional)")
        create = st.form_submit_button("Unternehmen speichern und Analyse anlegen", type="primary")

    if create:
        try:
            market_price = _optional_decimal(market_price_raw)
            with get_session() as session:
                company = get_or_create_from_candidate(session, candidate)
                upsert_provider_symbol(
                    session,
                    company,
                    provider="alphavantage",
                    purpose="fundamentals",
                    symbol=candidate.provider_symbol or candidate.ticker,
                    exchange=candidate.exchange,
                    currency=candidate.currency,
                    note="Über Alpha Vantage SYMBOL_SEARCH ausgewählt.",
                )
                analysis = create_analysis(session, company=company, as_of_date=analysis_date)
                update_analysis_metadata(
                    session,
                    analysis,
                    title=title or None,
                    notes=notes or None,
                    market_price=market_price,
                    market_price_currency=candidate.currency,
                )
            st.success(
                f"{candidate.name}: Analyse R{analysis.revision_number} angelegt. "
                "Als Nächstes auf **Datenimport** den 1-Request-Fundamentals-Test ausführen."
            )
        except ValueError as exc:
            st.error(str(exc))

st.divider()
st.subheader("Bereits gespeicherte Unternehmen")
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
        use_container_width=True,
        hide_index=True,
    )
else:
    st.caption("Noch keine Unternehmen gespeichert.")
