from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_valuation.analyses.service import complete_analysis
from stock_valuation.data.metric_requirements import MetricRequirement, metric_policy
from stock_valuation.data.preferred_data import load_preferred_data_states
from stock_valuation.database.models import (
    Analysis,
    AnalysisStatus,
    AnalysisStageSnapshot,
    FinancialFactSnapshot,
    MarketDataSnapshotRecord,
    ValuationSnapshotRecord,
)
from stock_valuation.market.engine import derive_market_metrics
from stock_valuation.market.models import (
    FXRate,
    ListingData,
    MarketDataSnapshot,
    NetDebtInput,
    NormalizedMarketQuote,
    NormalizedShareData,
)
from stock_valuation.metrics.calculation_engine import (
    CALCULATION_ENGINE_VERSION,
    CalculationInput,
    DerivedMetricResult,
    calculate_metrics_for_year,
)
from stock_valuation.metrics.historical_analysis import (
    HISTORICAL_ANALYSIS_VERSION,
    HistoricalPoint,
    HistoricalResult,
    analyze_historical_series,
    series_from_points,
)
from stock_valuation.quality.engine import evaluate_business_quality
from stock_valuation.quality.models import QUALITY_ENGINE_VERSION, QualityCompanyResult, QualityInput
from stock_valuation.valuation.dcf import equity_dcf
from stock_valuation.valuation.models import (
    AVAILABLE,
    DCFScenario,
    FinancialPoint,
    MarketSnapshotInput,
    NormalizedValue,
    ValuationSummary,
)
from stock_valuation.valuation.multiples import current_market_multiples
from stock_valuation.valuation.normalization import normalize_three_year_metric
from stock_valuation.valuation.persistence import (
    SNAPSHOT_ID_COLLISION,
    load_valuation_snapshot,
    list_valuation_snapshots_for_analysis,
    persist_valuation_snapshot,
)
from stock_valuation.valuation.snapshot import create_valuation_snapshot
from stock_valuation.valuation.summary import dcf_summary
from stock_valuation.valuation_assumptions.approvals import (
    APPROVAL_STALE,
    load_current_approvals,
    validate_approvals,
)
from stock_valuation.valuation_assumptions.models import APPROVED, ASSUMPTION_ENGINE_VERSION
from stock_valuation.valuation_assumptions.service import (
    build_assumption_set_for_analysis,
    build_effective_recommendations,
    build_effective_scenarios,
    effective_value,
)
from stock_valuation.workflow.models import (
    BLOCKED,
    NOT_RUN,
    READY,
    READY_FOR_PREVIEW,
    REVIEW_REQUIRED,
    STAGES,
    UNAVAILABLE,
    AnalysisState,
    FinalizationIssue,
    StageState,
)
from stock_valuation.workflow.persistence import canonical_hash, persist_stage_snapshot, payload_from_stage


BASE_FINANCIAL_METRICS = (
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "total_assets",
    "current_assets",
    "cash_and_equivalents",
    "accounts_receivable",
    "inventory",
    "total_liabilities",
    "current_liabilities",
    "accounts_payable",
    "short_term_debt",
    "long_term_debt",
    "shareholders_equity",
    "operating_cash_flow",
    "capital_expenditures",
    "depreciation_amortization",
    "interest_expense",
)
DISPLAY_FINANCIAL_METRICS = (
    "revenue",
    "operating_income",
    "net_income",
    "ebitda",
    "operating_cash_flow",
    "free_cash_flow",
    "cash_and_equivalents",
    "debt",
    "net_debt",
    "shareholders_equity",
)
ASSUMPTION_KEYS = (
    "base_fcf",
    "growth_rate",
    "discount_rate",
    "terminal_growth_rate",
    "projection_years",
)


def build_analysis_state(session: Session, analysis: Analysis) -> AnalysisState:
    rows = {
        stage: _stage_state_from_row(stage, _latest_stage(session, analysis, stage))
        for stage in STAGES
    }
    final = _latest_valuation_record(session, analysis)
    if final is not None and rows["VALUATION"].status == NOT_RUN:
        rows["VALUATION"] = _stage_from_valuation_record(final)
    market = _select_market_record(session, analysis)
    if market is not None and rows["MARKET_DATA"].status == NOT_RUN:
        rows["MARKET_DATA"] = _stage_from_market_record(market)
    years = tuple(
        int(item)
        for item in rows["CALCULATION"].payload.get("years", ())
        if str(item).isdigit()
    )
    return AnalysisState(
        analysis_id=analysis.id,
        company_name=analysis.company.name,
        ticker=analysis.company.ticker,
        as_of_date=analysis.as_of_date.isoformat(),
        revision_number=analysis.revision_number,
        analysis_status=analysis.status.value,
        stages=rows,
        history_years=years,
        market_snapshot_id=market.snapshot_id if market is not None else None,
        final_valuation_snapshot_id=final.snapshot_id if final is not None else None,
    )


def refresh_local_analysis_stages(session: Session, analysis: Analysis) -> AnalysisState:
    if analysis.status == AnalysisStatus.COMPLETED:
        return build_analysis_state(session, analysis)
    financial = _refresh_financial_data_stage(session, analysis)
    if financial.status in {READY, REVIEW_REQUIRED}:
        calculation = _refresh_calculation_stage(session, analysis)
    else:
        calculation = _blocked_stage("CALCULATION", CALCULATION_ENGINE_VERSION, financial.blockers)
    if calculation.status in {READY, REVIEW_REQUIRED}:
        historical = _refresh_historical_stage(session, analysis, calculation)
    else:
        historical = _blocked_stage("HISTORICAL_ANALYSIS", HISTORICAL_ANALYSIS_VERSION, calculation.blockers)
    if historical.status in {READY, REVIEW_REQUIRED}:
        quality = _refresh_quality_stage(session, analysis, calculation, historical)
    else:
        quality = _blocked_stage("BUSINESS_QUALITY", QUALITY_ENGINE_VERSION, historical.blockers)
    market = _refresh_market_stage(session, analysis)
    if calculation.status in {READY, REVIEW_REQUIRED} and historical.status in {READY, REVIEW_REQUIRED} and quality.status == READY:
        assumptions = _refresh_assumption_stage(session, analysis, calculation, historical, quality)
    else:
        assumptions = _blocked_stage("ASSUMPTIONS", ASSUMPTION_ENGINE_VERSION, ("Calculation, Historical und Quality muessen bereit sein.",))
    if market.status in {READY, REVIEW_REQUIRED} and assumptions.status in {READY_FOR_PREVIEW, READY, REVIEW_REQUIRED}:
        _refresh_valuation_stage(session, analysis, calculation, historical, quality, assumptions, market)
    return build_analysis_state(session, analysis)


def complete_analysis_if_ready(session: Session, analysis: Analysis) -> Analysis:
    state = refresh_local_analysis_stages(session, analysis)
    blockers = finalization_blockers(state)
    if blockers:
        raise ValueError("; ".join(blockers))
    return complete_analysis(session, analysis)


def finalization_blockers(state: AnalysisState) -> tuple[str, ...]:
    return tuple(issue.message_de for issue in finalization_issues(state) if issue.blocking)


