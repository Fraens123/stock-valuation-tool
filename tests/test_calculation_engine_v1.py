from __future__ import annotations

from decimal import Decimal

from stock_valuation.metrics.calculation_engine import (
    NOT_SEPARATELY_REPORTED,
    CalculationInput,
    calculate_metrics_for_year,
)


def _fact(metric: str, value: str | None, *, currency: str = "USD", status: str = "PASS") -> CalculationInput:
    return CalculationInput(
        metric=metric,
        fiscal_year=2025,
        value=Decimal(value) if value is not None else None,
        currency=currency,
        source_status=status,
        provider="test_preferred",
        provider_field=metric,
        accession="test-accn",
        filing_date="2026-01-01",
    )


def _base() -> dict[str, CalculationInput]:
    return {
        "revenue": _fact("revenue", "100"),
        "gross_profit": _fact("gross_profit", "60"),
        "operating_income": _fact("operating_income", "25"),
        "net_income": _fact("net_income", "20"),
        "depreciation_amortization": _fact("depreciation_amortization", "5"),
        "total_assets": _fact("total_assets", "200"),
        "current_assets": _fact("current_assets", "80"),
        "cash_and_equivalents": _fact("cash_and_equivalents", "30"),
        "accounts_receivable": _fact("accounts_receivable", "10"),
        "inventory": _fact("inventory", "15"),
        "ppe_net": _fact("ppe_net", "70"),
        "total_liabilities": _fact("total_liabilities", "90"),
        "current_liabilities": _fact("current_liabilities", "40"),
        "accounts_payable": _fact("accounts_payable", "8"),
        "short_term_debt": _fact("short_term_debt", "10"),
        "long_term_debt": _fact("long_term_debt", "50"),
        "shareholders_equity": _fact("shareholders_equity", "110"),
        "operating_cash_flow": _fact("operating_cash_flow", "35"),
        "capital_expenditures": _fact("capital_expenditures", "12"),
    }


def _by_id(results):
    return {result.metric_id: result for result in results}


def test_v1_formulas_use_decimal_ratios_not_percent_values() -> None:
    results = _by_id(calculate_metrics_for_year(_base(), 2025))

    assert results["gross_margin"].value == Decimal("0.6")
    assert results["operating_margin"].value == Decimal("0.25")
    assert results["ebitda"].value == Decimal("30")
    assert results["ebitda_margin"].value == Decimal("0.3")
    assert results["free_cash_flow"].value == Decimal("23")


def test_division_by_zero_makes_metric_unavailable() -> None:
    facts = _base()
    facts["revenue"] = _fact("revenue", "0")

    results = _by_id(calculate_metrics_for_year(facts, 2025))

    assert results["gross_margin"].status == "UNAVAILABLE"
    assert results["gross_margin"].issues[0].code == "DIVISION_BY_ZERO"


def test_negative_values_are_preserved_when_economic() -> None:
    facts = _base()
    facts["net_income"] = _fact("net_income", "-20")
    facts["cash_and_equivalents"] = _fact("cash_and_equivalents", "100")

    results = _by_id(calculate_metrics_for_year(facts, 2025))

    assert results["net_margin"].value == Decimal("-0.2")
    assert results["net_debt"].value == Decimal("-40")


def test_missing_inputs_do_not_create_values() -> None:
    facts = _base()
    del facts["accounts_receivable"]

    results = _by_id(calculate_metrics_for_year(facts, 2025))

    assert results["quick_ratio"].status == "UNAVAILABLE"
    assert results["quick_ratio"].issues[0].code == "MISSING_INPUT"


def test_not_separately_reported_inventory_is_not_zero() -> None:
    facts = _base()
    facts["inventory"] = _fact("inventory", None, status=NOT_SEPARATELY_REPORTED)

    results = _by_id(calculate_metrics_for_year(facts, 2025))

    assert results["inventory_intensity"].status == "UNAVAILABLE"
    assert results["inventory_intensity"].issues[0].code == NOT_SEPARATELY_REPORTED
    assert results["current_ratio"].status == "AVAILABLE"


def test_currency_mismatch_blocks_currency_based_ratios() -> None:
    facts = _base()
    facts["gross_profit"] = _fact("gross_profit", "60", currency="EUR")

    results = _by_id(calculate_metrics_for_year(facts, 2025))

    assert results["gross_margin"].status == "UNAVAILABLE"
    assert results["gross_margin"].issues[0].code == "CURRENCY_MISMATCH"


def test_days_metrics_reject_non_annual_period_length() -> None:
    results = _by_id(calculate_metrics_for_year(_base(), 2025, fiscal_year_days=200))

    assert results["receivables_days"].status == "UNAVAILABLE"
    assert results["receivables_days"].issues[0].code == "FISCAL_YEAR_LENGTH_UNSUPPORTED"


def test_derived_results_retain_input_provenance_and_hash() -> None:
    results = _by_id(calculate_metrics_for_year(_base(), 2025))

    ebitda_margin = results["ebitda_margin"]
    assert ebitda_margin.inputs_hash
    assert {item.metric for item in ebitda_margin.input_provenance} == {
        "operating_income",
        "depreciation_amortization",
        "revenue",
    }
