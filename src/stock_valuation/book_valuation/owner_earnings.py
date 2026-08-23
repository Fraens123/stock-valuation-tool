from __future__ import annotations

from decimal import Decimal

from stock_valuation.book_valuation.models import (
    AVAILABLE,
    BookValue,
    OwnerEarningsYear,
    available,
    stable_hash,
    unavailable,
)


def operating_working_capital(
    *,
    inventory: BookValue,
    accounts_receivable: BookValue,
    accounts_payable: BookValue,
) -> BookValue:
    refs = inventory.input_refs + accounts_receivable.input_refs + accounts_payable.input_refs
    issues = []
    for item in (inventory, accounts_receivable, accounts_payable):
        if item.status != AVAILABLE or item.value is None:
            issues.append(f"MISSING_{item.key.upper()}")
    if issues:
        return unavailable("operating_working_capital", "currency", tuple(issues), refs)
    assert inventory.value is not None and accounts_receivable.value is not None and accounts_payable.value is not None
    return available(
        "operating_working_capital",
        inventory.value + accounts_receivable.value - accounts_payable.value,
        "currency",
        refs,
        inventory.inputs_hash,
        accounts_receivable.inputs_hash,
        accounts_payable.inputs_hash,
    )


def change_in_operating_working_capital(current: BookValue, previous: BookValue) -> BookValue:
    refs = current.input_refs + previous.input_refs
    if current.status != AVAILABLE or current.value is None:
        return unavailable("change_in_operating_working_capital", "currency", ("MISSING_CURRENT_OPERATING_WORKING_CAPITAL",), refs)
    if previous.status != AVAILABLE or previous.value is None:
        return unavailable("change_in_operating_working_capital", "currency", ("MISSING_PREVIOUS_OPERATING_WORKING_CAPITAL",), refs)
    return available(
        "change_in_operating_working_capital",
        current.value - previous.value,
        "currency",
        refs,
        current.inputs_hash,
        previous.inputs_hash,
    )


def owner_earnings_capex(*, capital_expenditures: BookValue, intangible_purchases: BookValue | None = None) -> BookValue:
    refs = capital_expenditures.input_refs + (intangible_purchases.input_refs if intangible_purchases else ())
    issues = []
    if capital_expenditures.status != AVAILABLE or capital_expenditures.value is None:
        issues.append("MISSING_CAPITAL_EXPENDITURES")
    if intangible_purchases is None or intangible_purchases.status != AVAILABLE or intangible_purchases.value is None:
        issues.append("MISSING_INTANGIBLE_PURCHASES")
    if issues:
        return unavailable("owner_earnings_capex", "currency", tuple(issues), refs)
    assert intangible_purchases is not None and capital_expenditures.value is not None and intangible_purchases.value is not None
    return available(
        "owner_earnings_capex",
        capital_expenditures.value + intangible_purchases.value,
        "currency",
        refs,
        capital_expenditures.inputs_hash,
        intangible_purchases.inputs_hash,
    )


def owner_earnings(
    *,
    net_income: BookValue,
    depreciation_amortization: BookValue,
    capex: BookValue,
    change_in_owc: BookValue,
) -> BookValue:
    refs = net_income.input_refs + depreciation_amortization.input_refs + capex.input_refs + change_in_owc.input_refs
    issues = []
    for item in (net_income, depreciation_amortization, capex, change_in_owc):
        if item.status != AVAILABLE or item.value is None:
            issues.append(f"MISSING_{item.key.upper()}")
    if issues:
        return unavailable("owner_earnings", "currency", tuple(issues), refs)
    assert net_income.value is not None and depreciation_amortization.value is not None and capex.value is not None and change_in_owc.value is not None
    return available(
        "owner_earnings",
        net_income.value + depreciation_amortization.value - capex.value - change_in_owc.value,
        "currency",
        refs,
        net_income.inputs_hash,
        depreciation_amortization.inputs_hash,
        capex.inputs_hash,
        change_in_owc.inputs_hash,
    )


def ratio(key: str, numerator: BookValue, denominator: BookValue) -> BookValue:
    refs = numerator.input_refs + denominator.input_refs
    if numerator.status != AVAILABLE or numerator.value is None:
        return unavailable(key, "decimal_ratio", (f"MISSING_{numerator.key.upper()}",), refs)
    if denominator.status != AVAILABLE or denominator.value is None:
        return unavailable(key, "decimal_ratio", (f"MISSING_{denominator.key.upper()}",), refs)
    if denominator.value == 0:
        return unavailable(key, "decimal_ratio", ("DENOMINATOR_ZERO",), refs)
    return available(key, numerator.value / denominator.value, "decimal_ratio", refs, numerator.inputs_hash, denominator.inputs_hash)


def point(key: str, fiscal_year: int, value: Decimal | None, currency: str | None = None, status: str = AVAILABLE) -> BookValue:
    if value is None or status != AVAILABLE:
        return unavailable(key, "currency", (f"MISSING_{key.upper()}",), (f"financial_fact:{key}:{fiscal_year}",))
    return BookValue(key, value, "currency", AVAILABLE, (), (f"financial_fact:{key}:{fiscal_year}",), stable_hash((key, fiscal_year, value, currency)))