def finalization_issues(state: AnalysisState, book_valuation_result: Any | None = None) -> tuple[FinalizationIssue, ...]:
    required = (
        "FINANCIAL_DATA",
        "CALCULATION",
        "HISTORICAL_ANALYSIS",
        "BUSINESS_QUALITY",
        "MARKET_DATA",
        "ASSUMPTIONS",
        "VALUATION",
    )
    issues: list[FinalizationIssue] = []
    relevant_years = _finalization_relevant_years(state)
    for stage in required:
        row = state.stages[stage]
        if stage == "ASSUMPTIONS" and row.status != READY:
            issues.append(
                FinalizationIssue(
                    code="ASSUMPTIONS_NOT_APPROVED",
                    category="ANNAHMEN",
                    message_de="Bewertungsannahmen müssen noch geprüft oder freigegeben werden.",
                    severity="ERROR",
                    blocking=True,
                    action_label="Zu den Annahmen",
                    location_hint="Zu finden unter: 11. DCF-Bewertung -> Annahmen prüfen",
                )
            )
        elif stage == "VALUATION" and row.status != READY:
            issues.append(
                FinalizationIssue(
                    code="FINAL_VALUATION_SNAPSHOT_MISSING",
                    category="TECHNISCH",
                    message_de="Finaler Bewertungssnapshot fehlt.",
                    severity="ERROR",
                    blocking=True,
                    action_label="Bewertung finalisieren",
                    location_hint="Zu finden unter: Abschluss",
                )
            )
        elif stage in {"MARKET_DATA", "BUSINESS_QUALITY", "HISTORICAL_ANALYSIS"} and row.status not in {READY, REVIEW_REQUIRED}:
            issues.append(_stage_issue(stage, row.status, blocking=True))
        elif stage in {"FINANCIAL_DATA", "CALCULATION"} and row.status not in {READY, REVIEW_REQUIRED}:
            issues.append(_stage_issue(stage, row.status, blocking=True))
        if stage == "FINANCIAL_DATA":
            issues.extend(_financial_review_issues(row.payload, relevant_years))
        elif stage != "FINANCIAL_DATA":
            for blocker in row.blockers:
                issues.append(
                    FinalizationIssue(
                        code="TECHNICAL_DETAIL",
                        category="TECHNISCH",
                        message_de="Technisches Detail erfordert Prüfung.",
                        severity="WARNING",
                        blocking=False,
                        location_hint=blocker,
                    )
                )
    if book_valuation_result is not None:
        issues.extend(_book_valuation_issues(book_valuation_result))
    return tuple(_dedupe_issues(issues))


def _finalization_relevant_years(state: AnalysisState) -> set[int]:
    years = set(state.history_years)
    if not years:
        calc = state.stages.get("CALCULATION")
        if calc is not None:
            years = {int(year) for year in calc.payload.get("base_facts", {}) if str(year).isdigit()}
    ordered = sorted(years)
    return set(ordered[-5:])


def _stage_issue(stage: str, status: str, *, blocking: bool) -> FinalizationIssue:
    labels = {
        "FINANCIAL_DATA": ("DATEN", "Finanzdaten müssen noch geprüft werden."),
        "CALCULATION": ("DATEN", "Kennzahlenberechnung ist noch nicht vollständig verfügbar."),
        "HISTORICAL_ANALYSIS": ("DATEN", "Historische Analyse ist noch nicht vollständig verfügbar."),
        "BUSINESS_QUALITY": ("DATEN", "Qualitätsanalyse ist noch nicht vollständig verfügbar."),
        "MARKET_DATA": ("MARKTDATEN", "Marktdaten müssen noch geprüft oder ergänzt werden."),
    }
    category, message = labels.get(stage, ("TECHNISCH", "Technischer Workflow-Status muss geprüft werden."))
    return FinalizationIssue(
        code=f"{stage}_NOT_READY",
        category=category,
        message_de=message,
        severity="ERROR" if blocking else "WARNING",
        blocking=blocking,
    )


def _financial_review_issues(payload: dict, relevant_years: set[int]) -> tuple[FinalizationIssue, ...]:
    parsed = [_parse_financial_review(item) for item in payload.get("review_required", ())]
    parsed = [item for item in parsed if item is not None]
    issues: list[FinalizationIssue] = []
    historical: dict[str, list[int]] = {}
    for year, metric, status in parsed:
        if year in relevant_years:
            issues.append(_current_financial_issue(year, metric, status))
        else:
            historical.setdefault(metric, []).append(year)
    for metric, years in sorted(historical.items()):
        issues.append(
            FinalizationIssue(
                code="HISTORICAL_REVIEW_WARNING",
                category="HISTORISCHE_WARNUNG",
                message_de=f"{_metric_label_de(metric)}: {len(years)} ältere Geschäftsjahre enthalten noch nicht bestätigte Detaildaten.",
                severity="WARNING",
                blocking=False,
                metric=metric,
                action_label="Technische Datenprüfungen anzeigen",
                location_hint=", ".join(str(year) for year in sorted(years)),
            )
        )
    return tuple(issues)


def _book_valuation_issues(book_valuation_result: Any) -> tuple[FinalizationIssue, ...]:
    values = getattr(book_valuation_result, "values", {}) or {}
    issues: list[FinalizationIssue] = []
    owner = values.get("owner_earnings")
    if owner is not None and getattr(owner, "status", None) != AVAILABLE:
        issues.append(
            FinalizationIssue(
                code="BOOK_OWNER_EARNINGS_INCOMPLETE",
                category="DCF",
                message_de="Die Investitionsbasis für Owner Earnings ist noch unvollständig.",
                severity="ERROR",
                blocking=True,
                metric="owner_earnings",
                action_label="Zum DCF",
                location_hint="Zu finden unter: 11. DCF-Bewertung -> 1. Bestimmung Owner Earnings",
            )
        )
    cost = values.get("cost_of_equity")
    if cost is not None and getattr(cost, "status", None) != AVAILABLE:
        issues.append(
            FinalizationIssue(
                code="BOOK_DISCOUNT_RATE_INCOMPLETE",
                category="DCF",
                message_de="Der Diskontierungszins der Excel-/Buchmethode ist noch nicht vollständig berechenbar.",
                severity="ERROR",
                blocking=True,
                metric="cost_of_equity",
                action_label="Zum DCF",
                location_hint="Zu finden unter: 11. DCF-Bewertung -> 2. Bestimmung des Diskontierungsfaktors",
            )
        )
    fair_price = values.get("multiplicator_fair_price_per_share")
    if fair_price is not None and getattr(fair_price, "status", None) != AVAILABLE:
        issues.append(
            FinalizationIssue(
                code="BOOK_MULTIPLICATOR_INCOMPLETE",
                category="MULTIPLIKATOREN",
                message_de="Die Multiplikatorenmethode ist noch nicht vollständig ausgefüllt.",
                severity="ERROR",
                blocking=True,
                metric="multiplicator_fair_price_per_share",
                action_label="Zur Multiplikatorenmethode",
                location_hint="Zu finden unter: 12. Multiplikatorenmethode",
            )
        )
    scenario_results = getattr(book_valuation_result, "scenario_results", {}) or {}
    base = scenario_results.get("base")
    if base is not None and getattr(base.fair_value_per_share, "status", None) != AVAILABLE:
        issues.append(
            FinalizationIssue(
                code="BOOK_BASE_SCENARIO_INCOMPLETE",
                category="DCF",
                message_de="Das Basis-Szenario der Excel-/Buch-DCF ist noch nicht vollständig gespeichert.",
                severity="ERROR",
                blocking=True,
                metric="book_dcf_base",
                action_label="Zum DCF",
                location_hint="Zu finden unter: 11. DCF-Bewertung -> Excel-/Buch-DCF-Szenarien",
            )
        )
    return tuple(issues)


