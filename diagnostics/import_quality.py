from __future__ import annotations

import pandas as pd
import streamlit as st

from stock_valuation.analyses.service import get_analysis, list_analyses
from stock_valuation.data.resolution import load_preferred_financial_facts
from stock_valuation.database.session import get_session, init_database


init_database()
st.set_page_config(page_title="Importqualität – Diagnose", layout="wide")

CORE_FIELDS = (
    "revenue",
    "cost_of_revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "total_assets",
    "shareholders_equity",
    "current_assets",
    "current_liabilities",
    "cash_and_equivalents",
    "accounts_receivable",
    "inventory",
    "accounts_payable",
    "depreciation_amortization",
    "operating_cash_flow",
    "capital_expenditures",
)

st.title("Importqualität – Diagnose")

with get_session() as session:
    analyses = list_analyses(session, include_archived=True)
    options = {
        f"{item.company.name} · {item.as_of_date} · R{item.revision_number}": item.id
        for item in analyses
    }

if not options:
    st.info("Keine Analyse vorhanden.")
    st.stop()

analysis_id = options[st.selectbox("Analyse", list(options))]
with get_session() as session:
    analysis = get_analysis(session, analysis_id)
    if analysis is None:
        st.stop()
    preferred = load_preferred_financial_facts(session, analysis.id)

if not preferred:
    st.warning("Keine Fundamentaldaten vorhanden.")
    st.stop()

years = sorted({fact.period_end.year for fact in preferred})
latest_years = years[-2:] if len(years) >= 2 else years
index = {(fact.metric, fact.period_end.year): fact for fact in preferred}
rows = []
for metric in CORE_FIELDS:
    for year in latest_years:
        fact = index.get((metric, year))
        rows.append(
            {
                "Jahr": year,
                "Metrik": metric,
                "Vorhanden": bool(fact is not None and fact.value is not None),
                "Wert": float(fact.value) if fact is not None and fact.value is not None else None,
                "Quelle": fact.provider if fact is not None else None,
                "Source Type": fact.source_type if fact is not None else None,
            }
        )

st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
