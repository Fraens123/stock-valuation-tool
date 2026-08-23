from __future__ import annotations

import re
from dataclasses import dataclass

from stock_valuation.companies.selection import canonical_issuer_key
from stock_valuation.data.providers.gleif import GLEIFProvider, GLEIFProviderError, LEICandidate
from stock_valuation.data.providers.sec import SECCompanyCandidate, SECCompanyFactsProvider, SECProviderError


EURO_COUNTRIES = {
    "AT", "BE", "HR", "CY", "EE", "FI", "FR", "DE", "GR", "IE", "IT", "LV", "LT",
    "LU", "MT", "NL", "PT", "SK", "SI", "ES",
}
COUNTRY_CURRENCY = {
    "US": "USD",
    "CA": "CAD",
    "GB": "GBP",
    "CH": "CHF",
    "DK": "DKK",
    "SE": "SEK",
    "NO": "NOK",
    "JP": "JPY",
    "AU": "AUD",
}


@dataclass(frozen=True)
class CompanyDiscoveryCandidate:
    name: str
    ticker: str | None
    country: str | None
    currency: str
    sec_cik: str | None = None
    lei: str | None = None
    sources: tuple[str, ...] = ()

    @property
    def display_name(self) -> str:
        details: list[str] = []
        if self.ticker:
            details.append(self.ticker)
        if self.country:
            details.append(self.country)
        if self.sources:
            details.append("/".join(self.sources))
        suffix = f" · {' · '.join(details)}" if details else ""
        return f"{self.name}{suffix}"


def _currency_for_country(country: str | None, *, sec_only: bool = False) -> str:
    code = (country or "").strip().upper()
    if code in EURO_COUNTRIES:
        return "EUR"
    if code in COUNTRY_CURRENCY:
        return COUNTRY_CURRENCY[code]
    return "USD" if sec_only else "EUR"


def _query_looks_like_ticker(query: str) -> bool:
    raw = query.strip()
    return (
        bool(raw)
        and raw == raw.upper()
        and bool(re.fullmatch(r"[A-Z0-9.\-]{1,15}", raw))
    )


def discover_companies(
    query: str,
    *,
    sec_provider: SECCompanyFactsProvider | None = None,
    gleif_provider: GLEIFProvider | None = None,
    limit: int = 12,
) -> tuple[list[CompanyDiscoveryCandidate], list[str]]:
    """Combine free official identity sources without depending on a market-data provider.

    SEC contributes ticker + CIK for SEC registrants. GLEIF contributes legal entity + LEI and
    country. Results with the same normalized legal name are merged. Provider failures are returned
    as diagnostic notes instead of aborting the whole discovery workflow.
    """
    term = query.strip()
    if not term:
        return [], []

    sec_rows: list[SECCompanyCandidate] = []
    lei_rows: list[LEICandidate] = []
    notes: list[str] = []

    if sec_provider is not None:
        try:
            sec_rows = sec_provider.search_companies(term, limit=limit)
        except (SECProviderError, ValueError) as exc:
            notes.append(f"SEC-Suche nicht verfügbar: {exc}")

    if gleif_provider is not None:
        try:
            lei_rows = gleif_provider.search_by_name(term, limit=limit)
        except GLEIFProviderError as exc:
            notes.append(f"GLEIF-Suche nicht verfügbar: {exc}")

    merged: dict[str, dict[str, object]] = {}
    for row in sec_rows:
        key = canonical_issuer_key(row.name)
        merged.setdefault(
            key,
            {
                "name": row.name,
                "ticker": row.ticker,
                "country": None,
                "sec_cik": row.cik,
                "lei": None,
                "sources": set(),
            },
        )
        data = merged[key]
        data["ticker"] = data.get("ticker") or row.ticker
        data["sec_cik"] = row.cik
        cast_sources = data["sources"]
        if isinstance(cast_sources, set):
            cast_sources.add("SEC")

    fallback_ticker = term.upper() if _query_looks_like_ticker(term) else None
    for row in lei_rows:
        key = canonical_issuer_key(row.legal_name)
        data = merged.setdefault(
            key,
            {
                "name": row.legal_name,
                "ticker": fallback_ticker,
                "country": row.country,
                "sec_cik": None,
                "lei": row.lei,
                "sources": set(),
            },
        )
        # Prefer GLEIF legal spelling/country, but retain SEC ticker when present.
        data["name"] = row.legal_name
        data["country"] = row.country or data.get("country")
        data["lei"] = row.lei
        cast_sources = data["sources"]
        if isinstance(cast_sources, set):
            cast_sources.add("GLEIF")

    candidates: list[CompanyDiscoveryCandidate] = []
    for data in merged.values():
        sources = tuple(sorted(str(item) for item in data.get("sources", set())))
        country = str(data.get("country") or "").strip().upper() or None
        candidates.append(
            CompanyDiscoveryCandidate(
                name=str(data.get("name") or term),
                ticker=str(data.get("ticker") or "").strip().upper() or None,
                country=country,
                currency=_currency_for_country(country, sec_only=sources == ("SEC",)),
                sec_cik=str(data.get("sec_cik") or "").strip() or None,
                lei=str(data.get("lei") or "").strip().upper() or None,
                sources=sources,
            )
        )

    # Exact ticker/name first, then richer merged identities, then alphabetical.
    normalized_term = canonical_issuer_key(term)
    ticker_term = term.upper()
    candidates.sort(
        key=lambda row: (
            0 if row.ticker == ticker_term else 1 if canonical_issuer_key(row.name) == normalized_term else 2,
            -len(row.sources),
            row.name.casefold(),
        )
    )
    return candidates[:limit], notes
