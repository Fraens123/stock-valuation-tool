from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal

from stock_valuation.valuation.dcf import equity_dcf
from stock_valuation.valuation.models import DCFScenario, MarketSnapshotInput, NormalizedValue, stable_hash
from stock_valuation.valuation.summary import dcf_summary
from stock_valuation.valuation_assumptions.cashflow import assess_fcf_base
from stock_valuation.valuation_assumptions.discount_rate import discount_rate_recommendation
from stock_valuation.valuation_assumptions.evidence import evidence_from_historical_context
from stock_valuation.valuation_assumptions.growth import growth_recommendation, scenario_growths
from stock_valuation.valuation_assumptions.models import (
    ASSUMPTION_ENGINE_VERSION,
    ASSUMPTION_POLICY_VERSION,
    AVAILABLE,
    LOW,
    PROJECT_POLICY_ID,
    RECOMMENDED,
    REVIEW_REQUIRED,
    AssumptionRecommendation,
    AssumptionSetRecommendation,
    ScenarioAssumptionRecommendation,
)
from stock_valuation.valuation_assumptions.policy import (
    DEFAULT_BEAR_DISCOUNT_RATE,
    DEFAULT_BEAR_TERMINAL_GROWTH,
    DEFAULT_BULL_DISCOUNT_RATE,
    DEFAULT_BULL_TERMINAL_GROWTH,
    DEFAULT_PROJECTION_YEARS,
)
from stock_valuation.valuation_assumptions.terminal_growth import terminal_growth_recommendation


def build_assumption_set(
    *,
    ticker: str,
    analysis_as_of_date: str,
    normalized_fcf: dict,
    historical_context: dict,
    quality_context: dict,
) -> AssumptionSetRecommendation:
    evidence = evidence_from_historical_context(ticker, historical_context)
    fcf_base = assess_fcf_base(normalized_fcf)
    growth = growth_recommendation(evidence)
    discount = discount_rate_recommendation()
    terminal = terminal_growth_recommendation(discount.recommended_value or Decimal("0"))
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
    discounts = (
        DEFAULT_BEAR_DISCOUNT_RATE,
        discount.recommended_value,
        DEFAULT_BULL_DISCOUNT_RATE,
    )
    terminal_growths = (
        DEFAULT_BEAR_TERMINAL_GROWTH,
        terminal.recommended_value,
        DEFAULT_BULL_TERMINAL_GROWTH,
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
