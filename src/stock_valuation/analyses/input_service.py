from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import ensure_editable
from stock_valuation.data.providers.ecb import RiskFreeRateObservation
from stock_valuation.database.models import (
    Analysis,
    FinancialFactSnapshot,
    GuidanceSnapshot,
    ManualInputSnapshot,
)


def _decimal(value: Decimal | float | int | str | None) -> Decimal | None:
    return Decimal(str(value)) if value not in (None, "") else None


def upsert_manual_input(
    session: Session,
    analysis: Analysis,
    *,
    metric: str,
    period: str | None,
    value: Decimal | float | int | str | None,
    source_name: str = "Aktienfinder",
    currency: str | None = None,
    unit: str | None = None,
    note: str | None = None,
    overrides_metric: str | None = None,
) -> ManualInputSnapshot:
    ensure_editable(analysis)
    row = session.scalar(
        select(ManualInputSnapshot).where(
            ManualInputSnapshot.analysis_id == analysis.id,
            ManualInputSnapshot.metric == metric,
            ManualInputSnapshot.period == period,
            ManualInputSnapshot.source_name == source_name,
        )
    )
    if row is None:
        row = ManualInputSnapshot(
            analysis_id=analysis.id,
            metric=metric,
            period=period,
            source_name=source_name,
        )
        session.add(row)

    row.value = _decimal(value)
    row.currency = currency
    row.unit = unit
    row.note = note.strip() if note else None
    row.overrides_metric = overrides_metric or None
    row.entered_at = datetime.now(UTC)
    session.commit()
    return row


def upsert_manual_financial_override(
    session: Session,
    analysis: Analysis,
    *,
    metric: str,
    period_end: date,
    value: Decimal | float | int | str,
    currency: str | None,
    unit: str | None,
    statement: str,
    source_name: str,
    source_url: str | None = None,
    note: str | None = None,
) -> FinancialFactSnapshot:
    """Store an explicit user-approved correction without deleting provider data.

    Manual overrides live beside the imported rows as `provider=manual_override`. The central
    source resolver gives them highest priority, while the original Alpha-Vantage/primary-source
    facts remain available for audit and comparison.
    """
    ensure_editable(analysis)
    normalized_value = _decimal(value)
    if normalized_value is None:
        raise ValueError("Ein Override benötigt einen Zahlenwert.")

    row = session.scalar(
        select(FinancialFactSnapshot).where(
            FinancialFactSnapshot.analysis_id == analysis.id,
            FinancialFactSnapshot.provider == "manual_override",
            FinancialFactSnapshot.metric == metric,
            FinancialFactSnapshot.period_end == period_end,
            FinancialFactSnapshot.period_type == "FY",
        )
    )
    if row is None:
        row = FinancialFactSnapshot(
            analysis_id=analysis.id,
            provider="manual_override",
            metric=metric,
            period_end=period_end,
            period_type="FY",
        )
        session.add(row)

    row.statement = statement
    row.value = normalized_value
    row.provider_value = normalized_value
    row.currency = currency
    row.unit = unit
    row.provider_field = "manual_override"
    row.source_type = "manual_override"
    row.source_url = source_url.strip() if source_url else None
    row.retrieved_at = datetime.now(UTC)
    row.is_restated = False
    row.is_cross_check_only = False
    source_label = source_name.strip() or "Manuelle Korrektur"
    reason = note.strip() if note else "Keine zusätzliche Begründung angegeben."
    row.note = f"Quelle: {source_label}. {reason}"
    session.commit()
    return row


def remove_manual_financial_override(
    session: Session,
    analysis: Analysis,
    *,
    metric: str,
    period_end: date,
) -> None:
    ensure_editable(analysis)
    session.execute(
        delete(FinancialFactSnapshot).where(
            FinancialFactSnapshot.analysis_id == analysis.id,
            FinancialFactSnapshot.provider == "manual_override",
            FinancialFactSnapshot.metric == metric,
            FinancialFactSnapshot.period_end == period_end,
            FinancialFactSnapshot.period_type == "FY",
        )
    )
    session.commit()


def upsert_guidance(
    session: Session,
    analysis: Analysis,
    *,
    metric: str,
    period: str,
    low: Decimal | float | int | str | None = None,
    point_estimate: Decimal | float | int | str | None = None,
    high: Decimal | float | int | str | None = None,
    currency: str | None = None,
    unit: str | None = None,
    publication_date: date | None = None,
    source_url: str | None = None,
    note: str | None = None,
) -> GuidanceSnapshot:
    ensure_editable(analysis)
    row = session.scalar(
        select(GuidanceSnapshot).where(
            GuidanceSnapshot.analysis_id == analysis.id,
            GuidanceSnapshot.metric == metric,
            GuidanceSnapshot.period == period,
        )
    )
    if row is None:
        row = GuidanceSnapshot(analysis_id=analysis.id, metric=metric, period=period)
        session.add(row)

    row.low = _decimal(low)
    row.point_estimate = _decimal(point_estimate)
    row.high = _decimal(high)
    row.currency = currency
    row.unit = unit
    row.publication_date = publication_date
    row.source_url = source_url.strip() if source_url else None
    row.note = note.strip() if note else None
    session.commit()
    return row


def store_risk_free_rate(
    session: Session,
    analysis: Analysis,
    observation: RiskFreeRateObservation,
) -> FinancialFactSnapshot:
    """Store ECB risk-free rate as a market fact in the current snapshot.

    Internal `value` is decimal (e.g. 0.031), while `provider_value` preserves the
    ECB's percent-per-annum representation (e.g. 3.1).
    """
    ensure_editable(analysis)
    row = session.scalar(
        select(FinancialFactSnapshot).where(
            FinancialFactSnapshot.analysis_id == analysis.id,
            FinancialFactSnapshot.statement == "market",
            FinancialFactSnapshot.metric == "risk_free_rate_eur_aaa_10y",
        )
    )
    if row is None:
        row = FinancialFactSnapshot(
            analysis_id=analysis.id,
            statement="market",
            metric="risk_free_rate_eur_aaa_10y",
            period_end=observation.observation_date,
            period_type="D",
        )
        session.add(row)

    row.period_end = observation.observation_date
    row.value = observation.rate_decimal
    row.provider_value = observation.percent_per_annum
    row.currency = "EUR"
    row.unit = "ratio"
    row.provider = "ecb"
    row.provider_field = observation.series_key
    row.source_type = "provider"
    row.source_url = (
        "https://data.ecb.europa.eu/data/datasets/YC/"
        "YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y"
    )
    row.retrieved_at = observation.retrieved_at
    row.is_restated = False
    row.is_cross_check_only = False
    row.note = "ECB Euro-area AAA 10-year spot yield; provider value is percent p.a."
    session.commit()
    return row
