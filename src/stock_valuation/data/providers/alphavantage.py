from __future__ import annotations

import os
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


class AlphaVantageProvider(FinancialDataProvider):
    """Alpha Vantage adapter for free-tier-friendly fundamentals testing.

    Financial statements are fetched from the documented INCOME_STATEMENT,
    BALANCE_SHEET and CASH_FLOW endpoints. Estimates use EARNINGS_ESTIMATES.
    """

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str | None = None, timeout: int = 30) -> None:
        self.api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        self.timeout = timeout
        if not self.api_key:
            raise ValueError("ALPHA_VANTAGE_API_KEY fehlt.")

    def _request(self, function: str, **params: Any) -> dict[str, Any]:
        query = {"function": function, "apikey": self.api_key, **params}
        response = requests.get(self.BASE_URL, params=query, timeout=self.timeout)
        if response.status_code == 403:
            raise ProviderAccessError("Alpha Vantage hat den Abruf mit HTTP 403 abgelehnt.")
        if response.status_code == 429:
            raise ProviderRateLimitError("Alpha-Vantage-API-Limit erreicht. Bitte später erneut versuchen.")
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderResponseError("Alpha Vantage lieferte keine gültige JSON-Antwort.") from exc

        if not isinstance(data, dict):
            raise ProviderResponseError("Unerwartetes Antwortformat von Alpha Vantage.")

        # Alpha Vantage reports free-tier throttling and entitlement messages inside JSON
        # with HTTP 200, so these must be handled explicitly.
        message = str(data.get("Information") or data.get("Note") or data.get("Error Message") or "")
        lowered = message.lower()
        if message:
            if "rate limit" in lowered or "call frequency" in lowered or "requests per day" in lowered:
                raise ProviderRateLimitError(message)
            if "premium" in lowered or "subscription" in lowered or "entitlement" in lowered:
                raise ProviderAccessError(message)
            if data.get("Error Message"):
                raise ProviderResponseError(message)
        return data

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
