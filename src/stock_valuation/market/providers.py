from __future__ import annotations

import csv
import os
import time
from email.utils import parsedate_to_datetime
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Any

import requests

from stock_valuation.data.providers.response_cache import ProviderResponseCache
from stock_valuation.market.models import (
    FXRate,
    NormalizedMarketQuote,
    NormalizedShareData,
    SHARE_BASIS_ORDINARY,
)


STOOQ_URL = "https://stooq.com/q/l/"
FRANKFURTER_URL = "https://api.frankfurter.app/{date}"
OPEN_ER_URL = "https://open.er-api.com/v6/latest/{currency}"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


class MarketProviderError(RuntimeError):
    pass


def _decimal(raw: Any) -> Decimal | None:
    if raw in (None, "", "N/D"):
        return None
    try:
        return Decimal(str(raw).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def _date(raw: Any) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        try:
            return parsedate_to_datetime(str(raw)).date()
        except (TypeError, ValueError):
            return None


class StooqQuoteProvider:
    """Normalize live Stooq quote CSV rows into provider-independent market quotes."""

    def __init__(self, timeout: int = 20, *, use_cache: bool = True) -> None:
        self.timeout = timeout
        self.use_cache = use_cache
        self.cache = ProviderResponseCache("stooq_market")

    def latest_quote(
        self,
        symbol: str,
        *,
        ticker: str,
        exchange: str,
        currency: str,
        security_type: str = "ordinary_share",
    ) -> NormalizedMarketQuote:
        params = {"s": symbol, "f": "sd2t2c", "h": "", "e": "csv"}
        text = self._get_text(STOOQ_URL, params)
        reader = csv.DictReader(StringIO(text))
        row = next(reader, None)
        if row is None:
            raise MarketProviderError(f"Stooq lieferte keine Quote-Zeile fuer {symbol}.")
        close = _decimal(row.get("Close"))
        price_date = _date(row.get("Date"))
        if close is None or price_date is None:
            raise MarketProviderError(f"Stooq Quote fuer {symbol} ist unvollstaendig: {row}")
        return NormalizedMarketQuote(
            ticker=ticker,
            exchange=exchange,
            listing_currency=currency,
            price=close,
            price_date=price_date,
            retrieved_at=datetime.now(UTC),
            provider="stooq",
            provider_symbol=symbol,
            source_url=f"{STOOQ_URL}?s={symbol}&f=sd2t2c&h&e=csv",
            original_value=close,
            security_type=security_type,
        )

    def _get_text(self, url: str, params: dict[str, str]) -> str:
        if self.use_cache:
            cached = self.cache.get_text("GET", {"url": url, **params})
            if cached is not None:
                return cached
        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        if self.use_cache:
            self.cache.put_text("GET", {"url": url, **params}, response.text)
        return response.text


class AlphaVantageQuoteProvider:
    """Normalize Alpha Vantage GLOBAL_QUOTE responses into market quotes."""

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int = 20,
        min_request_interval_seconds: float = 13.0,
        *,
        use_cache: bool = True,
    ) -> None:
        self.api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        self.timeout = timeout
        self.min_request_interval_seconds = max(0.0, min_request_interval_seconds)
        self.use_cache = use_cache
        self.cache = ProviderResponseCache("alphavantage_market")
        self._last_request_started_at: float | None = None
        if not self.api_key:
            raise ValueError("ALPHA_VANTAGE_API_KEY fehlt fuer Market Quotes.")

    def latest_quote(
        self,
        symbol: str,
        *,
        ticker: str,
        exchange: str,
        currency: str,
        security_type: str = "ordinary_share",
    ) -> NormalizedMarketQuote:
        payload = self._get_json({"function": "GLOBAL_QUOTE", "symbol": symbol})
        quote = payload.get("Global Quote") if isinstance(payload, dict) else None
        if not isinstance(quote, dict):
            raise MarketProviderError(f"Alpha Vantage lieferte keine GLOBAL_QUOTE fuer {symbol}.")
        price = _decimal(quote.get("05. price"))
        price_date = _date(quote.get("07. latest trading day"))
        if price is None or price_date is None:
            raise MarketProviderError(f"Alpha Vantage Quote fuer {symbol} ist unvollstaendig: {quote}")
        return NormalizedMarketQuote(
            ticker=ticker,
            exchange=exchange,
            listing_currency=currency,
            price=price,
            price_date=price_date,
            retrieved_at=datetime.now(UTC),
            provider="alphavantage_global_quote",
            provider_symbol=symbol,
            source_url=f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}",
            original_value=price,
            security_type=security_type,
        )

    def _get_json(self, params: dict[str, str]) -> dict[str, Any]:
        cache_params = dict(params)
        if self.use_cache:
            cached = self.cache.get("GET", cache_params)
            if cached is not None:
                return cached
        query = {"apikey": self.api_key, **params}
        if self._last_request_started_at is not None and self.min_request_interval_seconds:
            elapsed = time.monotonic() - self._last_request_started_at
            remaining = self.min_request_interval_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_started_at = time.monotonic()
        response = requests.get(self.BASE_URL, params=query, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise MarketProviderError("Alpha Vantage returned non-object JSON.")
        message = str(payload.get("Information") or payload.get("Note") or payload.get("Error Message") or "")
        if message:
            raise MarketProviderError(f"Alpha Vantage GLOBAL_QUOTE: {message}")
        if self.use_cache:
            self.cache.put("GET", cache_params, payload)
        return payload


class FrankfurterFXProvider:
    """Free ECB-based FX adapter for reproducible date-specific currency conversion."""

    def __init__(self, timeout: int = 20, *, use_cache: bool = True) -> None:
        self.timeout = timeout
        self.use_cache = use_cache
        self.cache = ProviderResponseCache("frankfurter_fx")

    def rate(self, from_currency: str, to_currency: str, fx_date: date) -> FXRate:
        from_ccy = from_currency.upper()
        to_ccy = to_currency.upper()
        if from_ccy == to_ccy:
            return FXRate(from_ccy, to_ccy, Decimal("1"), fx_date, "identity", None)
        payload = self._get_json(
            FRANKFURTER_URL.format(date=fx_date.isoformat()),
            {"from": from_ccy, "to": to_ccy},
        )
        rates = payload.get("rates") if isinstance(payload, dict) else None
        value = _decimal(rates.get(to_ccy) if isinstance(rates, dict) else None)
        actual_date = _date(payload.get("date")) if isinstance(payload, dict) else fx_date
        return FXRate(
            from_ccy,
            to_ccy,
            value,
            actual_date or fx_date,
            "frankfurter",
            f"https://api.frankfurter.app/{fx_date.isoformat()}?from={from_ccy}&to={to_ccy}",
        )

    def _get_json(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        if self.use_cache:
            cached = self.cache.get("GET", {"url": url, **params})
            if cached is not None:
                return cached
        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise MarketProviderError("FX provider returned non-object JSON.")
        if self.use_cache:
            self.cache.put("GET", {"url": url, **params}, payload)
        return payload


class OpenExchangeRateFXProvider:
    """Free latest FX adapter used when ECB/Frankfurter does not cover a currency such as TWD."""

    def __init__(self, timeout: int = 20, *, use_cache: bool = True) -> None:
        self.timeout = timeout
        self.use_cache = use_cache
        self.cache = ProviderResponseCache("open_er_fx")

    def latest_rate(self, from_currency: str, to_currency: str) -> FXRate:
        from_ccy = from_currency.upper()
        to_ccy = to_currency.upper()
        if from_ccy == to_ccy:
            return FXRate(from_ccy, to_ccy, Decimal("1"), date.today(), "identity", None)
        payload = self._get_json(OPEN_ER_URL.format(currency=from_ccy), {})
        rates = payload.get("rates") if isinstance(payload, dict) else None
        value = _decimal(rates.get(to_ccy) if isinstance(rates, dict) else None)
        updated = _date(payload.get("time_last_update_utc")) if isinstance(payload, dict) else None
        return FXRate(
            from_ccy,
            to_ccy,
            value,
            updated,
            "open_er_api",
            OPEN_ER_URL.format(currency=from_ccy),
        )

    def _get_json(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        if self.use_cache:
            cached = self.cache.get("GET", {"url": url, **params})
            if cached is not None:
                return cached
        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise MarketProviderError("Open ER FX provider returned non-object JSON.")
        if payload.get("result") not in {None, "success"}:
            raise MarketProviderError(f"Open ER FX provider error: {payload.get('result')}")
        if self.use_cache:
            self.cache.put("GET", {"url": url, **params}, payload)
        return payload


class SECShareDataProvider:
    """Read official SEC CompanyFacts share concepts into NormalizedShareData."""

    SHARE_CONCEPTS = (
        ("dei", "EntityCommonStockSharesOutstanding", "shares_outstanding"),
        ("us-gaap", "CommonStocksIncludingAdditionalPaidInCapitalSharesOutstanding", "shares_outstanding"),
        ("us-gaap", "CommonStockSharesOutstanding", "shares_outstanding"),
        ("us-gaap", "WeightedAverageNumberOfSharesOutstandingBasic", "basic_weighted_average_shares"),
        ("us-gaap", "WeightedAverageNumberOfDilutedSharesOutstanding", "diluted_weighted_average_shares"),
    )

    def __init__(
        self,
        user_agent: str | None = None,
        timeout: int = 20,
        *,
        use_cache: bool = True,
    ) -> None:
        self.user_agent = (user_agent or os.getenv("SEC_USER_AGENT") or "").strip()
        self.timeout = timeout
        self.use_cache = use_cache
        self.cache = ProviderResponseCache("sec_share_data")
        if not self.user_agent:
            raise ValueError("SEC_USER_AGENT fehlt fuer SEC Share Data.")

    def latest_share_data(self, cik: str, *, ticker: str, as_of_date: date) -> NormalizedShareData:
        payload = self._companyfacts(cik)
        selected: dict[str, tuple[Decimal, date, date | None, str]] = {}
        facts = payload.get("facts") if isinstance(payload, dict) else None
        for taxonomy, concept, target in self.SHARE_CONCEPTS:
            units = (
                facts.get(taxonomy, {}).get(concept, {}).get("units", {})
                if isinstance(facts, dict)
                else {}
            )
            for unit, rows in units.items():
                if unit.lower() not in {"shares", "pure"} or not isinstance(rows, list):
                    continue
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    end = _date(row.get("end"))
                    filed = _date(row.get("filed"))
                    value = _decimal(row.get("val"))
                    form = str(row.get("form") or "")
                    if value is None or end is None or end > as_of_date or (filed and filed > as_of_date):
                        continue
                    if form and form not in {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A", "10-Q", "10-Q/A"}:
                        continue
                    existing = selected.get(target)
                    if existing is None or (end, filed or date.min) > (existing[1], existing[2] or date.min):
                        selected[target] = (value, end, filed, f"{taxonomy}:{concept}")
        shares = selected.get("shares_outstanding")
        basic = selected.get("basic_weighted_average_shares")
        diluted = selected.get("diluted_weighted_average_shares")
        basis = shares or basic or diluted
        if basis is None:
            raise MarketProviderError(f"Keine SEC Share Facts fuer CIK {cik} bis {as_of_date}.")
        return NormalizedShareData(
            ticker=ticker,
            shares_outstanding=shares[0] if shares else None,
            diluted_weighted_average_shares=diluted[0] if diluted else None,
            basic_weighted_average_shares=basic[0] if basic else None,
            fiscal_year=basis[1].year,
            share_date=shares[1] if shares else basis[1],
            filing_date=shares[2] if shares else basis[2],
            provider="sec_companyfacts",
            source="official_sec_xbrl",
            source_url=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{str(cik).zfill(10)}.json",
            provider_field=shares[3] if shares else basis[3],
            provenance="SEC CompanyFacts share concepts; no diluted-share substitution for market cap.",
            share_basis=SHARE_BASIS_ORDINARY,
        )

    def _companyfacts(self, cik: str) -> dict[str, Any]:
        normalized = str(cik).strip().replace("CIK", "").zfill(10)
        params = {"cik": normalized}
        if self.use_cache:
            cached = self.cache.get("COMPANYFACTS", params)
            if cached is not None:
                return cached
        response = requests.get(
            SEC_COMPANYFACTS_URL.format(cik=normalized),
            headers={"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise MarketProviderError("SEC CompanyFacts returned non-object JSON.")
        if self.use_cache:
            self.cache.put("COMPANYFACTS", params, payload)
        return payload
