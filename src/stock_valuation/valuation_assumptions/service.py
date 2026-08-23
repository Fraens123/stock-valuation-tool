from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_valuation.database.models import Analysis, ValuationAssumption
from stock_valuation.valuation.dcf import equity_dcf
from stock_valuation.valuation.models import DCFScenario, MarketSnapshotInput, NormalizedValue, stable_hash
from stock_valuation.valuation.summary import dcf_summary
from stock_valuation.valuation_assumptions.cashflow import assess_fcf_base
from stock_valuation.valuation_assumptions.discount_rate import discount_rate_recommendation
from stock_valuation.valuation_assumptions.evidence import collect_forward_evidence, evidence_from_historical_context
from stock_valuation.valuation_assumptions.growth import growth_recommendation, scenario_growths
from stock_valuation.valuation_assumptions.models import (
    ASSUMPTION_ENGINE_VERSION,
    ASSUMPTION_POLICY_VERSION,
    AVAILABLE,
    LOW,
    PROJECT_POLICY_ID,
    RECOMMENDED,
    REVIEW_REQUIRED,
    APPROVED,
    AssumptionRecommendation,
    AssumptionSetRecommendation,
    ScenarioAssumptionRecommendation,
)
from stock_valuation.valuation_assumptions.approvals import apply_approval
from stock_valuation.valuation_assumptions.policy import (
    DEFAULT_BEAR_TERMINAL_GROWTH,
    DEFAULT_BULL_TERMINAL_GROWTH,
    DISCOUNT_RATE_SCENARIO_SPREAD,
    DEFAULT_PROJECTION_YEARS,
    TERMINAL_GROWTH_SCENARIO_SPREAD,
)
from stock_valuation.valuation_assumptions.terminal_growth import terminal_growth_recommendation


def build_assumption_set(
    *,
    ticker: str,
    analysis_as_of_date: str,
    normalized_fcf: dict,
    historical_context: dict,
    quality_context: dict,
    additional_evidence=(),
    approved_assumptions: dict[str, ValuationAssumption] | None = None,
) -> AssumptionSetRecommendation:
    approved_assumptions = approved_assumptions or {}
    evidence = evidence_from_historical_context(ticker, historical_context) + tuple(additional_evidence)
    fcf_base = _apply_manual_approval(assess_fcf_base(normalized_fcf), approved_assumptions.get("base_fcf"))
    growth = growth_recommendation(evidence)
    growth = _apply_manual_approval(growth, approved_assumptions.get("growth_rate"))
    discount = discount_rate_recommendation(approved_assumptions.get("discount_rate"))
    terminal = terminal_growth_recommendation(discount.approved_value or discount.recommended_value or Decimal("0"), approved_assumptions.get("terminal_growth_rate"))
    projection_years = AssumptionRecommendation(
        "projection_years",
        Decimal(DEFAULT_PROJECTION_YEARS),
        "years",
        RECOMMENDED,
        PROJECT_POLICY_ID,
        ASSUMPTION_POLICY_VERSION,
        (),
        "Projection years remain fixed at 5 under PROJECT_POLICY_V1; Phase 7 does not vary horizon automatically.",
        LOW,
        (),
        False,
        "PROJECT_POLICY_V1",
        primary_anchor="project policy",
    )
    scenarios = _scenarios(fcf_base, growth, discount, terminal, evidence)
    warnings = tuple(
        dict.fromkeys(
            fcf_base.warnings
            + growth.warnings
            + discount.warnings
            + terminal.warnings
            + tuple(warning for scenario in scenarios for warning in scenario.warnings)
        )
    )
    requires_review = any(
        item.requires_review for item in (fcf_base, growth, discount, terminal, projection_years)
    )
    confidence = _overall_confidence((fcf_base.confidence, growth.confidence, discount.confidence, terminal.confidence))
    status = REVIEW_REQUIRED if requires_review else RECOMMENDED
    inputs_hash = stable_hash(
        (
            normalized_fcf.get("inputs_hash", ""),
            historical_context.get("context_hash", ""),
            quality_context.get("context_hash", ""),
            repr([asdict(item) for item in evidence]),
            ASSUMPTION_ENGINE_VERSION,
            ASSUMPTION_POLICY_VERSION,
        )
    )
    return AssumptionSetRecommendation(
        ticker=ticker,
        analysis_as_of_date=analysis_as_of_date,
        normalized_fcf=fcf_base.recommended_value,
        fcf_base_assessment=fcf_base,
        growth_recommendation=growth,
        discount_rate_recommendation=discount,
        terminal_growth_recommendation=terminal,
        projection_years_recommendation=projection_years,
        scenarios=scenarios,
        evidence=evidence,
        quality_context=quality_context,
        historical_context=historical_context,
        status=status,
        confidence=confidence,
        warnings=warnings,
        requires_review=requires_review,
        inputs_hash=inputs_hash,
    )


