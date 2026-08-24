from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_valuation.data.missing_data_search import (
    MissingDataSearchStatus,
    is_valuation_relevant,
    metric_impacts,
    search_missing_metric_candidates,
)
from stock_valuation.database.models import Analysis, EstimateSnapshot
from stock_valuation.workflow.models import AnalysisState, READY, READY_FOR_PREVIEW


@dataclass(frozen=True)
class ReviewTask:
    id: str
    analysis_id: int
    category: str
    title_de: str
    description_de: str
    metric: str | None
    fiscal_year: int | None
    severity: str
    blocking_for: tuple[str, ...]
    suggested_value: Decimal | None
    source: str | None
    actions: tuple[str, ...]


REVIEW_CATEGORY_DATA = "Daten pruefen"
REVIEW_CATEGORY_MARKET = "Marktdaten pruefen"
REVIEW_CATEGORY_FORECAST = "Prognose ergaenzen"
REVIEW_CATEGORY_DCF = "DCF-Annahme pruefen"
REVIEW_CATEGORY_MULTIPLES = "Multiplikatorenannahme pruefen"


def build_review_tasks(
    session: Session,
    analysis: Analysis,
    state: AnalysisState,
    *,
    book_valuation_result: Any | None = None,
) -> tuple[ReviewTask, ...]:
    tasks: list[ReviewTask] = []
    tasks.extend(_financial_review_tasks(session, analysis, state))
    tasks.extend(_market_review_tasks(analysis, state))
    tasks.extend(_assumption_review_tasks(session, analysis, state))
    tasks.extend(_book_review_tasks(analysis, book_valuation_result))
    return tuple(_dedupe_tasks(tasks))


def priority_tasks(tasks: tuple[ReviewTask, ...]) -> tuple[ReviewTask, ...]:
    return tuple(item for item in tasks if item.severity in {"A", "B"})


def additional_data_hints(tasks: tuple[ReviewTask, ...]) -> tuple[ReviewTask, ...]:
    return tuple(item for item in tasks if item.severity not in {"A", "B"})


def user_status_from_tasks(tasks: tuple[ReviewTask, ...], *, ready_for_final: bool) -> str:
    if ready_for_final:
        return "Analyse abgeschlossen"
    if priority_tasks(tasks):
        return "Pruefung erforderlich"
    return "Analyse bereit"


def _financial_review_tasks(session: Session, analysis: Analysis, state: AnalysisState) -> list[ReviewTask]:
    years = _relevant_years(state, fallback_year=analysis.as_of_date.year)
    latest_year = max(years) if years else analysis.as_of_date.year
    tasks: list[ReviewTask] = []
    seen_metric_year: set[tuple[str, int]] = set()

    financial = state.stages.get("FINANCIAL_DATA")
    for raw in (financial.payload.get("review_required", ()) if financial else ()):
        parsed = _parse_review_required(raw)
        if parsed is None:
            continue
        year, metric, _status = parsed
        if year not in years or not is_valuation_relevant(metric):
            continue
        task = _task_from_missing_search(session, analysis, metric, year)
        if year != latest_year:
            task = replace(
                task,
                severity="C",
                blocking_for=("Weitere Datenhinweise",),
                actions=("Details anzeigen",),
            )
        tasks.append(task)
        seen_metric_year.add((metric, year))

    if financial is not None and financial.status == READY and not financial.payload.get("review_required"):
        return tasks

    for metric in ("short_term_debt", "depreciation_amortization", "intangible_purchases"):
        key = (metric, latest_year)
        if key in seen_metric_year:
            continue
        result = search_missing_metric_candidates(session, analysis, metric=metric, fiscal_year=latest_year)
        if result.status in {
            MissingDataSearchStatus.FOUND_REVIEW_REQUIRED,
            MissingDataSearchStatus.MULTIPLE_CANDIDATES,
            MissingDataSearchStatus.NOT_FOUND,
            MissingDataSearchStatus.NOT_SEPARATELY_REPORTED,
        }:
            if metric == "depreciation_amortization" and result.status == MissingDataSearchStatus.NOT_FOUND:
                continue
            tasks.append(_task_from_search_result(analysis, metric, latest_year, result))
    return tasks