def _parse_financial_review(text: str) -> tuple[int, str, str] | None:
    parts = str(text).split()
    if len(parts) < 3 or not parts[0].isdigit():
        return None
    metric = parts[1].rstrip(":")
    status = " ".join(parts[2:]).strip()
    return int(parts[0]), metric, status


def _current_financial_issue(year: int, metric: str, status: str) -> FinalizationIssue:
    if metric == "short_term_debt":
        return FinalizationIssue(
            code="CURRENT_SHORT_TERM_DEBT_REVIEW",
            category="DATEN",
            message_de=f"Kurzfristige Finanzschulden {year} müssen noch bestätigt werden. Relevant für Nettoverschuldung und Enterprise Value.",
            severity="ERROR",
            blocking=True,
            metric=metric,
            fiscal_year=year,
            action_label="Zum EV-Bereich",
            location_hint="Zu finden unter: 10. Bewertungskennzahlen -> Enterprise Value Ansatz prüfen",
        )
    if metric == "depreciation_amortization":
        return FinalizationIssue(
            code="CURRENT_DEPRECIATION_REVIEW",
            category="DATEN",
            message_de=f"Abschreibungen {year} müssen noch bestätigt werden. Relevant für EBITDA und Owner Earnings.",
            severity="ERROR",
            blocking=True,
            metric=metric,
            fiscal_year=year,
            action_label="Zum DCF",
            location_hint="Zu finden unter: 11. DCF-Bewertung -> 1. Bestimmung Owner Earnings",
        )
    return FinalizationIssue(
        code="CURRENT_FINANCIAL_REVIEW",
        category="DATEN",
        message_de=f"{_metric_label_de(metric)} {year} muss noch bestätigt werden.",
        severity="ERROR",
        blocking=True,
        metric=metric,
        fiscal_year=year,
        action_label="Zur Datenprüfung",
        location_hint="Zu finden unter: 1. Datenimport oder im jeweiligen Analyseabschnitt",
    )


def _metric_label_de(metric: str) -> str:
    return {
        "short_term_debt": "Kurzfristige Finanzschulden",
        "depreciation_amortization": "Abschreibungen",
        "intangible_purchases": "Käufe immaterieller Anlagewerte",
        "operating_cash_flow": "Operativer Cashflow",
        "capital_expenditures": "Sachinvestitionen",
        "long_term_debt": "Langfristige Finanzschulden",
    }.get(metric, metric.replace("_", " "))


def _dedupe_issues(issues: list[FinalizationIssue]) -> list[FinalizationIssue]:
    seen = set()
    output = []
    for issue in issues:
        key = (issue.code, issue.metric, issue.fiscal_year, issue.message_de)
        if key in seen:
            continue
        seen.add(key)
        output.append(issue)
    return output


def _refresh_financial_data_stage(session: Session, analysis: Analysis) -> StageState:
    states = load_preferred_data_states(session, analysis.id, metrics=BASE_FINANCIAL_METRICS, period_type="FY")
    ready = [item for item in states if item.calculation_ready and item.fact.period_end <= analysis.as_of_date]
    years = sorted({item.fact.period_end.year for item in ready})
    review_items = [
        item
        for item in states
        if item.fact.period_end <= analysis.as_of_date
        and not item.calculation_ready
        and _is_core_required_input(item.fact.metric)
        and item.quality_status in {"primary_semantic_review_required", "review_stale"}
    ]
    blockers = tuple(
        f"{item.fact.period_end.year} {item.fact.metric}: {item.quality_status}"
        for item in states
        if not item.calculation_ready and item.fact.period_end <= analysis.as_of_date
    )
    payload = {
        "production_input_path": "Analysis -> FinancialFactSnapshot -> Preferred Data",
        "diagnostics_csv_used": False,
        "ready_fact_count": len(ready),
        "years": years,
        "blockers": blockers[:20],
        "review_required": tuple(
            f"{item.fact.period_end.year} {item.fact.metric}: {item.quality_status}"
            for item in review_items[:50]
        ),
        "metric_count": len({item.fact.metric for item in ready}),
    }
    if ready and len(years) >= 2 and review_items:
        status = REVIEW_REQUIRED
    else:
        status = READY if ready and len(years) >= 2 else BLOCKED
    inputs_hash = canonical_hash(
        [
            (
                item.fact.metric,
                item.fact.period_end.isoformat(),
                str(item.fact.value),
                item.fact.currency,
                item.fact.provider,
                item.quality_status,
            )
            for item in states
        ]
    )
    row = persist_stage_snapshot(
        session,
        analysis,
        stage="FINANCIAL_DATA",
        engine_version="preferred-data-v1",
        inputs_hash=inputs_hash,
        status=status,
        payload=payload,
    )
    return _stage_state_from_row("FINANCIAL_DATA", row)


def _refresh_calculation_stage(session: Session, analysis: Analysis) -> StageState:
    by_year = _calculation_inputs_by_year(session, analysis)
    results: list[DerivedMetricResult] = []
    for year in sorted(by_year):
        results.extend(calculate_metrics_for_year(by_year[year], year))
    payload = {
        "production_input_path": "Preferred Data -> CalculationInput -> Calculation Engine V1",
        "diagnostics_csv_used": False,
        "years": sorted(by_year),
        "base_facts": _base_fact_payload(by_year),
        "results": [asdict(item) for item in results],
        "warnings": _result_issues(results),
    }
    available = {item.metric_id for item in results if item.status == AVAILABLE}
    review_sensitive_missing = [
        item
        for item in results
        if item.metric_id in {"ebitda", "ebitda_margin", "net_debt", "net_debt_to_ebitda"}
        and item.status != AVAILABLE
    ]
    if by_year and "free_cash_flow" in available and review_sensitive_missing:
        status = REVIEW_REQUIRED
    else:
        status = READY if by_year and "free_cash_flow" in available else BLOCKED
    inputs_hash = canonical_hash(payload["base_facts"])
    row = persist_stage_snapshot(
        session,
        analysis,
        stage="CALCULATION",
        engine_version=CALCULATION_ENGINE_VERSION,
        inputs_hash=inputs_hash,
        status=status,
        payload=payload,
    )
    return _stage_state_from_row("CALCULATION", row)


