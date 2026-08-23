from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal

from stock_valuation.market.models import (
    ADR_RATIO_REQUIRED,
    AVAILABLE,
    CURRENCY_MATCH,
    DATE_MISMATCH,
    FX_REQUIRED,
    FX_UNAVAILABLE,
    INVALID_SHARE_COUNT,
    MISSING_PRICE,
    STALE,
    UNAVAILABLE,
    VALUATION_NOT_READY,
    DerivedMarketMetric,
    MarketDataSnapshot,
)


def derive_market_metrics(
    snapshot: MarketDataSnapshot,
    *,
    max_stale_days: int = 5,
) -> tuple[DerivedMarketMetric, ...]:
    market_cap = calculate_market_cap(snapshot, max_stale_days=max_stale_days)
    enterprise_value = calculate_enterprise_value(snapshot, market_cap)
    return market_cap, enterprise_value


def calculate_market_cap(
    snapshot: MarketDataSnapshot,
    *,
    max_stale_days: int = 5,
) -> DerivedMarketMetric:
    issues = _base_issues(snapshot, max_stale_days=max_stale_days)
    refs = _base_refs(snapshot)
    if issues:
        return _metric("market_cap", None, snapshot.quote.listing_currency, issues[0], tuple(issues), refs)

    factor = _adr_conversion_factor(snapshot)
    assert factor is not None
    assert snapshot.quote.price is not None
    assert snapshot.share_data.shares_outstanding is not None
    value = snapshot.quote.price * snapshot.share_data.shares_outstanding * factor
    return _metric(
        "market_cap",
        value,
        snapshot.quote.listing_currency,
        AVAILABLE,
        (CURRENCY_MATCH if snapshot.quote.listing_currency == snapshot.financial_statement_currency else FX_REQUIRED,),
        refs,
    )


def calculate_enterprise_value(
    snapshot: MarketDataSnapshot,
    market_cap: DerivedMarketMetric,
) -> DerivedMarketMetric:
    refs = (*market_cap.input_refs, _net_debt_ref(snapshot))
    if market_cap.value is None or market_cap.status != AVAILABLE:
        return _metric("enterprise_value", None, market_cap.currency, market_cap.status, market_cap.issues, refs)
    if snapshot.net_debt is None or snapshot.net_debt.value is None:
        return _metric("enterprise_value", None, market_cap.currency, UNAVAILABLE, ("MISSING_NET_DEBT",), refs)
    if not snapshot.net_debt.currency:
        return _metric("enterprise_value", None, market_cap.currency, UNAVAILABLE, ("MISSING_NET_DEBT_CURRENCY",), refs)
    if snapshot.net_debt.currency == market_cap.currency:
        return _metric(
            "enterprise_value",
            market_cap.value + snapshot.net_debt.value,
            market_cap.currency,
            AVAILABLE,
            (CURRENCY_MATCH,),
            refs,
        )
    fx = snapshot.fx_rate
    if fx is None:
        return _metric("enterprise_value", None, market_cap.currency, FX_REQUIRED, (FX_REQUIRED,), refs)
    if fx.rate is None or fx.rate <= 0:
        return _metric("enterprise_value", None, market_cap.currency, FX_UNAVAILABLE, (FX_UNAVAILABLE,), refs)
    if fx.from_currency != snapshot.net_debt.currency or fx.to_currency != market_cap.currency:
        return _metric("enterprise_value", None, market_cap.currency, FX_UNAVAILABLE, ("FX_PAIR_MISMATCH",), refs)
    return _metric(
        "enterprise_value",
        market_cap.value + snapshot.net_debt.value * fx.rate,
        market_cap.currency,
        AVAILABLE,
        ("FX_APPLIED",),
        (*refs, _fx_ref(snapshot)),
    )


def _base_issues(snapshot: MarketDataSnapshot, *, max_stale_days: int) -> list[str]:
    issues: list[str] = []
    if snapshot.quote.price is None:
        issues.append(MISSING_PRICE)
    elif snapshot.quote.price <= 0:
        issues.append("INVALID_PRICE")
    if snapshot.quote.price_date is None:
        issues.append(DATE_MISMATCH)
    elif (snapshot.analysis_as_of_date - snapshot.quote.price_date).days > max_stale_days:
        issues.append(STALE)
    if snapshot.share_data.shares_outstanding is None or snapshot.share_data.shares_outstanding <= 0:
        issues.append(INVALID_SHARE_COUNT)
    if snapshot.listing.security_type.upper() in {"ADR", "ADS"} and _adr_conversion_factor(snapshot) is None:
        issues.extend([ADR_RATIO_REQUIRED, VALUATION_NOT_READY])
    return issues


def _adr_conversion_factor(snapshot: MarketDataSnapshot) -> Decimal | None:
    if snapshot.listing.security_type.upper() not in {"ADR", "ADS"}:
        return Decimal("1")
    if (
        snapshot.listing.adr_ratio is None
        or snapshot.listing.underlying_share_ratio is None
        or snapshot.listing.adr_ratio <= 0
        or snapshot.listing.underlying_share_ratio <= 0
    ):
        return None
    return snapshot.listing.adr_ratio / snapshot.listing.underlying_share_ratio


def _metric(
    metric_id: str,
    value: Decimal | None,
    currency: str | None,
    status: str,
    issues: tuple[str, ...],
    refs: tuple[str, ...],
) -> DerivedMarketMetric:
    return DerivedMarketMetric(
        metric_id=metric_id,
        value=value,
        currency=currency,
        status=status,
        issues=issues,
        input_refs=refs,
        inputs_hash=_hash_refs(refs),
    )


def _base_refs(snapshot: MarketDataSnapshot) -> tuple[str, ...]:
    quote = snapshot.quote
    shares = snapshot.share_data
    listing = snapshot.listing
    return (
        f"quote:{quote.provider}:{quote.provider_symbol}:{quote.price}:{quote.listing_currency}:{quote.price_date}",
        f"shares:{shares.provider}:{shares.provider_field or shares.source}:{shares.shares_outstanding}:{shares.share_date}:{shares.filing_date}",
        f"listing:{listing.provider or 'unknown'}:{listing.ticker}:{listing.exchange}:{listing.security_type}:{listing.adr_ratio}:{listing.underlying_share_ratio}",
        f"analysis_as_of:{snapshot.analysis_as_of_date}",
    )


def _net_debt_ref(snapshot: MarketDataSnapshot) -> str:
    if snapshot.net_debt is None:
        return "net_debt:missing"
    return (
        f"net_debt:{snapshot.net_debt.source}:{snapshot.net_debt.fiscal_year}:"
        f"{snapshot.net_debt.value}:{snapshot.net_debt.currency}:{snapshot.net_debt.inputs_hash or ''}"
    )


def _fx_ref(snapshot: MarketDataSnapshot) -> str:
    if snapshot.fx_rate is None:
        return "fx:missing"
    return (
        f"fx:{snapshot.fx_rate.provider or 'unknown'}:{snapshot.fx_rate.from_currency}:"
        f"{snapshot.fx_rate.to_currency}:{snapshot.fx_rate.rate}:{snapshot.fx_rate.fx_date}"
    )


def _hash_refs(refs: tuple[str, ...]) -> str:
    return hashlib.sha256("|".join(sorted(refs)).encode("utf-8")).hexdigest()