def build_assumption_set_for_analysis(
    session: Session,
    analysis: Analysis,
    *,
    ticker: str,
    normalized_fcf: dict,
    historical_context: dict,
    quality_context: dict,
    latest_actuals: dict[str, dict],
) -> AssumptionSetRecommendation:
    forward_evidence = collect_forward_evidence(session, analysis, latest_actuals=latest_actuals)
    return build_assumption_set(
        ticker=ticker,
        analysis_as_of_date=analysis.as_of_date.isoformat(),
        normalized_fcf=normalized_fcf,
        historical_context=historical_context,
        quality_context=quality_context,
        additional_evidence=forward_evidence,
    )


def effective_value(recommendation: AssumptionRecommendation) -> Decimal | None:
    return recommendation.approved_value if recommendation.approved_value is not None else recommendation.recommended_value


def build_effective_recommendations(
    assumption_set: AssumptionSetRecommendation,
    valid_approvals: dict[tuple[str, str], object],
    *,
    scenario: str = "base",
) -> dict[str, AssumptionRecommendation]:
    raw = {
        "base_fcf": assumption_set.fcf_base_assessment,
        "growth_rate": assumption_set.growth_recommendation,
        "discount_rate": assumption_set.discount_rate_recommendation,
        "terminal_growth_rate": assumption_set.terminal_growth_recommendation,
        "projection_years": assumption_set.projection_years_recommendation,
    }
    return {
        key: apply_approval(recommendation, valid_approvals.get((scenario, key)))
        for key, recommendation in raw.items()
    }


def build_effective_scenarios(
    effective_recommendations: dict[str, AssumptionRecommendation],
    evidence,
) -> tuple[ScenarioAssumptionRecommendation, ...]:
    base_fcf = effective_value(effective_recommendations["base_fcf"])
    base_growth = effective_value(effective_recommendations["growth_rate"])
    base_discount = effective_value(effective_recommendations["discount_rate"])
    base_terminal = effective_value(effective_recommendations["terminal_growth_rate"])
    projection_years_value = effective_value(effective_recommendations["projection_years"])
    if (
        base_fcf is None
        or base_growth is None
        or base_discount is None
        or base_terminal is None
        or projection_years_value is None
    ):
        return ()
    projection_years = int(projection_years_value)
    growths = scenario_growths(base_growth, evidence)
    discounts = (
        base_discount + DISCOUNT_RATE_SCENARIO_SPREAD,
        base_discount,
        max(Decimal("0"), base_discount - DISCOUNT_RATE_SCENARIO_SPREAD),
    )
    terminals = (
        max(Decimal("0"), base_terminal - TERMINAL_GROWTH_SCENARIO_SPREAD),
        base_terminal,
        base_terminal + TERMINAL_GROWTH_SCENARIO_SPREAD,
    )
    source_map = {
        key: recommendation.source_type
        for key, recommendation in effective_recommendations.items()
    }
    refs = tuple(
        ref
        for recommendation in effective_recommendations.values()
        for ref in recommendation.evidence_refs
    )
    warnings = tuple(
        dict.fromkeys(
            warning
            for recommendation in effective_recommendations.values()
            for warning in recommendation.warnings
        )
    )
    scenarios = []
    for name, growth, discount, terminal in zip(("bear", "base", "bull"), growths, discounts, terminals):
        scenario_warnings = warnings
        status = RECOMMENDED
        if terminal >= discount:
            scenario_warnings = scenario_warnings + ("TERMINAL_GROWTH_NOT_BELOW_DISCOUNT_RATE",)
            status = "INVALID_ASSUMPTION"
        scenarios.append(
            ScenarioAssumptionRecommendation(
                scenario=name,
                projection_years=projection_years,
                base_fcf=base_fcf,
                annual_growth_rate=growth,
                discount_rate=discount,
                terminal_growth_rate=terminal,
                status=status,
                confidence=effective_recommendations["growth_rate"].confidence,
                warnings=scenario_warnings,
                evidence_refs=refs,
                sources={
                    **source_map,
                    "base_source": "effective_base_assumptions",
                    "scenario_derivation_source": "PROJECT_POLICY_V1_SCENARIO_SPREAD",
                },
            )
        )
    return tuple(scenarios)


