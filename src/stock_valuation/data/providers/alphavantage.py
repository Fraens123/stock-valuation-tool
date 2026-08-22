from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import requests

from stock_valuation.data.normalization_alphavantage import (
    normalize_alphavantage_estimates,
    normalize_alphavantage_financials,
)
from stock_valuation.data.types import NormalizedEstimate, NormalizedFinancialFact

from .base import (
    FinancialDataProvider,
    ProviderAccessError,
    ProviderRateLimitError,
    ProviderResponseError,
)
from .response_cache import DEFAULT_PROVIDER_CACHE_DIR, ProviderResponseCache


def extract_matching_annual_fields(
    payload: dict[str, Any],
    *,
    statement: str,
    keywords: tuple[str, ...],
    max_reports: int = 2,
) -> list[dict[str, Any]]:
    rows = payload.get("annualReports") or []
    if not isinstance(rows, list):
        return []
    output: list[dict[str, Any]] = []
    for row in rows[:max_reports]:
        if not isinstance(row, dict):
            continue
        fiscal_date = row.get("fiscalDateEnding")
        currency = row.get("reportedCurrency")
        for field, value in row.items():
            if field in {"fiscalDateEnding", "reportedCurrency"}:
                continue
            lowered = field.lower()
            if any(keyword in lowered for keyword in keywords):
                output.append(
                    {
                        "statement": statement,
                        "fiscal_date": fiscal_date,
                        "reported_currency": currency,
                        "field": field,
                        "value": value,
                    }
                )
    return output


def extract_candidate_annual_fields(
    payload: dict[str, Any],
    *,
    statement: str,
    candidates: dict[str, tuple[str, ...]],
    max_reports: int = 2,
) -> list[dict[str, Any]]:
    """Return raw annual fields that may represent one of our blocked internal facts.

    A provider field can be emitted for more than one candidate on purpose. This is a
    diagnostic helper only; it never decides the mapping. The caller can compare each
    candidate with primary-source controls before changing normalization rules.
    """
    rows = payload.get("annualReports") or []
    if not isinstance(rows, list):
        return []

    output: list[dict[str, Any]] = []
    for row in rows[:max_reports]:
        if not isinstance(row, dict):
            continue
        fiscal_date = row.get("fiscalDateEnding")
        currency = row.get("reportedCurrency")
        for field, value in row.items():
            if field in {"fiscalDateEnding", "reportedCurrency"}:
                continue
            lowered = field.lower()
            for candidate, keywords in candidates.items():
                if any(keyword in lowered for keyword in keywords):
                    output.append(
                        {
                            "candidate_for": candidate,
                            "statement": statement,
                            "fiscal_date": fiscal_date,
                            "reported_currency": currency,
                            "field": field,
                            "value": value,
                        }
                    )
    return output


