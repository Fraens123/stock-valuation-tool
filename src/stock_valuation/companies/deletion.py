from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from stock_valuation.database.ai_review_models import AIReviewFinding, AIReviewRun
from stock_valuation.database.models import (
    Analysis,
    Company,
    CompanyProviderSymbol,
    EstimateSnapshot,
    FinancialAdjustmentSnapshot,
    FinancialFactSnapshot,
    GuidanceSnapshot,
    InvestmentThesis,
    ManualInputSnapshot,
    MetricSnapshot,
    OperatingFactSnapshot,
    QualitativeAssessment,
    ValuationAssumption,
    ValuationResult,
)


@dataclass(frozen=True)
class CompanyDeletionSummary:
    companies: int
    analyses: int
    related_rows: int


ANALYSIS_CHILD_MODELS = (
    AIReviewFinding,
    AIReviewRun,
    FinancialFactSnapshot,
    FinancialAdjustmentSnapshot,
    EstimateSnapshot,
    GuidanceSnapshot,
    ManualInputSnapshot,
    OperatingFactSnapshot,
    MetricSnapshot,
    QualitativeAssessment,
    ValuationAssumption,
    ValuationResult,
    InvestmentThesis,
)


def _delete_for_company_ids(
    session: Session,
    company_ids: list[int],
) -> CompanyDeletionSummary:
    ids = sorted({int(company_id) for company_id in company_ids})
    if not ids:
        return CompanyDeletionSummary(companies=0, analyses=0, related_rows=0)

    existing_company_ids = list(
        session.scalars(select(Company.id).where(Company.id.in_(ids))).all()
    )
    if not existing_company_ids:
        return CompanyDeletionSummary(companies=0, analyses=0, related_rows=0)

    analysis_ids = list(
        session.scalars(
            select(Analysis.id).where(Analysis.company_id.in_(existing_company_ids))
        ).all()
    )

    related_rows = 0
    if analysis_ids:
        # Revisionen referenzieren sich selbst über previous_analysis_id. Diese Referenzen werden
        # zuerst gelöst, damit der Löschvorgang auch bei aktivierten SQLite-Foreign-Keys sauber ist.
        session.execute(
            update(Analysis)
            .where(Analysis.previous_analysis_id.in_(analysis_ids))
            .values(previous_analysis_id=None)
        )

        # AIReviewFinding muss vor AIReviewRun entfernt werden; danach können alle übrigen
        # analysebezogenen Snapshot-Tabellen gelöscht werden.
        for model in ANALYSIS_CHILD_MODELS:
            result = session.execute(
                delete(model).where(model.analysis_id.in_(analysis_ids))
            )
            related_rows += int(result.rowcount or 0)

        analyses_result = session.execute(
            delete(Analysis).where(Analysis.id.in_(analysis_ids))
        )
        analyses_deleted = int(analyses_result.rowcount or 0)
    else:
        analyses_deleted = 0

    symbols_result = session.execute(
        delete(CompanyProviderSymbol).where(
            CompanyProviderSymbol.company_id.in_(existing_company_ids)
        )
    )
    related_rows += int(symbols_result.rowcount or 0)

    companies_result = session.execute(
        delete(Company).where(Company.id.in_(existing_company_ids))
    )
    companies_deleted = int(companies_result.rowcount or 0)

    session.commit()
    return CompanyDeletionSummary(
        companies=companies_deleted,
        analyses=analyses_deleted,
        related_rows=related_rows,
    )


def delete_company_completely(
    session: Session,
    company_id: int,
) -> CompanyDeletionSummary:
    """Delete one company and every locally stored analysis artefact belonging to it."""
    return _delete_for_company_ids(session, [company_id])


def delete_all_companies_completely(session: Session) -> CompanyDeletionSummary:
    """Delete the complete local company/analysis dataset while keeping the DB schema intact."""
    company_ids = list(session.scalars(select(Company.id)).all())
    return _delete_for_company_ids(session, company_ids)
