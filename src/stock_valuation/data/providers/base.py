from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class FinancialDataProvider(ABC):
    @abstractmethod
    def search_companies(self, query: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_fundamentals(self, symbol: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_estimates(self, symbol: str) -> dict[str, Any]:
        raise NotImplementedError