class AlphaVantageProvider(FinancialDataProvider):
    """Alpha Vantage adapter with persistent cache for the quota-limited free API.

    Successful responses are stored below ``data/cache/providers/alphavantage``. By default a
    repeated identical request is served from disk and therefore consumes no new provider quota.
    ``force_refresh=True`` explicitly bypasses the cache, while ``cache_only=True`` forbids network
    access completely.
    """

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int = 30,
        min_request_interval_seconds: float = 2.0,
        *,
        cache_enabled: bool = True,
        cache_only: bool = False,
        force_refresh: bool = False,
        cache_root: Path = DEFAULT_PROVIDER_CACHE_DIR,
    ) -> None:
        self.api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        self.timeout = timeout
        self.min_request_interval_seconds = max(0.0, min_request_interval_seconds)
        self.cache_enabled = cache_enabled
        self.cache_only = cache_only
        self.force_refresh = force_refresh
        self.cache = ProviderResponseCache("alphavantage", root=cache_root)
        self.cache_hits = 0
        self.cache_misses = 0
        self.network_requests = 0
        self.last_response_from_cache = False
        self._last_request_started_at: float | None = None
        if not self.api_key and not self.cache_only:
            raise ValueError("ALPHA_VANTAGE_API_KEY fehlt.")

    def _wait_for_request_slot(self) -> None:
        if self._last_request_started_at is None or self.min_request_interval_seconds <= 0:
            return
        elapsed = time.monotonic() - self._last_request_started_at
        remaining = self.min_request_interval_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _sanitized_message(self, message: str) -> str:
        if self.api_key:
            return message.replace(self.api_key, "***")
        return message

    def _request(self, function: str, **params: Any) -> dict[str, Any]:
        cache_params = dict(params)
        if self.cache_enabled and not self.force_refresh:
            cached = self.cache.get(function, cache_params)
            if cached is not None:
                self.cache_hits += 1
                self.last_response_from_cache = True
                return cached
            self.cache_misses += 1

        if self.cache_only:
            self.last_response_from_cache = False
            raise ProviderAccessError(
                "Alpha Vantage: Offline-Modus aktiv, aber für diese Anfrage liegt noch kein lokaler Cache vor."
            )
        if not self.api_key:
            raise ValueError("ALPHA_VANTAGE_API_KEY fehlt.")

        self._wait_for_request_slot()
        self._last_request_started_at = time.monotonic()
        self.network_requests += 1
        self.last_response_from_cache = False

        query = {"function": function, "apikey": self.api_key, **params}
        response = requests.get(self.BASE_URL, params=query, timeout=self.timeout)
        if response.status_code == 403:
            raise ProviderAccessError(
                f"Alpha Vantage: {function} wurde mit HTTP 403 abgelehnt."
            )
        if response.status_code == 429:
            raise ProviderRateLimitError(
                f"Alpha Vantage: {function} — HTTP 429. API-Limit erreicht; bitte später erneut versuchen."
            )
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderResponseError(
                f"Alpha Vantage: {function} lieferte keine gültige JSON-Antwort."
            ) from exc

        if not isinstance(data, dict):
            raise ProviderResponseError(
                f"Alpha Vantage: {function} lieferte ein unerwartetes Antwortformat."
            )

        message = str(data.get("Information") or data.get("Note") or data.get("Error Message") or "")
        safe_message = self._sanitized_message(message)
        lowered = message.lower()
        if message:
            rate_limit_markers = (
                "rate limit",
                "call frequency",
                "requests per day",
                "request per second",
                "requests per second",
                "more sparingly",
            )
            if any(marker in lowered for marker in rate_limit_markers):
                raise ProviderRateLimitError(f"Alpha Vantage: {function} — {safe_message}")
            if "premium" in lowered or "subscription" in lowered or "entitlement" in lowered:
                raise ProviderAccessError(f"Alpha Vantage: {function} — {safe_message}")
            if data.get("Error Message"):
                raise ProviderResponseError(f"Alpha Vantage: {function} — {safe_message}")

        if self.cache_enabled:
            self.cache.put(function, cache_params, data)
        return data

    def probe_income_statement(self, symbol: str) -> dict[str, Any]:
        data = self._request("INCOME_STATEMENT", symbol=symbol)
        annual = data.get("annualReports") or []
        quarterly = data.get("quarterlyReports") or []
        annual_count = len(annual) if isinstance(annual, list) else 0
        quarterly_count = len(quarterly) if isinstance(quarterly, list) else 0
        latest = annual[0] if annual_count and isinstance(annual[0], dict) else {}
        return {
            "function": "INCOME_STATEMENT",
            "requested_symbol": symbol,
            "returned_symbol": data.get("symbol") or symbol,
            "annual_report_count": annual_count,
            "quarterly_report_count": quarterly_count,
            "latest_fiscal_date": latest.get("fiscalDateEnding"),
            "reported_currency": latest.get("reportedCurrency"),
            "latest_revenue": latest.get("totalRevenue"),
        }

    def probe_depreciation_fields(self, symbol: str) -> list[dict[str, Any]]:
        keywords = ("depreci", "amorti", "depletion")
        income = self._request("INCOME_STATEMENT", symbol=symbol)
        cash_flow = self._request("CASH_FLOW", symbol=symbol)
        return [
            *extract_matching_annual_fields(
                income,
                statement="income_statement",
                keywords=keywords,
                max_reports=2,
            ),
            *extract_matching_annual_fields(
                cash_flow,
                statement="cash_flow",
                keywords=keywords,
                max_reports=2,
            ),
        ]

    def probe_blocked_field_candidates(self, symbol: str) -> list[dict[str, Any]]:
        """Inspect candidate raw fields for still-blocked ASML facts using two requests."""
        balance_candidates = {
            "accounts_receivable": ("receiv",),
            "inventory": ("invent",),
            "ppe_net": ("property", "plant", "equipment"),
            "short_term_debt": ("shorttermdebt", "currentdebt", "borrow"),
            "cash_and_short_term_investments": ("cash", "shortterminvest"),
        }
        cash_flow_candidates = {
            "operating_cash_flow": ("operatingcash", "operatingactivit", "cashflowfromoperating"),
            "capital_expenditures": ("capitalexpend", "property", "plant", "equipment", "purchase"),
            "dividends_paid": ("dividend",),
        }

        balance = self._request("BALANCE_SHEET", symbol=symbol)
        cash_flow = self._request("CASH_FLOW", symbol=symbol)
        return [
            *extract_candidate_annual_fields(
                balance,
                statement="balance_sheet",
                candidates=balance_candidates,
                max_reports=2,
            ),
            *extract_candidate_annual_fields(
                cash_flow,
                statement="cash_flow",
                candidates=cash_flow_candidates,
                max_reports=2,
            ),
        ]

    def get_income_statement(self, symbol: str) -> dict[str, Any]:
        """Fetch only the income statement; one API request or cache hit."""
        return self._request("INCOME_STATEMENT", symbol=symbol)

    def search_companies(self, query: str) -> list[dict[str, Any]]:
        data = self._request("SYMBOL_SEARCH", keywords=query)
        matches = data.get("bestMatches") or []
        return list(matches) if isinstance(matches, list) else []

    def get_fundamentals(self, symbol: str) -> dict[str, Any]:
        return {
            "income_statement": self._request("INCOME_STATEMENT", symbol=symbol),
            "balance_sheet": self._request("BALANCE_SHEET", symbol=symbol),
            "cash_flow": self._request("CASH_FLOW", symbol=symbol),
        }

    def get_estimates(self, symbol: str) -> dict[str, Any]:
        return self._request("EARNINGS_ESTIMATES", symbol=symbol)

    def get_normalized_financials(
        self, symbol: str, *, period_type: str = "FY"
    ) -> list[NormalizedFinancialFact]:
        return normalize_alphavantage_financials(
            self.get_fundamentals(symbol),
            period_type=period_type,
        )

    def get_normalized_estimates(self, symbol: str) -> list[NormalizedEstimate]:
        return normalize_alphavantage_estimates(self.get_estimates(symbol))
