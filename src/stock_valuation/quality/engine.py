from __future__ import annotations

import hashlib
from collections import defaultdict
from decimal import Decimal
from typing import Iterable

from stock_valuation.quality.models import (
    AVAILABLE,
    INSUFFICIENT_HISTORY,
    NOT_APPLICABLE,
    QUALITY_ENGINE_VERSION,
    UNAVAILABLE,
    UPSTREAM_NON_PENALTY_STATUSES,
    QualityCompanyResult,
    QualityInput,
    QualityMetricDefinition,
    QualityMetricResult,
    QualityScoreComponent,
)
from stock_valuation.quality.rules import QUALITY_DEFINITION_BY_ID, QUALITY_DEFINITIONS
from stock_valuation.quality.scoring import (
    QualityScoringConfig,
    assessment_from_score,
    clamp_score,
    population_volatility,
    score_growth,
    score_liquidity,
    score_lower_is_better,
    score_positive_ratio,
    score_volatility,
    weighted_average,
)


def evaluate_business_quality(
    ticker: str,
    inputs: Iterable[QualityInput],
    *,
    config: QualityScoringConfig | None = None,
) -> QualityCompanyResult:
    cfg = config or QualityScoringConfig()
    rows = tuple(inputs)
    by_metric = _group_by_metric(rows)
    years = tuple(sorted({row.fiscal_year for row in rows if row.fiscal_year is not None}))
    results = tuple(_evaluate_definition(definition, by_metric, years, cfg) for definition in QUALITY_DEFINITIONS)
    components = _component_scores(results, cfg)
    overall = weighted_average(
        [
            (component.score, component.weight)
            for component in components
            if component.status == AVAILABLE and component.score is not None
        ]
    )
    positives = tuple(
        f"{result.name}: {result.assessment}"
        for result in results
        if result.status == AVAILABLE and result.score is not None and result.score >= Decimal("8")
    )
    negatives = tuple(
        f"{result.name}: {result.assessment}"
        for result in results
        if result.status == AVAILABLE and result.score is not None and result.score < Decimal("4")
    )
    unavailable = tuple(
        f"{result.name}: {result.issue or result.status}"
        for result in results
        if result.status in {UNAVAILABLE, INSUFFICIENT_HISTORY}
    )
    not_applicable = tuple(
        f"{result.name}: {result.issue or result.status}"
        for result in results
        if result.status == NOT_APPLICABLE
    )
    return QualityCompanyResult(
        ticker=ticker,
        years=years,
        metrics=results,
        component_scores=components,
        overall_score=overall,
        assessment=assessment_from_score(overall),
        positive_factors=positives,
        negative_factors=negatives,
        unavailable_factors=unavailable,
        not_applicable_factors=not_applicable,
    )


def _group_by_metric(rows: Iterable[QualityInput]) -> dict[str, list[QualityInput]]:
    grouped: dict[str, list[QualityInput]] = defaultdict(list)
    for row in rows:
        grouped[row.metric_id].append(row)
    for metric_rows in grouped.values():
        metric_rows.sort(key=lambda item: (-1 if item.fiscal_year is None else item.fiscal_year, item.window))
    return dict(grouped)


