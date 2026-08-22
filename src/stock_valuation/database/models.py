from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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
    provider_symbol: Mapped[str | None] = mapped_column(String(80), nullable=True)

    analyses: Mapped[list[Analysis]] = relationship(back_populates="company")


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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
    period_end: Mapped[date] = mapped_column(Date)
    period_type: Mapped[str] = mapped_column(String(20))
    value: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


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
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


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
    entered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


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