def _market_review_tasks(analysis: Analysis, state: AnalysisState) -> list[ReviewTask]:
    market = state.stages.get("MARKET_DATA")
    if market is None:
        return []
    availability = market.payload.get("availability", {})
    tasks: list[ReviewTask] = []
    if market.status not in {READY, "REVIEW_REQUIRED"}:
        tasks.append(
            _task(
                analysis,
                category=REVIEW_CATEGORY_MARKET,
                title="Marktdaten pruefen",
                description="Kurs, Aktienzahl oder Market Cap konnten nicht vollstaendig automatisch geladen werden.",
                metric="market_data",
                fiscal_year=None,
                severity="A",
                blocking_for=("Bewertung", "Multiplikatoren"),
                suggested_value=None,
                source=None,
                actions=("Erneut versuchen", "Manuell eingeben"),
            )
        )
    elif availability.get("enterprise_value") == "EV_REVIEW_REQUIRED":
        has_short_debt_task = any(
            _parse_review_required(raw) and _parse_review_required(raw)[1] == "short_term_debt"
            for raw in state.stages.get("FINANCIAL_DATA", market).payload.get("review_required", ())
        )
        if not has_short_debt_task:
            tasks.append(
                _task(
                    analysis,
                    category=REVIEW_CATEGORY_MARKET,
                    title="Enterprise Value pruefen",
                    description="Der Unternehmenswert ist noch nicht vollstaendig berechenbar, weil Net Debt fehlt.",
                    metric="enterprise_value",
                    fiscal_year=None,
                    severity="B",
                    blocking_for=("EV", "EV/EBITDA", "EV/Sales"),
                    suggested_value=None,
                    source=None,
                    actions=("Zur Datenpruefung",),
                )
            )
    return tasks


def _assumption_review_tasks(session: Session, analysis: Analysis, state: AnalysisState) -> list[ReviewTask]:
    assumptions = state.stages.get("ASSUMPTIONS")
    tasks: list[ReviewTask] = []
    if assumptions is not None and assumptions.status != READY:
        recommendations = assumptions.payload.get("recommendations", {})
        open_recommendations = []
        for key, item in recommendations.items():
            if item.get("approved_value") is not None or item.get("status") == "APPROVED":
                continue
            open_recommendations.append((key, item))
        if open_recommendations:
            labels = ", ".join(_assumption_title(key) for key, _item in open_recommendations)
            tasks.append(
                _task(
                    analysis,
                    category=REVIEW_CATEGORY_DCF,
                    title="Bewertungsannahmen bestaetigen",
                    description=f"Folgende Vorschlaege muessen vor der finalen Bewertung bestaetigt oder angepasst werden: {labels}.",
                    metric="valuation_assumptions",
                    fiscal_year=None,
                    severity="A",
                    blocking_for=("DCF", "Bewertung"),
                    suggested_value=None,
                    source="Assumption Engine",
                    actions=("Vorschlaege uebernehmen", "Aendern"),
                )
            )
        if assumptions.status not in {READY, READY_FOR_PREVIEW, "REVIEW_REQUIRED"} and not tasks:
            tasks.append(
                _task(
                    analysis,
                    category=REVIEW_CATEGORY_DCF,
                    title="Bewertungsannahmen vorbereiten",
                    description="Die Bewertungsannahmen konnten noch nicht vollstaendig vorbereitet werden.",
                    metric="assumptions",
                    fiscal_year=None,
                    severity="A",
                    blocking_for=("DCF", "Bewertung"),
                    suggested_value=None,
                    source=None,
                    actions=("Zur Analyse",),
                )
            )
    if not _has_forward_net_income_estimate(session, analysis):
        tasks.append(
            _task(
                analysis,
                category=REVIEW_CATEGORY_FORECAST,
                title=f"Jahresueberschuss {analysis.as_of_date.year + 1}e ergaenzen",
                description="Noch keine gespeicherte Schaetzung fuer den naechsten prognostizierten Jahresueberschuss vorhanden.",
                metric="net_income",
                fiscal_year=analysis.as_of_date.year + 1,
                severity="B",
                blocking_for=("Multiplikatorenmethode", "Prognose"),
                suggested_value=None,
                source="Aktienfinder",
                actions=("Wert eingeben",),
            )
        )
    return tasks


def _book_review_tasks(analysis: Analysis, book_valuation_result: Any | None) -> list[ReviewTask]:
    # Book valuation gaps are intentionally not emitted as broad duplicate tasks here.
    # The actionable inputs are surfaced as concrete data, forecast or assumption tasks above.
    return []


def _task_from_missing_search(session: Session, analysis: Analysis, metric: str, year: int) -> ReviewTask:
    result = search_missing_metric_candidates(session, analysis, metric=metric, fiscal_year=year)
    return _task_from_search_result(analysis, metric, year, result)


