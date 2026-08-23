from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

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


def collect_forward_evidence(session: Session, analysis: Analysis) -> tuple[AssumptionEvidence, ...]:
    output: list[AssumptionEvidence] = []
    estimates = session.scalars(select(EstimateSnapshot).where(EstimateSnapshot.analysis_id == analysis.id)).all()
    for row in estimates:
        source_date = row.retrieved_at.date() if row.retrieved_at else analysis.as_of_date
        status = AVAILABLE if source_date <= analysis.as_of_date else LOOKAHEAD_BLOCKED
        for field, value in (("low", row.low), ("average", row.average), ("high", row.high)):
            evidence_id = f"estimate:{row.id}:{row.metric}:{row.period}:{field}"
            output.append(
                AssumptionEvidence(
                    evidence_id,
                    row.metric,
                    decimal_or_none(value),
                    row.unit or "",
                    row.period,
                    field,
                    "ANALYST_ESTIMATE",
                    evidence_id,
                    source_date.isoformat(),
                    status,
                    MEDIUM if row.analyst_count and row.analyst_count >= 5 else LOW,
                    f"provider={row.provider or ''};analyst_count={row.analyst_count or ''}",
                )
            )
    guidance = session.scalars(select(GuidanceSnapshot).where(GuidanceSnapshot.analysis_id == analysis.id)).all()
    for row in guidance:
        source_date = row.publication_date or analysis.as_of_date
        status = AVAILABLE if source_date <= analysis.as_of_date else LOOKAHEAD_BLOCKED
        for field, value in (("low", row.low), ("point_estimate", row.point_estimate), ("high", row.high)):
            evidence_id = f"guidance:{row.id}:{row.metric}:{row.period}:{field}"
            output.append(
                AssumptionEvidence(
                    evidence_id,
                    row.metric,
                    decimal_or_none(value),
                    row.unit or "",
                    row.period,
                    field,
                    "MANAGEMENT_GUIDANCE",
                    evidence_id,
                    source_date.isoformat(),
                    status,
                    MEDIUM,
                )
            )
    return tuple(output)


def date_from_iso(value: str) -> date:
    return datetime.fromisoformat(value).date()
