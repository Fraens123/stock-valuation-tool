from __future__ import annotations

import os
import time
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


def extract_matching_annual_fields(
    payload: dict[str, Any],
    *,
    statement: str,
    keywords: tuple[str, ...],
    max_reports: int = 2,
) -> list[dict[str, Any]]:
    """Return matching raw fields from the latest annual reports without interpreting them.

    This helper is deliberately semantic-free. It is used for provider diagnostics so we can
    inspect candidate raw fields before changing the normalisation mapping.
    """
    reports = payload.get("annualReports") or []
    if not isinstance(reports, list):
        return []

    lowered_keywords = tuple(keyword.lower() for keyword in keywords)
    rows: list[dict[str, Any]] = []
    for report in reports[:max_reports]:
        if not isinstance(report, dict):
            continue
        fiscal_date = report.get("fiscalDateEnding")
        currency = report.get("reportedCurrency")
        for field, value in report.items():
            lowered_field = str(field).lower()
            if any(keyword in lowered_field for keyword in lowered_keywords):
                rows.append(
                    {
                        "statement": statement,
                        "fiscal_date": fiscal_date,
                        "reported_currency": currency,
                        "field": field,
                        "value": value,
                    }
                )
    return rows


class AlphaVantageProvider(FinancialDataProvider):
    """Alpha Vantage adapter for fundamentals testing.

    Financial statements are fetched from the documented INCOME_STATEMENT,
    BALANCE_SHEET and CASH_FLOW endpoints. Estimates use EARNINGS_ESTIMATES.

    The free tier currently has a daily quota and also asks users to spread requests
    out. Full imports therefore pace calls. Diagnostic probes are exposed separately
    so access/symbol/mapping problems can be inspected without modifying snapshots.
    """

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int = 30,
        min_request_interval_seconds: float = 2.0,
    ) -> None:
        self.api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        self.timeout = timeout
        self.min_request_interval_seconds = max(0.0, min_request_interval_seconds)
        self._last_request_started_at: float | None = None
        if not self.api_key:
            raise ValueError("ALPHA_VANTAGE_API_KEY fehlt.")

    def _wait_for_request_slot(self) -> None:
        """Space consecutive requests conservatively for the free tier."""
        if self._last_request_started_at is None or self.min_request_interval_seconds <= 0:
            return
        elapsed = time.monotonic() - self._last_request_started_at
        remaining = self.min_request_interval_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _request(self, function: str, **params: Any) -> dict[str, Any]:
        self._wait_for_request_slot()
        self._last_request_started_at = time.monotonic()

        query = {"function": function, "apikey": self.api_key, **params}
        response = requests.get(self.BASE_URL, params=query, timeout=self.timeout)
        if response.status_code == 403:
            raise ProviderAccessError(
                f"Alpha Vantage: {function} wurde mit HTTP 403 abgelehnt."
            )
        if response.status_code == 429:
            raise ProviderRateLimitError(
                f"Alpha Vantage: {function} — HTTP 429. API-Limit erreicht; "
                "bitte später erneut versuchen."
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

        # Alpha Vantage can report throttling and entitlement messages inside JSON
        # while still returning HTTP 200, so those messages must be handled explicitly.
        message = str(data.get("Information") or data.get("Note") or data.get("Error Message") or "")
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
                raise ProviderRateLimitError(f"Alpha Vantage: {function} — {message}")
            if "premium" in lowered or "subscription" in lowered or "entitlement" in lowered:
                raise ProviderAccessError(f"Alpha Vantage: {function} — {message}")
            if data.get("Error Message"):
                raise ProviderResponseError(f"Alpha Vantage: {function} — {message}")
        return data

    def probe_income_statement(self, symbol: str) -> dict[str, Any]:
        """Perform exactly one API request for diagnostics without persisting data."""
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
        """Inspect D&A-like raw fields using exactly two requests and no persistence.

        Both INCOME_STATEMENT and CASH_FLOW are inspected because normalized provider
        taxonomies may expose depreciation/amortisation concepts in more than one statement.
        Returned values remain raw strings; this method makes no decision about which field
        should be used by the metrics engine.
        """
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
