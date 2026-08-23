from __future__ import annotations

from decimal import Decimal

from stock_valuation.book_valuation.models import MultiplicatorMethodResult, available, unavailable


PORTER_KEYS = (
    "rivalry_existing_competitors",
    "threat_new_entrants",
    "supplier_power",
    "buyer_power",
    "threat_substitutes",
)


def fair_pe_from_components(
    *,
    base_pe: Decimal,
    financial_stability_addon: Decimal,
    porter_scores: dict[str, Decimal],
    market_position_addon: Decimal,
    profitability_multiplier: Decimal,
    growth_addon: Decimal,
    individuality_addon: Decimal,
    forecast_net_income: Decimal | None,
    shares_outstanding: Decimal | None,
) -> MultiplicatorMethodResult:
    base = available("base_pe", base_pe, "multiple", ("manual:base_pe",))
    stability = available("financial_stability_addon", financial_stability_addon, "multiple_points", ("manual:financial_stability_addon",))
    missing_porter = tuple(key for key in PORTER_KEYS if key not in porter_scores)
    if missing_porter:
        porter_points = unavailable("market_position_points", "points", tuple(f"MISSING_{key.upper()}" for key in missing_porter))
    else:
        porter_points = available("market_position_points", sum(porter_scores.values(), Decimal("0")), "points", tuple(f"manual:{key}" for key in PORTER_KEYS))
    market_addon = available("market_position_addon", market_position_addon, "multiple_points", ("manual:market_position_addon",))
    profitability = available("profitability_multiplier", profitability_multiplier, "factor", ("manual:profitability_multiplier",))
    if market_addon.value is None or profitability.value is None:
        combined = unavailable("market_profitability_addon", "multiple_points", ("MISSING_MARKET_OR_PROFITABILITY_INPUT",))
    else:
        combined = available("market_profitability_addon", market_addon.value * profitability.value, "multiple_points", market_addon.input_refs + profitability.input_refs)
    growth = available("growth_addon", growth_addon, "multiple_points", ("manual:growth_addon",))
    individuality = available("individuality_addon", individuality_addon, "multiple_points", ("manual:individuality_addon",))
    if combined.value is None:
        fair_pe = unavailable("fair_pe", "multiple", ("MISSING_MARKET_PROFITABILITY_ADDON",))
    else:
        fair_pe = available("fair_pe", base_pe + financial_stability_addon + combined.value + growth_addon + individuality_addon, "multiple", base.input_refs + stability.input_refs + combined.input_refs + growth.input_refs + individuality.input_refs)
    forecast = unavailable("forecast_net_income", "currency", ("MISSING_FORECAST_NET_INCOME",)) if forecast_net_income is None else available("forecast_net_income", forecast_net_income, "currency", ("estimate:annual_net_income",))
    shares = unavailable("shares_outstanding", "shares", ("MISSING_SHARES_OUTSTANDING",)) if shares_outstanding is None or shares_outstanding <= 0 else available("shares_outstanding", shares_outstanding, "shares", ("market:shares_outstanding",))
    if forecast.value is None or shares.value is None:
        eps = unavailable("forecast_eps", "currency_per_share", ("MISSING_FORECAST_NET_INCOME_OR_SHARES",), forecast.input_refs + shares.input_refs)
    else:
        eps = available("forecast_eps", forecast.value / shares.value, "currency_per_share", forecast.input_refs + shares.input_refs)
    if fair_pe.value is None or eps.value is None:
        price = unavailable("multiplicator_fair_price_per_share", "currency_per_share", ("MISSING_FAIR_PE_OR_FORECAST_EPS",), fair_pe.input_refs + eps.input_refs)
    else:
        price = available("multiplicator_fair_price_per_share", fair_pe.value * eps.value, "currency_per_share", fair_pe.input_refs + eps.input_refs)
    return MultiplicatorMethodResult(base, stability, porter_points, market_addon, profitability, combined, growth, individuality, fair_pe, forecast, shares, eps, price)
