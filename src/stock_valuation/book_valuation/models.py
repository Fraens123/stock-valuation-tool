from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


BOOK_VALUATION_VERSION = "excel-book-valuation-v1.0"

AVAILABLE = "AVAILABLE"
UNAVAILABLE = "UNAVAILABLE"
NOT_MEANINGFUL = "NOT_MEANINGFUL"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
INVALID_ASSUMPTION = "INVALID_ASSUMPTION"


@dataclass(frozen=True)
class BookValue:
    key: str
    value: Decimal | None
    unit: str
    status: str
    issues: tuple[str, ...]
    input_refs: tuple[str, ...]
    inputs_hash: str
    method_version: str = BOOK_VALUATION_VERSION
    note: str | None = None


@dataclass(frozen=True)
class OwnerEarningsYear:
    fiscal_year: int
    net_income: BookValue
    revenue: BookValue
    owner_earnings_capex: BookValue
    capex_to_revenue: BookValue
    depreciation_amortization: BookValue
    depreciation_to_capex: BookValue
    operating_working_capital: BookValue
    operating_working_capital_to_revenue: BookValue
    change_in_operating_working_capital: BookValue
    owner_earnings: BookValue


@dataclass(frozen=True)
class DiscountRateResult:
    fair_pe: BookValue
    risk_premium: BookValue
    risk_free_rate: BookValue
    minimum_return_addon: BookValue
    cost_of_equity: BookValue


@dataclass(frozen=True)
class PresentValueRow:
    year_index: int
    owner_earnings: BookValue
    discount_factor: BookValue
    present_value: BookValue


@dataclass(frozen=True)
class TerminalValueResult:
    terminal_growth_rate: BookValue
    terminal_value: BookValue
    present_value_terminal_value: BookValue


@dataclass(frozen=True)
class FairValueResult:
    shares_outstanding: BookValue
    present_value_owner_earnings_sum: BookValue
    present_value_terminal_value: BookValue
    equity_value: BookValue
    fair_value_per_share: BookValue
    margin_of_safety: BookValue
    fair_value_after_safety_margin: BookValue
    market_price: BookValue
    valuation_gap: BookValue


@dataclass(frozen=True)
class MultiplicatorMethodResult:
    base_pe: BookValue
    financial_stability_addon: BookValue
    market_position_points: BookValue
    market_position_addon: BookValue
    profitability_multiplier: BookValue
    market_profitability_addon: BookValue
    growth_addon: BookValue
    individuality_addon: BookValue
    fair_pe: BookValue
    forecast_net_income: BookValue
    shares_outstanding: BookValue
    forecast_eps: BookValue
    fair_price_per_share: BookValue


@dataclass(frozen=True)
class BookValuationAnalysisResult:
    method_version: str
    owner_earnings_history: tuple[OwnerEarningsYear, ...]
    owner_earnings_forecast: tuple[PresentValueRow, ...]
    discount_rate_result: DiscountRateResult
    terminal_value_result: TerminalValueResult
    fair_value_result: FairValueResult
    multiplicator_method_result: MultiplicatorMethodResult
    market_inputs: dict[str, Any]
    manual_inputs: dict[str, Any]
    values: dict[str, BookValue]
    warnings: tuple[str, ...]
    review_required: bool
    input_refs: tuple[str, ...]
    inputs_hash: str


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()


def unavailable(key: str, unit: str, issues: tuple[str, ...], refs: tuple[str, ...] = ()) -> BookValue:
    return BookValue(key, None, unit, UNAVAILABLE, issues, refs, stable_hash((key, issues, refs)))


def available(key: str, value: Decimal, unit: str, refs: tuple[str, ...], *parts: Any, note: str | None = None) -> BookValue:
    return BookValue(key, value, unit, AVAILABLE, (), refs, stable_hash((key, value, refs, parts)), note=note)
