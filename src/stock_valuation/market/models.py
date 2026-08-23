from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


MARKET_DATA_VERSION = "market-data-v1.0"

AVAILABLE = "AVAILABLE"
UNAVAILABLE = "UNAVAILABLE"
STALE = "STALE"
CURRENCY_MATCH = "CURRENCY_MATCH"
FX_REQUIRED = "FX_REQUIRED"
FX_UNAVAILABLE = "FX_UNAVAILABLE"
ADR_RATIO_REQUIRED = "ADR_RATIO_REQUIRED"
INVALID_SHARE_COUNT = "INVALID_SHARE_COUNT"
DATE_MISMATCH = "DATE_MISMATCH"
VALUATION_NOT_READY = "VALUATION_NOT_READY"
MISSING_PRICE = "MISSING_PRICE"


@dataclass(frozen=True)
class ListingData:
    ticker: str
    exchange: str
    trading_currency: str
    security_type: str
    primary_listing: bool
    isin: str | None = None
    adr_ratio: Decimal | None = None
    underlying_share_ratio: Decimal | None = None
    provider: str | None = None
    source_url: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class NormalizedMarketQuote:
    ticker: str
    exchange: str
    listing_currency: str
    price: Decimal | None
    price_date: date | None
    retrieved_at: datetime
    provider: str
    provider_symbol: str
    source_url: str | None = None
    original_value: Decimal | None = None
    security_type: str = "ordinary_share"


@dataclass(frozen=True)
class NormalizedShareData:
    ticker: str
    shares_outstanding: Decimal | None
    diluted_weighted_average_shares: Decimal | None
    basic_weighted_average_shares: Decimal | None
    fiscal_year: int | None
    share_date: date | None
    filing_date: date | None
    provider: str
    source: str
    source_url: str | None = None
    provider_field: str | None = None
    unit: str = "shares"
    provenance: str | None = None


@dataclass(frozen=True)
class FXRate:
    from_currency: str
    to_currency: str
    rate: Decimal | None
    fx_date: date | None
    provider: str | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class NetDebtInput:
    fiscal_year: int
    value: Decimal | None
    currency: str | None
    source: str
    inputs_hash: str | None = None


@dataclass(frozen=True)
class MarketDataSnapshot:
    company: str
    analysis_as_of_date: date
    listing: ListingData
    quote: NormalizedMarketQuote
    share_data: NormalizedShareData
    financial_statement_currency: str
    net_debt: NetDebtInput | None = None
    fx_rate: FXRate | None = None
    snapshot_id: str | None = None


@dataclass(frozen=True)
class DerivedMarketMetric:
    metric_id: str
    value: Decimal | None
    currency: str | None
    status: str
    issues: tuple[str, ...]
    input_refs: tuple[str, ...]
    inputs_hash: str
    market_data_version: str = MARKET_DATA_VERSION