def _evaluate_definition(
    definition: QualityMetricDefinition,
    by_metric: dict[str, list[QualityInput]],
    years: tuple[int, ...],
    config: QualityScoringConfig,
) -> QualityMetricResult:
    metric_id = definition.metric_id
    if metric_id == "fcf_to_ocf_quality":
        return _fcf_to_ocf(definition, by_metric, config)
    if metric_id in {"ocf_to_net_income_quality", "fcf_to_net_income_quality", "roic_quality"}:
        return _unavailable_result(definition, "UPSTREAM_MEASURE_NOT_EXPOSED")
    if metric_id == "inventory_applicability_quality":
        return _inventory_applicability(definition, by_metric)
    if metric_id == "margin_volatility_quality":
        return _volatility_result(definition, by_metric, config, definition.inputs)
    if metric_id == "growth_volatility_quality":
        return _historical_volatility(definition, by_metric, config, ("revenue", "net_income", "free_cash_flow"))
    if metric_id == "negative_years_quality":
        return _historical_count(definition, by_metric, "negative_years", lower_is_better=True)
    if metric_id == "missing_years_quality":
        return _historical_count(definition, by_metric, "missing_years", lower_is_better=True)
    if metric_id in {"revenue_growth_quality", "earnings_growth_quality", "fcf_growth_quality"}:
        growth_metric = {
            "revenue_growth_quality": "revenue",
            "earnings_growth_quality": "net_income",
            "fcf_growth_quality": "free_cash_flow",
        }[metric_id]
        return _growth_result(definition, by_metric, growth_metric, config)

    calc_metric = definition.inputs[0]
    latest = _latest_available(by_metric.get(calc_metric, []), source="calculation")
    if latest is None:
        return _input_unavailable(definition, by_metric.get(calc_metric, []))
    score = _score_latest(definition, latest.value or Decimal("0"), config)
    trend = _trend_for_metric(by_metric, calc_metric)
    return _result(definition, latest, latest.value, latest.unit, trend, score)


def _latest_available(rows: list[QualityInput], *, source: str | None = None) -> QualityInput | None:
    candidates = [
        row
        for row in rows
        if row.status == AVAILABLE
        and row.value is not None
        and row.fiscal_year is not None
        and (source is None or row.source == source)
    ]
    return max(candidates, key=lambda item: item.fiscal_year) if candidates else None


def _score_latest(
    definition: QualityMetricDefinition,
    value: Decimal,
    config: QualityScoringConfig,
) -> Decimal:
    metric_id = definition.metric_id
    if metric_id in {
        "gross_margin_quality",
        "operating_margin_quality",
        "net_margin_quality",
        "ebitda_margin_quality",
        "free_cash_flow_margin_quality",
        "return_on_assets_quality",
        "return_on_equity_quality",
        "equity_ratio_quality",
    }:
        return score_positive_ratio(value, config)
    if metric_id in {"debt_to_assets_quality", "debt_to_equity_quality", "net_debt_to_ebitda_quality"}:
        return score_lower_is_better(value, config.leverage_low, config.leverage_high)
    if metric_id in {"current_ratio_quality", "quick_ratio_quality", "cash_ratio_quality"}:
        return score_liquidity(value, config)
    if metric_id == "capex_intensity_quality":
        return score_lower_is_better(value, Decimal("0.20"), Decimal("0.80"))
    return Decimal("5")


def _trend_for_metric(by_metric: dict[str, list[QualityInput]], metric_id: str) -> str:
    trend = next(
        (
            row
            for row in by_metric.get(metric_id, [])
            if row.source == "historical" and row.window == "trend" and row.status == AVAILABLE
        ),
        None,
    )
    if trend is None or trend.value is None:
        return "UNKNOWN"
    if trend.value > Decimal("0.01"):
        return "IMPROVING"
    if trend.value < Decimal("-0.01"):
        return "DETERIORATING"
    return "STABLE"


def _growth_result(
    definition: QualityMetricDefinition,
    by_metric: dict[str, list[QualityInput]],
    metric_id: str,
    config: QualityScoringConfig,
) -> QualityMetricResult:
    rows = by_metric.get(metric_id, [])
    latest_yoy = _latest_by_window(rows, "YoY")
    cagr_3y = _latest_by_window(rows, "3Y_CAGR")
    usable = cagr_3y if cagr_3y and cagr_3y.status == AVAILABLE else latest_yoy
    if usable is None or usable.status != AVAILABLE or usable.value is None:
        issue = usable.issue if usable is not None else "INSUFFICIENT_HISTORY"
        status = INSUFFICIENT_HISTORY if issue in UPSTREAM_NON_PENALTY_STATUSES else UNAVAILABLE
        return _status_result(definition, status, issue or "INSUFFICIENT_HISTORY", rows)
    score = score_growth(usable.value, config)
    trend = "IMPROVING" if score >= Decimal("7") else "DETERIORATING" if score < Decimal("4") else "STABLE"
    return _result(definition, usable, usable.value, usable.unit, trend, score)


