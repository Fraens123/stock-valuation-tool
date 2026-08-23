from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_valuation.book_valuation.models import BOOK_VALUATION_VERSION
from stock_valuation.database.models import Analysis, ValuationAssumption


METHOD = "excel_book_valuation"


def upsert_book_assumption(
    session: Session,
    analysis: Analysis,
    *,
    key: str,
    value: Decimal,
    note: str | None = None,
    scenario: str = "base",
    unit: str | None = None,
    source_type: str | None = None,
) -> ValuationAssumption:
    row = session.scalar(
        select(ValuationAssumption).where(
            ValuationAssumption.analysis_id == analysis.id,
            ValuationAssumption.method == METHOD,
            ValuationAssumption.scenario == scenario,
            ValuationAssumption.key == key,
        )
    )
    if row is None:
        row = ValuationAssumption(
            analysis_id=analysis.id,
            method=METHOD,
            scenario=scenario,
            key=key,
        )
        session.add(row)
    row.value = value
    row.unit = unit
    row.source_type = source_type or BOOK_VALUATION_VERSION
    row.note = note
    session.commit()
    return row


def load_book_assumptions(session: Session, analysis: Analysis, *, scenario: str = "base") -> dict[str, ValuationAssumption]:
    rows = session.scalars(
        select(ValuationAssumption).where(
            ValuationAssumption.analysis_id == analysis.id,
            ValuationAssumption.method == METHOD,
            ValuationAssumption.scenario == scenario,
        )
    ).all()
    return {row.key: row for row in rows}


def load_all_book_assumptions(session: Session, analysis: Analysis) -> dict[str, dict[str, ValuationAssumption]]:
    rows = session.scalars(
        select(ValuationAssumption).where(
            ValuationAssumption.analysis_id == analysis.id,
            ValuationAssumption.method == METHOD,
        )
    ).all()
    grouped: dict[str, dict[str, ValuationAssumption]] = {}
    for row in rows:
        grouped.setdefault(row.scenario or "base", {})[row.key] = row
    return grouped
