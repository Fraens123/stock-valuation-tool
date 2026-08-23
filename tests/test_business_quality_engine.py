from __future__ import annotations

from decimal import Decimal

from stock_valuation.quality.engine import evaluate_business_quality
from stock_valuation.quality.models import (
    AVAILABLE,
    INSUFFICIENT_HISTORY,
    NOT_APPLICABLE,
    UNAVAILABLE,
    QualityInput,
)
from stock_valuation.quality.scoring import QualityScoringConfig, clamp_score, weighted_average


def _calc(metric: str, year: int, value: str, status: str = AVAILABLE, issue: str | None = None) -> QualityInput:
    return QualityInput(
        metric_id=metric,
        fiscal_year=year,
        window="FY",
        value=Decimal(value) if value != "" else None,
        unit="decimal_ratio",
        status=status,
        issue=issue,
        source="calculation",
        inputs_hash=f"{metric}-{year}-{value}-{status}",
        source_version="calc-v1.0",
    )


def _hist(metric: str, year: int | None, window: str, value: str, status: str = AVAILABLE, issue: str | None = None) -> QualityInput:
    return QualityInput(
        metric_id=metric,
        fiscal_year=year,
        window=window,
        value=Decimal(value) if value != "" else None,
        unit="decimal_ratio",
        status=status,
        issue=issue,
        source="historical",
        source_version="historical-v1.0",
    )


def _complete_inputs() -> list[QualityInput]:
    rows: list[QualityInput] = []
    for year in (2023, 2024, 2025):
        for metric, value in {
            "gross_margin": "0.45",
            "operating_margin": "0.30",
            "net_margin": "0.22",
            "ebitda_margin": "0.35",
            "free_cash_flow_margin": "0.18",
            "return_on_assets": "0.12",
            "return_on_equity": "0.25",
            "equity_ratio": "0.45",
            "debt_to_assets": "0.20",
            "debt_to_equity": "0.45",
            "net_debt_to_ebitda": "0.60",
            "current_ratio": "1.80",
            "quick_ratio": "1.40",
            "cash_ratio": "0.80",
            "capex_ratio": "0.25",
            "inventory_intensity": "0.05",
            "inventory_days": "20",
        }.items():
            rows.append(_calc(metric, year, value))
    for metric in ("revenue", "net_income", "free_cash_flow"):
        rows.append(_hist(metric, 2024, "YoY", "0.08"))
        rows.append(_hist(metric, 2025, "YoY", "0.10"))
        rows.append(_hist(metric, 2025, "3Y_CAGR", "0.09"))
        rows.append(_hist(metric, 2025, "negative_years", "0"))
        rows.append(_hist(metric, 2025, "missing_years", "0"))
    return rows


def test_quality_engine_separates_measurement_assessment_and_score() -> None:
    result = evaluate_business_quality("EXM", _complete_inputs())
    metric = next(item for item in result.metrics if item.metric_id == "operating_margin_quality")

    assert metric.value == Decimal("0.30")
    assert metric.assessment == "STRONG"
    assert metric.score == Decimal("9")
    assert result.overall_score is not None
    assert result.assessment in {"STRONG", "SOLID"}


def test_not_separately_reported_inventory_becomes_not_applicable_not_bad_score() -> None:
    rows = [
        row
        for row in _complete_inputs()
        if row.metric_id not in {"inventory_intensity", "inventory_days"}
    ]
    rows.append(_calc("inventory_intensity", 2025, "", UNAVAILABLE, "NOT_SEPARATELY_REPORTED:inventory"))
    rows.append(_calc("inventory_days", 2025, "", UNAVAILABLE, "NOT_SEPARATELY_REPORTED:inventory"))

    result = evaluate_business_quality("SOFT", rows)
    inventory = next(item for item in result.metrics if item.metric_id == "inventory_applicability_quality")

    assert inventory.status == NOT_APPLICABLE
    assert inventory.score is None
    assert not any("Inventory Applicability" in factor for factor in result.negative_factors)


def test_missing_and_division_by_zero_upstream_inputs_stay_unavailable_without_zero_imputation() -> None:
    rows = [row for row in _complete_inputs() if row.metric_id != "current_ratio"]
    rows.append(_calc("current_ratio", 2025, "", UNAVAILABLE, "DIVISION_BY_ZERO:current_liabilities"))

    result = evaluate_business_quality("ZERO", rows)
    current = next(item for item in result.metrics if item.metric_id == "current_ratio_quality")

    assert current.status == UNAVAILABLE
    assert current.value is None
    assert current.score is None
    assert current.issue == "DIVISION_BY_ZERO:current_liabilities"


