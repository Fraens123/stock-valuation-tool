from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal


VALUATION_ENGINE_VERSION = "valuation-v1.0"

AVAILABLE = "AVAILABLE"
UNAVAILABLE = "UNAVAILABLE"
NOT_MEANINGFUL = "NOT_MEANINGFUL"
FX_REQUIRED = "FX_REQUIRED"
INVALID_ASSUMPTION = "INVALID_ASSUMPTION"
INVALID_SHARE_COUNT = "INVALID_SHARE_COUNT"
ADR_RATIO_REQUIRED = "ADR_RATIO_REQUIRED"
GENERIC_ASSUMPTION_SOURCE = "GENERIC_V1_DEFAULT"
ASSUMPTIONS_NOT_COMPANY_SPECIFIC = "ASSUMPTIONS_NOT_COMPANY_SPECIFIC"


@dataclass(frozen=True)
class FinancialPoint:
    metric_id: str
    fiscal_year: int
    value: Decimal | None
    currency: str
    status: str
    input_ref: str
    inputs_hash: str


@dataclass(frozen=True)
class MarketSnapshotInput:
    ticker: str
    company: str
    analysis_as_of_date: str
    market_snapshot_id: str
    market_data_version: str
    security_type: str
    price: Decimal | None
    market_cap: Decimal | None
    enterprise_value: Decimal | None
    shares_outstanding: Decimal | None
    share_basis: str
    financial_currency: str
    trading_currency: str
    fx_rate: Decimal | None
    adr_ratio: Decimal | None
    underlying_share_ratio: Decimal | None
    input_refs: tuple[str, ...]
    inputs_hash: str


@dataclass(frozen=True)
class ValuationMetricResult:
    metric_id: str
    fiscal_year: int | None
    method: str
    value: Decimal | None
    unit: str
    currency: str | None
    status: str
    issues: tuple[str, ...]
    input_refs: tuple[str, ...]
    inputs_hash: str
    valuation_version: str = VALUATION_ENGINE_VERSION


@dataclass(frozen=True)
class NormalizedValue:
    metric_id: str
    method: str
    value: Decimal | None
    currency: str
    status: str
    issues: tuple[str, ...]
    input_refs: tuple[str, ...]
    inputs_hash: str
    used_fiscal_years: tuple[int, ...] = ()
    input_values: tuple[Decimal, ...] = ()


@dataclass(frozen=True)
class DCFScenario:
    scenario: str
    projection_years: int
    annual_growth_rate: Decimal
    discount_rate: Decimal
    terminal_growth_rate: Decimal
    assumption_source: str = GENERIC_ASSUMPTION_SOURCE


@dataclass(frozen=True)
class DCFProjectionRow:
    ticker: str
    scenario: str
    year_index: int
    projected_fcf: Decimal
    present_value: Decimal


@dataclass(frozen=True)
class DCFResult:
    ticker: str
    scenario: str
    status: str
    equity_value: Decimal | None
    currency: str
    terminal_value: Decimal | None
    projected_rows: tuple[DCFProjectionRow, ...]
    issues: tuple[str, ...]
    input_refs: tuple[str, ...]
    inputs_hash: str
    valuation_version: str = VALUATION_ENGINE_VERSION


@dataclass(frozen=True)
class ValuationSummary:
    ticker: str
    company: str
    scenario: str
    status: str
    fair_value_per_unit: Decimal | None
    trading_currency: str
    market_price: Decimal | None
    upside_downside: Decimal | None
    margin_of_safety: Decimal | None
    issues: tuple[str, ...]
    input_refs: tuple[str, ...]
    inputs_hash: str
    valuation_version: str = VALUATION_ENGINE_VERSION


@dataclass(frozen=True)
class ValuationSnapshot:
    analysis_id: str
    analysis_as_of_date: str
    market_snapshot_id: str
    market_data_version: str
    financial_data_reference: str
    calculation_version: str
    historical_analysis_version: str
    quality_version: str
    valuation_version: str
    assumptions: dict
    assumptions_hash: str
    normalized_inputs: dict
    valuation_results: dict
    quality_context: dict
    historical_context: dict
    input_refs: tuple[str, ...]
    inputs_hash: str
    created_at: str
    snapshot_id: str


def stable_hash(parts: tuple[str, ...]) -> str:
    return hashlib.sha256("|".join(sorted(parts)).encode("utf-8")).hexdigest()
