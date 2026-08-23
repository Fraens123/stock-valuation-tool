from __future__ import annotations

from decimal import Decimal

from stock_valuation.valuation.models import (
    AVAILABLE,
    FX_REQUIRED,
    NOT_MEANINGFUL,
    UNAVAILABLE,
    FinancialPoint,
    MarketSnapshotInput,
    ValuationMetricResult,
    stable_hash,
)


def convert_financial_to_trading(
    value: Decimal, currency: str, market: MarketSnapshotInput
) -> tuple[Decimal | None, str | None]:
    if currency == market.trading_currency:
        return value, None
    if market.fx_rate is None:
        return None, FX_REQUIRED
    return value * market.fx_rate, None


def current_market_multiples(
    latest_points: dict[str, FinancialPoint],
    market: MarketSnapshotInput,
) -> tuple[ValuationMetricResult, ...]:
    specs = (
        ("latest_fy_pe", "market_cap", "net_income"),
        ("latest_fy_pb", "market_cap", "shareholders_equity"),
        ("latest_fy_p_ocf", "market_cap", "operating_cash_flow"),
        ("latest_fy_ev_ebit", "enterprise_value", "operating_income"),
        ("latest_fy_ev_ebitda", "enterprise_value", "ebitda"),
        ("latest_fy_ev_sales", "enterprise_value", "revenue"),
        ("latest_fy_ev_fcf", "enterprise_value", "entity_free_cash_flow_excel_book"),
        ("latest_fy_p_fcf", "market_cap", "free_cash_flow"),
    )
    results = [
        _multiple(metric_id, numerator, denominator, latest_points, market)
        for metric_id, numerator, denominator in specs
    ]
    results.append(_yield("earnings_yield", "net_income", latest_points, market))
    results.append(_yield("fcf_yield", "free_cash_flow", latest_points, market))
    return tuple(results)


def _multiple(
    metric_id: str,
    numerator_name: str,
    denominator_name: str,
    points: dict[str, FinancialPoint],
    market: MarketSnapshotInput,
) -> ValuationMetricResult:
    numerator = market.market_cap if numerator_name == "market_cap" else market.enterprise_value
    denominator_point = points.get(denominator_name)
    refs = list(market.input_refs)
    issues: list[str] = []
    if numerator is None:
        issues.append(f"MISSING_{numerator_name.upper()}")
    if denominator_point is None or denominator_point.value is None:
        issues.append(f"MISSING_{denominator_name.upper()}")
        return _result(metric_id, None, None, UNAVAILABLE, issues, refs, denominator_point, market)
    refs.append(denominator_point.input_ref)
    denominator, fx_issue = convert_financial_to_trading(
        denominator_point.value, denominator_point.currency, market
    )
    if fx_issue:
        issues.append(fx_issue)
    if denominator is not None and denominator <= 0:
        issues.append("DENOMINATOR_NOT_POSITIVE")
        return _result(
            metric_id, denominator_point.fiscal_year, None, NOT_MEANINGFUL, issues, refs, denominator_point, market
        )
    if numerator is None or denominator is None or issues:
        return _result(
            metric_id, denominator_point.fiscal_year, None, UNAVAILABLE, issues, refs, denominator_point, market
        )
    return _result(
        metric_id, denominator_point.fiscal_year, numerator / denominator, AVAILABLE, issues, refs, denominator_point, market
    )


def _yield(
    metric_id: str,
    denominator_name: str,
    points: dict[str, FinancialPoint],
    market: MarketSnapshotInput,
) -> ValuationMetricResult:
    denominator_point = points.get(denominator_name)
    refs = list(market.input_refs)
    issues: list[str] = []
    if market.market_cap is None or market.market_cap <= 0:
        issues.append("MARKET_CAP_NOT_POSITIVE")
    if denominator_point is None or denominator_point.value is None:
        issues.append(f"MISSING_{denominator_name.upper()}")
        return _result(metric_id, None, None, UNAVAILABLE, issues, refs, denominator_point, market)
    refs.append(denominator_point.input_ref)
    numerator, fx_issue = convert_financial_to_trading(denominator_point.value, denominator_point.currency, market)
    if fx_issue:
        issues.append(fx_issue)
    if numerator is None or market.market_cap is None or market.market_cap <= 0 or issues:
        return _result(
            metric_id, denominator_point.fiscal_year, None, UNAVAILABLE, issues, refs, denominator_point, market
        )
    return _result(
        metric_id, denominator_point.fiscal_year, numerator / market.market_cap, AVAILABLE, issues, refs, denominator_point, market
    )


def _result(metric_id, fiscal_year, value, status, issues, refs, point, market):
    hashes = [market.inputs_hash]
    if point is not None:
        hashes.append(point.inputs_hash)
    return ValuationMetricResult(
        metric_id=metric_id,
        fiscal_year=fiscal_year,
        method="current_market_multiples",
        value=value,
        unit="decimal_ratio",
        currency=None,
        status=status,
        issues=tuple(issues),
        input_refs=tuple(refs),
        inputs_hash=stable_hash(tuple(hashes)),
    )
