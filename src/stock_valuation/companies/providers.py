from __future__ import annotations

from typing import Protocol

from .service import CompanyCandidate


class CompanySearchProvider(Protocol):
    """Provider interface for future remote symbol/company search implementations."""

    def search(self, query: str) -> list[CompanyCandidate]:
        """Return matching companies/listings for a user query."""
        ...