def _latest_by_window(rows: list[QualityInput], window: str) -> QualityInput | None:
    candidates = [row for row in rows if row.window == window and row.fiscal_year is not None]
    return max(candidates, key=lambda item: item.fiscal_year) if candidates else None


def _fcf_to_ocf(
    definition: QualityMetricDefinition,
    by_metric: dict[str, list[QualityInput]],
    config: QualityScoringConfig,
) -> QualityMetricResult:
    capex = _latest_available(by_metric.get("capex_ratio", []), source="calculation")
    if capex is None or capex.value is None:
        return _input_unavailable(definition, by_metric.get("capex_ratio", []))
    value = Decimal("1") - capex.value
    score = score_positive_ratio(value, config)
    return _result(definition, capex, value, "decimal_ratio", _trend_for_metric(by_metric, "capex_ratio"), score)


def _inventory_applicability(
    definition: QualityMetricDefinition,
    by_metric: dict[str, list[QualityInput]],
) -> QualityMetricResult:
    rows = [*by_metric.get("inventory_intensity", []), *by_metric.get("inventory_days", [])]
    if any("NOT_SEPARATELY_REPORTED" in (row.issue or "") for row in rows):
        return _status_result(definition, NOT_APPLICABLE, "INVENTORY_NOT_SEPARATELY_REPORTED", rows)
    if any(row.status == AVAILABLE for row in rows):
        base = next(row for row in rows if row.status == AVAILABLE)
        return _result(definition, base, None, "status", "NOT_A_TREND_METRIC", None, assessment="APPLICABLE")
    return _status_result(definition, UNAVAILABLE, "INVENTORY_SIGNAL_UNAVAILABLE", rows)


def _volatility_result(
    definition: QualityMetricDefinition,
    by_metric: dict[str, list[QualityInput]],
    config: QualityScoringConfig,
    metric_ids: tuple[str, ...],
) -> QualityMetricResult:
    values = [
        row.value
        for metric in metric_ids
        for row in by_metric.get(metric, [])
        if row.source == "calculation" and row.status == AVAILABLE and row.value is not None
    ]
    volatility = population_volatility(values)
    if volatility is None:
        return _status_result(definition, INSUFFICIENT_HISTORY, "INSUFFICIENT_HISTORY", [])
    score = score_volatility(volatility, config)
    ref = QualityInput(definition.metric_id, max(_years(by_metric)), "volatility", volatility, "decimal_ratio", AVAILABLE, None, "quality")
    return _result(definition, ref, volatility, "decimal_ratio", "STABLE" if score >= Decimal("6") else "VOLATILE", score)


def _historical_volatility(
    definition: QualityMetricDefinition,
    by_metric: dict[str, list[QualityInput]],
    config: QualityScoringConfig,
    metric_ids: tuple[str, ...],
) -> QualityMetricResult:
    values = [
        row.value
        for metric in metric_ids
        for row in by_metric.get(metric, [])
        if row.source == "historical" and row.window == "YoY" and row.status == AVAILABLE and row.value is not None
    ]
    volatility = population_volatility(values)
    if volatility is None:
        return _status_result(definition, INSUFFICIENT_HISTORY, "INSUFFICIENT_HISTORY", [])
    score = score_volatility(volatility, config)
    ref = QualityInput(definition.metric_id, max(_years(by_metric)), "volatility", volatility, "decimal_ratio", AVAILABLE, None, "quality")
    return _result(definition, ref, volatility, "decimal_ratio", "STABLE" if score >= Decimal("6") else "VOLATILE", score)


def _historical_count(
    definition: QualityMetricDefinition,
    by_metric: dict[str, list[QualityInput]],
    window: str,
    *,
    lower_is_better: bool,
) -> QualityMetricResult:
    values = [
        row.value
        for metric in definition.inputs
        for row in by_metric.get(metric, [])
        if row.source == "historical" and row.window == window and row.status == AVAILABLE and row.value is not None
    ]
    if not values:
        return _status_result(definition, INSUFFICIENT_HISTORY, "INSUFFICIENT_HISTORY", [])
    total = sum(values, Decimal("0"))
    score = clamp_score(Decimal("10") - total * Decimal("2")) if lower_is_better else Decimal("5")
    ref = QualityInput(definition.metric_id, max(_years(by_metric)), window, total, "count", AVAILABLE, None, "historical")
    return _result(definition, ref, total, "count", "STABLE" if total == 0 else "ISSUES_PRESENT", score)