def _task_from_search_result(
    analysis: Analysis,
    metric: str,
    year: int,
    result,
) -> ReviewTask:
    candidate = result.candidates[0] if result.candidates else None
    value = candidate.value if candidate else None
    source = candidate.provider if candidate else None
    if metric == "short_term_debt":
        title = f"Kurzfristige Finanzschulden {year}"
        description = (
            f"Offizieller Kandidat gefunden: {value} {candidate.currency or ''}. "
            "Der Wert kann nur den kurzfristigen Anteil langfristiger Schulden enthalten."
            if candidate and value is not None
            else "Kurzfristige Finanzschulden fehlen oder muessen manuell bestaetigt werden."
        )
        actions = ("Bestaetigen", "Eigenen Wert verwenden", "Quelle ansehen")
        blocking = ("Nettoverschuldung", "Enterprise Value", "EV/EBITDA")
    elif metric == "intangible_purchases" and result.status == MissingDataSearchStatus.NOT_SEPARATELY_REPORTED:
        title = f"Kaeufe immaterieller Vermoegenswerte {year}"
        description = "Die offizielle Quelle wurde geprueft; die Kennzahl ist nicht separat berichtet."
        actions = ("0 bestaetigen", "Wert eingeben", "Quelle pruefen")
        blocking = ("Owner Earnings",)
    else:
        title = f"{_metric_label(metric)} {year}"
        description = result.message
        actions = ("Pruefen", "Wert eingeben")
        blocking = metric_impacts(metric) or ("Bewertung",)
    return _task(
        analysis,
        category=REVIEW_CATEGORY_DATA,
        title=title,
        description=description,
        metric=metric,
        fiscal_year=year,
        severity="A" if metric in {"short_term_debt", "depreciation_amortization"} else "B",
        blocking_for=tuple(blocking),
        suggested_value=value,
        source=source,
        actions=actions,
    )


def _task(
    analysis: Analysis,
    *,
    category: str,
    title: str,
    description: str,
    metric: str | None,
    fiscal_year: int | None,
    severity: str,
    blocking_for: tuple[str, ...],
    suggested_value: Decimal | None,
    source: str | None,
    actions: tuple[str, ...],
) -> ReviewTask:
    task_id = _stable_task_id(analysis.id, category, metric, fiscal_year, title)
    return ReviewTask(
        id=task_id,
        analysis_id=analysis.id,
        category=category,
        title_de=title,
        description_de=description,
        metric=metric,
        fiscal_year=fiscal_year,
        severity=severity,
        blocking_for=blocking_for,
        suggested_value=suggested_value,
        source=source,
        actions=actions,
    )


def _stable_task_id(
    analysis_id: int,
    category: str,
    metric: str | None,
    fiscal_year: int | None,
    title: str,
) -> str:
    raw = f"{analysis_id}|{category}|{metric or ''}|{fiscal_year or ''}|{title}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _dedupe_tasks(tasks: list[ReviewTask]) -> list[ReviewTask]:
    seen = set()
    output = []
    for task in tasks:
        key = (task.category, task.metric, task.fiscal_year, task.title_de)
        if key in seen:
            continue
        seen.add(key)
        output.append(task)
    order = {"A": 0, "B": 1, "C": 2}
    return sorted(output, key=lambda item: (order.get(item.severity, 9), item.category, item.title_de))


def _parse_review_required(raw: str) -> tuple[int, str, str] | None:
    parts = str(raw).split()
    if len(parts) < 3 or not parts[0].isdigit():
        return None
    return int(parts[0]), parts[1].rstrip(":"), " ".join(parts[2:])


def _relevant_years(state: AnalysisState, *, fallback_year: int) -> set[int]:
    years = sorted(set(int(year) for year in state.history_years if str(year).isdigit()))
    if not years:
        calc = state.stages.get("CALCULATION")
        if calc is not None:
            years = sorted(int(year) for year in calc.payload.get("base_facts", {}) if str(year).isdigit())
    return set((years or [fallback_year])[-5:])


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _has_forward_net_income_estimate(session: Session, analysis: Analysis) -> bool:
    rows = session.scalars(
        select(EstimateSnapshot).where(
            EstimateSnapshot.analysis_id == analysis.id,
            EstimateSnapshot.metric.in_(("net_income", "eps")),
        )
    ).all()
    current_year = analysis.as_of_date.year
    for row in rows:
        year = _period_year(row.period)
        if year is not None and year > current_year:
            return True
    return False


def _period_year(period: str | None) -> int | None:
    if not period:
        return None
    text = str(period)
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def _assumption_title(key: str) -> str:
    return {
        "base_fcf": "Ausgangs-Cashflow bestaetigen",
        "growth_rate": "Wachstumsrate bestaetigen",
        "discount_rate": "Diskontierungszins bestaetigen",
        "terminal_growth_rate": "Ewige Wachstumsrate bestaetigen",
        "projection_years": "Planungszeitraum bestaetigen",
    }.get(key, key.replace("_", " ").title())


def _metric_label(metric: str) -> str:
    return {
        "short_term_debt": "Kurzfristige Finanzschulden",
        "depreciation_amortization": "Abschreibungen und Amortisation",
        "intangible_purchases": "Kaeufe immaterieller Vermoegenswerte",
        "interest_expense": "Zinsaufwand",
    }.get(metric, metric.replace("_", " "))
