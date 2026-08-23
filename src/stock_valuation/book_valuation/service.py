from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_valuation.book_valuation.dcf import fair_value, present_value_owner_earnings, terminal_value
from stock_valuation.book_valuation.discount_rate import excel_book_discount_rate
from stock_valuation.book_valuation.models import (
    AVAILABLE,
    MISSING,
    MANUAL_CONFIRMED,
    SUGGESTED,
    BookAssumptionState,
    BookDCFScenarioResult,
    BOOK_VALUATION_VERSION,
    BookValue,
    BookValuationAnalysisResult,
    OwnerEarningsYear,
    available,
    stable_hash,
    unavailable,
)
from stock_valuation.book_valuation.multiplicator_method import PORTER_KEYS, fair_pe_from_components
from stock_valuation.book_valuation.owner_earnings import (
    change_in_operating_working_capital,
    operating_working_capital,
    owner_earnings,
    owner_earnings_capex,
    point,
    ratio,
)
from stock_valuation.book_valuation.persistence import load_all_book_assumptions, load_book_assumptions
from stock_valuation.database.models import Analysis, EstimateSnapshot, FinancialFactSnapshot, GuidanceSnapshot
from stock_valuation.workflow.persistence import canonical_hash, persist_stage_snapshot


BOOK_VALUATION_STAGE = "BOOK_VALUATION"

SCENARIOS = {
    "bear": "Pessimistisch",
    "base": "Basis",
    "bull": "Optimistisch",
}

SUGGESTIONS = {
    "base_pe": Decimal("7.5"),
    "financial_stability_addon": Decimal("0"),
    "market_position_addon": Decimal("0"),
    "profitability_multiplier": Decimal("1"),
    "growth_addon": Decimal("0"),
    "individuality_addon": Decimal("0"),
    "projection_years": Decimal("5"),
    "growth_rate": Decimal("0.03"),
    "terminal_growth_rate": Decimal("0.02"),
    "margin_of_safety": Decimal("0.5"),
}

ASSUMPTION_LABELS = {
    "base_pe": "Sockel-KGV",
    "financial_stability_addon": "KGV-Aufschlag finanzielle Stabilitaet",
    "market_position_addon": "KGV-Aufschlag Marktposition",
    "profitability_multiplier": "Rentabilitaetsmultiplikator",
    "growth_addon": "KGV-Aufschlag Wachstum",
    "individuality_addon": "KGV-Aufschlag Individualitaet",
    "forecast_net_income": "Prognostizierter Jahresueberschuss",
    "risk_free_rate": "Risikofreier Zins",
    "projection_years": "Planungszeitraum",
    "growth_rate": "Book-DCF-Wachstum",
    "terminal_growth_rate": "Ewige Wachstumsrate",
    "margin_of_safety": "Sicherheitsmarge",
}


