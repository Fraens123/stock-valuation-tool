from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_valuation.database.models import (
    Analysis,
    EstimateSnapshot,
    FinancialFactSnapshot,
    GuidanceSnapshot,
    ManualInputSnapshot,
    QualitativeAssessment,
    ValuationAssumption,
    ValuationResult,
)


@dataclass(frozen=True)
class ChangeItem:
    category: str
    key: str
    label: str
    old_value: Any
    new_value: Any

    @property
    def changed(self) -> bool:
        return self.old_value != self.new_value


def _normalize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def _add_change(
    items: list[ChangeItem],
    *,
    category: str,
    key: str,
    label: str,
    old_value: Any,
    new_value: Any,
) -> None:
    old_value = _normalize(old_value)
    new_value = _normalize(new_value)
    if old_value != new_value:
        items.append(ChangeItem(category, key, label, old_value, new_value))


def _row_map(rows: Iterable[Any], key_fn) -> dict[Any, Any]:
    return {key_fn(row): row for row in rows}


def compare_analyses(session: Session, old: Analysis, new: Analysis) -> list[ChangeItem]:
    """Return structured differences between two stored analysis snapshots.

    The comparison uses only persisted snapshot data. It never fetches current/live data.
    """
    if old.company_id != new.company_id:
        raise ValueError("Nur Analysen desselben Unternehmens können verglichen werden.")

    changes: list[ChangeItem] = []

    # Analysis metadata / market context.
    _add_change(
        changes,
        category="Analyse",
        key="market_price",
        label="Aktienkurs zum Analyse-Stichtag",
        old_value=old.market_price,
        new_value=new.market_price,
    )
    _add_change(
        changes,
        category="Analyse",
        key="notes",
        label="Analyse-Notizen / Investmentthese",
        old_value=old.notes,
        new_value=new.notes,
    )

    # Published financial facts.
    old_rows = session.scalars(
        select(FinancialFactSnapshot).where(FinancialFactSnapshot.analysis_id == old.id)
    ).all()
    new_rows = session.scalars(
        select(FinancialFactSnapshot).where(FinancialFactSnapshot.analysis_id == new.id)
    ).all()
    old_map = _row_map(old_rows, lambda r: (r.statement, r.metric, r.period_end, r.period_type))
    new_map = _row_map(new_rows, lambda r: (r.statement, r.metric, r.period_end, r.period_type))
    for key in sorted(set(old_map) | set(new_map), key=str):
        left = old_map.get(key)
        right = new_map.get(key)
        _add_change(
            changes,
            category="Fundamentaldaten",
            key="|".join(map(str, key)),
            label=f"{key[1]} · {key[2]} · {key[3]}",
            old_value=left.value if left else None,
            new_value=right.value if right else None,
        )

    # Analyst estimates.
    old_rows = session.scalars(
        select(EstimateSnapshot).where(EstimateSnapshot.analysis_id == old.id)
    ).all()
    new_rows = session.scalars(
        select(EstimateSnapshot).where(EstimateSnapshot.analysis_id == new.id)
    ).all()
    old_map = _row_map(old_rows, lambda r: (r.metric, r.period))
    new_map = _row_map(new_rows, lambda r: (r.metric, r.period))
    for key in sorted(set(old_map) | set(new_map), key=str):
        left = old_map.get(key)
        right = new_map.get(key)
        for field, label_suffix in [
            ("low", "Low"),
            ("average", "Konsens"),
            ("high", "High"),
            ("analyst_count", "Analystenzahl"),
        ]:
            _add_change(
                changes,
                category="Prognosen",
                key=f"estimate|{key[0]}|{key[1]}|{field}",
                label=f"{key[0]} {key[1]} · {label_suffix}",
                old_value=getattr(left, field) if left else None,
                new_value=getattr(right, field) if right else None,
            )

    # Management guidance.
    old_rows = session.scalars(
        select(GuidanceSnapshot).where(GuidanceSnapshot.analysis_id == old.id)
    ).all()
    new_rows = session.scalars(
        select(GuidanceSnapshot).where(GuidanceSnapshot.analysis_id == new.id)
    ).all()
    old_map = _row_map(old_rows, lambda r: (r.metric, r.period))
    new_map = _row_map(new_rows, lambda r: (r.metric, r.period))
    for key in sorted(set(old_map) | set(new_map), key=str):
        left = old_map.get(key)
        right = new_map.get(key)
        for field, label_suffix in [
            ("low", "Low"),
            ("point_estimate", "Punktwert"),
            ("high", "High"),
        ]:
            _add_change(
                changes,
                category="Prognosen",
                key=f"guidance|{key[0]}|{key[1]}|{field}",
                label=f"Management Guidance {key[0]} {key[1]} · {label_suffix}",
                old_value=getattr(left, field) if left else None,
                new_value=getattr(right, field) if right else None,
            )

    # Manually entered source data (e.g. Aktienfinder).
    old_rows = session.scalars(
        select(ManualInputSnapshot).where(ManualInputSnapshot.analysis_id == old.id)
    ).all()
    new_rows = session.scalars(
        select(ManualInputSnapshot).where(ManualInputSnapshot.analysis_id == new.id)
    ).all()
    old_map = _row_map(old_rows, lambda r: (r.metric, r.period, r.source_name))
    new_map = _row_map(new_rows, lambda r: (r.metric, r.period, r.source_name))
    for key in sorted(set(old_map) | set(new_map), key=str):
        left = old_map.get(key)
        right = new_map.get(key)
        _add_change(
            changes,
            category="Prognosen",
            key=f"manual|{key[0]}|{key[1]}|{key[2]}",
            label=f"{key[0]} {key[1] or ''} · {key[2]}",
            old_value=left.value if left else None,
            new_value=right.value if right else None,
        )

    # Qualitative thesis/assessment.
    old_rows = session.scalars(
        select(QualitativeAssessment).where(QualitativeAssessment.analysis_id == old.id)
    ).all()
    new_rows = session.scalars(
        select(QualitativeAssessment).where(QualitativeAssessment.analysis_id == new.id)
    ).all()
    old_map = _row_map(old_rows, lambda r: r.criterion_id)
    new_map = _row_map(new_rows, lambda r: r.criterion_id)
    for key in sorted(set(old_map) | set(new_map)):
        left = old_map.get(key)
        right = new_map.get(key)
        _add_change(
            changes,
            category="Eigene Einschätzung",
            key=f"qualitative|{key}|rating",
            label=f"{key} · Bewertung",
            old_value=left.rating_key if left else None,
            new_value=right.rating_key if right else None,
        )
        _add_change(
            changes,
            category="Eigene Einschätzung",
            key=f"qualitative|{key}|comment",
            label=f"{key} · Begründung",
            old_value=left.comment if left else None,
            new_value=right.comment if right else None,
        )

    # Valuation assumptions.
    old_rows = session.scalars(
        select(ValuationAssumption).where(ValuationAssumption.analysis_id == old.id)
    ).all()
    new_rows = session.scalars(
        select(ValuationAssumption).where(ValuationAssumption.analysis_id == new.id)
    ).all()
    old_map = _row_map(old_rows, lambda r: (r.method, r.scenario, r.key))
    new_map = _row_map(new_rows, lambda r: (r.method, r.scenario, r.key))
    for key in sorted(set(old_map) | set(new_map), key=str):
        left = old_map.get(key)
        right = new_map.get(key)
        _add_change(
            changes,
            category="Bewertung",
            key=f"assumption|{'|'.join(key)}",
            label=f"{key[0]} · {key[1]} · {key[2]}",
            old_value=left.value if left else None,
            new_value=right.value if right else None,
        )

    # Valuation results.
    old_rows = session.scalars(
        select(ValuationResult).where(ValuationResult.analysis_id == old.id)
    ).all()
    new_rows = session.scalars(
        select(ValuationResult).where(ValuationResult.analysis_id == new.id)
    ).all()
    old_map = _row_map(old_rows, lambda r: (r.method, r.scenario, r.metric))
    new_map = _row_map(new_rows, lambda r: (r.method, r.scenario, r.metric))
    for key in sorted(set(old_map) | set(new_map), key=str):
        left = old_map.get(key)
        right = new_map.get(key)
        _add_change(
            changes,
            category="Bewertung",
            key=f"result|{'|'.join(key)}",
            label=f"{key[0]} · {key[1]} · {key[2]}",
            old_value=left.value if left else None,
            new_value=right.value if right else None,
        )

    return changes
