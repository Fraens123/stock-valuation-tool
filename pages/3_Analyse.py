from __future__ import annotations

from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st

from stock_valuation.database.models import AnalysisStatus
from stock_valuation.database.session import get_session, init_database
from stock_valuation.analyses.service import get_analysis
from stock_valuation.ui.navigation import STATUS_LABELS, current_analysis_id, render_analysis_selector, render_navigation
from stock_valuation.valuation_assumptions.approvals import approve_recommended_value, override_assumption
from stock_valuation.valuation_assumptions.models import AssumptionRecommendation
from stock_valuation.workflow.service import complete_analysis_if_ready, refresh_local_analysis_stages


STATUS_TEXT = {
    "READY": "Bereit",
    "READY_FOR_PREVIEW": "Preview",
    "REVIEW_REQUIRED": "Pruefung noetig",
    "BLOCKED": "Blockiert",
    "NOT_RUN": "Nicht ausgefuehrt",
    "STALE": "Veraltet",
    "UNAVAILABLE": "Nicht verfuegbar",
}


def _fmt(value, suffix: str = "") -> str:
    if value in (None, ""):
        return "-"
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)
    return f"{number:,.2f}{suffix}"


def _pct(value) -> str:
    if value in (None, ""):
        return "-"
    return f"{Decimal(str(value)) * Decimal('100'):.1f} %"


def _recommendations(payload: dict) -> list[dict]:
    rows = []
    for key, label in {
        "base_fcf": "Base FCF",
        "growth_rate": "Growth Rate",
        "discount_rate": "Required Return",
        "terminal_growth_rate": "Terminal Growth",
        "projection_years": "Projection Years",
    }.items():
        item = payload.get("recommendations", {}).get(key, {})
        rows.append(
            {
                "key": key,
                "Annahme": label,
                "Empfehlung": _pct(item.get("recommended_value")) if item.get("unit") == "decimal_ratio" else _fmt(item.get("recommended_value")),
                "Freigegeben": _pct(item.get("approved_value")) if item.get("unit") == "decimal_ratio" else _fmt(item.get("approved_value")),
                "Confidence": item.get("confidence"),
                "Quelle": item.get("source_type"),
                "Status": item.get("status"),
                "Warnings": ", ".join(item.get("warnings", ())),
                "raw": item,
            }
        )
    return rows


def _recommendation_from_payload(payload: dict) -> AssumptionRecommendation:
    return AssumptionRecommendation(
        **{
            **payload,
            "recommended_value": Decimal(str(payload["recommended_value"])) if payload.get("recommended_value") is not None else None,
            "approved_value": Decimal(str(payload["approved_value"])) if payload.get("approved_value") is not None else None,
            "warnings": tuple(payload.get("warnings", ())),
            "evidence_refs": tuple(payload.get("evidence_refs", ())),
        }
    )


init_database()
st.set_page_config(page_title="Analyse", layout="wide")
render_navigation()

st.title("Analyse")

with get_session() as session:
    analysis = render_analysis_selector(session, key="analysis-main-selector")
    if analysis is None:
        st.info("Zuerst unter Unternehmen eine Analyse anlegen.")
        st.stop()
    state = refresh_local_analysis_stages(session, analysis)

header = st.columns(7)
header[0].metric("Unternehmen", state.company_name)
header[1].metric("Ticker", state.ticker)
header[2].metric("Stichtag", state.as_of_date)
header[3].metric("Revision", f"R{state.revision_number}")
header[4].metric("Status", STATUS_LABELS.get(analysis.status, analysis.status.value))
market = state.stages["MARKET_DATA"].payload
header[5].metric("Market Price", _fmt(market.get("price"), f" {market.get('trading_currency') or ''}"))
header[6].metric("Price Date", market.get("price_date") or "-")

status_cols = st.columns(7)
for col, stage in zip(status_cols, ("FINANCIAL_DATA", "CALCULATION", "HISTORICAL_ANALYSIS", "BUSINESS_QUALITY", "MARKET_DATA", "ASSUMPTIONS", "VALUATION")):
    row = state.stages[stage]
    col.metric(stage.replace("_", " ").title(), STATUS_TEXT.get(row.status, row.status))

tabs = st.tabs(["Status", "Fundamentaldaten", "Entwicklung", "Qualitaet", "Markt", "Annahmen", "Bewertung", "Abschluss"])

