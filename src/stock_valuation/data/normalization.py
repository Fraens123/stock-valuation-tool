from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from stock_valuation.data.mapping import load_provider_mapping
from stock_valuation.data.types import NormalizedEstimate, NormalizedFinancialFact, ProviderCompany


_STATEMENT_PAYLOAD_KEYS = {
    "income_statement": "Income_Statement",
    "balance_sheet": "Balance_Sheet",
    "cash_flow": "Cash_Flow",
}


def _decimal(value: Any) -> Decimal | None:
    if value in (None, "", "None", "null"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _first_present(row: dict[str, Any], field: str, fallbacks: Iterable[str]) -> tuple[str, Any]:
    if row.get(field) not in (None, ""):
        return field, row[field]
    for candidate in fallbacks:
        if row.get(candidate) not in (None, ""):
            return candidate, row[candidate]
    return field, None


def _apply_sign_policy(value: Decimal | None, policy: str | None) -> Decimal | None:
    if value is None:
        return None
    if policy == "outflow_magnitude":
        return abs(value)
    return value


def normalize_eodhd_company(payload: dict[str, Any]) -> ProviderCompany:
    general = payload.get("General") or {}
    code = str(general.get("Code") or "").strip()
    exchange = str(general.get("Exchange") or "").strip() or None
    provider_symbol = f"{code}.{exchange}" if code and exchange else code
    return ProviderCompany(
        name=str(general.get("Name") or code),
        ticker=code,
        provider_symbol=provider_symbol,
        exchange=exchange,
        country=general.get("CountryName"),
        currency=general.get("CurrencyCode"),
        isin=general.get("ISIN"),
        sector=general.get("Sector"),
        industry=general.get("Industry"),
    )


def normalize_eodhd_financials(
    payload: dict[str, Any],
    *,
    period_type: str = "FY",
    retrieved_at: datetime | None = None,
) -> list[NormalizedFinancialFact]:
    """Normalize EODHD financial statement data to internal keys.

    This function performs only field mapping and documented sign normalization.
    It does not calculate financial ratios or silently invent missing values.
    """
    retrieved_at = retrieved_at or datetime.now(timezone.utc)
    mapping = load_provider_mapping("eodhd")
    financials = payload.get("Financials") or {}
    period_key = "yearly" if period_type == "FY" else "quarterly"
    output: list[NormalizedFinancialFact] = []

    for statement, payload_key in _STATEMENT_PAYLOAD_KEYS.items():
        block = financials.get(payload_key) or {}
        currency = block.get("currency_symbol")
        rows = block.get(period_key) or {}
        specs = mapping.get(statement, {})

        if isinstance(rows, list):
            iterable = enumerate(rows)
        else:
            iterable = rows.items()

        for _, row in iterable:
            if not isinstance(row, dict):
                continue
            period_end = _date(row.get("date"))
            if period_end is None:
                continue
            filing_date = _date(row.get("filing_date"))

            for metric, spec in specs.items():
                provider_field, raw = _first_present(
                    row,
                    spec["field"],
                    spec.get("fallback_fields", []),
                )
                provider_value = _decimal(raw)
                value = _apply_sign_policy(provider_value, spec.get("sign_policy"))
                output.append(
                    NormalizedFinancialFact(
                        statement=statement,
                        metric=metric,
                        period_end=period_end,
                        period_type=period_type,
                        value=value,
                        provider_value=provider_value,
                        currency=currency,
                        unit=spec.get("unit", "currency"),
                        provider="eodhd",
                        provider_field=provider_field,
                        filing_date=filing_date,
                        retrieved_at=retrieved_at,
                        is_cross_check_only=bool(spec.get("cross_check_only", False)),
                        note="optional provider field" if spec.get("optional") else None,
                    )
                )

    return output


def _estimate_count(row: dict[str, Any], metric: str) -> int | None:
    candidates = (
        ["revenueEstimateNumberOfAnalysts", "revenueAnalystCount", "numberOfAnalysts"]
        if metric == "revenue"
        else ["earningsEstimateNumberOfAnalysts", "epsAnalystCount", "numberOfAnalysts"]
    )
    for key in candidates:
        raw = row.get(key)
        if raw not in (None, ""):
            try:
                return int(raw)
            except (TypeError, ValueError):
                pass
    return None


def normalize_eodhd_estimates(
    payload: dict[str, Any], *, retrieved_at: datetime | None = None
) -> list[NormalizedEstimate]:
    """Normalize annual EODHD Earnings Trend estimates.

    v1.1 splits Trend into Annual and Quarterly. The parser tolerates the legacy flat
    structure for testability, but production requests use v1.1.
    """
    retrieved_at = retrieved_at or datetime.now(timezone.utc)
    earnings = payload.get("Earnings") or {}
    trend = earnings.get("Trend") or {}
    annual = trend.get("Annual") if isinstance(trend, dict) else None
    rows = annual if isinstance(annual, (dict, list)) else trend

    if isinstance(rows, list):
        iterable = enumerate(rows)
    elif isinstance(rows, dict):
        iterable = rows.items()
    else:
        return []

    general_currency = (payload.get("General") or {}).get("CurrencyCode")
    estimates: list[NormalizedEstimate] = []

    for key, row in iterable:
        if not isinstance(row, dict):
            continue
        period = str(row.get("date") or row.get("period") or key)

        eps_avg = _decimal(row.get("earningsEstimateAvg"))
        eps_low = _decimal(row.get("earningsEstimateLow"))
        eps_high = _decimal(row.get("earningsEstimateHigh"))
        if any(value is not None for value in (eps_avg, eps_low, eps_high)):
            estimates.append(
                NormalizedEstimate(
                    metric="eps",
                    period=period,
                    low=eps_low,
                    average=eps_avg,
                    high=eps_high,
                    analyst_count=_estimate_count(row, "eps"),
                    provider="eodhd",
                    currency=general_currency,
                    unit="currency_per_share",
                    retrieved_at=retrieved_at,
                )
            )

        revenue_avg = _decimal(row.get("revenueEstimateAvg"))
        revenue_low = _decimal(row.get("revenueEstimateLow"))
        revenue_high = _decimal(row.get("revenueEstimateHigh"))
        if any(value is not None for value in (revenue_avg, revenue_low, revenue_high)):
            estimates.append(
                NormalizedEstimate(
                    metric="revenue",
                    period=period,
                    low=revenue_low,
                    average=revenue_avg,
                    high=revenue_high,
                    analyst_count=_estimate_count(row, "revenue"),
                    provider="eodhd",
                    currency=general_currency,
                    unit="currency",
                    retrieved_at=retrieved_at,
                )
            )

    return estimates
