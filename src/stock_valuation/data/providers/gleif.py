from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import requests

from stock_valuation.data.providers.base import ProviderResponseError
from stock_valuation.data.providers.response_cache import ProviderResponseCache


GLEIF_BASE_URL = "https://api.gleif.org/api/v1"
LEI_PATTERN = re.compile(r"^[A-Z0-9]{20}$")

# Legal-form abbreviations are frequently punctuated differently across registries/providers.
# Normalize only well-known suffixes; never merge arbitrary initials inside an entity name.
CORPORATE_SUFFIX_ALIASES: dict[tuple[str, ...], str] = {
    ("n", "v"): "nv",
    ("s", "a"): "sa",
    ("s", "p", "a"): "spa",
    ("a", "g"): "ag",
    ("p", "l", "c"): "plc",
    ("l", "t", "d"): "ltd",
}


class GLEIFProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class LEICandidate:
    lei: str
    legal_name: str
    country: str | None
    registration_status: str | None


def _normalized_name(value: str) -> str:
    cleaned = value.casefold().replace(".", "").replace(",", " ")
    tokens = re.findall(r"[a-z0-9]+", cleaned)

    for parts, replacement in sorted(
        CORPORATE_SUFFIX_ALIASES.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if len(tokens) >= len(parts) and tuple(tokens[-len(parts) :]) == parts:
            tokens = [*tokens[: -len(parts)], replacement]
            break

    return " ".join(tokens)


class GLEIFProvider:
    """Free official LEI identity lookup used for ESEF discovery.

    GLEIF is an identity source, not a financial statement provider. It resolves a legal entity
    name to a LEI so the ESEF registry can be queried without asking the user for technical IDs.
    """

    def __init__(self, timeout: int = 30, *, use_cache: bool = True) -> None:
        self.timeout = timeout
        self.use_cache = use_cache
        self.cache = ProviderResponseCache("gleif")
        self.cache_hits = 0
        self.network_requests = 0

    def _get_json(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.use_cache:
            cached = self.cache.get(endpoint, params)
            if cached is not None:
                self.cache_hits += 1
                return cached

        try:
            response = requests.get(
                f"{GLEIF_BASE_URL}/{endpoint.lstrip('/')}",
                params=params,
                headers={"Accept": "application/vnd.api+json"},
                timeout=self.timeout,
            )
            self.network_requests += 1
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise GLEIFProviderError(f"GLEIF-Abruf fehlgeschlagen: {exc}") from exc
        except ValueError as exc:
            raise ProviderResponseError("GLEIF lieferte keine gültige JSON-Antwort.") from exc

        if not isinstance(payload, dict):
            raise ProviderResponseError("GLEIF lieferte ein unerwartetes Antwortformat.")
        if self.use_cache:
            self.cache.put(endpoint, params, payload)
        return payload

    @staticmethod
    def _candidate(item: dict[str, Any]) -> LEICandidate | None:
        attrs = item.get("attributes") or {}
        if not isinstance(attrs, dict):
            return None
        entity = attrs.get("entity") or {}
        registration = attrs.get("registration") or {}
        if not isinstance(entity, dict):
            entity = {}
        if not isinstance(registration, dict):
            registration = {}
        legal_name_raw = entity.get("legalName") or {}
        legal_name = (
            str(legal_name_raw.get("name") or "").strip()
            if isinstance(legal_name_raw, dict)
            else str(legal_name_raw or "").strip()
        )
        legal_address = entity.get("legalAddress") or {}
        country = (
            str(legal_address.get("country") or "").strip().upper() or None
            if isinstance(legal_address, dict)
            else None
        )
        lei = str(item.get("id") or attrs.get("lei") or "").strip().upper()
        if not legal_name or not LEI_PATTERN.fullmatch(lei):
            return None
        status = str(registration.get("status") or "").strip().upper() or None
        return LEICandidate(
            lei=lei,
            legal_name=legal_name,
            country=country,
            registration_status=status,
        )

    def search_by_name(self, name: str, *, limit: int = 10) -> list[LEICandidate]:
        term = name.strip()
        if not term:
            return []
        payload = self._get_json(
            "lei-records",
            {
                "filter[entity.legalName]": term,
                "page[number]": 1,
                "page[size]": max(1, min(int(limit), 50)),
            },
        )
        rows = payload.get("data") or []
        if not isinstance(rows, list):
            return []
        candidates = [self._candidate(row) for row in rows if isinstance(row, dict)]
        return [candidate for candidate in candidates if candidate is not None]

    def resolve_lei(self, legal_name: str, *, country: str | None = None) -> LEICandidate | None:
        """Resolve only a sufficiently safe legal-name match; never guess among ambiguous entities."""
        candidates = self.search_by_name(legal_name, limit=20)
        if not candidates:
            return None
        target = _normalized_name(legal_name)
        country_code = (country or "").strip().upper()

        exact = [row for row in candidates if _normalized_name(row.legal_name) == target]
        if not exact:
            return None

        if country_code:
            country_exact = [row for row in exact if row.country == country_code]
            if len(country_exact) == 1:
                return country_exact[0]
            # With an explicit country, never fall back to an entity from another jurisdiction.
            return None

        # Without a country discriminator, any multiple exact legal-name match is ambiguous,
        # even if only one record happens to be currently ISSUED.
        if len(exact) == 1:
            return exact[0]
        return None

    def get_by_lei(self, lei: str) -> LEICandidate | None:
        normalized = lei.strip().upper()
        if not LEI_PATTERN.fullmatch(normalized):
            return None
        payload = self._get_json(f"lei-records/{normalized}", {})
        row = payload.get("data")
        return self._candidate(row) if isinstance(row, dict) else None