with tabs[0]:
    rows = []
    for stage, item in state.stages.items():
        rows.append(
            {
                "Stage": stage,
                "Status": STATUS_TEXT.get(item.status, item.status),
                "Version": item.version,
                "Snapshot ID": item.snapshot_id,
                "Updated": item.created_at,
                "Warnings": ", ".join(item.warnings),
                "Blocker": ", ".join(item.blockers),
            }
        )
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

with tabs[1]:
    calc = state.stages["CALCULATION"].payload
    facts = []
    for year, items in calc.get("base_facts", {}).items():
        for item in items:
            if item["metric"] in {"revenue", "operating_income", "net_income", "operating_cash_flow", "cash_and_equivalents", "shareholders_equity"}:
                facts.append({"Jahr": int(year), "Metrik": item["metric"], "Wert": float(item["value"]) if item.get("value") is not None else None, "Einheit": item.get("currency") or item.get("unit")})
    for item in calc.get("results", []):
        if item["metric_id"] in {"ebitda", "free_cash_flow", "net_debt"}:
            facts.append({"Jahr": item["fiscal_year"], "Metrik": item["metric_id"], "Wert": float(item["value"]) if item.get("value") is not None else None, "Einheit": item.get("unit")})
    data = pd.DataFrame(facts)
    if data.empty:
        st.warning("Keine calculation-ready Fundamentaldaten vorhanden. Unter Finanzdaten pruefen.")
    else:
        st.caption(f"Historie: {len(sorted(data['Jahr'].unique()))} Jahre")
        st.dataframe(data.sort_values(["Jahr", "Metrik"], ascending=[False, True]), width="stretch", hide_index=True)

with tabs[2]:
    hist = state.stages["HISTORICAL_ANALYSIS"].payload
    years = hist.get("history_years", [])
    st.write(f"Historie: {len(years)} Jahre" if years else "Historie nicht verfuegbar.")
    series = hist.get("series", {})
    for metric in ("revenue", "net_income", "free_cash_flow", "operating_margin", "net_margin", "free_cash_flow_margin"):
        points = series.get(metric, [])
        chart_rows = [{"Jahr": item["fiscal_year"], metric: float(item["value"])} for item in points if item.get("status") == "AVAILABLE" and item.get("value") is not None]
        if chart_rows:
            st.markdown(f"#### {metric}")
            st.line_chart(pd.DataFrame(chart_rows).set_index("Jahr"))

with tabs[3]:
    quality = state.stages["BUSINESS_QUALITY"].payload.get("result", {})
    cols = st.columns(3)
    cols[0].metric("Overall Quality Score", _fmt(quality.get("overall_score")))
    cols[1].metric("Assessment", quality.get("assessment") or "-")
    cols[2].metric("Data Confidence", "separat")
    comps = quality.get("component_scores", [])
    if comps:
        st.dataframe(
            pd.DataFrame(
                {
                    "Komponente": item["component_id"],
                    "Score": item["score"],
                    "Status": item["status"],
                    "Metriken": ", ".join(item["contributing_metrics"]),
                }
                for item in comps
            ),
            width="stretch",
            hide_index=True,
        )
    if state.stages["BUSINESS_QUALITY"].payload.get("data_confidence"):
        with st.expander("Data Confidence"):
            st.json(state.stages["BUSINESS_QUALITY"].payload["data_confidence"])

with tabs[4]:
    if not market:
        st.warning("Kein Market Snapshot vorhanden. Marktdaten explizit unter der Marktdaten-Funktion aktualisieren.")
    else:
        cols = st.columns(4)
        cols[0].metric("Price", _fmt(market.get("price"), f" {market.get('trading_currency') or ''}"))
        cols[1].metric("Shares", _fmt(market.get("shares_outstanding")))
        cols[2].metric("Market Cap", _fmt(market.get("market_cap"), f" {market.get('trading_currency') or ''}"))
        cols[3].metric("Enterprise Value", _fmt(market.get("enterprise_value"), f" {market.get('trading_currency') or ''}"))
        st.write(f"Security Type: **{market.get('security_type') or '-'}** · Snapshot ID: `{market.get('snapshot_id')}`")
        with st.expander("Technische Market-Provenienz"):
            st.json(market)