def _refresh_historical_stage(session: Session, analysis: Analysis, calculation: StageState) -> StageState:
    series = _historical_series_from_calculation(calculation.payload)
    results = analyze_historical_series(series) if series else {}
    payload = {
        "production_input_path": "Persisted Calculation Stage Snapshot -> Historical Analysis Engine V1",
        "diagnostics_csv_used": False,
        "history_years": sorted({point.fiscal_year for item in series.values() for point in item.points}),
        "series": {
            metric: [asdict(point) for point in data.points]
            for metric, data in series.items()
        },
        "results": {
            key: [asdict(item) for item in value]
            for key, value in results.items()
        },
    }
    status = READY if payload["history_years"] else BLOCKED
    inputs_hash = canonical_hash(calculation.payload)
    row = persist_stage_snapshot(
        session,
        analysis,
        stage="HISTORICAL_ANALYSIS",
        engine_version=HISTORICAL_ANALYSIS_VERSION,
        inputs_hash=inputs_hash,
        status=status,
        payload=payload,
    )
    return _stage_state_from_row("HISTORICAL_ANALYSIS", row)


def _refresh_quality_stage(session: Session, analysis: Analysis, calculation: StageState, historical: StageState) -> StageState:
    inputs = _quality_inputs(calculation.payload, historical.payload)
    result = evaluate_business_quality(analysis.company.ticker, inputs)
    payload = {
        "production_input_path": "Calculation + Historical Stage Snapshots -> Business Quality Engine V1",
        "diagnostics_csv_used": False,
        "result": asdict(result),
        "data_confidence": _data_confidence(result),
    }
    status = READY if result.overall_score is not None else REVIEW_REQUIRED
    inputs_hash = canonical_hash([calculation.inputs_hash, historical.inputs_hash])
    row = persist_stage_snapshot(
        session,
        analysis,
        stage="BUSINESS_QUALITY",
        engine_version=QUALITY_ENGINE_VERSION,
        inputs_hash=inputs_hash,
        status=status,
        payload=payload,
    )
    return _stage_state_from_row("BUSINESS_QUALITY", row)


def _refresh_market_stage(session: Session, analysis: Analysis) -> StageState:
    row = _select_market_record(session, analysis)
    if row is None:
        return StageState(
            "MARKET_DATA",
            UNAVAILABLE,
            blockers=("Kein persistierter MarketDataSnapshotRecord vorhanden. Marktdaten explizit aktualisieren.",),
        )
    state = _stage_from_market_record(row)
    persist_stage_snapshot(
        session,
        analysis,
        stage="MARKET_DATA",
        engine_version=row.payload_json and "market-data-v1.0",
        inputs_hash=row.inputs_hash or row.snapshot_id,
        status=state.status,
        payload=state.payload,
    )
    return state


def _refresh_assumption_stage(
    session: Session,
    analysis: Analysis,
    calculation: StageState,
    historical: StageState,
    quality: StageState,
) -> StageState:
    normalized = _normalized_fcf(calculation.payload)
    latest_actuals = _latest_actuals(calculation.payload)
    historical_context = _historical_context(historical.payload)
    quality_context = _quality_context(quality.payload)
    assumption_set = build_assumption_set_for_analysis(
        session,
        analysis,
        ticker=analysis.company.ticker,
        normalized_fcf=normalized,
        historical_context=historical_context,
        quality_context=quality_context,
        latest_actuals=latest_actuals,
    )
    approvals = load_current_approvals(session, analysis)
    valid_approvals, approval_warnings = validate_approvals(
        approvals,
        recommendation_inputs_hash=assumption_set.inputs_hash,
    )
    raw_recommendations = {
        item.assumption_key: item
        for item in (
            assumption_set.fcf_base_assessment,
            assumption_set.growth_recommendation,
            assumption_set.discount_rate_recommendation,
            assumption_set.terminal_growth_recommendation,
            assumption_set.projection_years_recommendation,
        )
    }
    recommendations = build_effective_recommendations(assumption_set, valid_approvals)
    effective_scenarios = build_effective_scenarios(recommendations, assumption_set.evidence)
    approved = all(recommendations[key].status == APPROVED for key in ASSUMPTION_KEYS)
    stale_refs = tuple(f"assumption_approval:{row.id}:{row.scenario}:{row.key}" for row in approvals.values() if row not in valid_approvals.values())
    valid_refs = tuple(f"assumption_approval:{row.id}:{row.scenario}:{row.key}" for row in valid_approvals.values())
    payload = {
        "production_input_path": "Current Analysis snapshots + EstimateSnapshot + GuidanceSnapshot + AssumptionApprovalRecord",
        "diagnostics_csv_used": False,
        "assumption_set": asdict(assumption_set),
        "raw_recommendations": {key: asdict(value) for key, value in raw_recommendations.items()},
        "effective_recommendations": {key: asdict(value) for key, value in recommendations.items()},
        "recommendations": {key: asdict(value) for key, value in recommendations.items()},
        "effective_scenarios": [asdict(item) for item in effective_scenarios],
        "valid_approval_refs": valid_refs,
        "stale_approval_refs": stale_refs,
        "recommendation_inputs_hash": assumption_set.inputs_hash,
        "approval_warnings": approval_warnings,
        "approved": approved,
        "normalized_fcf": normalized,
        "historical_context": historical_context,
        "quality_context": quality_context,
    }
    status = READY if approved else READY_FOR_PREVIEW
    if approval_warnings or assumption_set.requires_review:
        status = REVIEW_REQUIRED if not approved else READY
    row = persist_stage_snapshot(
        session,
        analysis,
        stage="ASSUMPTIONS",
        engine_version=ASSUMPTION_ENGINE_VERSION,
        inputs_hash=assumption_set.inputs_hash,
        status=status,
        payload=payload,
    )
    return _stage_state_from_row("ASSUMPTIONS", row)


