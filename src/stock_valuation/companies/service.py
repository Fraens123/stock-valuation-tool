from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from stock_valuation.database.models import Company


@dataclass(frozen=True)
class CompanyCandidate:
    name: str
    ticker: str
    isin: str | None
    exchange: str | None
    country: str | None
    currency: str
    provider_symbol: str | None
    sector: str | None = None
    industry: str | None = None
    provider: str | None = None

    @property
    def display_name(self) -> str:
        details = [self.ticker]
        if self.exchange:
            details.append(self.exchange)
        details.append(self.currency)
        return f"{self.name} · {' · '.join(details)}"


REFERENCE_COMPANIES: tuple[CompanyCandidate, ...] = (
    CompanyCandidate(
        name="ASML Holding N.V.",
        ticker="ASML",
        isin="NL0010273215",
        exchange="Euronext Amsterdam",
        country="Netherlands",
        currency="EUR",
        provider_symbol="ASML.AS",
        sector="Technology",
        industry="Semiconductor Equipment & Materials",
        provider="eodhd",
    ),
)


def alpha_vantage_company_candidates(matches: list[dict[str, Any]]) -> list[CompanyCandidate]:
    """Convert Alpha Vantage SYMBOL_SEARCH rows into generic company candidates."""
    candidates: list[CompanyCandidate] = []
    seen: set[tuple[str, str | None]] = set()
    for row in matches:
        symbol = str(row.get("1. symbol") or row.get("symbol") or "").strip()
        name = str(row.get("2. name") or row.get("name") or "").strip()
        if not symbol or not name:
            continue
        region = str(row.get("4. region") or row.get("region") or "").strip() or None
        currency = str(row.get("8. currency") or row.get("currency") or "USD").strip().upper()
        key = (symbol.upper(), region)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            CompanyCandidate(
                name=name,
                ticker=symbol.upper(),
                isin=None,
                exchange=region,
                country=region,
                currency=currency,
                provider_symbol=symbol,
                provider="alphavantage",
            )
        )
    return candidates


def get_company(session: Session, company_id: int) -> Company | None:
    return session.get(Company, company_id)


def get_company_by_ticker(session: Session, ticker: str) -> Company | None:
    return session.scalar(select(Company).where(Company.ticker == ticker.strip().upper()))


def get_or_create_company(
    session: Session,
    *,
    name: str,
    ticker: str,
    currency: str = "EUR",
    isin: str | None = None,
    exchange: str | None = None,
    country: str | None = None,
    provider_symbol: str | None = None,
    sector: str | None = None,
    industry: str | None = None,
) -> Company:
    normalized_ticker = ticker.strip().upper()
    company = get_company_by_ticker(session, normalized_ticker)
    if company:
        return company

    company = Company(
        name=name.strip(),
        ticker=normalized_ticker,
        isin=isin.strip().upper() if isin else None,
        exchange=exchange.strip() if exchange else None,
        country=country.strip() if country else None,
        currency=currency.strip().upper(),
        provider_symbol=provider_symbol.strip().upper() if provider_symbol else None,
        sector=sector.strip() if sector else None,
        industry=industry.strip() if industry else None,
    )
    session.add(company)
    session.commit()
    return company


def get_or_create_from_candidate(session: Session, candidate: CompanyCandidate) -> Company:
    legacy_symbol = candidate.provider_symbol if candidate.provider in {None, "eodhd"} else None
    return get_or_create_company(
        session,
        name=candidate.name,
        ticker=candidate.ticker,
        isin=candidate.isin,
        exchange=candidate.exchange,
        country=candidate.country,
        currency=candidate.currency,
        provider_symbol=legacy_symbol,
        sector=candidate.sector,
        industry=candidate.industry,
    )


def list_companies(session: Session) -> list[Company]:
    query = select(Company).order_by(Company.name.asc(), Company.ticker.asc())
    return list(session.scalars(query).all())


def search_company_candidates(session: Session, query: str) -> list[CompanyCandidate]:
    """Search locally known companies and the small reference registry.

    Online provider discovery is intentionally explicit in the UI because Alpha Vantage
    SYMBOL_SEARCH consumes one free API request. Local search therefore remains quota-free.
    """
    term = query.strip()
    if not term:
        return list(REFERENCE_COMPANIES)

    like = f"%{term}%"
    persisted = list(
        session.scalars(
            select(Company).where(
                or_(
                    Company.name.ilike(like),
                    Company.ticker.ilike(like),
                    Company.isin.ilike(like),
                    Company.provider_symbol.ilike(like),
                )
            )
        ).all()
    )

    candidates: dict[tuple[str, str | None], CompanyCandidate] = {}
    for company in persisted:
        candidate = CompanyCandidate(
            name=company.name,
            ticker=company.ticker,
            isin=company.isin,
            exchange=company.exchange,
            country=company.country,
            currency=company.currency,
            provider_symbol=company.provider_symbol,
            sector=company.sector,
            industry=company.industry,
        )
        candidates[(candidate.ticker, candidate.exchange)] = candidate

    normalized = term.casefold()
    for candidate in REFERENCE_COMPANIES:
        haystack = " ".join(
            value
            for value in [
                candidate.name,
                candidate.ticker,
                candidate.isin,
                candidate.provider_symbol,
                candidate.exchange,
            ]
            if value
        ).casefold()
        if normalized in haystack:
            candidates.setdefault((candidate.ticker, candidate.exchange), candidate)

    return sorted(candidates.values(), key=lambda item: (item.name, item.exchange or ""))
