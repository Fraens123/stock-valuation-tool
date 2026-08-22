from __future__ import annotations

from collections import defaultdict

import pandas as pd
import streamlit as st

from stock_valuation.analyses.service import get_analysis, list_analyses
from stock_valuation.data.resolution import load_preferred_financial_facts
from stock_valuation.database.session import get_session, init_database


init_database()
st.set_page_config(page_title="Importqualität", layout="wide")

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


st.title("Importqualität – alle Unternehmen")
st.caption(
    "Diese Seite funktioniert für jede importierte Aktie. Sie trennt **Import-Verfügbarkeit** "
    "von **Primärquellen-Validierung**: fehlende oder vorhandene API-Daten werden sichtbar, "
    "ohne so zu tun, als seien ungeprüfte Providerwerte bereits offiziell bestätigt."
)

with get_session() as session:
    analyses = list_analyses(session, include_archived=True)
    options = {
        f"{item.company.name} · {item.as_of_date} · R{item.revision_number}": item.id
        for item in analyses
    }

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
    preferred = load_preferred_financial_facts(session, analysis.id)

if not preferred:
    st.warning("Für diese Analyse wurden noch keine Fundamentaldaten importiert.")
    st.stop()

years = sorted({fact.period_end.year for fact in preferred})
latest_years = years[-2:] if len(years) >= 2 else years
by_key = {(fact.metric, fact.period_end.year): fact for fact in preferred}

available_core = 0
missing_core = 0
rows: list[dict] = []
for metric in CORE_FIELDS:
    for year in latest_years:
        fact = by_key.get((metric, year))
        if fact is None or fact.value is None:
            status = "❌ FEHLT"
            missing_core += 1
            rows.append(
                {
                    "Status": status,
                    "Jahr": year,
                    "Interner Schlüssel": metric,
                    "Wert": None,
                    "Währung": None,
                    "Bevorzugte Quelle": None,
                    "Source Type": None,
                    "Provider-Feld": None,
                }
            )
            continue

        available_core += 1
        if fact.source_type == "primary_source":
            status = "✅ PRIMÄRQUELLE"
        else:
            status = "🟡 API – NICHT PRIMÄRVALIDIERT"
        rows.append(
            {
                "Status": status,
                "Jahr": year,
                "Interner Schlüssel": metric,
                "Wert": float(fact.value),
                "Währung": fact.currency,
                "Bevorzugte Quelle": fact.provider,
                "Source Type": fact.source_type,
                "Provider-Feld": fact.provider_field,
            }
        )

primary_count = sum(fact.source_type == "primary_source" for fact in preferred)
provider_counts: dict[str, int] = defaultdict(int)
for fact in preferred:
    provider_counts[fact.provider or "—"] += 1

summary = st.columns(5)
summary[0].metric("Geschäftsjahre", len(years))
summary[1].metric("Bevorzugte Datenpunkte", len(preferred))
summary[2].metric("Primärquellen-Fakten", primary_count)
summary[3].metric("Core verfügbar", available_core)
summary[4].metric("Core fehlt", missing_core)

st.subheader("Kernfelder der letzten Geschäftsjahre")
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.subheader("Quellenmix")
st.dataframe(
    pd.DataFrame(
        [
            {"Quelle": provider, "Bevorzugte Datenpunkte": count}
            for provider, count in sorted(provider_counts.items())
        ]
    ),
    use_container_width=True,
    hide_index=True,
)

if analysis.company.ticker.upper() == "ASML":
    st.success(
        "Für ASML existiert zusätzlich ein detaillierter 2024/2025-Primärquellen-Gate auf "
        "der Seite **Datenqualität**."
    )
else:
    st.warning(
        "Für dieses Unternehmen sind importierte Providerwerte derzeit noch nicht automatisch "
        "gegen den offiziellen Geschäftsbericht validiert. Das verhindert den Import **nicht**; "
        "es kennzeichnet lediglich die Datenqualität korrekt. Generische Primärquellenadapter "
        "(SEC/XBRL/ESEF bzw. IR-Dokumente) werden als nächste Schicht ergänzt."
    )
