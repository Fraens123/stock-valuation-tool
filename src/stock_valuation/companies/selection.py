from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from stock_valuation.companies.service import CompanyCandidate


SUSPICIOUS_INSTRUMENT_MARKERS = (
    " etf",
    " etp",
    " cdr",
    " certificate",
    " warrant",
    " options",
)

EXCHANGE_PRIORITY = {
    "amsterdam": 40,
    "xetra": 38,
    "frankfurt": 30,
    "paris": 38,
    "milan": 36,
    "madrid": 36,
    "brussels": 36,
    "vienna": 34,
    "switzerland": 36,
    "stockholm": 34,
    "copenhagen": 34,
    "helsinki": 34,
    "oslo": 34,
    "london": 34,
    "united kingdom": 20,
    "united states": 32,
    "nasdaq": 36,
    "nyse": 36,
}


class FundamentalsProbeProvider(Protocol):
    def probe_income_statement(self, symbol: str) -> dict[str, object]: ...


@dataclass(frozen=True)
class IssuerCandidateGroup:
    key: str
    name: str
    candidates: tuple[CompanyCandidate, ...]


@dataclass(frozen=True)
class FundamentalsResolution:
    symbol: str
    reported_currency: str | None
    latest_fiscal_date: str | None
    annual_report_count: int
    attempts: tuple[str, ...]


def canonical_issuer_key(name: str) -> str:
    """Normalize punctuation/casing so e.g. `N.V.` and `NV` group together."""
    return " ".join(re.findall(r"[a-z0-9]+", name.casefold()))


def group_company_candidates(candidates: list[CompanyCandidate]) -> list[IssuerCandidateGroup]:
    grouped: dict[str, list[CompanyCandidate]] = {}
    for candidate in candidates:
        key = canonical_issuer_key(candidate.name)
        grouped.setdefault(key, []).append(candidate)

    groups: list[IssuerCandidateGroup] = []
    for key, rows in grouped.items():
        # Prefer the most punctuated/descriptive spelling for display, then shortest.
        display = sorted((row.name for row in rows), key=lambda value: (-value.count("."), len(value)))[0]
        groups.append(
            IssuerCandidateGroup(
                key=key,
                name=display,
                candidates=tuple(rows),
            )
        )
    return sorted(groups, key=lambda group: group.name.casefold())


def _is_suspicious(candidate: CompanyCandidate) -> bool:
    text = f" {candidate.name.casefold()} "
    return any(marker in text for marker in SUSPICIOUS_INSTRUMENT_MARKERS)


def _symbol_order_score(candidate: CompanyCandidate) -> tuple[int, int, int, str]:
    symbol = candidate.provider_symbol or candidate.ticker
    return (
        1 if _is_suspicious(candidate) else 0,
        0 if "." not in symbol else 1,
        len(symbol),
        symbol,
    )


def fundamentals_symbol_candidates(candidates: tuple[CompanyCandidate, ...] | list[CompanyCandidate]) -> list[str]:
    """Return unique provider symbols in the order most likely to expose fundamentals.

    Plain provider symbols are tried before exchange-suffixed listings because providers often
    attach company fundamentals to one canonical symbol while local listings remain useful for
    market-price metadata only.
    """
    symbols: list[str] = []
    seen: set[str] = set()
    for candidate in sorted(candidates, key=_symbol_order_score):
        symbol = (candidate.provider_symbol or candidate.ticker).strip()
        normalized = symbol.upper()
        if not symbol or normalized in seen:
            continue
        seen.add(normalized)
        symbols.append(symbol)
    return symbols


def resolve_fundamentals_symbol(
    provider: FundamentalsProbeProvider,
    candidates: tuple[CompanyCandidate, ...] | list[CompanyCandidate],
    *,
    max_attempts: int = 3,
) -> FundamentalsResolution:
    """Probe plausible symbols and return the first one with real annual statements."""
    attempts: list[str] = []
    for symbol in fundamentals_symbol_candidates(candidates)[: max(1, max_attempts)]:
        attempts.append(symbol)
        probe = provider.probe_income_statement(symbol)
        annual_count = int(probe.get("annual_report_count") or 0)
        if annual_count <= 0:
            continue
        currency = str(probe.get("reported_currency") or "").strip().upper() or None
        fiscal_date = str(probe.get("latest_fiscal_date") or "").strip() or None
        return FundamentalsResolution(
            symbol=symbol,
            reported_currency=currency,
            latest_fiscal_date=fiscal_date,
            annual_report_count=annual_count,
            attempts=tuple(attempts),
        )

    tried = ", ".join(attempts) if attempts else "keine Symbole"
    raise ValueError(
        "Alpha Vantage konnte für die automatisch geprüften Symbole keine Jahresabschlüsse "
        f"bestätigen ({tried}). Es wurde noch keine Analyse angelegt."
    )


def _listing_score(candidate: CompanyCandidate, reported_currency: str | None) -> tuple[int, int, int, str]:
    score = 0
    if not _is_suspicious(candidate):
        score += 100
    if reported_currency and candidate.currency.upper() == reported_currency.upper():
        score += 60
    exchange = (candidate.exchange or "").casefold()
    for marker, points in EXCHANGE_PRIORITY.items():
        if marker in exchange:
            score += points
            break
    symbol = candidate.provider_symbol or candidate.ticker
    if "." in symbol:
        score += 5
    return (score, -len(symbol), -len(candidate.name), symbol)


def choose_recommended_listing(
    candidates: tuple[CompanyCandidate, ...] | list[CompanyCandidate],
    *,
    reported_currency: str | None,
) -> CompanyCandidate:
    """Choose display/market listing metadata without affecting the fundamentals symbol."""
    if not candidates:
        raise ValueError("Keine Börsenplätze für dieses Unternehmen vorhanden.")
    return max(candidates, key=lambda row: _listing_score(row, reported_currency))
