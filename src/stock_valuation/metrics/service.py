from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import ensure_editable
from stock_valuation.data.preferred_data import PreferredDataState, load_preferred_data_states
from stock_valuation.database.models import Analysis, FinancialFactSnapshot, MetricSnapshot
from stock_valuation.metrics.engine import (
    CALCULATION_VERSION,
    MetricPoint,
    calculate_ebit_margin,
    calculate_ebitda_margin,
)


class MetricDataQualityError(RuntimeError):
    """Raised when a metric would rely on facts that are not calculation-ready."""


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
        "Berechnung ausschließlich aus verifizierter Preferred Data. ASML nutzt die validierte Operating-Income-Zuordnung; andere Unternehmen verwenden das freigegebene interne EBIT-Feld.",
    ),
    Phase3AMetricState(
        "ebitda_margin",
        "implemented",
        "EBITDA wird selbst aus verifiziertem EBIT plus sauber definiertem D&A berechnet. Provider-EBITDA wird nicht als Berechnungsinput verwendet.",
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


def _inputs_hash(*facts: FinancialFactSnapshot) -> str:
    payload = "|".join(
        sorted(
            f"{fact.metric}:{fact.period_end.isoformat()}:{fact.value}:{fact.provider}:"
            f"{fact.provider_field}:{fact.retrieved_at}"
            for fact in facts
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ebit_input_metric(analysis: Analysis) -> str:
    # D-012 remains valid for the ASML reference case: its validated Income from operations is the
    # EBIT basis. For other companies we do not silently equate operating income with EBIT.
    return "operating_income" if analysis.company.ticker.upper() == "ASML" else "ebit"


def _annual_ready_facts(
    session: Session,
    analysis: Analysis,
    required: set[str],
) -> tuple[dict[object, dict[str, FinancialFactSnapshot]], list[PreferredDataState]]:
    states = load_preferred_data_states(
        session,
        analysis.id,
        metrics=required,
        period_type="FY",
    )
    by_period: dict[object, dict[str, FinancialFactSnapshot]] = {}
    for state in states:
        fact = state.fact
        if fact.period_end > analysis.as_of_date or not state.calculation_ready:
            continue
        by_period.setdefault(fact.period_end, {})[fact.metric] = fact
    return by_period, states


def _blocked_reason(
    states: list[PreferredDataState],
    required: set[str],
    *,
    label: str,
) -> str:
    unresolved = [state for state in states if state.fact.metric in required and not state.calculation_ready]
    if not unresolved:
        return f"{label} hat keine vollständigen, berechnungsbereiten Jahresinputs."

    latest = sorted(unresolved, key=lambda state: state.fact.period_end, reverse=True)[:6]
    details = "; ".join(
        f"{state.fact.period_end.year} {state.fact.metric}: {state.quality_status}"
        for state in latest
    )
    return f"{label} ist wegen nicht freigegebener Preferred-Data-Inputs blockiert: {details}"


def calculate_ebit_margin_series(
    session: Session,
    analysis: Analysis,
) -> list[MetricPoint]:
    ebit_metric = _ebit_input_metric(analysis)
    required = {"revenue", ebit_metric}
    by_period, states = _annual_ready_facts(session, analysis, required)

    points: list[MetricPoint] = []
    for period_end in sorted(by_period):
        period_facts = by_period[period_end]
        revenue = period_facts.get("revenue")
        ebit = period_facts.get(ebit_metric)
        if revenue is None or ebit is None:
            continue
        points.append(
            MetricPoint(
                metric_id="ebit_margin",
                period_end=period_end,
                value=calculate_ebit_margin(ebit.value, revenue.value),
                unit="decimal_ratio",
                basis="reported",
                calculation_version=CALCULATION_VERSION,
                inputs_hash=_inputs_hash(revenue, ebit),
            )
        )

    if not points:
        raise MetricDataQualityError(_blocked_reason(states, required, label="EBIT-Marge"))
    return points


def calculate_ebitda_margin_series(
    session: Session,
    analysis: Analysis,
) -> list[MetricPoint]:
    ebit_metric = _ebit_input_metric(analysis)
    required = {"revenue", ebit_metric, "depreciation_amortization"}
    by_period, states = _annual_ready_facts(session, analysis, required)

    points: list[MetricPoint] = []
    for period_end in sorted(by_period):
        period_facts = by_period[period_end]
        revenue = period_facts.get("revenue")
        ebit = period_facts.get(ebit_metric)
        d_and_a = period_facts.get("depreciation_amortization")
        if revenue is None or ebit is None or d_and_a is None:
            continue
        points.append(
            MetricPoint(
                metric_id="ebitda_margin",
                period_end=period_end,
                value=calculate_ebitda_margin(
                    ebit.value,
                    d_and_a.value,
                    revenue.value,
                ),
                unit="decimal_ratio",
                basis="reported",
                calculation_version=CALCULATION_VERSION,
                inputs_hash=_inputs_hash(revenue, ebit, d_and_a),
            )
        )

    if not points:
        raise MetricDataQualityError(_blocked_reason(states, required, label="EBITDA-Marge"))
    return points


# Backward-compatible names used by existing tests/reference tooling.
def calculate_asml_ebit_margin_series(
    session: Session,
    analysis: Analysis,
) -> list[MetricPoint]:
    if analysis.company.ticker.upper() != "ASML":
        raise MetricDataQualityError("Diese Kompatibilitätsfunktion ist nur für ASML vorgesehen.")
    return calculate_ebit_margin_series(session, analysis)


def calculate_asml_ebitda_margin_series(
    session: Session,
    analysis: Analysis,
) -> list[MetricPoint]:
    if analysis.company.ticker.upper() != "ASML":
        raise MetricDataQualityError("Diese Kompatibilitätsfunktion ist nur für ASML vorgesehen.")
    return calculate_ebitda_margin_series(session, analysis)


def replace_metric_points(
    session: Session,
    analysis: Analysis,
    points: list[MetricPoint],
    *,
    metric_id: str,
    basis: str = "reported",
) -> int:
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
    ebit_points = calculate_ebit_margin_series(session, analysis)
    counts = {
        "ebit_margin": replace_metric_points(
            session,
            analysis,
            ebit_points,
            metric_id="ebit_margin",
            basis="reported",
        )
    }

    try:
        ebitda_points = calculate_ebitda_margin_series(session, analysis)
    except MetricDataQualityError:
        counts["ebitda_margin"] = 0
    else:
        counts["ebitda_margin"] = replace_metric_points(
            session,
            analysis,
            ebitda_points,
            metric_id="ebitda_margin",
            basis="reported",
        )
    return counts


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
