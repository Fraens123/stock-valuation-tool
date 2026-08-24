from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import create_analysis, create_revision, mark_in_progress
from stock_valuation.book_valuation.service import build_book_valuation_for_analysis
from stock_valuation.data.sec_history_completion import sync_sec_history_text_candidates
from stock_valuation.data.source_router import FinancialSourceResult, sync_best_available_financials
from stock_valuation.database.models import Analysis, AnalysisStatus, Company
from stock_valuation.market.refresh_service import market_refresh_missing_reason, refresh_market_snapshot_for_analysis
from stock_valuation.workflow.models import AnalysisState, READY
from stock_valuation.workflow.review_tasks import ReviewTask, build_review_tasks, priority_tasks, user_status_from_tasks
from stock_valuation.workflow.service import refresh_local_analysis_stages


@dataclass(frozen=True)
class ProgressStep:
    label_de: str
    status: str
    message_de: str | None = None


@dataclass(frozen=True)
class CompleteAnalysisRunResult:
    analysis_id: int
    status: str
    progress_steps: tuple[ProgressStep, ...]
    review_tasks: tuple[ReviewTask, ...]
    warnings: tuple[str, ...]
    analysis_state: AnalysisState
    market_snapshot_id: str | None
    ready_for_review: bool
    ready_for_final: bool


FinancialSync = Callable[[Session, Analysis], FinancialSourceResult]
MarketRefresh = Callable[[Session, Analysis], str]


def run_complete_analysis(
    session: Session,
    *,
    company_id: int,
    as_of_date: date,
    refresh_market_data: bool = True,
    search_missing_data: bool = True,
    financial_sync: FinancialSync | None = None,
    market_refresh: MarketRefresh | None = None,
) -> CompleteAnalysisRunResult:
    steps: list[ProgressStep] = []
    warnings: list[str] = []

    company = session.get(Company, company_id)
    if company is None:
        raise ValueError("Unternehmen wurde nicht gefunden.")

    analysis = _analysis_for_run(session, company, as_of_date)
    mark_in_progress(session, analysis)
    steps.append(ProgressStep("Unternehmensdaten", "OK", f"{company.name} ist ausgewaehlt."))

    try:
        sync = financial_sync or sync_best_available_financials
        result = sync(session, analysis)
        if result.success:
            steps.append(ProgressStep("Finanzdaten", "OK", f"{result.fact_count} Fakten geladen."))
        else:
            steps.append(ProgressStep("Finanzdaten", "PRUEFUNG", "Keine vollstaendige automatische Quelle gefunden."))
            warnings.extend(_attempt_messages(result))
    except Exception as exc:  # Provider failures must not crash the full user workflow.
        steps.append(ProgressStep("Finanzdaten", "PRUEFUNG", "Finanzdaten konnten nicht vollstaendig geladen werden."))
        warnings.append(str(exc))

    if search_missing_data:
        try:
            completion = sync_sec_history_text_candidates(session, analysis)
            steps.append(
                ProgressStep(
                    "10-Jahres-Historie",
                    "OK" if completion.candidate_count or completion.filings_checked else "OK",
                    f"{completion.candidate_count} ergaenzende Kandidaten gefunden.",
                )
            )
        except Exception as exc:
            steps.append(ProgressStep("10-Jahres-Historie", "PRUEFUNG", "Historie wurde geprueft, aber nicht vollstaendig ergaenzt."))
            warnings.append(str(exc))

    state = refresh_local_analysis_stages(session, analysis)
    steps.append(ProgressStep("Kennzahlen", "OK", "Kennzahlen und Historie wurden soweit moeglich berechnet."))

    market_snapshot_id = state.market_snapshot_id
    if refresh_market_data:
        try:
            refresh = market_refresh or refresh_market_snapshot_for_analysis
            market_snapshot_id = refresh(session, analysis)
            steps.append(ProgressStep("Marktdaten", "OK", "Kurs, Aktienzahl und Market Cap wurden aktualisiert."))
        except Exception as exc:
            steps.append(ProgressStep("Marktdaten", "PRUEFUNG", "Marktdaten konnten gerade nicht aktualisiert werden."))
            warnings.append(market_refresh_missing_reason(exc))
    else:
        steps.append(ProgressStep("Marktdaten", "UEBERSPRUNGEN", "Marktdaten wurden in diesem Lauf nicht aktualisiert."))

    state = refresh_local_analysis_stages(session, analysis)

    try:
        book_valuation = build_book_valuation_for_analysis(session, analysis, state)
        steps.append(ProgressStep("Bewertungsgrundlagen", "OK", "Owner Earnings, DCF und Multiplikatoren wurden vorbereitet."))
    except Exception as exc:
        book_valuation = None
        steps.append(ProgressStep("Bewertungsgrundlagen", "PRUEFUNG", "Bewertung wurde vorbereitet, benoetigt aber noch Eingaben."))
        warnings.append(str(exc))

    state = refresh_local_analysis_stages(session, analysis)
    tasks = build_review_tasks(session, analysis, state, book_valuation_result=book_valuation)
    blocking_tasks = priority_tasks(tasks)
    ready_for_final = not blocking_tasks and state.stages["VALUATION"].status == READY
    status = user_status_from_tasks(tasks, ready_for_final=ready_for_final)
    steps.append(
        ProgressStep(
            "Analysezustand",
            "OK" if not blocking_tasks else "PRUEFUNG",
            "Analyse ist bereit." if not blocking_tasks else f"{len(blocking_tasks)} Punkt(e) benoetigen Pruefung.",
        )
    )

    return CompleteAnalysisRunResult(
        analysis_id=analysis.id,
        status=status,
        progress_steps=tuple(steps),
        review_tasks=tasks,
        warnings=tuple(dict.fromkeys(warnings)),
        analysis_state=state,
        market_snapshot_id=market_snapshot_id,
        ready_for_review=True,
        ready_for_final=ready_for_final,
    )


def _analysis_for_run(session: Session, company: Company, as_of_date: date) -> Analysis:
    existing = session.scalar(
        select(Analysis)
        .where(
            Analysis.company_id == company.id,
            Analysis.as_of_date == as_of_date,
            Analysis.status.in_((AnalysisStatus.DRAFT, AnalysisStatus.IN_PROGRESS)),
        )
        .order_by(Analysis.revision_number.desc())
        .limit(1)
    )
    if existing is not None:
        return existing
    latest = session.scalar(
        select(Analysis)
        .where(Analysis.company_id == company.id)
        .order_by(Analysis.as_of_date.desc(), Analysis.revision_number.desc())
        .limit(1)
    )
    if latest is not None and latest.status == AnalysisStatus.COMPLETED:
        return create_revision(session, source=latest, as_of_date=as_of_date, copy_qualitative=True)
    return create_analysis(session, company=company, as_of_date=as_of_date)


def _attempt_messages(result: FinancialSourceResult) -> list[str]:
    messages = []
    for attempt in result.attempts:
        if attempt.message:
            messages.append(f"{attempt.source}: {attempt.message}")
    return messages
