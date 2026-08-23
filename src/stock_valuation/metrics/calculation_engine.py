from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Mapping


CALCULATION_ENGINE_VERSION = "calc-v1.0"
NOT_SEPARATELY_REPORTED = "NOT_SEPARATELY_REPORTED"


@dataclass(frozen=True)
class CalculationInput:
    metric: str
    fiscal_year: int
    value: Decimal | None
    currency: str | None = None
    unit: str = "currency"
    source_status: str = "PASS"
    provider: str | None = None
    provider_field: str | None = None
    accession: str | None = None
    filing_date: str | None = None


@dataclass(frozen=True)
class MetricDefinition:
    metric_id: str
    name: str
    category: str
    formula: str
    inputs: tuple[str, ...]
    unit: str
    sign_convention: str
    missing_inputs: str
    interpretation: str
    implemented: bool = True


@dataclass(frozen=True)
class AvailabilityIssue:
    code: str
    detail: str
    inputs: tuple[str, ...] = ()


@dataclass(frozen=True)
class DerivedMetricResult:
    metric_id: str
    fiscal_year: int
    value: Decimal | None
    unit: str
    status: str
    issues: tuple[AvailabilityIssue, ...]
    input_metrics: tuple[str, ...]
    input_provenance: tuple[CalculationInput, ...]
    calculation_version: str = CALCULATION_ENGINE_VERSION
    inputs_hash: str | None = None


FactsByMetric = Mapping[str, CalculationInput]
Formula = Callable[[FactsByMetric, Mapping[str, DerivedMetricResult]], Decimal | None]


def _d(value: str) -> Decimal:
    return Decimal(value)