with tabs[5]:
    assumptions = state.stages["ASSUMPTIONS"].payload
    if not assumptions:
        st.warning("Annahmen sind noch nicht berechenbar.")
    else:
        if any("APPROVAL_STALE" in warning for warning in assumptions.get("approval_warnings", ())):
            st.warning("Fruehere Freigabe ist wegen geaenderter Daten oder Methodik nicht mehr gueltig.")
        rows = _recommendations(assumptions)
        st.dataframe(pd.DataFrame([{k: v for k, v in row.items() if k not in {"raw", "key"}} for row in rows]), width="stretch", hide_index=True)
        editable = analysis.status in {AnalysisStatus.DRAFT, AnalysisStatus.IN_PROGRESS}
        for row in rows:
            with st.expander(f"{row['Annahme']} - warum diese Empfehlung?"):
                st.write(row["raw"].get("reasoning_summary") or "-")
                st.write(f"Primary Anchor: {row['raw'].get('primary_anchor') or '-'}")
                st.write(f"Policy: {row['raw'].get('policy_version') or '-'}")
                st.write(f"Warnings: {', '.join(row['raw'].get('warnings', ())) or '-'}")
                left, right = st.columns(2)
                if left.button("Empfehlung freigeben", key=f"approve-{row['key']}", disabled=not editable or row["raw"].get("recommended_value") is None):
                    with get_session() as session:
                        fresh = get_analysis(session, current_analysis_id() or analysis.id)
                        if fresh is not None:
                            recommendation = _recommendation_from_payload(row["raw"])
                            approve_recommended_value(session, fresh, recommendation, recommendation_inputs_hash=assumptions["assumption_set"]["inputs_hash"])
                            st.rerun()
                with right.form(f"override-{row['key']}"):
                    value = st.text_input("Override Value", key=f"override-value-{row['key']}")
                    note = st.text_input("Begruendung", key=f"override-note-{row['key']}")
                    submitted = st.form_submit_button("Override speichern", disabled=not editable)
                    if submitted:
                        if not note.strip():
                            st.error("Begruendung ist Pflicht.")
                        else:
                            with get_session() as session:
                                fresh = get_analysis(session, current_analysis_id() or analysis.id)
                                if fresh is not None:
                                    recommendation = _recommendation_from_payload(row["raw"])
                                    override_assumption(session, fresh, recommendation, approved_value=Decimal(value.replace(",", ".")), note=note, recommendation_inputs_hash=assumptions["assumption_set"]["inputs_hash"])
                                    st.rerun()

with tabs[6]:
    valuation = state.stages["VALUATION"].payload
    mode = valuation.get("mode") or ("FINAL" if state.final_valuation_snapshot_id else "PREVIEW")
    st.subheader("Freigegebene Bewertung" if mode == "FINAL" else "Bewertungs-Preview")
    if valuation.get("preview"):
        rows = []
        for scenario, item in valuation["preview"].items():
            rows.append(
                {
                    "Szenario": scenario,
                    "Fair Value": item.get("fair_value_per_unit"),
                    "Market Price": item.get("market_price"),
                    "Upside/Downside": item.get("upside_downside"),
                    "Margin of Safety": item.get("margin_of_safety"),
                    "Status": item.get("status"),
                    "Warnings": ", ".join(item.get("warnings", ())),
                }
            )
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    if valuation.get("multiples"):
        st.markdown("#### Current Multiples")
        st.dataframe(pd.DataFrame(valuation["multiples"]), width="stretch", hide_index=True)
    if state.final_valuation_snapshot_id:
        st.success(f"Final Valuation Snapshot: {state.final_valuation_snapshot_id}")
    elif state.stages["VALUATION"].status == "READY_FOR_PREVIEW":
        st.warning("Noch nicht final freigegeben.")

with tabs[7]:
    blockers = []
    from stock_valuation.workflow.service import finalization_blockers

    blockers = list(finalization_blockers(state))
    if blockers:
        st.warning("Analyse kann noch nicht final eingefroren werden.")
        for blocker in blockers:
            st.write(f"- {blocker}")
    else:
        st.success("Alle Pflichtstufen sind bereit.")
    if st.button("Analyse abschliessen und einfrieren", type="primary", disabled=bool(blockers) or analysis.status == AnalysisStatus.COMPLETED):
        with get_session() as session:
            fresh = get_analysis(session, current_analysis_id() or analysis.id)
            if fresh is not None:
                try:
                    complete_analysis_if_ready(session, fresh)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
