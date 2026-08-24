from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_valuation.data.missing_data_search import (
    MissingDataCandidate,
    MissingDataSearchStatus,
    is_short_term_debt_candidate_field,
    search_missing_metric_candidates,
)
from stock_valuation.data.metric_requirements import METRIC_POLICIES
from stock_valuation.data.preferred_data import PreferredDataState
from stock_valuation.database.models import Analysis, FinancialFactSnapshot


class WorksheetCellStatus(str, Enum):
    PRESENT_RELEASED = "VORHANDEN_UND_FREIGEGEBEN"
    PRESENT_REVIEW_REQUIRED = "VORHANDEN_ABER_PRUEFUNG_ERFORDERLICH"
    OFFICIAL_CANDIDATE_FOUND = "OFFIZIELLER_KANDIDAT_GEFUNDEN"
    DERIVABLE = "ABLEITBAR"
    NOT_FOUND = "NICHT_GEFUNDEN"
    AUTOMATIC_CONFIRMED = "AUTOMATISCH_BESTAETIGT"
    REVIEW_REQUIRED = "PRUEFUNG_ERFORDERLICH"
    MANUAL_CONFIRMED = "MANUELL_BESTAETIGT"
    MANUAL_OVERRIDE = "MANUELL_UEBERSCHRIEBEN"
    CANDIDATE_FOUND = "KANDIDAT_GEFUNDEN"
    MISSING = "FEHLT"
    NOT_SEPARATELY_REPORTED = "NICHT_SEPARAT_BERICHTET"


STATUS_DISPLAY = {
    WorksheetCellStatus.PRESENT_RELEASED: "OK automatisch freigegeben",
    WorksheetCellStatus.PRESENT_REVIEW_REQUIRED: "Pruefung erforderlich",
    WorksheetCellStatus.OFFICIAL_CANDIDATE_FOUND: "Kandidat gefunden",
    WorksheetCellStatus.DERIVABLE: "ableitbar",
    WorksheetCellStatus.NOT_FOUND: "nicht gefunden",
    WorksheetCellStatus.AUTOMATIC_CONFIRMED: "✓ automatisch",
    WorksheetCellStatus.REVIEW_REQUIRED: "⚠ prüfen",
    WorksheetCellStatus.MANUAL_CONFIRMED: "✎ manuell",
    WorksheetCellStatus.MANUAL_OVERRIDE: "✎ überschrieben",
    WorksheetCellStatus.CANDIDATE_FOUND: "? Kandidat",
    WorksheetCellStatus.MISSING: "— fehlt",
    WorksheetCellStatus.NOT_SEPARATELY_REPORTED: "n/a nicht separat berichtet",
}

OPEN_STATUSES = {
    WorksheetCellStatus.PRESENT_REVIEW_REQUIRED,
    WorksheetCellStatus.OFFICIAL_CANDIDATE_FOUND,
    WorksheetCellStatus.DERIVABLE,
    WorksheetCellStatus.NOT_FOUND,
    WorksheetCellStatus.REVIEW_REQUIRED,
    WorksheetCellStatus.CANDIDATE_FOUND,
    WorksheetCellStatus.MISSING,
}


@dataclass(frozen=True)
class WorksheetMetric:
    metric: str
    label: str
    statement: str
    help_text: str


@dataclass(frozen=True)
class WorksheetCandidate:
    fact_id: int
    metric: str
    fiscal_year: int
    value: Decimal | None
    currency: str | None
    provider: str | None
    provider_field: str | None
    source_url: str | None
    filing_date: date | None
    retrieved_at: object | None
    semantic_decision: str
    semantic_reason: str
    selectable_without_review: bool
    rejected_reason: str | None = None
    candidate_type: str | None = None
    confidence: Decimal | None = None
    input_refs: tuple[str, ...] = ()
    formula: str | None = None