def build_book_valuation_for_analysis(session: Session, analysis: Analysis, workflow_state) -> BookValuationAnalysisResult:
    manual = load_book_assumptions(session, analysis)
    scenario_manual = load_all_book_assumptions(session, analysis)
    calc = workflow_state.stages["CALCULATION"].payload
    market = workflow_state.stages["MARKET_DATA"].payload
    assumptions = workflow_state.stages["ASSUMPTIONS"].payload
    valuation = workflow_state.stages["VALUATION"].payload
    history = _owner_earnings_history(calc, manual)
    shares = _decimal(market.get("shares_outstanding"))
    market_price = _decimal(market.get("price"))
    forecast_net_income = _forecast_net_income(session, analysis, manual)
    multiplicator = fair_pe_from_components(
        base_pe=_manual(manual, "base_pe"),
        financial_stability_addon=_manual(manual, "financial_stability_addon"),
        porter_scores={key: row.value for key, row in manual.items() if key in PORTER_KEYS and row.value is not None},
        market_position_addon=_manual(manual, "market_position_addon"),
        profitability_multiplier=_manual(manual, "profitability_multiplier"),
        growth_addon=_manual(manual, "growth_addon"),
        individuality_addon=_manual(manual, "individuality_addon"),
        forecast_net_income=forecast_net_income,
        shares_outstanding=shares,
    )
    fair_pe = multiplicator.fair_pe.value if multiplicator.fair_pe.status == AVAILABLE else _manual(manual, "fair_pe")
    risk_free = _manual(manual, "risk_free_rate")
    if risk_free is None:
        risk_free = _risk_free_from_financial_facts(session, analysis)
    discount = excel_book_discount_rate(fair_pe=fair_pe, risk_free_rate=risk_free)
    projection_years_value = _manual(manual, "projection_years")
    projection_years = int(projection_years_value) if projection_years_value is not None else 0
    growth = _manual(manual, "growth_rate")
    terminal_growth = _manual(manual, "terminal_growth_rate")
    safety = _manual(manual, "margin_of_safety")
    base_oe = _manual(manual, "base_owner_earnings")
    if base_oe is None:
        base_oe = _latest_available_owner_earnings(history)
    forecast_values = _forecast_owner_earnings(base_oe, growth, projection_years)
    discount_rate = discount.cost_of_equity.value
    pv_rows = present_value_owner_earnings(forecast_values, discount_rate) if discount_rate is not None else ()
    terminal = terminal_value(
        forecast_values[-1] if forecast_values else None,
        discount_rate,
        terminal_growth,
        projection_years,
    )
    fair = fair_value(
        present_value_rows=pv_rows,
        present_value_terminal_value=terminal.present_value_terminal_value.value,
        shares_outstanding=shares,
        margin_of_safety=safety,
        market_price=market_price,
    )
    assumption_states = _assumption_states(manual)
    scenario_results = {
        scenario: _scenario_result(
            scenario,
            label,
            scenario_manual.get(scenario, {}),
            base_owner_earnings=base_oe,
            fair_pe=fair_pe,
            risk_free=risk_free,
            shares=shares,
            market_price=market_price,
        )
        for scenario, label in SCENARIOS.items()
    }
    values = {
        "owner_earnings": history[-1].owner_earnings if history else unavailable("owner_earnings", "currency", ("MISSING_OWNER_EARNINGS_HISTORY",)),
        "cost_of_equity": discount.cost_of_equity,
        "terminal_value": terminal.terminal_value,
        "fair_value": fair.fair_value_per_share,
        "margin_of_safety": fair.margin_of_safety,
        "base_pe": multiplicator.base_pe,
        "financial_stability_addon": multiplicator.financial_stability_addon,
        "market_position": multiplicator.market_position_points,
        "profitability_addon": multiplicator.market_profitability_addon,
        "growth_addon": multiplicator.growth_addon,
        "individuality_addon": multiplicator.individuality_addon,
        "fair_pe": multiplicator.fair_pe,
        "multiplicator_fair_price_per_share": multiplicator.fair_price_per_share,
    }
    warnings = tuple(sorted({issue for item in values.values() for issue in item.issues}))
    refs = tuple(ref for item in values.values() for ref in item.input_refs)
    result = BookValuationAnalysisResult(
        method_version=BOOK_VALUATION_VERSION,
        owner_earnings_history=tuple(history),
        owner_earnings_forecast=pv_rows,
        discount_rate_result=discount,
        terminal_value_result=terminal,
        fair_value_result=fair,
        multiplicator_method_result=multiplicator,
        market_inputs={
            "price": market.get("price"),
            "shares_outstanding": market.get("shares_outstanding"),
            "market_snapshot_id": workflow_state.market_snapshot_id,
        },
        manual_inputs={key: {"value": str(row.value) if row.value is not None else None, "note": row.note, "unit": row.unit} for key, row in manual.items()},
        assumption_states=assumption_states,
        scenario_results=scenario_results,
        values=values,
        warnings=warnings,
        review_required=bool(warnings),
        input_refs=refs,
        inputs_hash=stable_hash((canonical_hash(calc), canonical_hash(market), canonical_hash(scenario_manual), canonical_hash(assumptions), canonical_hash(valuation))),
    )
    persist_stage_snapshot(
        session,
        analysis,
        stage=BOOK_VALUATION_STAGE,
        engine_version=BOOK_VALUATION_VERSION,
        inputs_hash=result.inputs_hash,
        status="REVIEW_REQUIRED" if result.review_required else "READY",
        payload=asdict(result),
    )
    return result


