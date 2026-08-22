from __future__ import annotations

import os
from typing import Any

import requests

from .base import FinancialDataProvider


class EODHDProvider(FinancialDataProvider):
    """Initial EODHD adapter.

    Exact endpoint/filter mappings are validated against ASML in Roadmap Phase 2
    before this provider is considered production-ready.
    """

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
        response.raise_for_status()
        return response.json()

    def search_companies(self, query: str) -> list[dict[str, Any]]:
        data = self._get(f"https://eodhd.com/api/search/{query}")
        return list(data) if isinstance(data, list) else []

    def get_fundamentals(self, symbol: str) -> dict[str, Any]:
        data = self._get(f"https://eodhd.com/api/fundamentals/{symbol}")
        if not isinstance(data, dict):
            raise ValueError("Unerwartetes Fundamentals-Format von EODHD.")
        return data

    def get_estimates(self, symbol: str) -> dict[str, Any]:
        fundamentals = self.get_fundamentals(symbol)
        earnings = fundamentals.get("Earnings", {})
        return earnings if isinstance(earnings, dict) else {}
