from __future__ import annotations

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

# GLEIF is a legal-entity registry and can return funds/structured products that merely contain
# the search term. These are not suitable normal stock issuers and are hidden from the standard
# company-selection list. This is a generic instrument filter, not company-specific logic.
NON_ISSUER_NAME_MARKERS = (
    " etf",
    " etp",
    " fund",
    " cdr",
    " warrant",
    " certificate",
    " options",
    " adrhedged",
)


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


def _is_obvious_non_issuer(name: str) -> bool:
    text = f" {name.casefold()} "
    return any(marker in text for marker in NON_ISSUER_NAME_MARKERS)


def discover_companies(
    query: str,
    *,
    sec_provider: SECCompanyFactsProvider | None = None,
    gleif_provider: GLEIFProvider | None = None,
    limit: int = 12,
) -> tuple[list[CompanyDiscoveryCandidate], list[str]]:
    """Combine free official identity sources without depending on a market-data provider.

    SEC contributes ticker + CIK for SEC registrants. GLEIF contributes legal entity + LEI and
    country. Results with the same normalized legal name are merged. GLEIF never contributes a
    ticker because LEI records do not provide a reliable exchange symbol. Provider failures are
    returned as diagnostic notes instead of aborting the whole discovery workflow.
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

    for row in lei_rows:
        if _is_obvious_non_issuer(row.legal_name):
            continue
        key = canonical_issuer_key(row.legal_name)
        data = merged.setdefault(
            key,
            {
                "name": row.legal_name,
                "ticker": None,
                "country": row.country,
                "sec_cik": None,
                "lei": row.lei,
                "sources": set(),
            },
        )
        # Prefer GLEIF legal spelling/country, but retain a ticker only if SEC supplied it.
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

    # Exact SEC ticker/name first. For GLEIF-only broad name searches, prefer legal names that
    # start with the query and then the shortest legal name. This tends to surface the parent issuer
    # ahead of similarly named subsidiaries without inventing identity data.
    normalized_term = canonical_issuer_key(term)
    ticker_term = term.upper()
    candidates.sort(
        key=lambda row: (
            0
            if row.ticker == ticker_term
            else 1
            if canonical_issuer_key(row.name) == normalized_term
            else 2
            if canonical_issuer_key(row.name).startswith(normalized_term + " ")
            else 3,
            -len(row.sources),
            len(canonical_issuer_key(row.name)),
            row.name.casefold(),
        )
    )
    return candidates[:limit], notes