def _owner_earnings_history(calc: dict[str, Any], manual: dict[str, Any]) -> list[OwnerEarningsYear]:
    rows = []
    previous_owc: BookValue | None = None
    for year in sorted(int(item) for item in calc.get("base_facts", {}) if str(item).isdigit()):
        net_income = _base_point(calc, year, "net_income")
        revenue = _base_point(calc, year, "revenue")
        capex_base = _base_point(calc, year, "capital_expenditures")
        intangible = _base_point(calc, year, "intangible_purchases")
        manual_intangible = _manual(manual, f"intangible_purchases_{year}")
        if intangible.status != AVAILABLE and manual_intangible is not None:
            intangible = available("intangible_purchases", manual_intangible, "currency", (f"manual:intangible_purchases:{year}",), note="Manuell bestätigt.")
        capex = owner_earnings_capex(capital_expenditures=capex_base, intangible_purchases=intangible)
        depreciation = _base_point(calc, year, "depreciation_amortization")
        owc = operating_working_capital(
            inventory=_base_point(calc, year, "inventory"),
            accounts_receivable=_base_point(calc, year, "accounts_receivable"),
            accounts_payable=_base_point(calc, year, "accounts_payable"),
        )
        delta = change_in_operating_working_capital(owc, previous_owc) if previous_owc is not None else unavailable("change_in_operating_working_capital", "currency", ("MISSING_PREVIOUS_OPERATING_WORKING_CAPITAL",), owc.input_refs)
        oe = owner_earnings(net_income=net_income, depreciation_amortization=depreciation, capex=capex, change_in_owc=delta)
        rows.append(
            OwnerEarningsYear(
                year,
                net_income,
                revenue,
                capex,
                ratio("capex_to_revenue", capex, revenue),
                depreciation,
                ratio("depreciation_to_capex", depreciation, capex),
                owc,
                ratio("operating_working_capital_to_revenue", owc, revenue),
                delta,
                oe,
            )
        )
        previous_owc = owc
    return rows


def _base_point(calc: dict[str, Any], year: int, metric: str) -> BookValue:
    facts = calc.get("base_facts", {}).get(str(year), [])
    row = next((item for item in facts if item.get("metric") == metric), None)
    if row is None or row.get("value") is None:
        return unavailable(metric, "currency", (f"MISSING_{metric.upper()}",), (f"financial_fact:{metric}:{year}",))
    return point(metric, year, _decimal(row.get("value")), row.get("currency"), AVAILABLE)


def _latest_base_metric(calc: dict[str, Any], metric: str) -> tuple[Decimal | None, int | None]:
    selected = None
    for year, facts in calc.get("base_facts", {}).items():
        row = next((item for item in facts if item.get("metric") == metric and item.get("value") is not None), None)
        if row and (selected is None or int(year) > selected[1]):
            selected = (_decimal(row["value"]), int(year))
    return selected or (None, None)


def _latest_available_owner_earnings(history: list[OwnerEarningsYear]) -> Decimal | None:
    for row in reversed(history):
        if row.owner_earnings.status == AVAILABLE:
            return row.owner_earnings.value
    return None


def _forecast_owner_earnings(base: Decimal | None, growth: Decimal | None, years: int) -> tuple[Decimal, ...]:
    if base is None or growth is None or years <= 0:
        return ()
    values = []
    value = base
    for _ in range(years):
        value *= Decimal("1") + growth
        values.append(value)
    return tuple(values)


def _forecast_net_income(
    session: Session,
    analysis: Analysis,
    manual: dict[str, Any],
) -> Decimal | None:
    manual_value = _manual(manual, "forecast_net_income")
    if manual_value is not None:
        return manual_value

    estimate = session.scalar(
        select(EstimateSnapshot)
        .where(
            EstimateSnapshot.analysis_id == analysis.id,
            EstimateSnapshot.metric == "net_income",
            EstimateSnapshot.average.is_not(None),
        )
        .order_by(EstimateSnapshot.period.asc(), EstimateSnapshot.id.desc())
        .limit(1)
    )
    if estimate is not None and estimate.average is not None:
        return _decimal(estimate.average)

    guidance = session.scalar(
        select(GuidanceSnapshot)
        .where(
            GuidanceSnapshot.analysis_id == analysis.id,
            GuidanceSnapshot.metric == "net_income",
            GuidanceSnapshot.point_estimate.is_not(None),
        )
        .order_by(GuidanceSnapshot.period.asc(), GuidanceSnapshot.id.desc())
        .limit(1)
    )
    if guidance is not None and guidance.point_estimate is not None:
        return _decimal(guidance.point_estimate)
    return None


def _assumption_states(manual: dict[str, Any]) -> dict[str, BookAssumptionState]:
    output: dict[str, BookAssumptionState] = {}
    units = {
        "base_pe": "multiple",
        "financial_stability_addon": "multiple_points",
        "market_position_addon": "multiple_points",
        "profitability_multiplier": "factor",
        "growth_addon": "multiple_points",
        "individuality_addon": "multiple_points",
        "forecast_net_income": "currency",
        "risk_free_rate": "decimal_ratio",
        "projection_years": "years",
        "growth_rate": "decimal_ratio",
        "terminal_growth_rate": "decimal_ratio",
        "margin_of_safety": "decimal_ratio",
    }
    for key, label in ASSUMPTION_LABELS.items():
        row = manual.get(key)
        value = _decimal(row.value) if row is not None and row.value is not None else None
        status = MANUAL_CONFIRMED if value is not None else (SUGGESTED if key in SUGGESTIONS else MISSING)
        output[key] = BookAssumptionState(
            key=key,
            label=label,
            value=value,
            unit=units.get(key, ""),
            status=status,
            scenario="base",
            suggestion=SUGGESTIONS.get(key),
            source=row.source_type if row is not None else None,
            note=row.note if row is not None else None,
        )
    return output


