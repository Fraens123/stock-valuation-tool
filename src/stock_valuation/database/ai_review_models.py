from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from stock_valuation.database.models import Base, utc_now


class AIReviewRun(Base):
    __tablename__ = "ai_review_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)
    model: Mapped[str] = mapped_column(String(120))
    years_requested: Mapped[int] = mapped_column(Integer, default=3)
    status: Mapped[str] = mapped_column(String(40), default="completed", index=True)
    response_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    findings: Mapped[list[AIReviewFinding]] = relationship(
        "AIReviewFinding", back_populates="run", cascade="all, delete-orphan"
    )


class AIReviewPackageSnapshot(Base):
    """Immutable exported review package payload.

    The package id is derived from this payload. Import validation must compare the returned
    result against the stored package, not against a later live snapshot that may have changed.
    """

    __tablename__ = "ai_review_package_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)
    package_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    schema_version: Mapped[str] = mapped_column(String(20))
    years_requested: Mapped[int] = mapped_column(Integer)
    payload_json: Mapped[str] = mapped_column(Text)
    content_markdown: Mapped[str] = mapped_column(Text)
    result_filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(40), default="exported", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AIReviewFinding(Base):
    __tablename__ = "ai_review_findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ai_review_runs.id"), index=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    statement: Mapped[str] = mapped_column(String(40))
    metric: Mapped[str] = mapped_column(String(160), index=True)
    imported_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    official_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    deviation_pct: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    verdict: Mapped[str] = mapped_column(String(20), index=True)
    provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    provider_field: Mapped[str | None] = mapped_column(String(160), nullable=True)
    official_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped[AIReviewRun] = relationship("AIReviewRun", back_populates="findings")
