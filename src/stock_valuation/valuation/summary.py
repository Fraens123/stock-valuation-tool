from __future__ import annotations

from decimal import Decimal

from stock_valuation.valuation.multiples import convert_financial_to_trading
from stock_valuation.valuation.models import (
    ADR_RATIO_REQUIRED,
    AVAILABLE,
    INVALID_SHARE_COUNT,
    UNAVAILABLE,
    DCFResult,
    MarketSnapshotInput,
    ValuationSummary,
    stable_hash,
)


def dcf_summary(dcf_result: DCFResult, market: MarketSnapshotInput) -> ValuationSummary:
    issues = list(dcf_result.issues)
    if dcf_result.equity_value is None or dcf_result.status != AVAILABLE:
        return _summary(dcf_result, market, None, UNAVAILABLE, issues)
    equity_value, fx_issue = convert_financial_to_trading(dcf_result.equity_value, dcf_result.currency, market)
    if fx_issue:
        issues.append(fx_issue)
    units, unit_issue = listed_equivalent_units(market)
    if unit_issue:
        issues.append(unit_issue)
    if equity_value is None or units is None or issues:
        return _summary(dcf_result, market, None, UNAVAILABLE, issues)
    fair_value = equity_value / units
    return _summary(dcf_result, market, fair_value, AVAILABLE, issues)


def listed_equivalent_units(market: MarketSnapshotInput) -> tuple[Decimal | None, str | None]:
    if market.shares_outstanding is None or market.shares_outstanding <= 0:
        return None, INVALID_SHARE_COUNT
    security = market.security_type.upper()
    if security in {"ADR", "ADS"} and market.share_basis == "ORDINARY_SHARES":
        if not market.adr_ratio or not market.underlying_share_ratio or market.underlying_share_ratio == 0:
            return None, ADR_RATIO_REQUIRED
        return market.shares_outstanding * market.adr_ratio / market.underlying_share_ratio, None
    return market.shares_outstanding, None


def _summary(dcf_result: DCFResult, market: MarketSnapshotInput, fair_value, status, issues):
    upside = None
    mos = None
    if fair_value is not None and market.price is not None and market.price > 0:
        upside = fair_value / market.price - Decimal("1")
        mos = Decimal("1") - market.price / fair_value if fair_value > 0 else None
    return ValuationSummary(
        ticker=market.ticker,
        company=market.company,
        scenario=dcf_result.scenario,
        status=status,
        fair_value_per_unit=fair_value,
        trading_currency=market.trading_currency,
        market_price=market.price,
        upside_downside=upside,
        margin_of_safety=mos,
        issues=tuple(issues),
        input_refs=tuple(market.input_refs) + tuple(dcf_result.input_refs),
        inputs_hash=stable_hash((market.inputs_hash, dcf_result.inputs_hash)),
    )