def test_negative_growth_and_negative_years_are_visible_and_scored_with_bounds() -> None:
    rows = [
        row
        for row in _complete_inputs()
        if not (
            row.source == "historical"
            and row.metric_id == "free_cash_flow"
            and row.window in {"YoY", "3Y_CAGR"}
        )
    ]
    rows.append(_hist("free_cash_flow", 2025, "YoY", "-0.20"))
    rows.append(_hist("free_cash_flow", 2025, "negative_years", "2"))

    result = evaluate_business_quality("NEG", rows)
    fcf_growth = next(item for item in result.metrics if item.metric_id == "fcf_growth_quality")
    negative_years = next(item for item in result.metrics if item.metric_id == "negative_years_quality")

    assert fcf_growth.value == Decimal("-0.20")
    assert fcf_growth.score == Decimal("2")
    assert negative_years.value is not None
    assert Decimal("0") <= (negative_years.score or Decimal("-1")) <= Decimal("10")


def test_insufficient_history_is_not_a_zero_score() -> None:
    rows = [
        row
        for row in _complete_inputs()
        if not (row.source == "historical" and row.metric_id == "revenue")
    ]
    rows.append(_hist("revenue", 2025, "YoY", "", UNAVAILABLE, "MISSING_PRIOR_YEAR"))

    result = evaluate_business_quality("HIST", rows)
    growth = next(item for item in result.metrics if item.metric_id == "revenue_growth_quality")

    assert growth.status == INSUFFICIENT_HISTORY
    assert growth.score is None


def test_volatility_score_and_weighting_are_reproducible() -> None:
    rows = _complete_inputs()
    first = evaluate_business_quality("REP", rows)
    second = evaluate_business_quality("REP", rows)
    volatility = next(item for item in first.metrics if item.metric_id == "margin_volatility_quality")

    assert volatility.status == AVAILABLE
    assert volatility.inputs_hash == next(
        item for item in second.metrics if item.metric_id == "margin_volatility_quality"
    ).inputs_hash
    assert first.overall_score == second.overall_score
    assert weighted_average([(Decimal("8"), Decimal("0.25")), (Decimal("4"), Decimal("0.75"))]) == Decimal("5.00")


def test_margin_volatility_uses_time_series_not_cross_metric_dispersion() -> None:
    rows = [
        row
        for row in _complete_inputs()
        if row.metric_id not in {"gross_margin", "operating_margin", "net_margin", "ebitda_margin", "free_cash_flow_margin"}
    ]
    for year in (2023, 2024, 2025):
        rows.extend(
            [
                _calc("gross_margin", year, "0.80"),
                _calc("operating_margin", year, "0.30"),
                _calc("net_margin", year, "0.10"),
            ]
        )

    result = evaluate_business_quality("MARGIN", rows)
    volatility = next(item for item in result.metrics if item.metric_id == "margin_volatility_quality")

    assert volatility.value == Decimal("0")
    assert volatility.score == Decimal("9")
    assert len(volatility.input_refs) == 9


def test_growth_volatility_aggregates_per_growth_series() -> None:
    rows = [
        row
        for row in _complete_inputs()
        if not (row.source == "historical" and row.window == "YoY")
    ]
    for metric, first, second in (
        ("revenue", "0.10", "0.10"),
        ("net_income", "0.20", "0.20"),
        ("free_cash_flow", "-0.05", "-0.05"),
    ):
        rows.append(_hist(metric, 2024, "YoY", first))
        rows.append(_hist(metric, 2025, "YoY", second))

    result = evaluate_business_quality("GROWTH", rows)
    volatility = next(item for item in result.metrics if item.metric_id == "growth_volatility_quality")

    assert volatility.value == Decimal("0")
    assert volatility.score == Decimal("9")
    assert len(volatility.input_refs) == 6


def test_missing_years_is_data_confidence_not_scored_business_quality() -> None:
    result = evaluate_business_quality("MISS", _complete_inputs())
    missing = next(item for item in result.metrics if item.metric_id == "missing_years_quality")
    stability = next(item for item in result.component_scores if item.component_id == "stability")

    assert missing.category == "data_confidence"
    assert missing.assessment == "INFORMATIVE"
    assert missing.score is None
    assert "missing_years_quality" not in stability.contributing_metrics


def test_capex_intensity_has_explicit_weighted_component() -> None:
    result = evaluate_business_quality("CAPEX", _complete_inputs())
    cashflow = next(item for item in result.component_scores if item.component_id == "cashflow_quality")

    assert "capex_intensity_quality" in cashflow.contributing_metrics


def test_score_bounds_and_configurable_weights() -> None:
    config = QualityScoringConfig(component_weights={"profitability": Decimal("1")})
    result = evaluate_business_quality("CFG", _complete_inputs(), config=config)

    assert clamp_score(Decimal("-3")) == Decimal("0")
    assert clamp_score(Decimal("13")) == Decimal("10")
    assert len(result.component_scores) == 1
    assert result.component_scores[0].component_id == "profitability"


def test_no_market_or_provider_metric_is_required_for_quality() -> None:
    forbidden = {
        "share_price",
        "shares_outstanding",
        "market_cap",
        "enterprise_value",
        "pe",
        "ev_ebitda",
        "dcf",
        "fair_value",
    }
    result = evaluate_business_quality("NOMKT", _complete_inputs())
    used = {metric for item in result.metrics for metric in item.input_metrics}

    assert used.isdisjoint(forbidden)
    assert all("provider" not in ref.casefold() for item in result.metrics for ref in item.input_refs)
