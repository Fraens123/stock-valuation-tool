from __future__ import annotations

import enum
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for persisted audit fields."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class AnalysisStatus(str, enum.Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    ticker: Mapped[str] = mapped_column(String(40), index=True)
    isin: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="EUR")
    sector: Mapped[str | None] = mapped_column(String(160), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(160), nullable=True)
    # Legacy/default symbol kept for EODHD/backward compatibility. New provider-specific
    # identifiers belong in CompanyProviderSymbol.
    provider_symbol: Mapped[str | None] = mapped_column(String(80), nullable=True)

    analyses: Mapped[list[Analysis]] = relationship(back_populates="company")
    provider_symbols: Mapped[list[CompanyProviderSymbol]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class CompanyProviderSymbol(Base):
    """Persist a provider-specific identifier without overloading Company.ticker.

    One company may need different identifiers for local market prices and fundamentals;
    ASML is the first reference case (`ASML.AMS` vs `ASML`). The table is generic and is
    created safely in existing SQLite databases by SQLAlchemy `create_all`.
    """

    __tablename__ = "company_provider_symbols"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    provider: Mapped[str] = mapped_column(String(80), index=True)
    purpose: Mapped[str] = mapped_column(String(40), default="fundamentals", index=True)
    symbol: Mapped[str] = mapped_column(String(120), index=True)
    exchange: Mapped[str | None] = mapped_column(String(120), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    company: Mapped[Company] = relationship(back_populates="provider_symbols")


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    as_of_date: Mapped[date] = mapped_column(Date, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, default=1)
    previous_analysis_id: Mapped[int | None] = mapped_column(
        ForeignKey("analyses.id"), nullable=True
    )
    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus), default=AnalysisStatus.DRAFT
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    market_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    market_price_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    company: Mapped[Company] = relationship(back_populates="analyses")
    previous_analysis: Mapped[Analysis | None] = relationship(remote_side=[id])


class FinancialFactSnapshot(Base):
    __tablename__ = "financial_fact_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)
    statement: Mapped[str] = mapped_column(String(40))
    metric: Mapped[str] = mapped_column(String(160), index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    period_type: Mapped[str] = mapped_column(String(20))
    value: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    provider_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    provider_field: Mapped[str | None] = mapped_column(String(160), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    filing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_restated: Mapped[bool] = mapped_column(Boolean, default=False)
    is_cross_check_only: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class FinancialAdjustmentSnapshot(Base):
    __tablename__ = "financial_adjustment_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)
    metric: Mapped[str] = mapped_column(String(160), index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(30, 8))
    category: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    included_in_normalized: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EstimateSnapshot(Base):
    __tablename__ = "estimate_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)
    metric: Mapped[str] = mapped_column(String(160), index=True)
    period: Mapped[str] = mapped_column(String(40))
    low: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    average: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    high: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    analyst_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class GuidanceSnapshot(Base):
    __tablename__ = "guidance_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)
    metric: Mapped[str] = mapped_column(String(160), index=True)
    period: Mapped[str] = mapped_column(String(40))
    low: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    high: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    point_estimate: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ManualInputSnapshot(Base):
    __tablename__ = "manual_input_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)
    metric: Mapped[str] = mapped_column(String(160), index=True)
    period: Mapped[str | None] = mapped_column(String(40), nullable=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_name: Mapped[str] = mapped_column(String(120), default="Aktienfinder")
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    overrides_metric: Mapped[str | None] = mapped_column(String(160), nullable=True)


class OperatingFactSnapshot(Base):
    __tablename__ = "operating_fact_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)
    metric: Mapped[str] = mapped_column(String(160), index=True)
    period: Mapped[str] = mapped_column(String(40), index=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)
    metric_id: Mapped[str] = mapped_column(String(160), index=True)
    period: Mapped[str] = mapped_column(String(40), index=True)
    basis: Mapped[str] = mapped_column(String(24), default="reported")
    value: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    calculation_version: Mapped[str] = mapped_column(String(40), default="0.1")
    inputs_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)


class MarketDataSnapshotRecord(Base):
    __tablename__ = "market_data_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)
    snapshot_id: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    analysis_as_of_date: Mapped[date] = mapped_column(Date, index=True)
    provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    provider_symbol: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ticker: Mapped[str] = mapped_column(String(80), index=True)
    exchange: Mapped[str | None] = mapped_column(String(120), nullable=True)
    security_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    trading_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    financial_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    price_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    shares_outstanding: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    share_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    share_basis: Mapped[str | None] = mapped_column(String(40), nullable=True)
    filing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(30, 12), nullable=True)
    fx_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    net_debt_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    inputs_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ValuationSnapshotRecord(Base):
    __tablename__ = "valuation_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)
    snapshot_id: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    analysis_as_of_date: Mapped[date] = mapped_column(Date, index=True)
    market_snapshot_id: Mapped[str] = mapped_column(String(160), index=True)
    market_data_version: Mapped[str] = mapped_column(String(80))
    financial_data_reference: Mapped[str] = mapped_column(Text)
    calculation_version: Mapped[str] = mapped_column(String(80))
    historical_analysis_version: Mapped[str] = mapped_column(String(80))
    quality_version: Mapped[str] = mapped_column(String(80))
    valuation_version: Mapped[str] = mapped_column(String(80))
    assumptions_hash: Mapped[str] = mapped_column(String(128), index=True)
    inputs_hash: Mapped[str] = mapped_column(String(128), index=True)
    ticker: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    base_fair_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    trading_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    assumption_source: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class QualitativeAssessment(Base):
    __tablename__ = "qualitative_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)
    criterion_id: Mapped[str] = mapped_column(String(160), index=True)
    rating_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    rating_numeric: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)


class ValuationAssumption(Base):
    __tablename__ = "valuation_assumptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)
    method: Mapped[str] = mapped_column(String(80), index=True)
    scenario: Mapped[str] = mapped_column(String(40), default="base")
    key: Mapped[str] = mapped_column(String(160), index=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class AssumptionApprovalRecord(Base):
    __tablename__ = "assumption_approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)
    method: Mapped[str] = mapped_column(String(80), index=True)
    scenario: Mapped[str] = mapped_column(String(40), default="base", index=True)
    key: Mapped[str] = mapped_column(String(160), index=True)
    recommended_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    approved_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_type: Mapped[str] = mapped_column(String(80), index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation_inputs_hash: Mapped[str] = mapped_column(String(128), index=True)
    policy_version: Mapped[str] = mapped_column(String(80), index=True)
    engine_version: Mapped[str] = mapped_column(String(80), index=True)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ValuationResult(Base):
    __tablename__ = "valuation_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)
    method: Mapped[str] = mapped_column(String(80), index=True)
    scenario: Mapped[str] = mapped_column(String(40), default="base")
    metric: Mapped[str] = mapped_column(String(160), index=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    calculation_version: Mapped[str] = mapped_column(String(40), default="0.1")


class InvestmentThesis(Base):
    __tablename__ = "investment_theses"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), unique=True, index=True)
    thesis_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_drivers: Mapped[str | None] = mapped_column(Text, nullable=True)
    risks: Mapped[str | None] = mapped_column(Text, nullable=True)
    invalidation_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    watch_items: Mapped[str | None] = mapped_column(Text, nullable=True)
