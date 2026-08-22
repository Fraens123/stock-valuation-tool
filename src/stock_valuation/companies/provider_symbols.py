from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_valuation.database.models import Company, CompanyProviderSymbol


def get_provider_symbol(
    session: Session,
    company: Company,
    *,
    provider: str,
    purpose: str = "fundamentals",
) -> CompanyProviderSymbol | None:
    return session.scalar(
        select(CompanyProviderSymbol).where(
            CompanyProviderSymbol.company_id == company.id,
            CompanyProviderSymbol.provider == provider,
            CompanyProviderSymbol.purpose == purpose,
        )
    )


def upsert_provider_symbol(
    session: Session,
    company: Company,
    *,
    provider: str,
    symbol: str,
    purpose: str = "fundamentals",
    exchange: str | None = None,
    currency: str | None = None,
    note: str | None = None,
) -> CompanyProviderSymbol:
    normalized_provider = provider.strip().lower()
    normalized_purpose = purpose.strip().lower()
    normalized_symbol = symbol.strip()
    if not normalized_symbol:
        raise ValueError("Provider-Symbol darf nicht leer sein.")

    row = get_provider_symbol(
        session,
        company,
        provider=normalized_provider,
        purpose=normalized_purpose,
    )
    if row is None:
        row = CompanyProviderSymbol(
            company_id=company.id,
            provider=normalized_provider,
            purpose=normalized_purpose,
            symbol=normalized_symbol,
        )
        session.add(row)

    row.symbol = normalized_symbol
    row.exchange = exchange.strip() if exchange else None
    row.currency = currency.strip().upper() if currency else None
    row.note = note.strip() if note else None
    session.commit()
    return row


def list_provider_symbols(session: Session, company: Company) -> list[CompanyProviderSymbol]:
    return list(
        session.scalars(
            select(CompanyProviderSymbol)
            .where(CompanyProviderSymbol.company_id == company.id)
            .order_by(CompanyProviderSymbol.provider, CompanyProviderSymbol.purpose)
        ).all()
    )