def preview_scenarios(
    assumption_set: AssumptionSetRecommendation,
    market: MarketSnapshotInput,
    normalized_fcf: dict,
) -> dict[str, dict]:
    value = Decimal(str(normalized_fcf["value"])) if normalized_fcf.get("value") not in (None, "") else None
    normalized = NormalizedValue(
        "free_cash_flow",
        "three_year_median",
        value,
        normalized_fcf.get("currency", market.financial_currency),
        AVAILABLE if value is not None else "UNAVAILABLE",
        tuple(normalized_fcf.get("issues", ())),
        tuple(normalized_fcf.get("input_refs", ())),
        normalized_fcf.get("inputs_hash", ""),
        tuple(int(year) for year in normalized_fcf.get("used_fiscal_years", ()) if str(year).isdigit()),
        tuple(Decimal(str(item)) for item in normalized_fcf.get("input_values", ()) if item not in (None, "")),
    )
    output: dict[str, dict] = {}
    for scenario in assumption_set.scenarios:
        if scenario.annual_growth_rate is None or scenario.discount_rate is None or scenario.terminal_growth_rate is None:
            output[scenario.scenario] = {"status": "UNAVAILABLE", "warnings": scenario.warnings}
            continue
        dcf_scenario = DCFScenario(
            scenario.scenario,
            scenario.projection_years,
            scenario.annual_growth_rate,
            scenario.discount_rate,
            scenario.terminal_growth_rate,
            "ASSUMPTION_PREVIEW",
        )
        summary = dcf_summary(equity_dcf(assumption_set.ticker, normalized, dcf_scenario), market)
        output[scenario.scenario] = {
            "status": "ASSUMPTION_PREVIEW" if summary.status == AVAILABLE else summary.status,
            "fair_value_per_unit": summary.fair_value_per_unit,
            "market_price": summary.market_price,
            "upside_downside": summary.upside_downside,
            "margin_of_safety": summary.margin_of_safety,
            "warnings": tuple(dict.fromkeys(scenario.warnings + summary.issues)),
            "inputs_hash": summary.inputs_hash,
        }
    return output


