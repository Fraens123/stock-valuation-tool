from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ProviderError(RuntimeError):
    """Base class for user-facing data-provider failures."""


class ProviderAccessError(ProviderError):
    """The credential is valid enough to reach the provider, but access is not allowed."""


class ProviderRateLimitError(ProviderError):
    """The provider rejected the request because a usage/rate limit was reached."""


class ProviderResponseError(ProviderError):
    """The provider returned an unexpected or unusable response."""


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
