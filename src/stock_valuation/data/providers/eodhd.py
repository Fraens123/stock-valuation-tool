from __future__ import annotations

import os
from typing import Any

import requests

from stock_valuation.data.normalization import (
    normalize_eodhd_company,
    normalize_eodhd_estimates,
    normalize_eodhd_financials,
)
from stock_valuation.data.types import NormalizedEstimate, NormalizedFinancialFact, ProviderCompany

from .base import (
    FinancialDataProvider,
    ProviderAccessError,
    ProviderRateLimitError,
    ProviderResponseError,
)


class EODHDProvider(FinancialDataProvider):
    """EODHD adapter using the Fundamentals v1.1 endpoint.

    Raw provider responses remain available for debugging/audit. Public normalization
    methods map provider-specific names to the project's stable internal data keys.
    """

    FUNDAMENTALS_URL = "https://eodhd.com/api/v1.1/fundamentals"
    SEARCH_URL = "https://eodhd.com/api/search"

    def __init__(self, api_key: str | None = None, timeout: int = 30) -> None:
        self.api_key = api_key or os.getenv("EODHD_API_KEY")
        self.timeout = timeout
        if not self.api_key:
            raise ValueError("EODHD_API_KEY fehlt.")

    def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        merged = {"api_token": self.api_key, "fmt": "json"}
        if params:
            merged.update(params)
        response = requests.get(url, params=merged, timeout=self.timeout)
        if response.status_code == 403:
            raise ProviderAccessError(
                "EODHD hat die Anfrage mit HTTP 403 abgelehnt. Der API-Key ist vorhanden, "
                "aber der aktuelle Tarif enthält für diesen Abruf keinen Fundamentals-Zugriff. "
                "Bitte nicht automatisch upgraden; im Tool kann stattdessen ein anderer Provider "
                "verwendet werden."
            )
        if response.status_code == 429:
            raise ProviderRateLimitError("EODHD API-Limit erreicht. Bitte später erneut versuchen.")
        response.raise_for_status()
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderResponseError("EODHD lieferte keine gültige JSON-Antwort.") from exc

    def search_companies(self, query: str) -> list[dict[str, Any]]:
        data = self._get(f"{self.SEARCH_URL}/{query}")
        return list(data) if isinstance(data, list) else []

    def get_fundamentals(
        self, symbol: str, *, filter_: str | None = None
    ) -> dict[str, Any]:
        params = {"filter": filter_} if filter_ else None
        data = self._get(f"{self.FUNDAMENTALS_URL}/{symbol}", params=params)
        if not isinstance(data, dict):
            raise ProviderResponseError("Unerwartetes Fundamentals-Format von EODHD.")
        return data

    def get_estimates(self, symbol: str) -> dict[str, Any]:
        fundamentals = self.get_fundamentals(symbol)
        earnings = fundamentals.get("Earnings", {})
        return earnings if isinstance(earnings, dict) else {}

    def get_company(self, symbol: str) -> ProviderCompany:
        return normalize_eodhd_company(self.get_fundamentals(symbol))

    def get_normalized_financials(
        self, symbol: str, *, period_type: str = "FY"
    ) -> list[NormalizedFinancialFact]:
        payload = self.get_fundamentals(symbol, filter_="Financials")
        if "Financials" not in payload:
            payload = {"Financials": payload}
        return normalize_eodhd_financials(payload, period_type=period_type)

    def get_normalized_estimates(self, symbol: str) -> list[NormalizedEstimate]:
        payload = self.get_fundamentals(symbol)
        return normalize_eodhd_estimates(payload)