def _scenarios(
    fcf_base: AssumptionRecommendation,
    growth: AssumptionRecommendation,
    discount: AssumptionRecommendation,
    terminal: AssumptionRecommendation,
    evidence,
) -> tuple[ScenarioAssumptionRecommendation, ...]:
    base_growth = growth.recommended_value
    if base_growth is None:
        growths = (None, None, None)
    else:
        growths = scenario_growths(base_growth, evidence)
    base_discount = discount.approved_value or discount.recommended_value
    if base_discount is None:
        discounts = (None, None, None)
    else:
        discounts = (
            base_discount + DISCOUNT_RATE_SCENARIO_SPREAD,
            base_discount,
            max(Decimal("0"), base_discount - DISCOUNT_RATE_SCENARIO_SPREAD),
        )
    base_terminal = terminal.approved_value or terminal.recommended_value
    if base_terminal is None:
        terminal_growths = (None, None, None)
    else:
        terminal_growths = (
            max(Decimal("0"), base_terminal - TERMINAL_GROWTH_SCENARIO_SPREAD),
            base_terminal,
            base_terminal + TERMINAL_GROWTH_SCENARIO_SPREAD,
        )
    scenarios = []
    for name, growth_value, discount_value, terminal_value in zip(
        ("bear", "base", "bull"), growths, discounts, terminal_growths
    ):
        warnings = tuple(
            dict.fromkeys(
                fcf_base.warnings
                + growth.warnings
                + discount.warnings
                + terminal.warnings
            )
        )
        status = REVIEW_REQUIRED if warnings else RECOMMENDED
        if terminal_value is not None and discount_value is not None and terminal_value >= discount_value:
            warnings = warnings + ("TERMINAL_GROWTH_NOT_BELOW_DISCOUNT_RATE",)
            status = "INVALID_ASSUMPTION"
        scenarios.append(
            ScenarioAssumptionRecommendation(
                name,
                DEFAULT_PROJECTION_YEARS,
                fcf_base.recommended_value,
                growth_value,
                discount_value,
                terminal_value,
                status,
                growth.confidence,
                warnings,
                fcf_base.evidence_refs + growth.evidence_refs + discount.evidence_refs + terminal.evidence_refs,
                {
                    "base_fcf_source": fcf_base.source_type,
                    "growth_source": growth.source_type,
                    "discount_rate_source": discount.source_type,
                    "terminal_growth_source": terminal.source_type,
                    "projection_years_source": "PROJECT_POLICY_V1",
                },
            )
        )
    return tuple(scenarios)


def _overall_confidence(values: tuple[str, ...]) -> str:
    priority = {"VERY_LOW": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
    inverse = {value: key for key, value in priority.items()}
    return inverse[min(priority.get(value, 0) for value in values)]


def _manual_approvals(session: Session, analysis: Analysis) -> dict[str, ValuationAssumption]:
    rows = session.scalars(
        select(ValuationAssumption).where(
            ValuationAssumption.analysis_id == analysis.id,
            ValuationAssumption.method == "equity_dcf",
            ValuationAssumption.scenario == "base",
            ValuationAssumption.source_type.in_(("MANUAL_APPROVED", "MANUAL_APPROVED_OVERRIDE")),
        )
    ).all()
    return {row.key: row for row in rows}


def _apply_manual_approval(
    recommendation: AssumptionRecommendation,
    manual: ValuationAssumption | None,
) -> AssumptionRecommendation:
    if manual is None or manual.value is None:
        return recommendation
    if manual.source_type == "MANUAL_APPROVED_OVERRIDE" and not manual.note:
        return AssumptionRecommendation(
            **{
                **recommendation.__dict__,
                "warnings": recommendation.warnings + ("MANUAL_OVERRIDE_NOTE_REQUIRED",),
                "requires_review": True,
            }
        )
    return AssumptionRecommendation(
        assumption_key=recommendation.assumption_key,
        recommended_value=recommendation.recommended_value,
        unit=recommendation.unit,
        status=APPROVED,
        policy_id=recommendation.policy_id,
        policy_version=recommendation.policy_version,
        evidence_refs=recommendation.evidence_refs + (f"valuation_assumption:{manual.id}",),
        reasoning_summary=recommendation.reasoning_summary,
        confidence=recommendation.confidence,
        warnings=(),
        requires_review=False,
        source_type=manual.source_type or "MANUAL_APPROVED",
        approved_value=Decimal(manual.value),
        primary_anchor=recommendation.primary_anchor,
    )
