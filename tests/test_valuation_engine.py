from __future__ import annotations

from decimal import Decimal

from stock_valuation.valuation.dcf import equity_dcf
from stock_valuation.valuation.models import (
    AVAILABLE,
    INVALID_ASSUMPTION,
    NOT_MEANINGFUL,
    DCFScenario,
    FinancialPoint,
    MarketSnapshotInput,
)
from stock_valuation.valuation.multiples import current_market_multiples
from stock_valuation.valuation.normalization import normalize_three_year_metric
from stock_valuation.valuation.summary import dcf_summary, listed_equivalent_units


def point(metric: str, year: int, value: str | None, currency: str = "USD") -> FinancialPoint:
    return FinancialPoint(
        metric,
        year,
        Decimal(value) if value is not None else None,
        currency,
        AVAILABLE if value is not None else "UNAVAILABLE",
        f"calculation:{metric}:{year}",
        f"hash:{metric}:{year}:{value}",
    )


def market(**overrides) -> MarketSnapshotInput:
    values = {
        "ticker": "TEST",
        "company": "Test Co",
        "analysis_as_of_date": "2026-08-23",
        "security_type": "ordinary_share",
        "price": Decimal("100"),
        "market_cap": Decimal("1000"),
        "enterprise_value": Decimal("1200"),
        "shares_outstanding": Decimal("10"),
        "share_basis": "ORDINARY_SHARES",
        "financial_currency": "USD",
        "trading_currency": "USD",
        "fx_rate": None,
        "adr_ratio": None,
        "underlying_share_ratio": None,
        "input_refs": ("market:TEST",),
        "inputs_hash": "market-hash",
    }
    values.update(overrides)
    return MarketSnapshotInput(**values)


def by_id(results):
    return {result.metric_id: result for result in results}


def test_current_market_multiples_formulas_and_yields():
    results = by_id(
        current_market_multiples(
            {
                "net_income": point("net_income", 2025, "100"),
                "operating_income": point("operating_income", 2025, "80"),
                "ebitda": point("ebitda", 2025, "120"),
                "free_cash_flow": point("free_cash_flow", 2025, "50"),
            },
            market(),
        )
    )

    assert results["latest_fy_pe"].value == Decimal("10")
    assert results["latest_fy_ev_ebit"].value == Decimal("15")
    assert results["latest_fy_ev_ebitda"].value == Decimal("10")
    assert results["latest_fy_p_fcf"].value == Decimal("20")
    assert results["earnings_yield"].value == Decimal("0.1")
    assert results["fcf_yield"].value == Decimal("0.05")


def test_negative_and_zero_denominators_are_not_meaningful():
    results = by_id(
        current_market_multiples(
            {
                "net_income": point("net_income", 2025, "-1"),
                "operating_income": point("operating_income", 2025, "0"),
                "ebitda": point("ebitda", 2025, "10"),
                "free_cash_flow": point("free_cash_flow", 2025, "-5"),
            },
            market(),
        )
    )

    assert results["latest_fy_pe"].status == NOT_MEANINGFUL
    assert results["latest_fy_ev_ebit"].status == NOT_MEANINGFUL
    assert results["latest_fy_p_fcf"].status == NOT_MEANINGFUL


def test_normalization_average_median_missing_and_outlier():
    points = (point("free_cash_flow", 2023, "100"), point("free_cash_flow", 2024, "110"), point("free_cash_flow", 2025, "500"))

    median_result = normalize_three_year_metric("free_cash_flow", points)
    average_result = normalize_three_year_metric("free_cash_flow", points, method="three_year_average")
    missing_result = normalize_three_year_metric("free_cash_flow", (point("free_cash_flow", 2025, None),))

    assert median_result.value == Decimal("110")
    assert "OUTLIER_REVIEW" in median_result.issues
    assert average_result.value == Decimal("236.6666666666666666666666667")
    assert missing_result.status == "UNAVAILABLE"


def test_dcf_projection_and_terminal_growth_validation():
    normalized = normalize_three_year_metric(
        "free_cash_flow",
        (point("free_cash_flow", 2023, "90"), point("free_cash_flow", 2024, "100"), point("free_cash_flow", 2025, "110")),
    )

    result = equity_dcf("TEST", normalized, DCFScenario("base", 2, Decimal("0.05"), Decimal("0.10"), Decimal("0.02")))
    invalid = equity_dcf("TEST", normalized, DCFScenario("bad", 5, Decimal("0.05"), Decimal("0.02"), Decimal("0.02")))

    assert result.status == AVAILABLE
    assert len(result.projected_rows) == 2
    assert result.projected_rows[0].projected_fcf == Decimal("105.00")
    assert result.terminal_value is not None
    assert invalid.status == INVALID_ASSUMPTION
    assert "TERMINAL_GROWTH_NOT_BELOW_DISCOUNT_RATE" in invalid.issues


def test_equity_dcf_does_not_subtract_net_debt_and_summary_uses_market_units():
    normalized = normalize_three_year_metric(
        "free_cash_flow",
        (point("free_cash_flow", 2023, "100"), point("free_cash_flow", 2024, "100"), point("free_cash_flow", 2025, "100")),
    )
    dcf = equity_dcf("TEST", normalized, DCFScenario("base", 1, Decimal("0"), Decimal("0.10"), Decimal("0")))
    summary = dcf_summary(dcf, market(shares_outstanding=Decimal("10"), price=Decimal("50")))

    assert dcf.equity_value == Decimal("1000")
    assert summary.fair_value_per_unit == Decimal("100")
    assert summary.upside_downside == Decimal("1")


def test_fx_conversion_and_adr_equivalent_units():
    ordinary_backed_adr = market(
        security_type="ADR",
        financial_currency="EUR",
        trading_currency="USD",
        fx_rate=Decimal("2"),
        shares_outstanding=Decimal("1000"),
        adr_ratio=Decimal("1"),
        underlying_share_ratio=Decimal("5"),
    )
    normalized = normalize_three_year_metric(
        "free_cash_flow",
        (
            point("free_cash_flow", 2023, "100", "EUR"),
            point("free_cash_flow", 2024, "100", "EUR"),
            point("free_cash_flow", 2025, "100", "EUR"),
        ),
    )
    dcf = equity_dcf("TEST", normalized, DCFScenario("base", 1, Decimal("0"), Decimal("0.10"), Decimal("0")))
    summary = dcf_summary(dcf, ordinary_backed_adr)

    assert listed_equivalent_units(ordinary_backed_adr) == (Decimal("200"), None)
    assert summary.fair_value_per_unit == Decimal("10")


def test_inputs_hash_reproducibility():
    points = (point("free_cash_flow", 2023, "100"), point("free_cash_flow", 2024, "110"), point("free_cash_flow", 2025, "120"))

    first = normalize_three_year_metric("free_cash_flow", points)
    second = normalize_three_year_metric("free_cash_flow", tuple(reversed(points)))

    assert first.inputs_hash == second.inputs_hash
