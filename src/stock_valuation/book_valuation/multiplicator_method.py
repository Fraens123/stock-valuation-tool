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
    base_pe: Decimal | None,
    financial_stability_addon: Decimal | None,
    porter_scores: dict[str, Decimal],
    market_position_addon: Decimal | None,
    profitability_multiplier: Decimal | None,
    growth_addon: Decimal | None,
    individuality_addon: Decimal | None,
    forecast_net_income: Decimal | None,
    shares_outstanding: Decimal | None,
) -> MultiplicatorMethodResult:
    base = unavailable("base_pe", "multiple", ("MISSING_BASE_PE",)) if base_pe is None else available("base_pe", base_pe, "multiple", ("manual:base_pe",))
    stability = unavailable("financial_stability_addon", "multiple_points", ("MISSING_FINANCIAL_STABILITY_ADDON",)) if financial_stability_addon is None else available("financial_stability_addon", financial_stability_addon, "multiple_points", ("manual:financial_stability_addon",))
    missing_porter = tuple(key for key in PORTER_KEYS if key not in porter_scores)
    if missing_porter:
        porter_points = unavailable("market_position_points", "points", tuple(f"MISSING_{key.upper()}" for key in missing_porter))
    else:
        porter_points = available("market_position_points", sum(porter_scores.values(), Decimal("0")), "points", tuple(f"manual:{key}" for key in PORTER_KEYS))
    market_addon = unavailable("market_position_addon", "multiple_points", ("MISSING_MARKET_POSITION_ADDON",)) if market_position_addon is None else available("market_position_addon", market_position_addon, "multiple_points", ("manual:market_position_addon",))
    profitability = unavailable("profitability_multiplier", "factor", ("MISSING_PROFITABILITY_MULTIPLIER",)) if profitability_multiplier is None else available("profitability_multiplier", profitability_multiplier, "factor", ("manual:profitability_multiplier",))
    if market_addon.value is None or profitability.value is None:
        combined = unavailable("market_profitability_addon", "multiple_points", ("MISSING_MARKET_OR_PROFITABILITY_INPUT",))
    else:
        combined = available("market_profitability_addon", market_addon.value * profitability.value, "multiple_points", market_addon.input_refs + profitability.input_refs)
    growth = unavailable("growth_addon", "multiple_points", ("MISSING_GROWTH_ADDON",)) if growth_addon is None else available("growth_addon", growth_addon, "multiple_points", ("manual:growth_addon",))
    individuality = unavailable("individuality_addon", "multiple_points", ("MISSING_INDIVIDUALITY_ADDON",)) if individuality_addon is None else available("individuality_addon", individuality_addon, "multiple_points", ("manual:individuality_addon",))
    if (
        base.value is None
        or stability.value is None
        or combined.value is None
        or growth.value is None
        or individuality.value is None
    ):
        issues = base.issues + stability.issues + combined.issues + growth.issues + individuality.issues
        fair_pe = unavailable("fair_pe", "multiple", issues or ("MISSING_FAIR_PE_COMPONENT",))
    else:
        fair_pe = available("fair_pe", base.value + stability.value + combined.value + growth.value + individuality.value, "multiple", base.input_refs + stability.input_refs + combined.input_refs + growth.input_refs + individuality.input_refs)
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