def _scenario_result(
    scenario: str,
    label: str,
    manual: dict[str, Any],
    *,
    base_owner_earnings: Decimal | None,
    fair_pe: Decimal | None,
    risk_free: Decimal | None,
    shares: Decimal | None,
    market_price: Decimal | None,
) -> BookDCFScenarioResult:
    scenario_base = _manual(manual, "base_owner_earnings")
    if scenario_base is None:
        scenario_base = base_owner_earnings
    growth = _manual(manual, "growth_rate")
    years_value = _manual(manual, "projection_years")
    years = int(years_value) if years_value is not None else 0
    scenario_fair_pe = _manual(manual, "fair_pe")
    if scenario_fair_pe is None:
        scenario_fair_pe = fair_pe
    scenario_risk_free = _manual(manual, "risk_free_rate")
    if scenario_risk_free is None:
        scenario_risk_free = risk_free
    terminal_growth = _manual(manual, "terminal_growth_rate")
    safety = _manual(manual, "margin_of_safety")

    discount = excel_book_discount_rate(fair_pe=scenario_fair_pe, risk_free_rate=scenario_risk_free)
    forecast = _forecast_owner_earnings(scenario_base, growth, years)
    discount_rate = discount.cost_of_equity.value
    pv_rows = present_value_owner_earnings(forecast, discount_rate) if discount_rate is not None else ()
    terminal = terminal_value(forecast[-1] if forecast else None, discount_rate, terminal_growth, years)
    fair = fair_value(
        present_value_rows=pv_rows,
        present_value_terminal_value=terminal.present_value_terminal_value.value,
        shares_outstanding=shares,
        margin_of_safety=safety,
        market_price=market_price,
    )
    pv_sum = fair.present_value_owner_earnings_sum
    owner_base_value = unavailable("base_owner_earnings", "currency", ("MISSING_BASE_OWNER_EARNINGS",)) if scenario_base is None else available("base_owner_earnings", scenario_base, "currency", (f"book_scenario:{scenario}:base_owner_earnings",))
    growth_value = unavailable("growth_rate", "decimal_ratio", ("MISSING_GROWTH_RATE",)) if growth is None else available("growth_rate", growth, "decimal_ratio", (f"book_scenario:{scenario}:growth_rate",))
    years_book = unavailable("projection_years", "years", ("MISSING_PROJECTION_YEARS",)) if years_value is None else available("projection_years", years_value, "years", (f"book_scenario:{scenario}:projection_years",))
    return BookDCFScenarioResult(
        scenario=scenario,
        label=label,
        owner_earnings_base=owner_base_value,
        growth_rate=growth_value,
        projection_years=years_book,
        fair_pe=discount.fair_pe,
        risk_free_rate=discount.risk_free_rate,
        discount_rate=discount.cost_of_equity,
        terminal_growth_rate=terminal.terminal_growth_rate,
        present_value_owner_earnings_sum=pv_sum,
        present_value_terminal_value=terminal.present_value_terminal_value,
        fair_value_per_share=fair.fair_value_per_share,
        fair_value_after_safety_margin=fair.fair_value_after_safety_margin,
        market_price=fair.market_price,
    )


def _effective_assumption(payload: dict[str, Any], key: str) -> Decimal | None:
    row = payload.get("effective_recommendations", {}).get(key) or payload.get("recommendations", {}).get(key)
    if not row:
        return None
    return _decimal(row.get("approved_value") if row.get("approved_value") is not None else row.get("recommended_value"))


def _risk_free_from_financial_facts(session: Session, analysis: Analysis) -> Decimal | None:
    row = session.scalar(
        select(FinancialFactSnapshot)
        .where(
            FinancialFactSnapshot.analysis_id == analysis.id,
            FinancialFactSnapshot.statement == "market",
            FinancialFactSnapshot.metric == "risk_free_rate_eur_aaa_10y",
            FinancialFactSnapshot.value.is_not(None),
        )
        .order_by(FinancialFactSnapshot.period_end.desc(), FinancialFactSnapshot.id.desc())
        .limit(1)
    )
    if row is None or row.value is None:
        return None
    if (row.currency or "").upper() != (analysis.company.currency or "").upper():
        return None
    return _decimal(row.value)


def _manual(rows: dict[str, Any], key: str) -> Decimal | None:
    row = rows.get(key)
    return _decimal(row.value) if row is not None and row.value is not None else None


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))
