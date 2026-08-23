from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_valuation.analyses.estimate_service import (
    estimate_period_type,
    infer_fiscal_year_end_month_day,
)
from stock_valuation.database.models import Analysis, EstimateSnapshot, GuidanceSnapshot
from stock_valuation.valuation_assumptions.models import (
    AVAILABLE,
    LOW,
    LOOKAHEAD_BLOCKED,
    MEDIUM,
    AssumptionEvidence,
)


def decimal_or_none(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def evidence_from_historical_context(ticker: str, context: dict) -> tuple[AssumptionEvidence, ...]:
    output: list[AssumptionEvidence] = []
    for key, metric in (("revenue_growth", "revenue"), ("earnings_growth", "net_income"), ("fcf_growth", "free_cash_flow")):
        for item in context.get(key, []):
            evidence_id = f"{ticker}:historical:yoy:{metric}:{item.get('fiscal_year')}"
            output.append(
                AssumptionEvidence(
                    evidence_id,
                    metric,
                    decimal_or_none(item.get("value")),
                    "decimal_ratio",
                    str(item.get("fiscal_year", "")),
                    "YoY",
                    "HISTORICAL_ANALYSIS",
                    evidence_id,
                    None,
                    AVAILABLE,
                    MEDIUM,
                )
            )
    for metric, windows in context.get("cagr", {}).items():
        for window, value in windows.items():
            evidence_id = f"{ticker}:historical:cagr:{metric}:{window}"
            output.append(
                AssumptionEvidence(
                    evidence_id,
                    metric,
                    decimal_or_none(value),
                    "decimal_ratio",
                    window,
                    "CAGR",
                    "HISTORICAL_ANALYSIS",
                    evidence_id,
                    None,
                    AVAILABLE,
                    MEDIUM if window == "5Y_CAGR" else LOW,
                )
            )
    for metric, value in context.get("margin_trend", {}).items():
        evidence_id = f"{ticker}:historical:margin_trend:{metric}"
        output.append(
            AssumptionEvidence(
                evidence_id,
                metric,
                decimal_or_none(value),
                "decimal_ratio_delta",
                str(context.get("historical_window", "")),
                "trend",
                "HISTORICAL_ANALYSIS",
                evidence_id,
                None,
                AVAILABLE,
                MEDIUM,
            )
        )
    for bucket in ("volatility", "negative_years", "missing_years"):
        for metric, value in context.get(bucket, {}).items():
            evidence_id = f"{ticker}:historical:{bucket}:{metric}"
            output.append(
                AssumptionEvidence(
                    evidence_id,
                    metric,
                    decimal_or_none(value),
                    "count" if bucket != "volatility" else "various",
                    str(context.get("historical_window", "")),
                    bucket,
                    "HISTORICAL_ANALYSIS",
                    evidence_id,
                    None,
                    AVAILABLE,
                    MEDIUM,
                )
            )
    return tuple(output)


def collect_forward_evidence(
    session: Session,
    analysis: Analysis,
    *,
    latest_actuals: dict[str, dict] | None = None,
) -> tuple[AssumptionEvidence, ...]:
    output: list[AssumptionEvidence] = []
    latest_actuals = latest_actuals or {}
    fiscal_year_end = infer_fiscal_year_end_month_day([])
    estimates = session.scalars(select(EstimateSnapshot).where(EstimateSnapshot.analysis_id == analysis.id)).all()
    for row in estimates:
        source_date = row.retrieved_at.date() if row.retrieved_at else analysis.as_of_date
        period_type = _period_type(row.period, fiscal_year_end=fiscal_year_end)
        status = _forward_status(source_date, analysis.as_of_date, period_type)
        for field, value in (("low", row.low), ("average", row.average), ("high", row.high)):
            evidence_id = f"estimate:{row.id}:{row.metric}:{row.period}:{field}"
            growth_value, growth_note = _derive_forward_growth(row.metric, value, row.unit, row.currency, latest_actuals)
            metric = f"forward_{row.metric}_growth_{field}" if growth_value is not None else row.metric
            output.append(
                AssumptionEvidence(
                    evidence_id,
                    metric,
                    growth_value if growth_value is not None else decimal_or_none(value),
                    "decimal_ratio" if growth_value is not None else row.unit or "",
                    row.period,
                    f"{field}:{period_type}",
                    "ANALYST_ESTIMATE",
                    evidence_id,
                    source_date.isoformat(),
                    status,
                    MEDIUM if row.analyst_count and row.analyst_count >= 5 else LOW,
                    f"provider={row.provider or ''};analyst_count={row.analyst_count or ''};{growth_note}",
                )
            )
    guidance = session.scalars(select(GuidanceSnapshot).where(GuidanceSnapshot.analysis_id == analysis.id)).all()
    for row in guidance:
        source_date = row.publication_date or analysis.as_of_date
        period_type = _period_type(row.period, fiscal_year_end=fiscal_year_end)
        status = _forward_status(source_date, analysis.as_of_date, period_type)
        for field, value in (("low", row.low), ("point_estimate", row.point_estimate), ("high", row.high)):
            evidence_id = f"guidance:{row.id}:{row.metric}:{row.period}:{field}"
            growth_value, growth_note = _derive_forward_growth(row.metric, value, row.unit, row.currency, latest_actuals)
            metric = f"forward_{row.metric}_growth_{field}" if growth_value is not None else row.metric
            output.append(
                AssumptionEvidence(
                    evidence_id,
                    metric,
                    growth_value if growth_value is not None else decimal_or_none(value),
                    "decimal_ratio" if growth_value is not None else row.unit or "",
                    row.period,
                    f"{field}:{period_type}",
                    "MANAGEMENT_GUIDANCE",
                    evidence_id,
                    source_date.isoformat(),
                    status,
                    MEDIUM,
                    growth_note,
                )
            )
    return tuple(output)


def date_from_iso(value: str) -> date:
    return datetime.fromisoformat(value).date()


def _period_type(period: str, *, fiscal_year_end: tuple[int, int] | None) -> str:
    normalized = (period or "").upper()
    if normalized.startswith("FY") or "FULL" in normalized or "YEAR" in normalized:
        return "annual"
    classified = estimate_period_type(period, fiscal_year_end=fiscal_year_end)
    if classified == "Jahr":
        return "annual"
    if classified == "Quartal":
        return "quarterly"
    return "unknown"


def _forward_status(source_date: date, as_of_date: date, period_type: str) -> str:
    if source_date > as_of_date:
        return LOOKAHEAD_BLOCKED
    if period_type == "annual":
        return AVAILABLE
    if period_type == "quarterly":
        return "NOT_USED_FOR_ANNUAL_DCF_GROWTH"
    return "FORWARD_PERIOD_TYPE_UNCERTAIN"


def _derive_forward_growth(
    metric: str,
    estimate_value,
    unit: str | None,
    currency: str | None,
    latest_actuals: dict[str, dict],
) -> tuple[Decimal | None, str]:
    estimate = decimal_or_none(estimate_value)
    actual = latest_actuals.get(metric)
    if estimate is None or actual is None:
        return None, "forward_growth_unavailable"
    actual_value = decimal_or_none(actual.get("value"))
    if actual_value is None or actual_value == 0:
        return None, "reference_level_unavailable"
    actual_unit = actual.get("unit")
    actual_currency = actual.get("currency")
    if actual_unit and unit and actual_unit != unit:
        return None, "unit_mismatch"
    if actual_currency and currency and actual_currency != currency:
        return None, "currency_mismatch"
    return estimate / actual_value - Decimal("1"), "derived_forward_growth=estimate/reference_level-1"