@dataclass(frozen=True)
class WorksheetCell:
    metric: str
    label: str
    statement: str
    fiscal_year: int
    status: WorksheetCellStatus
    display: str
    value: Decimal | None = None
    currency: str | None = None
    provider: str | None = None
    provider_field: str | None = None
    source_url: str | None = None
    filing_date: date | None = None
    retrieved_at: object | None = None
    reason: str | None = None
    original_fact_id: int | None = None
    candidate_count: int = 0


@dataclass(frozen=True)
class FinancialWorksheet:
    years: tuple[int, ...]
    sections: dict[str, tuple[WorksheetMetric, ...]]
    cells: dict[tuple[str, int], WorksheetCell]


WORKSHEET_SECTIONS: dict[str, tuple[WorksheetMetric, ...]] = {
    "Gewinn- und Verlustrechnung": (
        WorksheetMetric("revenue", "Umsatz", "income_statement", "Gesamterlöse des Geschäftsjahres."),
        WorksheetMetric("cost_of_revenue", "Umsatzkosten", "income_statement", "Direkt dem Umsatz zuordenbare Kosten."),
        WorksheetMetric("gross_profit", "Bruttoergebnis", "income_statement", "Umsatz abzüglich Umsatzkosten."),
        WorksheetMetric("depreciation_amortization", "Abschreibungen und Amortisation", "cash_flow", "D&A wird für EBITDA benötigt; keine stillen Nullwerte."),
        WorksheetMetric("operating_income", "Betriebsergebnis", "income_statement", "Operatives Ergebnis vor Finanzierung und Steuern."),
        WorksheetMetric("interest_expense", "Zinsaufwand", "income_statement", "Zinsaufwand, sofern separat und passend berichtet."),
        WorksheetMetric("pretax_income", "Gewinn vor Steuern", "income_statement", "Ergebnis vor Ertragsteuern."),
        WorksheetMetric("net_income", "Jahresüberschuss", "income_statement", "Konsolidierter Gewinn nach Steuern."),
    ),
    "Bilanz": (
        WorksheetMetric("cash_and_equivalents", "Liquide Mittel", "balance_sheet", "Zahlungsmittel und Zahlungsmitteläquivalente."),
        WorksheetMetric("short_term_investments", "Kurzfristige Anlagen", "balance_sheet", "Kurzfristige marktgängige Anlagen, sofern separat berichtet."),
        WorksheetMetric("accounts_receivable", "Forderungen", "balance_sheet", "Forderungen aus Lieferungen und Leistungen."),
        WorksheetMetric("inventory", "Vorräte", "balance_sheet", "Nur verwenden, wenn separat berichtet; nie aus fehlendem Fact als 0 ableiten."),
        WorksheetMetric("current_assets", "Umlaufvermögen", "balance_sheet", "Kurzfristige Vermögenswerte."),
        WorksheetMetric("ppe_net", "Sachanlagen", "balance_sheet", "Netto-Sachanlagen ohne separat berichtete Leasing-/ROU-Vermögenswerte."),
        WorksheetMetric("goodwill", "Goodwill", "balance_sheet", "Geschäfts- oder Firmenwert, sofern separat berichtet."),
        WorksheetMetric("total_assets", "Gesamtvermögen", "balance_sheet", "Bilanzsumme."),
        WorksheetMetric("accounts_payable", "Verbindlichkeiten aus Lieferungen und Leistungen", "balance_sheet", "Operative Lieferantenverbindlichkeiten, keine Finanzschulden."),
        WorksheetMetric("short_term_debt", "Kurzfristige Finanzschulden", "balance_sheet", "Zinstragende Finanzschulden fällig innerhalb von 12 Monaten; wichtig für Net Debt und EV."),
        WorksheetMetric("current_liabilities", "Kurzfristige Verbindlichkeiten", "balance_sheet", "Kurzfristige Verbindlichkeiten insgesamt."),
        WorksheetMetric("long_term_debt", "Langfristige Finanzschulden", "balance_sheet", "Nicht kurzfristige zinstragende Finanzschulden."),
        WorksheetMetric("total_liabilities", "Gesamtverbindlichkeiten", "balance_sheet", "Verbindlichkeiten insgesamt."),
        WorksheetMetric("shareholders_equity", "Eigenkapital", "balance_sheet", "Den Aktionären zurechenbares Eigenkapital."),
    ),
    "Cashflow": (
        WorksheetMetric("operating_cash_flow", "Operativer Cashflow", "cash_flow", "Cashflow aus laufender Geschäftstätigkeit."),
        WorksheetMetric("capital_expenditures", "Sachinvestitionen", "cash_flow", "Auszahlungen für Sachanlagen; Vorzeichen wird normalisiert."),
        WorksheetMetric("intangible_purchases", "Käufe immaterieller Vermögenswerte", "cash_flow", "Auszahlungen für immaterielle Vermögenswerte, sofern separat berichtet."),
        WorksheetMetric("dividends_paid", "Dividenden", "cash_flow", "Zahlungswirksam ausgeschüttete Dividenden."),
    ),
}