def _refresh_valuation_stage(
    session: Session,
    analysis: Analysis,
    calculation: StageState,
    historical: StageState,
    quality: StageState,
    assumptions: StageState,
    market: StageState,
) -> StageState:
    market_input = _market_input_from_stage(analysis, market)
    normalized = _effective_normalized_fcf(assumptions.payload["normalized_fcf"], assumptions.payload["effective_recommendations"]["base_fcf"])
    effective_scenarios = _dcf_scenarios_from_payload(assumptions.payload.get("effective_scenarios", ()))
    if not effective_scenarios:
        row = persist_stage_snapshot(
            session,
            analysis,
            stage="VALUATION",
            engine_version="valuation-v1.0",
            inputs_hash=canonical_hash([market.inputs_hash, assumptions.inputs_hash, calculation.inputs_hash]),
            status=UNAVAILABLE,
            payload={
                "mode": "UNAVAILABLE",
                "blockers": ("VALUATION_NOT_READY: missing effective assumption value",),
                "effective_base_fcf": normalized.value,
                "effective_scenarios": assumptions.payload.get("effective_scenarios", ()),
                "assumption_stage_snapshot_id": assumptions.snapshot_id,
                "market_snapshot_id": market.snapshot_id,
            },
        )
        return _stage_state_from_row("VALUATION", row)
    summaries = tuple(dcf_summary(equity_dcf(analysis.company.ticker, normalized, scenario), market_input) for scenario in effective_scenarios)
    multiples = current_market_multiples(_latest_financial_points(calculation.payload), market_input)
    payload = {
        "production_input_path": "MarketDataSnapshotRecord + approved/preview Assumptions + Frozen Valuation Engine V1",
        "diagnostics_csv_used": False,
        "mode": "FINAL" if assumptions.payload.get("approved") else "PREVIEW",
        "effective_base_fcf": asdict(normalized),
        "effective_scenarios": assumptions.payload.get("effective_scenarios", ()),
        "valuation_results": [asdict(item) for item in summaries],
        "preview": {
            item.scenario: {
                "status": "ASSUMPTION_PREVIEW" if item.status == AVAILABLE and not assumptions.payload.get("approved") else item.status,
                "fair_value_per_unit": item.fair_value_per_unit,
                "market_price": item.market_price,
                "upside_downside": item.upside_downside,
                "margin_of_safety": item.margin_of_safety,
                "warnings": item.issues,
                "inputs_hash": item.inputs_hash,
            }
            for item in summaries
        },
        "multiples": [asdict(item) for item in multiples],
        "assumption_stage_snapshot_id": assumptions.snapshot_id,
        "market_snapshot_id": market.snapshot_id,
    }
    if assumptions.payload.get("approved"):
        snapshot = create_valuation_snapshot(
            analysis_id=str(analysis.id),
            market=market_input,
            financial_data_reference=calculation.snapshot_id or "",
            calculation_version=calculation.version or "",
            historical_analysis_version=historical.version or "",
            quality_version=quality.version or "",
            assumptions={
                "raw_recommendations": assumptions.payload["raw_recommendations"],
                "effective_recommendations": assumptions.payload["effective_recommendations"],
                "effective_scenarios": assumptions.payload["effective_scenarios"],
                "valid_approval_refs": assumptions.payload["valid_approval_refs"],
                "stale_approval_refs": assumptions.payload["stale_approval_refs"],
                "recommendation_inputs_hash": assumptions.payload["recommendation_inputs_hash"],
                "assumption_engine_version": ASSUMPTION_ENGINE_VERSION,
                "policy_version": assumptions.payload["assumption_set"]["policy_version"],
            },
            normalized_inputs=(normalized,),
            valuation_results=summaries + multiples,
            quality_context=assumptions.payload["quality_context"],
            historical_context=assumptions.payload["historical_context"],
        )
        try:
            record = persist_valuation_snapshot(session, analysis, snapshot)
        except ValueError as exc:
            if str(exc) != SNAPSHOT_ID_COLLISION:
                raise
            record = load_valuation_snapshot(session, snapshot.snapshot_id)
            if record is None or record.analysis_id != analysis.id:
                raise
            payload["final_snapshot_id"] = record.snapshot_id
            status = READY
        else:
            payload["final_snapshot_id"] = record.snapshot_id
            status = READY
    else:
        status = READY_FOR_PREVIEW
    row = persist_stage_snapshot(
        session,
        analysis,
        stage="VALUATION",
        engine_version="valuation-v1.0",
        inputs_hash=canonical_hash([market.inputs_hash, assumptions.inputs_hash, calculation.inputs_hash]),
        status=status,
        payload=payload,
    )
    return _stage_state_from_row("VALUATION", row)


def _calculation_inputs_by_year(session: Session, analysis: Analysis) -> dict[int, dict[str, CalculationInput]]:
    states = load_preferred_data_states(session, analysis.id, metrics=BASE_FINANCIAL_METRICS, period_type="FY")
    by_year: dict[int, dict[str, CalculationInput]] = {}
    for state in states:
        fact = state.fact
        if fact.period_end > analysis.as_of_date or not state.calculation_ready:
            continue
        by_year.setdefault(fact.period_end.year, {})[fact.metric] = CalculationInput(
            metric=fact.metric,
            fiscal_year=fact.period_end.year,
            value=fact.value,
            currency=fact.currency,
            unit=fact.unit or "currency",
            source_status=state.quality_status,
            provider=fact.provider,
            provider_field=fact.provider_field,
            accession=fact.source_url,
            filing_date=fact.filing_date.isoformat() if fact.filing_date else None,
        )
    return by_year


def _base_fact_payload(by_year: dict[int, dict[str, CalculationInput]]) -> dict[str, list[dict[str, Any]]]:
    return {
        str(year): [asdict(item) for item in rows.values()]
        for year, rows in sorted(by_year.items())
    }


def _result_issues(results: list[DerivedMetricResult]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            f"{item.fiscal_year}:{item.metric_id}:{issue.code}"
            for item in results
            for issue in item.issues
        )
    )


def _historical_series_from_calculation(payload: dict[str, Any]) -> dict[str, Any]:
    points: dict[str, list[HistoricalPoint]] = {}
    for year, facts in payload.get("base_facts", {}).items():
        for fact in facts:
            if fact["metric"] in {"revenue", "operating_income", "net_income", "operating_cash_flow", "cash_and_equivalents", "shareholders_equity"}:
                points.setdefault(fact["metric"], []).append(
                    HistoricalPoint(fact["metric"], int(year), _decimal_or_none(fact.get("value")), fact.get("unit") or "currency", "AVAILABLE" if fact.get("value") is not None else "UNAVAILABLE")
                )
    for item in payload.get("results", []):
        if item["metric_id"] == "debt_to_assets":
            continue
        points.setdefault(item["metric_id"], []).append(
            HistoricalPoint(item["metric_id"], int(item["fiscal_year"]), _decimal_or_none(item.get("value")), item.get("unit") or "n/a", item.get("status") or "UNAVAILABLE", _first_issue(item))
        )
    if "debt" not in points:
        debt_points = []
        for year, facts in payload.get("base_facts", {}).items():
            by_metric = {fact["metric"]: fact for fact in facts}
            short = _decimal_or_none(by_metric.get("short_term_debt", {}).get("value"))
            long = _decimal_or_none(by_metric.get("long_term_debt", {}).get("value"))
            if short is not None and long is not None:
                debt_points.append(HistoricalPoint("debt", int(year), short + long, by_metric.get("short_term_debt", {}).get("unit") or "currency"))
        points["debt"] = debt_points
    return {
        metric: series_from_points(rows)
        for metric, rows in points.items()
        if rows
    }


def _quality_inputs(calculation: dict[str, Any], historical: dict[str, Any]) -> list[QualityInput]:
    rows: list[QualityInput] = []
    for item in calculation.get("results", []):
        rows.append(
            QualityInput(
                metric_id=item["metric_id"],
                fiscal_year=int(item["fiscal_year"]),
                window="FY",
                value=_decimal_or_none(item.get("value")),
                unit=item.get("unit") or "n/a",
                status=item.get("status") or "UNAVAILABLE",
                issue=_first_issue(item),
                source="calculation",
                input_provenance=";".join(_input_refs_from_calc(item)),
                inputs_hash=item.get("inputs_hash") or "",
                source_version=item.get("calculation_version") or CALCULATION_ENGINE_VERSION,
            )
        )
    for values in historical.get("results", {}).values():
        for item in values:
            rows.append(
                QualityInput(
                    metric_id=item["metric_id"],
                    fiscal_year=item.get("fiscal_year"),
                    window=item["window"],
                    value=_decimal_or_none(item.get("value")),
                    unit=item.get("unit") or "n/a",
                    status=item.get("status") or "UNAVAILABLE",
                    issue=item.get("issue"),
                    source="historical",
                    source_version=item.get("calculation_version") or HISTORICAL_ANALYSIS_VERSION,
                )
            )
    return rows


def _data_confidence(result: QualityCompanyResult) -> dict[str, Any]:
    return {
        item.metric_id: {"value": item.value, "status": item.status, "issue": item.issue}
        for item in result.metrics
        if item.category == "data_confidence"
    }