def _safe_ratio(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _value(facts: FactsByMetric, metric: str) -> Decimal | None:
    fact = facts.get(metric)
    return None if fact is None else fact.value


def _derived(derived: Mapping[str, DerivedMetricResult], metric: str) -> Decimal | None:
    result = derived.get(metric)
    return None if result is None else result.value


def _sum_values(facts: FactsByMetric, *metrics: str) -> Decimal | None:
    values = [_value(facts, metric) for metric in metrics]
    if any(value is None for value in values):
        return None
    return sum(value or Decimal("0") for value in values)


def _currency_set(inputs: tuple[CalculationInput, ...]) -> set[str]:
    return {
        str(item.currency).upper()
        for item in inputs
        if item.currency and item.unit == "currency" and item.value is not None
    }


def _inputs_hash(inputs: tuple[CalculationInput, ...]) -> str:
    payload = "|".join(
        sorted(
            f"{item.metric}:{item.fiscal_year}:{item.value}:{item.currency}:{item.provider}:"
            f"{item.provider_field}:{item.accession}:{item.filing_date}:{item.source_status}"
            for item in inputs
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ratio(numerator: str, denominator: str) -> Formula:
    return lambda facts, derived: _safe_ratio(_value(facts, numerator), _value(facts, denominator))


def _derived_ratio(numerator: str, denominator: str) -> Formula:
    return lambda facts, derived: _safe_ratio(_derived(derived, numerator), _value(facts, denominator))


def _net_debt(facts: FactsByMetric, derived: Mapping[str, DerivedMetricResult]) -> Decimal | None:
    debt = _sum_values(facts, "short_term_debt", "long_term_debt")
    cash = _value(facts, "cash_and_equivalents")
    if debt is None or cash is None:
        return None
    return debt - cash


def _ebitda(facts: FactsByMetric, derived: Mapping[str, DerivedMetricResult]) -> Decimal | None:
    operating_income = _value(facts, "operating_income")
    d_and_a = _value(facts, "depreciation_amortization")
    if operating_income is None or d_and_a is None:
        return None
    return operating_income + d_and_a


def _free_cash_flow(facts: FactsByMetric, derived: Mapping[str, DerivedMetricResult]) -> Decimal | None:
    ocf = _value(facts, "operating_cash_flow")
    capex = _value(facts, "capital_expenditures")
    if ocf is None or capex is None:
        return None
    return ocf - capex


def _quick_ratio(facts: FactsByMetric, derived: Mapping[str, DerivedMetricResult]) -> Decimal | None:
    current_liabilities = _value(facts, "current_liabilities")
    numerator = _sum_values(facts, "cash_and_equivalents", "accounts_receivable")
    return _safe_ratio(numerator, current_liabilities)


def _working_capital(facts: FactsByMetric, derived: Mapping[str, DerivedMetricResult]) -> Decimal | None:
    current_assets = _value(facts, "current_assets")
    current_liabilities = _value(facts, "current_liabilities")
    if current_assets is None or current_liabilities is None:
        return None
    return current_assets - current_liabilities


def _receivables_days(facts: FactsByMetric, derived: Mapping[str, DerivedMetricResult]) -> Decimal | None:
    return _safe_ratio(_value(facts, "accounts_receivable") * _d("365") if _value(facts, "accounts_receivable") is not None else None, _value(facts, "revenue"))


def _payables_days(facts: FactsByMetric, derived: Mapping[str, DerivedMetricResult]) -> Decimal | None:
    return _safe_ratio(_value(facts, "accounts_payable") * _d("365") if _value(facts, "accounts_payable") is not None else None, _value(facts, "revenue"))


def _inventory_days(facts: FactsByMetric, derived: Mapping[str, DerivedMetricResult]) -> Decimal | None:
    return _safe_ratio(_value(facts, "inventory") * _d("365") if _value(facts, "inventory") is not None else None, _value(facts, "revenue"))


FORMULAS: dict[str, Formula] = {
    "gross_margin": _ratio("gross_profit", "revenue"),
    "operating_margin": _ratio("operating_income", "revenue"),
    "net_margin": _ratio("net_income", "revenue"),
    "ebitda": _ebitda,
    "ebitda_margin": _derived_ratio("ebitda", "revenue"),
    "return_on_assets": _ratio("net_income", "total_assets"),
    "return_on_equity": _ratio("net_income", "shareholders_equity"),
    "equity_ratio": _ratio("shareholders_equity", "total_assets"),
    "debt_to_assets": lambda facts, derived: _safe_ratio(_sum_values(facts, "short_term_debt", "long_term_debt"), _value(facts, "total_assets")),
    "debt_to_equity": lambda facts, derived: _safe_ratio(_sum_values(facts, "short_term_debt", "long_term_debt"), _value(facts, "shareholders_equity")),
    "net_debt": _net_debt,
    "net_debt_to_ebitda": lambda facts, derived: _safe_ratio(_derived(derived, "net_debt"), _derived(derived, "ebitda")),
    "current_ratio": _ratio("current_assets", "current_liabilities"),
    "quick_ratio": _quick_ratio,
    "cash_ratio": _ratio("cash_and_equivalents", "current_liabilities"),
    "operating_cash_flow_margin": _ratio("operating_cash_flow", "revenue"),
    "capex_ratio": _ratio("capital_expenditures", "operating_cash_flow"),
    "free_cash_flow": _free_cash_flow,
    "free_cash_flow_margin": _derived_ratio("free_cash_flow", "revenue"),
    "working_capital": _working_capital,
    "working_capital_to_revenue": _derived_ratio("working_capital", "revenue"),
    "receivables_days": _receivables_days,
    "payables_days": _payables_days,
    "inventory_intensity": _ratio("inventory", "total_assets"),
    "inventory_days": _inventory_days,
}


METRIC_DEFINITIONS: tuple[MetricDefinition, ...] = (
    MetricDefinition("gross_margin", "Gross Margin", "Margen", "gross_profit / revenue", ("gross_profit", "revenue"), "decimal_ratio", "positive ratio; negative values allowed if gross loss", "UNAVAILABLE if input missing or revenue is zero", "Shows retained revenue after direct costs."),
    MetricDefinition("operating_margin", "Operating Margin", "Margen", "operating_income / revenue", ("operating_income", "revenue"), "decimal_ratio", "positive is profitable; negative values allowed", "UNAVAILABLE if input missing or revenue is zero", "Measures operating profitability before financing and taxes."),
    MetricDefinition("net_margin", "Net Margin", "Margen", "net_income / revenue", ("net_income", "revenue"), "decimal_ratio", "positive is profitable; negative values allowed", "UNAVAILABLE if input missing or revenue is zero", "Shows consolidated profit per unit of revenue."),
    MetricDefinition("ebitda", "EBITDA", "Profitabilitaet", "operating_income + depreciation_amortization", ("operating_income", "depreciation_amortization"), "currency", "can be negative; D&A is positive expense add-back", "UNAVAILABLE if input missing", "Internal operating earnings proxy before D&A; never sourced from provider EBITDA."),
    MetricDefinition("ebitda_margin", "EBITDA Margin", "Margen", "ebitda / revenue", ("ebitda", "revenue"), "decimal_ratio", "positive is profitable; negative values allowed", "UNAVAILABLE if EBITDA unavailable or revenue is zero", "Operating profitability before D&A relative to revenue."),
    MetricDefinition("return_on_assets", "Return on Assets", "Kapitalrenditen", "net_income / total_assets", ("net_income", "total_assets"), "decimal_ratio", "negative values allowed", "UNAVAILABLE if input missing or total_assets is zero", "Measures earnings generated by the asset base."),
    MetricDefinition("return_on_equity", "Return on Equity", "Kapitalrenditen", "net_income / shareholders_equity", ("net_income", "shareholders_equity"), "decimal_ratio", "negative values allowed; negative equity makes interpretation special", "UNAVAILABLE if input missing or equity is zero", "Measures earnings relative to book equity."),
    MetricDefinition("equity_ratio", "Equity Ratio", "Kapitalstruktur", "shareholders_equity / total_assets", ("shareholders_equity", "total_assets"), "decimal_ratio", "negative values allowed if equity is negative", "UNAVAILABLE if input missing or total_assets is zero", "Shows balance-sheet capital buffer."),
    MetricDefinition("debt_to_assets", "Debt to Assets", "Verschuldung", "(short_term_debt + long_term_debt) / total_assets", ("short_term_debt", "long_term_debt", "total_assets"), "decimal_ratio", "debt uses positive carrying amount", "UNAVAILABLE if input missing or total_assets is zero", "Shows interest-bearing debt relative to assets."),
    MetricDefinition("debt_to_equity", "Debt to Equity", "Verschuldung", "(short_term_debt + long_term_debt) / shareholders_equity", ("short_term_debt", "long_term_debt", "shareholders_equity"), "decimal_ratio", "debt uses positive carrying amount; negative equity makes ratio negative", "UNAVAILABLE if input missing or equity is zero", "Shows balance-sheet leverage against equity."),
    MetricDefinition("net_debt", "Net Debt", "Verschuldung", "short_term_debt + long_term_debt - cash_and_equivalents", ("short_term_debt", "long_term_debt", "cash_and_equivalents"), "currency", "negative means net cash", "UNAVAILABLE if input missing", "Shows debt after cash offset."),
    MetricDefinition("net_debt_to_ebitda", "Net Debt / EBITDA", "Verschuldung", "net_debt / ebitda", ("net_debt", "ebitda"), "decimal_ratio", "negative means net cash; negative EBITDA makes interpretation special", "UNAVAILABLE if input missing or EBITDA is zero", "Approximates leverage relative to operating earnings power."),
    MetricDefinition("current_ratio", "Current Ratio", "Liquiditaet", "current_assets / current_liabilities", ("current_assets", "current_liabilities"), "decimal_ratio", "positive ratio", "UNAVAILABLE if input missing or current_liabilities is zero", "Measures broad short-term liquidity."),
    MetricDefinition("quick_ratio", "Quick Ratio", "Liquiditaet", "(cash_and_equivalents + accounts_receivable) / current_liabilities", ("cash_and_equivalents", "accounts_receivable", "current_liabilities"), "decimal_ratio", "positive ratio", "UNAVAILABLE if input missing or current_liabilities is zero", "Measures liquidity without relying on inventory."),
    MetricDefinition("cash_ratio", "Cash Ratio", "Liquiditaet", "cash_and_equivalents / current_liabilities", ("cash_and_equivalents", "current_liabilities"), "decimal_ratio", "positive ratio", "UNAVAILABLE if input missing or current_liabilities is zero", "Measures immediate liquidity coverage."),
    MetricDefinition("operating_cash_flow_margin", "Operating Cash Flow Margin", "Cashflow", "operating_cash_flow / revenue", ("operating_cash_flow", "revenue"), "decimal_ratio", "negative values allowed", "UNAVAILABLE if input missing or revenue is zero", "Shows operating cash generation relative to sales."),
    MetricDefinition("capex_ratio", "Capex Ratio", "Cashflow", "capital_expenditures / operating_cash_flow", ("capital_expenditures", "operating_cash_flow"), "decimal_ratio", "capex is positive cash outflow", "UNAVAILABLE if input missing or operating cash flow is zero", "Shows share of OCF reinvested into PPE."),
    MetricDefinition("free_cash_flow", "Free Cash Flow", "Cashflow", "operating_cash_flow - capital_expenditures", ("operating_cash_flow", "capital_expenditures"), "currency", "capex is positive cash outflow and subtracted", "UNAVAILABLE if input missing", "Cash left after PPE investment."),
    MetricDefinition("free_cash_flow_margin", "Free Cash Flow Margin", "Cashflow", "free_cash_flow / revenue", ("free_cash_flow", "revenue"), "decimal_ratio", "negative values allowed", "UNAVAILABLE if FCF unavailable or revenue is zero", "Shows post-capex cash generation relative to sales."),
    MetricDefinition("working_capital", "Working Capital", "Working Capital", "current_assets - current_liabilities", ("current_assets", "current_liabilities"), "currency", "negative values allowed", "UNAVAILABLE if input missing", "Shows net short-term operating funding position."),
    MetricDefinition("working_capital_to_revenue", "Working Capital / Revenue", "Working Capital", "working_capital / revenue", ("working_capital", "revenue"), "decimal_ratio", "negative values allowed", "UNAVAILABLE if input missing or revenue is zero", "Shows working-capital intensity relative to sales."),
    MetricDefinition("receivables_days", "Receivables Days", "Working Capital", "accounts_receivable * 365 / revenue", ("accounts_receivable", "revenue"), "days", "positive day count", "UNAVAILABLE if input missing, revenue is zero, or fiscal-year length not accepted", "Approximates customer collection period."),
    MetricDefinition("payables_days", "Payables Days", "Working Capital", "accounts_payable * 365 / revenue", ("accounts_payable", "revenue"), "days", "positive day count", "UNAVAILABLE if input missing, revenue is zero, or fiscal-year length not accepted", "Approximates supplier financing period using revenue as V1 denominator."),
    MetricDefinition("inventory_intensity", "Inventory Intensity", "Working Capital", "inventory / total_assets", ("inventory", "total_assets"), "decimal_ratio", "positive ratio", "UNAVAILABLE if inventory is NOT_SEPARATELY_REPORTED; never impute zero", "Shows asset base tied up in inventory where separately reported."),
    MetricDefinition("inventory_days", "Inventory Days", "Working Capital", "inventory * 365 / revenue", ("inventory", "revenue"), "days", "positive day count", "UNAVAILABLE if inventory is NOT_SEPARATELY_REPORTED; never impute zero", "Approximates inventory holding period where separately reported."),
    MetricDefinition("revenue_growth", "Revenue Growth", "Wachstum", "current revenue / prior-year revenue - 1", ("revenue",), "decimal_ratio", "negative means shrinkage", "UNAVAILABLE without prior year", "Shows year-over-year revenue growth.", implemented=False),
    MetricDefinition("valuation_multiples", "Valuation Multiples", "Aktien-/Bewertungskennzahlen", "requires market data not in frozen financial pipeline", ("market_price", "market_cap", "shares"), "various", "depends on metric", "UNAVAILABLE until market/share data source is approved", "Valuation layer is deliberately blocked from using financial provider data.", implemented=False),
)

METRIC_DEFINITION_BY_ID = {definition.metric_id: definition for definition in METRIC_DEFINITIONS}


def calculate_metrics_for_year(
    facts: Mapping[str, CalculationInput],
    fiscal_year: int,
    *,
    fiscal_year_days: int = 365,
    metric_ids: tuple[str, ...] | None = None,
) -> list[DerivedMetricResult]:
    selected = metric_ids or tuple(definition.metric_id for definition in METRIC_DEFINITIONS if definition.implemented)
    derived: dict[str, DerivedMetricResult] = {}
    output: list[DerivedMetricResult] = []
    for metric_id in selected:
        definition = METRIC_DEFINITION_BY_ID[metric_id]
        result = _calculate_one(definition, facts, fiscal_year, derived, fiscal_year_days=fiscal_year_days)
        output.append(result)
        derived[metric_id] = result
    return output


def _calculate_one(
    definition: MetricDefinition,
    facts: Mapping[str, CalculationInput],
    fiscal_year: int,
    derived: Mapping[str, DerivedMetricResult],
    *,
    fiscal_year_days: int,
) -> DerivedMetricResult:
    inputs = _collect_inputs(definition, facts, derived)
    issues = list(_availability_issues(definition, facts, derived, inputs, fiscal_year_days=fiscal_year_days))
    value = None if issues else FORMULAS[definition.metric_id](facts, derived)
    if value is None and not issues:
        issues.append(AvailabilityIssue("CALCULATION_UNAVAILABLE", "Formula returned no value.", definition.inputs))
    status = "AVAILABLE" if value is not None and not issues else "UNAVAILABLE"
    return DerivedMetricResult(
        metric_id=definition.metric_id,
        fiscal_year=fiscal_year,
        value=value,
        unit=definition.unit,
        status=status,
        issues=tuple(issues),
        input_metrics=definition.inputs,
        input_provenance=inputs,
        inputs_hash=_inputs_hash(inputs) if inputs else None,
    )


def _collect_inputs(
    definition: MetricDefinition,
    facts: Mapping[str, CalculationInput],
    derived: Mapping[str, DerivedMetricResult],
) -> tuple[CalculationInput, ...]:
    inputs: list[CalculationInput] = []
    for metric in definition.inputs:
        fact = facts.get(metric)
        if fact is not None:
            inputs.append(fact)
            continue
        derived_result = derived.get(metric)
        if derived_result is not None:
            inputs.extend(derived_result.input_provenance)
    seen: set[tuple[str, int, str | None]] = set()
    unique: list[CalculationInput] = []
    for item in inputs:
        key = (item.metric, item.fiscal_year, item.accession)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return tuple(unique)


def _availability_issues(
    definition: MetricDefinition,
    facts: Mapping[str, CalculationInput],
    derived: Mapping[str, DerivedMetricResult],
    inputs: tuple[CalculationInput, ...],
    *,
    fiscal_year_days: int,
) -> tuple[AvailabilityIssue, ...]:
    issues: list[AvailabilityIssue] = []
    missing: list[str] = []
    not_separate: list[str] = []
    for metric in definition.inputs:
        if metric in derived:
            if derived[metric].status != "AVAILABLE":
                missing.append(metric)
            continue
        fact = facts.get(metric)
        if fact is None:
            missing.append(metric)
        elif fact.source_status == NOT_SEPARATELY_REPORTED:
            not_separate.append(metric)
        elif fact.value is None:
            missing.append(metric)
    if not_separate:
        issues.append(
            AvailabilityIssue(
                NOT_SEPARATELY_REPORTED,
                "Conditional input is officially not separately reported; no zero was imputed.",
                tuple(not_separate),
            )
        )
    if missing:
        issues.append(AvailabilityIssue("MISSING_INPUT", "Required calculation input is unavailable.", tuple(missing)))
    if len(_currency_set(inputs)) > 1:
        issues.append(AvailabilityIssue("CURRENCY_MISMATCH", "Currency inputs differ.", tuple(item.metric for item in inputs)))
    if definition.unit in {"decimal_ratio", "days"}:
        denominator = _denominator_metric(definition.metric_id)
        denominator_value = _derived(derived, denominator) if denominator in derived else _value(facts, denominator)
        if denominator_value == 0:
            issues.append(AvailabilityIssue("DIVISION_BY_ZERO", "Denominator is zero.", (denominator,)))
    if definition.unit == "days" and not 350 <= fiscal_year_days <= 380:
        issues.append(
            AvailabilityIssue(
                "FISCAL_YEAR_LENGTH_UNSUPPORTED",
                f"Fiscal year length {fiscal_year_days} days is outside the accepted annual range.",
                definition.inputs,
            )
        )
    return tuple(issues)


def _denominator_metric(metric_id: str) -> str:
    return {
        "gross_margin": "revenue",
        "operating_margin": "revenue",
        "net_margin": "revenue",
        "ebitda_margin": "revenue",
        "return_on_assets": "total_assets",
        "return_on_equity": "shareholders_equity",
        "equity_ratio": "total_assets",
        "debt_to_assets": "total_assets",
        "debt_to_equity": "shareholders_equity",
        "net_debt_to_ebitda": "ebitda",
        "current_ratio": "current_liabilities",
        "quick_ratio": "current_liabilities",
        "cash_ratio": "current_liabilities",
        "operating_cash_flow_margin": "revenue",
        "capex_ratio": "operating_cash_flow",
        "free_cash_flow_margin": "revenue",
        "working_capital_to_revenue": "revenue",
        "receivables_days": "revenue",
        "payables_days": "revenue",
        "inventory_intensity": "total_assets",
        "inventory_days": "revenue",
    }[metric_id]
