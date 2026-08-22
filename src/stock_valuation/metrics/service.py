from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import ensure_editable
from stock_valuation.database.models import Analysis, FinancialFactSnapshot, MetricSnapshot
from stock_valuation.metrics.engine import CALCULATION_VERSION, MetricPoint, calculate_ebit_margin
from stock_valuation.validation.service import metric_validation_gates, validate_asml_primary_source


class MetricDataQualityError(RuntimeError):
    """Raised when a metric would rely on raw facts that have not passed the data gate."""


@dataclass(frozen=True)
class Phase3AMetricState:
    metric_id: str
    status: str
    reason: str


PHASE_3A_METHOD_STATES: tuple[Phase3AMetricState, ...] = (
    Phase3AMetricState(
        "roe",
        "methodology_blocked",
        "Rohdaten sind bereit; Endbestand vs. durchschnittliches Eigenkapital muss gegen Kindle-Seite 94 verifiziert werden.",
    ),
    Phase3AMetricState(
        "return_on_sales",
        "methodology_blocked",
        "Rohdaten sind bereit; die genaue Gewinn-Zählerdefinition muss gegen Kindle-Seite 101 verifiziert werden.",
    ),
    Phase3AMetricState(
        "ebit_margin",
        "implemented",
        "Für ASML werden die validierten Felder Income from operations / Revenue verwendet.",
    ),
    Phase3AMetricState(
        "ebitda_margin",
        "data_blocked",
        "Depreciation/Amortization ist im ASML-Primärquellen-Gate derzeit gesperrt.",
    ),
    Phase3AMetricState(
        "capital_turnover",
        "methodology_blocked",
        "Rohdaten sind bereit; die genaue Kapitalbasis bzw. Durchschnittsbildung muss gegen Kindle-Seite 107 verifiziert werden.",
    ),
    Phase3AMetricState(
        "roa",
        "methodology_blocked",
        "Zähler- und Kapitaldefinition müssen gegen Kindle-Seite 109 verifiziert werden.",
    ),
    Phase3AMetricState(
        "roce",
        "methodology_blocked",
        "Rohdatenbasis ist bereit; die genaue Capital-Employed-Definition muss gegen Kindle-Seite 111 verifiziert werden.",
    ),
    Phase3AMetricState(
        "sales_earning_rate",
        "methodology_blocked",
        "Die konkrete Buchdefinition muss gegen Kindle-Seite 114 verifiziert werden.",
    ),
)


def phase_3a_method_states() -> tuple[Phase3AMetricState, ...]:
    return PHASE_3A_METHOD_STATES


def _approved_asml_fields(session: Session, analysis: Analysis) -> set[str]:
    validation = validate_asml_primary_source(session, analysis)
    gates = metric_validation_gates(validation)
    return {gate.metric for gate in gates if gate.status == "approved"}


def _inputs_hash(*facts: FinancialFactSnapshot) -> str:
    payload = "|".join(
        sorted(
            f"{fact.metric}:{fact.period_end.isoformat()}:{fact.value}:{fact.provider}:"
            f"{fact.provider_field}:{fact.retrieved_at}"
            for fact in facts
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def calculate_asml_ebit_margin_series(
    session: Session,
    analysis: Analysis,
    *,
    provider: str = "alphavantage",
) -> list[MetricPoint]:
    """Calculate ASML EBIT margin only from field-gated annual snapshot facts.

    No live API call occurs here. The calculation uses only facts already stored inside the
    selected analysis snapshot. The 2024/2025 primary-source gate must approve both revenue
    and operating_income before the historical series is allowed to calculate.
    """
    if analysis.company.ticker.upper() != "ASML":
        raise MetricDataQualityError(
            "Phase 3A ist derzeit nur für den validierten ASML-Referenzfall freigegeben."
        )

    approved = _approved_asml_fields(session, analysis)
    required = {"revenue", "operating_income"}
    blocked = sorted(required - approved)
    if blocked:
        raise MetricDataQualityError(
            "EBIT-Marge ist wegen nicht freigegebener Rohdaten blockiert: " + ", ".join(blocked)
        )

    facts = session.scalars(
        select(FinancialFactSnapshot).where(
            FinancialFactSnapshot.analysis_id == analysis.id,
            FinancialFactSnapshot.provider == provider,
            FinancialFactSnapshot.period_type == "FY",
            FinancialFactSnapshot.metric.in_(required),
            FinancialFactSnapshot.period_end <= analysis.as_of_date,
        )
    ).all()

    by_period: dict[object, dict[str, FinancialFactSnapshot]] = {}
    for fact in facts:
        by_period.setdefault(fact.period_end, {})[fact.metric] = fact

    points: list[MetricPoint] = []
    for period_end in sorted(by_period):
        period_facts = by_period[period_end]
        revenue = period_facts.get("revenue")
        operating_income = period_facts.get("operating_income")
        if revenue is None or operating_income is None:
            continue

        value = calculate_ebit_margin(operating_income.value, revenue.value)
        points.append(
            MetricPoint(
                metric_id="ebit_margin",
                period_end=period_end,
                value=value,
                unit="decimal_ratio",
                basis="reported",
                calculation_version=CALCULATION_VERSION,
                inputs_hash=_inputs_hash(revenue, operating_income),
            )
        )
    return points


def replace_metric_points(
    session: Session,
    analysis: Analysis,
    points: list[MetricPoint],
    *,
    metric_id: str,
    basis: str = "reported",
) -> int:
    """Persist a deterministic metric series inside an editable analysis snapshot."""
    ensure_editable(analysis)
    session.execute(
        delete(MetricSnapshot).where(
            MetricSnapshot.analysis_id == analysis.id,
            MetricSnapshot.metric_id == metric_id,
            MetricSnapshot.basis == basis,
        )
    )
    for point in points:
        session.add(
            MetricSnapshot(
                analysis_id=analysis.id,
                metric_id=point.metric_id,
                period=str(point.period_end.year),
                basis=point.basis,
                value=point.value,
                unit=point.unit,
                calculation_version=point.calculation_version,
                inputs_hash=point.inputs_hash,
            )
        )
    session.commit()
    return len(points)


def calculate_and_store_phase_3a(session: Session, analysis: Analysis) -> dict[str, int]:
    points = calculate_asml_ebit_margin_series(session, analysis)
    count = replace_metric_points(
        session,
        analysis,
        points,
        metric_id="ebit_margin",
        basis="reported",
    )
    return {"ebit_margin": count}


def load_metric_series(
    session: Session,
    analysis_id: int,
    metric_id: str,
    *,
    basis: str = "reported",
) -> list[MetricSnapshot]:
    return list(
        session.scalars(
            select(MetricSnapshot)
            .where(
                MetricSnapshot.analysis_id == analysis_id,
                MetricSnapshot.metric_id == metric_id,
                MetricSnapshot.basis == basis,
            )
            .order_by(MetricSnapshot.period)
        ).all()
    )
