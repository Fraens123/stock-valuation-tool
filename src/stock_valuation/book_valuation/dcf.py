from __future__ import annotations

from decimal import Decimal

from stock_valuation.book_valuation.models import (
    AVAILABLE,
    FairValueResult,
    PresentValueRow,
    TerminalValueResult,
    available,
    unavailable,
)


def present_value_owner_earnings(owner_earnings_values: tuple[Decimal, ...], discount_rate: Decimal) -> tuple[PresentValueRow, ...]:
    rows = []
    for index, value in enumerate(owner_earnings_values, start=1):
        factor = (Decimal("1") + discount_rate) ** index
        rows.append(
            PresentValueRow(
                index,
                available("owner_earnings", value, "currency", (f"forecast:owner_earnings:{index}",)),
                available("discount_factor", factor, "factor", (f"discount_rate:{discount_rate}",)),
                available("present_value_owner_earnings", value / factor, "currency", (f"forecast:owner_earnings:{index}", f"discount_rate:{discount_rate}")),
            )
        )
    return tuple(rows)


def terminal_value(last_owner_earnings: Decimal | None, discount_rate: Decimal | None, terminal_growth_rate: Decimal | None, projection_years: int) -> TerminalValueResult:
    growth = unavailable("terminal_growth_rate", "decimal_ratio", ("MISSING_TERMINAL_GROWTH_RATE",)) if terminal_growth_rate is None else available("terminal_growth_rate", terminal_growth_rate, "decimal_ratio", ("assumption:terminal_growth_rate",))
    if last_owner_earnings is None:
        terminal = unavailable("terminal_value", "currency", ("MISSING_LAST_OWNER_EARNINGS",))
        pv = unavailable("present_value_terminal_value", "currency", ("MISSING_TERMINAL_VALUE",))
        return TerminalValueResult(growth, terminal, pv)
    if discount_rate is None:
        terminal = unavailable("terminal_value", "currency", ("MISSING_DISCOUNT_RATE",))
        pv = unavailable("present_value_terminal_value", "currency", ("MISSING_DISCOUNT_RATE",))
        return TerminalValueResult(growth, terminal, pv)
    if terminal_growth_rate is None:
        terminal = unavailable("terminal_value", "currency", ("MISSING_TERMINAL_GROWTH_RATE",))
        pv = unavailable("present_value_terminal_value", "currency", ("MISSING_TERMINAL_GROWTH_RATE",))
        return TerminalValueResult(growth, terminal, pv)
    if terminal_growth_rate >= discount_rate:
        terminal = unavailable("terminal_value", "currency", ("TERMINAL_GROWTH_NOT_BELOW_DISCOUNT_RATE",))
        pv = unavailable("present_value_terminal_value", "currency", ("TERMINAL_GROWTH_NOT_BELOW_DISCOUNT_RATE",))
        return TerminalValueResult(growth, terminal, pv)
    value = last_owner_earnings * (Decimal("1") + terminal_growth_rate) / (discount_rate - terminal_growth_rate)
    terminal = available("terminal_value", value, "currency", ("forecast:last_owner_earnings", "assumption:discount_rate", "assumption:terminal_growth_rate"))
    pv = available("present_value_terminal_value", value / ((Decimal("1") + discount_rate) ** projection_years), "currency", terminal.input_refs, terminal.inputs_hash)
    return TerminalValueResult(growth, terminal, pv)


def fair_value(
    *,
    present_value_rows: tuple[PresentValueRow, ...],
    present_value_terminal_value: Decimal | None,
    shares_outstanding: Decimal | None,
    margin_of_safety: Decimal | None,
    market_price: Decimal | None,
) -> FairValueResult:
    pv_sum = sum((row.present_value.value or Decimal("0")) for row in present_value_rows if row.present_value.status == AVAILABLE)
    pv_sum_value = available("present_value_owner_earnings_sum", pv_sum, "currency", tuple(ref for row in present_value_rows for ref in row.present_value.input_refs))
    pv_terminal = unavailable("present_value_terminal_value", "currency", ("MISSING_PRESENT_VALUE_TERMINAL_VALUE",)) if present_value_terminal_value is None else available("present_value_terminal_value", present_value_terminal_value, "currency", ("terminal_value:present_value",))
    shares = unavailable("shares_outstanding", "shares", ("MISSING_SHARES_OUTSTANDING",)) if shares_outstanding is None or shares_outstanding <= 0 else available("shares_outstanding", shares_outstanding, "shares", ("market:shares_outstanding",))
    safety = unavailable("margin_of_safety", "decimal_ratio", ("MISSING_MARGIN_OF_SAFETY",)) if margin_of_safety is None else available("margin_of_safety", margin_of_safety, "decimal_ratio", ("manual:margin_of_safety",))
    price = unavailable("market_price", "currency", ("MISSING_MARKET_PRICE",)) if market_price is None else available("market_price", market_price, "currency", ("market:price",))
    if pv_terminal.status != AVAILABLE or pv_terminal.value is None:
        equity = unavailable("equity_value", "currency", pv_terminal.issues, pv_terminal.input_refs)
    else:
        equity = available("equity_value", pv_sum + pv_terminal.value, "currency", pv_sum_value.input_refs + pv_terminal.input_refs)
    if equity.status != AVAILABLE or equity.value is None or shares.status != AVAILABLE or shares.value is None:
        fair = unavailable("fair_value_per_share", "currency_per_share", ("MISSING_EQUITY_VALUE_OR_SHARES",), equity.input_refs + shares.input_refs)
        safe = unavailable("fair_value_after_safety_margin", "currency_per_share", ("MISSING_FAIR_VALUE_PER_SHARE",), fair.input_refs)
    else:
        fair = available("fair_value_per_share", equity.value / shares.value, "currency_per_share", equity.input_refs + shares.input_refs)
        if safety.value is None:
            safe = unavailable("fair_value_after_safety_margin", "currency_per_share", ("MISSING_MARGIN_OF_SAFETY",), fair.input_refs + safety.input_refs)
        else:
            safe = available("fair_value_after_safety_margin", fair.value * (Decimal("1") - safety.value), "currency_per_share", fair.input_refs + safety.input_refs)
    if safe.status == AVAILABLE and safe.value is not None and price.status == AVAILABLE and price.value is not None and price.value > 0:
        gap = available("valuation_gap", Decimal("1") - (safe.value / price.value), "decimal_ratio", safe.input_refs + price.input_refs)
    else:
        gap = unavailable("valuation_gap", "decimal_ratio", ("MISSING_FAIR_VALUE_OR_MARKET_PRICE",), safe.input_refs + price.input_refs)
    return FairValueResult(shares, pv_sum_value, pv_terminal, equity, fair, safety, safe, price, gap)