def _years(by_metric: dict[str, list[QualityInput]]) -> tuple[int, ...]:
    years = [row.fiscal_year for rows in by_metric.values() for row in rows if row.fiscal_year is not None]
    return tuple(sorted(years)) or (0,)


def _input_unavailable(definition: QualityMetricDefinition, rows: list[QualityInput]) -> QualityMetricResult:
    issue = next((row.issue for row in rows if row.issue), "MISSING_INPUT")
    if issue and any(code in issue for code in UPSTREAM_NON_PENALTY_STATUSES):
        status = INSUFFICIENT_HISTORY if "HISTORY" in issue or "PRIOR" in issue else UNAVAILABLE
    else:
        status = UNAVAILABLE
    return _status_result(definition, status, issue or "MISSING_INPUT", rows)


def _unavailable_result(definition: QualityMetricDefinition, issue: str) -> QualityMetricResult:
    return _status_result(definition, UNAVAILABLE, issue, [])


def _status_result(
    definition: QualityMetricDefinition,
    status: str,
    issue: str,
    rows: list[QualityInput],
) -> QualityMetricResult:
    return QualityMetricResult(
        metric_id=definition.metric_id,
        name=definition.name,
        category=definition.category,
        fiscal_year=max((row.fiscal_year for row in rows if row.fiscal_year is not None), default=None),
        window="quality",
        value=None,
        unit=definition.unit,
        trend="UNKNOWN",
        assessment=status,
        score=None,
        status=status,
        issue=issue,
        source_category=definition.source_category,
        input_metrics=definition.inputs,
        input_refs=tuple(_input_ref(row) for row in rows),
        inputs_hash=_hash_rows(rows),
    )


def _result(
    definition: QualityMetricDefinition,
    source_row: QualityInput,
    value: Decimal | None,
    unit: str,
    trend: str,
    score: Decimal | None,
    *,
    assessment: str | None = None,
) -> QualityMetricResult:
    return QualityMetricResult(
        metric_id=definition.metric_id,
        name=definition.name,
        category=definition.category,
        fiscal_year=source_row.fiscal_year,
        window=source_row.window,
        value=value,
        unit=unit,
        trend=trend,
        assessment=assessment or assessment_from_score(score),
        score=score,
        status=AVAILABLE,
        issue=None,
        source_category=definition.source_category,
        input_metrics=definition.inputs,
        input_refs=(_input_ref(source_row),),
        inputs_hash=_hash_rows([source_row]),
    )


def _input_ref(row: QualityInput) -> str:
    return (
        f"{row.source}:{row.metric_id}:{row.fiscal_year or ''}:{row.window}:"
        f"{row.inputs_hash or row.input_provenance or row.source_version or row.status}"
    )


def _hash_rows(rows: Iterable[QualityInput]) -> str:
    payload = "|".join(sorted(_input_ref(row) for row in rows))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest() if payload else ""


def _component_scores(
    results: tuple[QualityMetricResult, ...],
    config: QualityScoringConfig,
) -> tuple[QualityScoreComponent, ...]:
    by_component: dict[str, list[QualityMetricResult]] = defaultdict(list)
    for result in results:
        by_component[result.category].append(result)
    components: list[QualityScoreComponent] = []
    for component_id, weight in config.component_weights.items():
        candidates = [
            result
            for result in by_component.get(component_id, [])
            if result.status == AVAILABLE and result.score is not None
        ]
        score = weighted_average([(result.score, Decimal("1")) for result in candidates])
        components.append(
            QualityScoreComponent(
                component_id=component_id,
                score=score,
                weight=weight,
                status=AVAILABLE if score is not None else UNAVAILABLE,
                contributing_metrics=tuple(result.metric_id for result in candidates),
                issue=None if score is not None else "NO_SCORABLE_METRICS",
            )
        )
    return tuple(components)