def _select_market_record(session: Session, analysis: Analysis) -> MarketDataSnapshotRecord | None:
    return session.scalar(
        select(MarketDataSnapshotRecord)
        .where(
            MarketDataSnapshotRecord.analysis_id == analysis.id,
            MarketDataSnapshotRecord.analysis_as_of_date <= analysis.as_of_date,
        )
        .order_by(
            MarketDataSnapshotRecord.price_date.desc().nullslast(),
            MarketDataSnapshotRecord.retrieved_at.desc(),
            MarketDataSnapshotRecord.id.desc(),
        )
        .limit(1)
    )


def _stage_from_market_record(row: MarketDataSnapshotRecord) -> StageState:
    snapshot = _market_snapshot_from_record(row)
    metrics = derive_market_metrics(snapshot)
    market_cap, enterprise_value = metrics
    status = READY if market_cap.status == AVAILABLE and enterprise_value.status == AVAILABLE else REVIEW_REQUIRED
    payload = {
        "snapshot_id": row.snapshot_id,
        "price": row.price,
        "price_date": row.price_date,
        "trading_currency": row.trading_currency,
        "shares_outstanding": row.shares_outstanding,
        "share_date": row.share_date,
        "market_cap": market_cap.value,
        "enterprise_value": enterprise_value.value,
        "fx_rate": row.fx_rate,
        "fx_date": row.fx_date,
        "security_type": row.security_type,
        "payload": json.loads(row.payload_json),
        "derived_metrics": [asdict(item) for item in metrics],
        "availability": {
            "market_cap": "MARKET_CAP_READY" if market_cap.status == AVAILABLE else market_cap.status,
            "enterprise_value": "EV_READY" if enterprise_value.status == AVAILABLE else "EV_REVIEW_REQUIRED",
            "enterprise_value_reason": tuple(enterprise_value.issues),
        },
    }
    return StageState(
        "MARKET_DATA",
        status,
        "market-data-v1.0",
        row.inputs_hash,
        row.snapshot_id,
        row.retrieved_at,
        warnings=tuple(issue for item in metrics for issue in item.issues if issue != "CURRENCY_MATCH"),
        payload=payload,
        technically_available=True,
        review_required=status != READY,
    )


def _is_core_required_input(metric: str) -> bool:
    try:
        return metric_policy(metric).requirement == MetricRequirement.REQUIRED
    except KeyError:
        return False


def _market_snapshot_from_record(row: MarketDataSnapshotRecord) -> MarketDataSnapshot:
    payload = json.loads(row.payload_json)
    listing = payload["listing"]
    quote = payload["quote"]
    shares = payload["shares"]
    fx = payload.get("fx")
    net_debt = payload.get("net_debt")
    return MarketDataSnapshot(
        company=payload["company"],
        analysis_as_of_date=date.fromisoformat(payload["analysis_as_of_date"]),
        listing=ListingData(
            ticker=listing["ticker"],
            exchange=listing["exchange"],
            trading_currency=listing["trading_currency"],
            security_type=listing["security_type"],
            primary_listing=bool(listing["primary_listing"]),
            liquidity_priority=listing.get("liquidity_priority"),
            isin=listing.get("isin"),
            adr_ratio=_decimal_or_none(listing.get("adr_ratio")),
            underlying_share_ratio=_decimal_or_none(listing.get("underlying_share_ratio")),
            provider=listing.get("provider"),
        ),
        quote=NormalizedMarketQuote(
            ticker=quote["ticker"],
            exchange=quote["exchange"],
            listing_currency=quote["listing_currency"],
            price=_decimal_or_none(quote.get("price")),
            price_date=_date_or_none(quote.get("price_date")),
            retrieved_at=datetime.fromisoformat(quote["retrieved_at"]),
            provider=quote["provider"],
            provider_symbol=quote["provider_symbol"],
            original_value=_decimal_or_none(quote.get("original_value")),
            security_type=quote.get("security_type") or listing["security_type"],
        ),
        share_data=NormalizedShareData(
            ticker=shares["ticker"],
            shares_outstanding=_decimal_or_none(shares.get("shares_outstanding")),
            diluted_weighted_average_shares=_decimal_or_none(shares.get("diluted_weighted_average_shares")),
            basic_weighted_average_shares=_decimal_or_none(shares.get("basic_weighted_average_shares")),
            fiscal_year=shares.get("fiscal_year"),
            share_date=_date_or_none(shares.get("share_date")),
            filing_date=_date_or_none(shares.get("filing_date")),
            provider=shares["provider"],
            source=shares["source"],
            provider_field=shares.get("provider_field"),
            share_basis=shares.get("share_basis") or "ORDINARY_SHARES",
        ),
        financial_statement_currency=payload["financial_statement_currency"],
        net_debt=NetDebtInput(
            fiscal_year=int(net_debt["fiscal_year"]),
            value=_decimal_or_none(net_debt.get("value")),
            currency=net_debt.get("currency"),
            source=net_debt["source"],
            inputs_hash=net_debt.get("inputs_hash"),
        )
        if net_debt
        else None,
        fx_rate=FXRate(
            from_currency=fx["from_currency"],
            to_currency=fx["to_currency"],
            rate=_decimal_or_none(fx.get("rate")),
            fx_date=_date_or_none(fx.get("fx_date")),
            provider=fx.get("provider"),
        )
        if fx
        else None,
        snapshot_id=row.snapshot_id,
    )


def _normalized_fcf(calculation: dict[str, Any]) -> dict[str, Any]:
    points = tuple(
        FinancialPoint(
            "free_cash_flow",
            int(item["fiscal_year"]),
            _decimal_or_none(item.get("value")),
            _currency_for_year(calculation, int(item["fiscal_year"])) or "",
            item.get("status") or "UNAVAILABLE",
            f"calculation:free_cash_flow:{item['fiscal_year']}",
            item.get("inputs_hash") or "",
        )
        for item in calculation.get("results", [])
        if item["metric_id"] == "free_cash_flow"
    )
    return asdict(normalize_three_year_metric("free_cash_flow", points))


