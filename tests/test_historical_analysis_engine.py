from __future__ import annotations

from decimal import Decimal

from stock_valuation.metrics.historical_analysis import (
    HistoricalPoint,
    analyze_historical_series,
    cagr,
    series_from_points,
    stability_profile,
    yoy_growth,
)


def _series(metric: str, values: dict[int, str | None], *, status: str = "AVAILABLE"):
    return series_from_points(
        [
            HistoricalPoint(metric, year, Decimal(value) if value is not None else None, "currency", status if value is not None else "UNAVAILABLE")
            for year, value in values.items()
        ]
    )


def test_yoy_growth_handles_first_year_and_standard_growth() -> None:
    result = yoy_growth(_series("revenue", {2023: "100", 2024: "120"}))

    assert result[0].status == "UNAVAILABLE"
    assert result[0].issue == "MISSING_PRIOR_YEAR"
    assert result[1].value == Decimal("0.2")


def test_yoy_growth_rejects_negative_base_year() -> None:
    result = yoy_growth(_series("net_income", {2023: "-10", 2024: "20"}))

    assert result[1].status == "UNAVAILABLE"
    assert result[1].issue == "NEGATIVE_BASE"


def test_cagr_requires_complete_positive_window() -> None:
    series = _series("revenue", {2023: "100", 2024: "110", 2025: "121"})

    assert cagr(series, 3).value == Decimal("0.10")
    assert cagr(series, 5).status == "UNAVAILABLE"
    assert cagr(series, 5).issue == "INSUFFICIENT_HISTORY"


def test_missing_calendar_year_is_counted_explicitly() -> None:
    profile = {item.window: item for item in stability_profile(_series("free_cash_flow", {2022: "10", 2024: "12"}))}

    assert profile["missing_years"].value == Decimal("1")


def test_not_separately_reported_point_blocks_inventory_trend_only() -> None:
    inventory = series_from_points(
        [
            HistoricalPoint("inventory_intensity", 2023, None, "decimal_ratio", "UNAVAILABLE", "NOT_SEPARATELY_REPORTED"),
            HistoricalPoint("inventory_intensity", 2024, None, "decimal_ratio", "UNAVAILABLE", "NOT_SEPARATELY_REPORTED"),
        ]
    )
    current_ratio = series_from_points(
        [
            HistoricalPoint("current_ratio", 2023, Decimal("1.1"), "decimal_ratio"),
            HistoricalPoint("current_ratio", 2024, Decimal("1.2"), "decimal_ratio"),
        ]
    )
    analysis = analyze_historical_series(
        {
            "inventory_intensity": inventory,
            "current_ratio": current_ratio,
        }
    )

    assert any(item.metric_id == "inventory_intensity" and item.window == "missing_years" for item in analysis["working_capital"])
    assert analysis["yoy_growth"] == ()
