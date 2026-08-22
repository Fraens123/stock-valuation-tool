from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True)
class NormalizedFinancialFact:
    """Provider-independent financial fact before it is persisted into an analysis snapshot.

    `value` follows the tool's documented economic sign convention. `provider_value`
    preserves the numeric value returned by the provider so transformations remain auditable.
    """

    statement: str
    metric: str
    period_end: date
    period_type: str
    value: Decimal | None
    provider_value: Decimal | None
    currency: str | None
    unit: str
    provider: str
    provider_field: str
    filing_date: date | None = None
    retrieved_at: datetime | None = None
    is_cross_check_only: bool = False
    note: str | None = None


@dataclass(frozen=True)
class NormalizedEstimate:
    metric: str
    period: str
    low: Decimal | None
    average: Decimal | None
    high: Decimal | None
    analyst_count: int | None
    provider: str
    currency: str | None = None
    unit: str | None = None
    retrieved_at: datetime | None = None


@dataclass(frozen=True)
class ProviderCompany:
    name: str
    ticker: str
    provider_symbol: str
    exchange: str | None
    country: str | None
    currency: str | None
    isin: str | None
    sector: str | None = None
    industry: str | None = None