def _latest_actuals(calculation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for year, facts in calculation.get("base_facts", {}).items():
        for fact in facts:
            if fact["metric"] == "revenue" and fact.get("value") is not None:
                if "revenue" not in output or int(year) > int(output["revenue"]["fiscal_year"]):
                    output["revenue"] = {"fiscal_year": int(year), "value": _decimal_or_none(fact["value"]), "unit": fact.get("unit"), "currency": fact.get("currency")}
    return output


def _historical_context(payload: dict[str, Any]) -> dict[str, Any]:
    results = payload.get("results", {})
    context = {
        "historical_analysis_version": HISTORICAL_ANALYSIS_VERSION,
        "historical_window": [str(year) for year in payload.get("history_years", ())],
        "revenue_growth": _hist_values(results, "revenue", "YoY"),
        "earnings_growth": _hist_values(results, "net_income", "YoY"),
        "fcf_growth": _hist_values(results, "free_cash_flow", "YoY"),
        "cagr": _cagr_context(results),
        "margin_trend": _latest_by_metric(results.get("margin_trends", [])),
        "volatility": _latest_by_metric([item for item in results.get("stability_quality", []) if item.get("window") == "volatility"]),
        "negative_years": _latest_by_metric([item for item in results.get("stability_quality", []) if item.get("window") == "negative_years"]),
        "missing_years": _latest_by_metric([item for item in results.get("stability_quality", []) if item.get("window") == "missing_years"]),
        "input_refs": (),
    }
    context["context_hash"] = canonical_hash(context)
    return context


def _quality_context(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result", {})
    context = {
        "overall_quality_score": result.get("overall_score"),
        "overall_quality_assessment": result.get("assessment"),
        "quality_version": result.get("quality_version") or QUALITY_ENGINE_VERSION,
        "component_scores": result.get("component_scores", []),
        "data_confidence": payload.get("data_confidence", {}),
    }
    context["context_hash"] = canonical_hash(context)
    return context


def _market_input_from_stage(analysis: Analysis, market: StageState) -> MarketSnapshotInput:
    payload = market.payload
    derived = {item["metric_id"]: item for item in payload.get("derived_metrics", [])}
    return MarketSnapshotInput(
        ticker=analysis.company.ticker,
        company=analysis.company.name,
        analysis_as_of_date=analysis.as_of_date.isoformat(),
        market_snapshot_id=payload["snapshot_id"],
        market_data_version=market.version or "market-data-v1.0",
        security_type=payload.get("security_type") or "ordinary_share",
        price=_decimal_or_none(payload.get("price")),
        market_cap=_decimal_or_none(derived.get("market_cap", {}).get("value")),
        enterprise_value=_decimal_or_none(derived.get("enterprise_value", {}).get("value")),
        shares_outstanding=_decimal_or_none(payload.get("shares_outstanding")),
        share_basis=payload.get("payload", {}).get("shares", {}).get("share_basis") or "ORDINARY_SHARES",
        financial_currency=payload.get("payload", {}).get("financial_statement_currency") or analysis.company.currency,
        trading_currency=payload.get("trading_currency") or analysis.company.currency,
        fx_rate=_decimal_or_none(payload.get("fx_rate")),
        adr_ratio=_decimal_or_none(payload.get("payload", {}).get("listing", {}).get("adr_ratio")),
        underlying_share_ratio=_decimal_or_none(payload.get("payload", {}).get("listing", {}).get("underlying_share_ratio")),
        input_refs=(f"market_snapshot:{payload['snapshot_id']}",),
        inputs_hash=market.inputs_hash or payload["snapshot_id"],
    )


def _latest_financial_points(calculation: dict[str, Any]) -> dict[str, FinancialPoint]:
    points: dict[str, FinancialPoint] = {}
    for item in calculation.get("results", []):
        if item.get("status") != AVAILABLE:
            continue
        year = int(item["fiscal_year"])
        if item["metric_id"] not in points or year > points[item["metric_id"]].fiscal_year:
            points[item["metric_id"]] = FinancialPoint(
                item["metric_id"],
                year,
                _decimal_or_none(item.get("value")),
                _currency_for_year(calculation, year) or "",
                item["status"],
                f"calculation:{item['metric_id']}:{year}",
                item.get("inputs_hash") or "",
            )
    entity_fcf_by_year = _entity_fcf_excel_book_points(calculation)
    for year, value, currency, refs, inputs_hash, status, issues in entity_fcf_by_year:
        current = points.get("entity_free_cash_flow_excel_book")
        if status == AVAILABLE and (current is None or year > current.fiscal_year):
            points["entity_free_cash_flow_excel_book"] = FinancialPoint(
                "entity_free_cash_flow_excel_book",
                year,
                value,
                currency,
                status,
                "book_valuation:entity_free_cash_flow_excel_book",
                inputs_hash,
            )
    for year, facts in calculation.get("base_facts", {}).items():
        for fact in facts:
            if fact["metric"] in {"revenue", "operating_income", "net_income", "shareholders_equity", "operating_cash_flow"} and fact.get("value") is not None:
                current = points.get(fact["metric"])
                if current is None or int(year) > current.fiscal_year:
                    points[fact["metric"]] = FinancialPoint(
                        fact["metric"],
                        int(year),
                        _decimal_or_none(fact.get("value")),
                        fact.get("currency") or "",
                        AVAILABLE,
                        f"financial_fact:{fact['metric']}:{year}",
                        canonical_hash(fact),
                    )
    return points


def _entity_fcf_excel_book_points(calculation: dict[str, Any]) -> list[tuple[int, Decimal | None, str, tuple[str, ...], str, str, tuple[str, ...]]]:
    output = []
    for year, facts in calculation.get("base_facts", {}).items():
        by_metric = {fact["metric"]: fact for fact in facts}
        ocf = by_metric.get("operating_cash_flow")
        capex = by_metric.get("capital_expenditures")
        interest = by_metric.get("interest_expense")
        currency = (ocf or {}).get("currency") or (capex or {}).get("currency") or ""
        refs = tuple(
            f"financial_fact:{metric}:{year}"
            for metric in ("operating_cash_flow", "capital_expenditures", "interest_expense")
        )
        issues = []
        if ocf is None or ocf.get("value") is None:
            issues.append("MISSING_OPERATING_CASH_FLOW")
        if capex is None or capex.get("value") is None:
            issues.append("MISSING_CAPITAL_EXPENDITURES")
        if interest is None or interest.get("value") is None:
            issues.append("MISSING_INTEREST_EXPENSE_FOR_ENTITY_FCF")
        if issues:
            output.append((int(year), None, currency, refs, canonical_hash([year, issues]), UNAVAILABLE, tuple(issues)))
            continue
        value = _decimal_or_none(ocf.get("value")) + _decimal_or_none(interest.get("value")) - _decimal_or_none(capex.get("value"))
        output.append((int(year), value, currency, refs, canonical_hash([year, value, refs]), AVAILABLE, ()))
    return output


def _effective_normalized_fcf(normalized: dict[str, Any], base_fcf: dict[str, Any]) -> NormalizedValue:
    effective = effective_value(_recommendation_from_payload(base_fcf))
    original = _normalized_value_from_payload(normalized)
    refs = tuple(original.input_refs) + tuple(base_fcf.get("evidence_refs", ())) + (
        f"original_normalized_fcf:{original.inputs_hash}",
        f"recommended_base_fcf:{base_fcf.get('recommended_value')}",
        f"approved_base_fcf:{base_fcf.get('approved_value')}",
    )
    return NormalizedValue(
        metric_id=original.metric_id,
        method="effective_base_fcf",
        value=effective,
        currency=original.currency,
        status=original.status if effective is not None else UNAVAILABLE,
        issues=tuple(original.issues) if effective is not None else ("VALUATION_NOT_READY",),
        input_refs=refs,
        inputs_hash=canonical_hash([original.inputs_hash, base_fcf]),
        used_fiscal_years=original.used_fiscal_years,
        input_values=original.input_values,
    )


def _dcf_scenarios_from_payload(rows: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> tuple[DCFScenario, ...]:
    scenarios: list[DCFScenario] = []
    for row in rows:
        growth = _decimal_or_none(row.get("annual_growth_rate"))
        discount = _decimal_or_none(row.get("discount_rate"))
        terminal = _decimal_or_none(row.get("terminal_growth_rate"))
        if growth is None or discount is None or terminal is None:
            return ()
        scenarios.append(
            DCFScenario(
                row["scenario"],
                int(row["projection_years"]),
                growth,
                discount,
                terminal,
                "EFFECTIVE_ASSUMPTIONS",
            )
        )
    return tuple(scenarios)


def _recommendation_from_payload(payload: dict[str, Any]) -> Any:
    from stock_valuation.valuation_assumptions.models import AssumptionRecommendation

    return AssumptionRecommendation(
        **{
            **payload,
            "recommended_value": _decimal_or_none(payload.get("recommended_value")),
            "approved_value": _decimal_or_none(payload.get("approved_value")),
            "warnings": tuple(payload.get("warnings", ())),
            "evidence_refs": tuple(payload.get("evidence_refs", ())),
        }
    )


def _normalized_value_from_payload(payload: dict[str, Any]) -> NormalizedValue:
    return NormalizedValue(
        payload["metric_id"],
        payload["method"],
        _decimal_or_none(payload.get("value")),
        payload["currency"],
        payload["status"],
        tuple(payload.get("issues", ())),
        tuple(payload.get("input_refs", ())),
        payload.get("inputs_hash") or "",
        tuple(int(year) for year in payload.get("used_fiscal_years", ())),
        tuple(_decimal_or_none(value) or Decimal("0") for value in payload.get("input_values", ())),
    )


def _assumption_set_from_payload(payload: dict[str, Any]):
    from stock_valuation.valuation_assumptions.models import AssumptionSetRecommendation, AssumptionEvidence, AssumptionRecommendation, ScenarioAssumptionRecommendation

    def rec(data):
        return AssumptionRecommendation(**{**data, "recommended_value": _decimal_or_none(data.get("recommended_value")), "approved_value": _decimal_or_none(data.get("approved_value"))})

    return AssumptionSetRecommendation(
        ticker=payload["ticker"],
        analysis_as_of_date=payload["analysis_as_of_date"],
        normalized_fcf=_decimal_or_none(payload.get("normalized_fcf")),
        fcf_base_assessment=rec(payload["fcf_base_assessment"]),
        growth_recommendation=rec(payload["growth_recommendation"]),
        discount_rate_recommendation=rec(payload["discount_rate_recommendation"]),
        terminal_growth_recommendation=rec(payload["terminal_growth_recommendation"]),
        projection_years_recommendation=rec(payload["projection_years_recommendation"]),
        scenarios=tuple(
            ScenarioAssumptionRecommendation(
                item["scenario"],
                int(item["projection_years"]),
                _decimal_or_none(item.get("base_fcf")),
                _decimal_or_none(item.get("annual_growth_rate")),
                _decimal_or_none(item.get("discount_rate")),
                _decimal_or_none(item.get("terminal_growth_rate")),
                item["status"],
                item["confidence"],
                tuple(item.get("warnings", ())),
                tuple(item.get("evidence_refs", ())),
                dict(item.get("sources", {})),
            )
            for item in payload["scenarios"]
        ),
        evidence=tuple(
            AssumptionEvidence(
                item["evidence_id"],
                item["metric"],
                _decimal_or_none(item.get("value")),
                item["unit"],
                item["period"],
                item["window"],
                item["source_type"],
                item["source_ref"],
                item.get("source_date"),
                item["status"],
                item["confidence"],
                item.get("note", ""),
            )
            for item in payload["evidence"]
        ),
        quality_context=payload["quality_context"],
        historical_context=payload["historical_context"],
        status=payload["status"],
        confidence=payload["confidence"],
        warnings=tuple(payload["warnings"]),
        requires_review=payload["requires_review"],
        inputs_hash=payload["inputs_hash"],
    )


def _stage_state_from_row(stage: str, row: AnalysisStageSnapshot | None) -> StageState:
    if row is None:
        return StageState(stage, NOT_RUN)
    payload = payload_from_stage(row)
    warnings = tuple(payload.get("warnings", ())) + tuple(payload.get("approval_warnings", ()))
    blockers = tuple(payload.get("blockers", ()))
    return StageState(
        stage,
        row.status,
        row.engine_version,
        row.inputs_hash,
        row.snapshot_id,
        row.created_at,
        warnings=warnings,
        blockers=blockers,
        payload=payload,
        technically_available=row.status in {READY, REVIEW_REQUIRED, READY_FOR_PREVIEW},
        review_required=row.status in {REVIEW_REQUIRED, READY_FOR_PREVIEW},
        approved=row.status == READY and stage in {"ASSUMPTIONS", "VALUATION"},
    )


def _stage_from_valuation_record(row: ValuationSnapshotRecord) -> StageState:
    return StageState(
        "VALUATION",
        READY,
        row.valuation_version,
        row.inputs_hash,
        row.snapshot_id,
        row.created_at,
        payload=json.loads(row.payload_json),
        technically_available=True,
        approved=True,
    )


def _blocked_stage(stage: str, version: str, blockers: tuple[str, ...]) -> StageState:
    return StageState(stage, BLOCKED, version, blockers=blockers)


def _latest_stage(session: Session, analysis: Analysis, stage: str) -> AnalysisStageSnapshot | None:
    return session.scalar(
        select(AnalysisStageSnapshot)
        .where(AnalysisStageSnapshot.analysis_id == analysis.id, AnalysisStageSnapshot.stage == stage)
        .order_by(AnalysisStageSnapshot.created_at.desc(), AnalysisStageSnapshot.id.desc())
        .limit(1)
    )


def _latest_valuation_record(session: Session, analysis: Analysis) -> ValuationSnapshotRecord | None:
    rows = list_valuation_snapshots_for_analysis(session, analysis)
    return rows[-1] if rows else None


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _date_or_none(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _first_issue(item: dict[str, Any]) -> str | None:
    issues = item.get("issues") or ()
    if not issues:
        return None
    first = issues[0]
    if isinstance(first, dict):
        code = first.get("code")
        inputs = ",".join(first.get("inputs", ()))
        return f"{code}:{inputs}" if inputs else code
    return str(first)


def _input_refs_from_calc(item: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        f"{row.get('provider')}:{row.get('provider_field')}:{row.get('fiscal_year')}"
        for row in item.get("input_provenance", ())
    )


def _currency_for_year(calculation: dict[str, Any], year: int) -> str | None:
    facts = calculation.get("base_facts", {}).get(str(year), [])
    currencies = [fact.get("currency") for fact in facts if fact.get("currency")]
    return currencies[0] if currencies else None


def _hist_values(results: dict[str, Any], metric: str, window: str) -> list[dict[str, Any]]:
    return [
        {"fiscal_year": item["fiscal_year"], "value": item["value"]}
        for item in results.get("yoy_growth", [])
        if item["metric_id"] == metric and item["window"] == window and item["status"] == AVAILABLE
    ]


def _cagr_context(results: dict[str, Any]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for item in results.get("cagr", []):
        if item.get("status") == AVAILABLE:
            output.setdefault(item["metric_id"], {})[item["window"]] = item["value"]
    return output


def _latest_by_metric(items: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for item in items:
        if item.get("status") == AVAILABLE:
            output[item["metric_id"]] = item.get("value")
    return output
