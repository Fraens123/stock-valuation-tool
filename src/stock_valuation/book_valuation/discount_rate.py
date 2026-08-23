from __future__ import annotations

from decimal import Decimal

from stock_valuation.book_valuation.models import AVAILABLE, DiscountRateResult, available, unavailable


def excel_book_discount_rate(
    *,
    fair_pe: Decimal | None,
    risk_free_rate: Decimal | None,
    minimum_return: Decimal = Decimal("0.07"),
) -> DiscountRateResult:
    fair_pe_value = unavailable("fair_pe", "multiple", ("MISSING_FAIR_PE",)) if fair_pe is None else available("fair_pe", fair_pe, "multiple", ("manual_or_multiplicator:fair_pe",))
    risk_free = unavailable("risk_free_rate", "decimal_ratio", ("MISSING_RISK_FREE_RATE",)) if risk_free_rate is None else available("risk_free_rate", risk_free_rate, "decimal_ratio", ("market:aaa_10y_rate",))
    if fair_pe is None or fair_pe <= 0:
        risk_premium = unavailable("risk_premium", "decimal_ratio", ("FAIR_PE_NOT_POSITIVE",), fair_pe_value.input_refs)
    else:
        risk_premium = available("risk_premium", Decimal("1") / fair_pe, "decimal_ratio", fair_pe_value.input_refs, fair_pe_value.inputs_hash)
    if risk_premium.status != AVAILABLE or risk_premium.value is None or risk_free.status != AVAILABLE or risk_free.value is None:
        addon = unavailable("minimum_return_addon", "decimal_ratio", ("MISSING_DISCOUNT_INPUT",), risk_premium.input_refs + risk_free.input_refs)
        cost = unavailable("cost_of_equity", "decimal_ratio", ("MISSING_DISCOUNT_INPUT",), risk_premium.input_refs + risk_free.input_refs)
        return DiscountRateResult(fair_pe_value, risk_premium, risk_free, addon, cost)
    raw_cost = risk_premium.value + risk_free.value
    addon_value = max(Decimal("0"), minimum_return - raw_cost)
    addon = available("minimum_return_addon", addon_value, "decimal_ratio", risk_premium.input_refs + risk_free.input_refs, minimum_return)
    cost = available("cost_of_equity", raw_cost + addon_value, "decimal_ratio", risk_premium.input_refs + risk_free.input_refs + addon.input_refs, risk_premium.inputs_hash, risk_free.inputs_hash, addon.inputs_hash)
    return DiscountRateResult(fair_pe_value, risk_premium, risk_free, addon, cost)