def worksheet_metrics() -> tuple[WorksheetMetric, ...]:
    rows: list[WorksheetMetric] = []
    for section_rows in WORKSHEET_SECTIONS.values():
        rows.extend(row for row in section_rows if row.metric in METRIC_POLICIES)
    return tuple(rows)


def worksheet_metric_label(metric: str) -> str:
    for row in worksheet_metrics():
        if row.metric == metric:
            return row.label
    return metric.replace("_", " ")


def years_for_mode(years: Iterable[int], mode: str) -> tuple[int, ...]:
    ordered = tuple(sorted(set(int(year) for year in years)))
    if mode == "5 Jahre":
        return ordered[-5:]
    if mode == "10 Jahre":
        return ordered[-10:]
    return ordered


def _all_metric_keys() -> tuple[str, ...]:
    return tuple(row.metric for row in worksheet_metrics())


def _format_value(value: Decimal | None, currency: str | None) -> str:
    if value is None:
        return ""
    text = f"{float(value):,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text} {currency or ''}".strip()


def _state_status(state: PreferredDataState, candidates: tuple[WorksheetCandidate, ...]) -> WorksheetCellStatus:
    fact = state.fact
    if fact.value is None:
        return WorksheetCellStatus.NOT_SEPARATELY_REPORTED
    if fact.provider == "manual_override":
        if "Best" in (fact.note or "") and "Kandidat" in (fact.note or ""):
            return WorksheetCellStatus.MANUAL_CONFIRMED
        return WorksheetCellStatus.MANUAL_OVERRIDE
    if state.calculation_ready:
        return WorksheetCellStatus.PRESENT_RELEASED
    if fact.provider in {"sec_filing_extension", "sec_filing_text_candidate"}:
        return WorksheetCellStatus.OFFICIAL_CANDIDATE_FOUND
    if candidates:
        if any(candidate.candidate_type == "DERIVED" for candidate in candidates):
            return WorksheetCellStatus.DERIVABLE
        return WorksheetCellStatus.OFFICIAL_CANDIDATE_FOUND
    return WorksheetCellStatus.PRESENT_REVIEW_REQUIRED


def worksheet_candidates(
    session: Session,
    analysis_id: int,
    metric: str,
    fiscal_year: int,
) -> tuple[WorksheetCandidate, ...]:
    analysis = session.get(Analysis, analysis_id)
    if analysis is None:
        return ()
    result = search_missing_metric_candidates(
        session,
        analysis,
        metric=metric,
        fiscal_year=fiscal_year,
    )
    return tuple(_worksheet_candidate(candidate) for candidate in result.candidates)


