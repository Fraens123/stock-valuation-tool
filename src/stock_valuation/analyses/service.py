from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from stock_valuation.companies.service import get_or_create_company as company_get_or_create
from stock_valuation.database.models import (
    Analysis,
    AnalysisStatus,
    Company,
    QualitativeAssessment,
    ValuationAssumption,
)


class AnalysisFrozenError(ValueError):
    """Raised when content of a completed/archived analysis would be modified."""


class InvalidAnalysisTransition(ValueError):
    """Raised for invalid lifecycle transitions."""


def get_or_create_company(*args, **kwargs) -> Company:
    """Backward-compatible wrapper; company logic lives in companies.service."""
    return company_get_or_create(*args, **kwargs)


def get_analysis(session: Session, analysis_id: int) -> Analysis | None:
    return session.scalar(
        select(Analysis)
        .options(selectinload(Analysis.company))
        .where(Analysis.id == analysis_id)
    )


def create_analysis(
    session: Session,
    *,
    company: Company,
    as_of_date: date,
    previous_analysis: Analysis | None = None,
) -> Analysis:
    max_revision = session.scalar(
        select(func.max(Analysis.revision_number)).where(Analysis.company_id == company.id)
    )
    analysis = Analysis(
        company_id=company.id,
        as_of_date=as_of_date,
        revision_number=(max_revision or 0) + 1,
        previous_analysis_id=previous_analysis.id if previous_analysis else None,
        status=AnalysisStatus.DRAFT,
        market_price_currency=company.currency,
    )
    session.add(analysis)
    session.commit()
    return analysis


def list_analyses(
    session: Session,
    company_id: int | None = None,
    *,
    include_archived: bool = False,
) -> list[Analysis]:
    query = (
        select(Analysis)
        .options(selectinload(Analysis.company))
        .order_by(Analysis.as_of_date.desc(), Analysis.revision_number.desc())
    )
    if company_id is not None:
        query = query.where(Analysis.company_id == company_id)
    if not include_archived:
        query = query.where(Analysis.status != AnalysisStatus.ARCHIVED)
    return list(session.scalars(query).all())


def ensure_editable(analysis: Analysis) -> None:
    """Public domain guard used by all services that mutate an analysis snapshot."""
    if analysis.status in {AnalysisStatus.COMPLETED, AnalysisStatus.ARCHIVED}:
        raise AnalysisFrozenError(
            "Abgeschlossene oder archivierte Analysen sind eingefroren. "
            "Zum Aktualisieren eine neue Revision erstellen."
        )


def update_analysis_metadata(
    session: Session,
    analysis: Analysis,
    *,
    title: str | None,
    notes: str | None,
    market_price: Decimal | float | None,
    market_price_currency: str | None = None,
) -> Analysis:
    ensure_editable(analysis)
    analysis.title = title.strip() if title else None
    analysis.notes = notes.strip() if notes else None
    analysis.market_price = Decimal(str(market_price)) if market_price is not None else None
    analysis.market_price_currency = (
        market_price_currency.strip().upper()
        if market_price_currency
        else analysis.company.currency
    )
    session.commit()
    return analysis


def mark_in_progress(session: Session, analysis: Analysis) -> Analysis:
    ensure_editable(analysis)
    if analysis.status == AnalysisStatus.DRAFT:
        analysis.status = AnalysisStatus.IN_PROGRESS
        session.commit()
    return analysis


def complete_analysis(session: Session, analysis: Analysis) -> Analysis:
    ensure_editable(analysis)
    if analysis.status not in {AnalysisStatus.DRAFT, AnalysisStatus.IN_PROGRESS}:
        raise InvalidAnalysisTransition(
            f"Analyse kann aus Status {analysis.status.value} nicht abgeschlossen werden."
        )
    analysis.status = AnalysisStatus.COMPLETED
    analysis.completed_at = datetime.utcnow()
    session.commit()
    return analysis


def archive_analysis(session: Session, analysis: Analysis) -> Analysis:
    if analysis.status != AnalysisStatus.COMPLETED:
        raise InvalidAnalysisTransition("Nur abgeschlossene Analysen können archiviert werden.")
    analysis.status = AnalysisStatus.ARCHIVED
    session.commit()
    return analysis


def create_revision(
    session: Session,
    *,
    source: Analysis,
    as_of_date: date,
    copy_qualitative: bool = True,
    copy_valuation_assumptions: bool = False,
) -> Analysis:
    """Create a new editable revision without changing the source snapshot.

    Financial facts, estimates, guidance and market data are intentionally NOT copied:
    they must be refreshed for the new snapshot. User-owned context can be carried
    forward explicitly as a starting point and must then be reviewed.
    """
    if source.status != AnalysisStatus.COMPLETED:
        raise InvalidAnalysisTransition(
            "Eine neue Revision soll aus einer abgeschlossenen Analyse erstellt werden."
        )

    new_analysis = create_analysis(
        session,
        company=source.company,
        as_of_date=as_of_date,
        previous_analysis=source,
    )
    new_analysis.title = source.title
    new_analysis.notes = source.notes

    if copy_qualitative:
        rows = session.scalars(
            select(QualitativeAssessment).where(QualitativeAssessment.analysis_id == source.id)
        ).all()
        for row in rows:
            session.add(
                QualitativeAssessment(
                    analysis_id=new_analysis.id,
                    criterion_id=row.criterion_id,
                    rating_key=row.rating_key,
                    rating_numeric=row.rating_numeric,
                    comment=row.comment,
                    source_note=row.source_note,
                    source_url=row.source_url,
                    needs_review=True,
                )
            )

    if copy_valuation_assumptions:
        rows = session.scalars(
            select(ValuationAssumption).where(ValuationAssumption.analysis_id == source.id)
        ).all()
        for row in rows:
            session.add(
                ValuationAssumption(
                    analysis_id=new_analysis.id,
                    method=row.method,
                    scenario=row.scenario,
                    key=row.key,
                    value=row.value,
                    unit=row.unit,
                    source_type="carried_forward",
                    note=row.note,
                )
            )

    session.commit()
    return new_analysis
