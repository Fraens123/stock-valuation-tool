from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from stock_valuation.database.models import Analysis, AnalysisStatus, Company


def get_or_create_company(
    session: Session,
    *,
    name: str,
    ticker: str,
    currency: str = "EUR",
    isin: str | None = None,
    exchange: str | None = None,
    country: str | None = None,
    provider_symbol: str | None = None,
) -> Company:
    company = session.scalar(select(Company).where(Company.ticker == ticker))
    if company:
        return company

    company = Company(
        name=name,
        ticker=ticker,
        isin=isin,
        exchange=exchange,
        country=country,
        currency=currency,
        provider_symbol=provider_symbol,
    )
    session.add(company)
    session.commit()
    return company


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


def list_analyses(session: Session, company_id: int | None = None) -> list[Analysis]:
    query = select(Analysis).order_by(Analysis.as_of_date.desc(), Analysis.revision_number.desc())
    if company_id is not None:
        query = query.where(Analysis.company_id == company_id)
    return list(session.scalars(query).all())


def mark_in_progress(session: Session, analysis: Analysis) -> Analysis:
    if analysis.status == AnalysisStatus.COMPLETED:
        raise ValueError("Eine abgeschlossene Analyse darf nicht wieder geöffnet werden; neue Revision anlegen.")
    analysis.status = AnalysisStatus.IN_PROGRESS
    session.commit()
    return analysis