def _worksheet_candidate(candidate: MissingDataCandidate) -> WorksheetCandidate:
    return WorksheetCandidate(
        fact_id=candidate.fact_id or 0,
        metric=candidate.metric,
        fiscal_year=candidate.fiscal_year,
        value=candidate.value,
        currency=candidate.currency,
        provider=candidate.provider,
        provider_field=candidate.provider_field,
        source_url=candidate.source_url,
        filing_date=candidate.filing_date,
        retrieved_at=candidate.retrieved_at,
        semantic_decision=candidate.semantic_status,
        semantic_reason=candidate.semantic_reason,
        selectable_without_review=candidate.semantic_status == "SAFE_STANDARD_MAPPING",
        rejected_reason=None,
        candidate_type=candidate.candidate_type,
        confidence=candidate.confidence,
        input_refs=candidate.input_refs,
        formula=candidate.formula,
    )


def build_financial_worksheet(
    session: Session,
    analysis_id: int,
    preferred_states: Iterable[PreferredDataState],
    *,
    year_mode: str = "5 Jahre",
) -> FinancialWorksheet:
    metrics = _all_metric_keys()
    states = [state for state in preferred_states if state.fact.metric in metrics and state.fact.period_type == "FY"]
    all_facts = session.scalars(
        select(FinancialFactSnapshot).where(
            FinancialFactSnapshot.analysis_id == analysis_id,
            FinancialFactSnapshot.period_type == "FY",
            FinancialFactSnapshot.metric.in_(metrics),
        )
    ).all()
    all_years = {fact.period_end.year for fact in all_facts}
    years = years_for_mode(all_years, year_mode)
    state_index = {(state.fact.metric, state.fact.period_end.year): state for state in states}
    metric_by_key = {row.metric: row for row in worksheet_metrics()}

    cells: dict[tuple[str, int], WorksheetCell] = {}
    for metric in metrics:
        row = metric_by_key[metric]
        for fiscal_year in years:
            candidates = worksheet_candidates(session, analysis_id, metric, fiscal_year)
            state = state_index.get((metric, fiscal_year))
            if state is None:
                if any(candidate.candidate_type == "DERIVED" for candidate in candidates):
                    status = WorksheetCellStatus.DERIVABLE
                elif candidates:
                    status = WorksheetCellStatus.OFFICIAL_CANDIDATE_FOUND
                else:
                    status = WorksheetCellStatus.NOT_FOUND
                cells[(metric, fiscal_year)] = WorksheetCell(
                    metric=metric,
                    label=row.label,
                    statement=row.statement,
                    fiscal_year=fiscal_year,
                    status=status,
                    display=STATUS_DISPLAY[status],
                    reason="Kein Preferred-Data-Wert für diese Zelle vorhanden.",
                    candidate_count=len(candidates),
                )
                continue
            fact = state.fact
            status = _state_status(state, candidates)
            value_text = _format_value(fact.value, fact.currency)
            cells[(metric, fiscal_year)] = WorksheetCell(
                metric=metric,
                label=row.label,
                statement=row.statement,
                fiscal_year=fiscal_year,
                status=status,
                display=f"{value_text}\n{STATUS_DISPLAY[status]}" if value_text else STATUS_DISPLAY[status],
                value=fact.value,
                currency=fact.currency,
                provider=fact.provider,
                provider_field=fact.provider_field,
                source_url=fact.source_url,
                filing_date=fact.filing_date,
                retrieved_at=fact.retrieved_at,
                reason=state.reason,
                original_fact_id=fact.id,
                candidate_count=len(candidates),
            )

    return FinancialWorksheet(years=years, sections=WORKSHEET_SECTIONS, cells=cells)


def worksheet_status_counts(worksheet: FinancialWorksheet) -> dict[WorksheetCellStatus, int]:
    return {
        status: sum(1 for cell in worksheet.cells.values() if cell.status == status)
        for status in WorksheetCellStatus
    }


def open_cells(worksheet: FinancialWorksheet) -> tuple[WorksheetCell, ...]:
    return tuple(
        sorted(
            (cell for cell in worksheet.cells.values() if cell.status in OPEN_STATUSES),
            key=lambda item: (item.fiscal_year, item.label),
            reverse=True,
        )
    )
