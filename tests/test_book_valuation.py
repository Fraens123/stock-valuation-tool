from __future__ import annotations

from datetime import date
from decimal import Decimal
import json
from pathlib import Path

from stock_valuation.book_valuation.dcf import fair_value, present_value_owner_earnings, terminal_value
from stock_valuation.book_valuation.discount_rate import excel_book_discount_rate
from stock_valuation.book_valuation.models import AVAILABLE, UNAVAILABLE
from stock_valuation.book_valuation.multiplicator_method import PORTER_KEYS, fair_pe_from_components
from stock_valuation.book_valuation.owner_earnings import (
    change_in_operating_working_capital,
    operating_working_capital,
    owner_earnings,
    owner_earnings_capex,
    point,
)
from stock_valuation.valuation.models import FinancialPoint, MarketSnapshotInput
from stock_valuation.valuation.multiples import current_market_multiples


def _book_point(key: str, value: str):
    return point(key, 2025, Decimal(value), "EUR")


def _market(*, market_cap: str | None = "1000", ev: str | None = None) -> MarketSnapshotInput:
    return MarketSnapshotInput(
        ticker="EXM",
        company="Example",
        analysis_as_of_date="2026-08-23",
        market_snapshot_id="m1",
        market_data_version="market-data-v1.0",
        security_type="ordinary_share",
        price=Decimal("10"),
        market_cap=Decimal(market_cap) if market_cap is not None else None,
        enterprise_value=Decimal(ev) if ev is not None else None,
        shares_outstanding=Decimal("100"),
        share_basis="ORDINARY_SHARES",
        financial_currency="EUR",
        trading_currency="EUR",
        fx_rate=None,
        adr_ratio=None,
        underlying_share_ratio=None,
        input_refs=("market:m1",),
        inputs_hash="mh",
    )


def _financial_points() -> dict[str, FinancialPoint]:
    return {
        key: FinancialPoint(key, 2025, Decimal(value), "EUR", AVAILABLE, f"calc:{key}:2025", f"h-{key}")
        for key, value in {
            "net_income": "100",
            "shareholders_equity": "500",
            "operating_cash_flow": "125",
            "operating_income": "80",
            "ebitda": "120",
            "revenue": "400",
            "free_cash_flow": "90",
            "entity_free_cash_flow_excel_book": "105",
        }.items()
    }


def test_market_cap_multiples_work_without_enterprise_value() -> None:
    rows = {item.metric_id: item for item in current_market_multiples(_financial_points(), _market(ev=None))}
    assert rows["latest_fy_pe"].status == AVAILABLE
    assert rows["latest_fy_pe"].value == Decimal("10")
    assert rows["latest_fy_pb"].status == AVAILABLE
    assert rows["latest_fy_pb"].value == Decimal("2")
    assert rows["latest_fy_p_ocf"].status == AVAILABLE
    assert rows["latest_fy_p_ocf"].value == Decimal("8")
    assert rows["latest_fy_ev_ebit"].status == UNAVAILABLE
    assert rows["latest_fy_ev_ebitda"].status == UNAVAILABLE
    assert rows["latest_fy_ev_sales"].status == UNAVAILABLE


def test_ev_fcf_uses_entity_fcf_not_equity_fcf() -> None:
    rows = {item.metric_id: item for item in current_market_multiples(_financial_points(), _market(ev="2100"))}
    assert rows["latest_fy_ev_fcf"].status == AVAILABLE
    assert rows["latest_fy_ev_fcf"].value == Decimal("20")


def test_negative_denominator_is_not_meaningful() -> None:
    points = _financial_points()
    points["net_income"] = FinancialPoint("net_income", 2025, Decimal("-1"), "EUR", AVAILABLE, "calc:net_income:2025", "h")
    row = {item.metric_id: item for item in current_market_multiples(points, _market())}["latest_fy_pe"]
    assert row.status == "NOT_MEANINGFUL"
    assert "DENOMINATOR_NOT_POSITIVE" in row.issues


def test_owner_earnings_formula_and_no_zero_imputing() -> None:
    owc_2024 = operating_working_capital(inventory=_book_point("inventory", "20"), accounts_receivable=_book_point("accounts_receivable", "30"), accounts_payable=_book_point("accounts_payable", "10"))
    owc_2025 = operating_working_capital(inventory=_book_point("inventory", "25"), accounts_receivable=_book_point("accounts_receivable", "35"), accounts_payable=_book_point("accounts_payable", "15"))
    delta = change_in_operating_working_capital(owc_2025, owc_2024)
    capex = owner_earnings_capex(capital_expenditures=_book_point("capital_expenditures", "40"), intangible_purchases=_book_point("intangible_purchases", "5"))
    result = owner_earnings(net_income=_book_point("net_income", "100"), depreciation_amortization=_book_point("depreciation_amortization", "12"), capex=capex, change_in_owc=delta)
    assert owc_2025.value == Decimal("45")
    assert delta.value == Decimal("5")
    assert capex.value == Decimal("45")
    assert result.value == Decimal("62")
    missing_capex = owner_earnings_capex(capital_expenditures=_book_point("capital_expenditures", "40"))
    assert missing_capex.status == UNAVAILABLE
    assert "MISSING_INTANGIBLE_PURCHASES" in missing_capex.issues


def test_excel_book_discount_terminal_and_fair_value_formula() -> None:
    fixture = json.loads(Path("tests/fixtures/book_valuation_excel_fixture.json").read_text(encoding="utf-8"))
    values = fixture["numeric_fixture"]
    discount = excel_book_discount_rate(fair_pe=Decimal(values["fair_pe"]), risk_free_rate=Decimal(values["risk_free_rate"]))
    assert discount.risk_premium.value == Decimal(values["risk_premium"])
    assert discount.minimum_return_addon.value == Decimal(values["minimum_return_addon"])
    assert discount.cost_of_equity.value == Decimal(values["cost_of_equity"])
    rows = present_value_owner_earnings((Decimal("100"), Decimal("110")), Decimal("0.10"))
    assert rows[0].present_value.value == Decimal("90.90909090909090909090909091")
    terminal = terminal_value(Decimal(values["terminal_last_owner_earnings"]), Decimal("0.10"), Decimal(values["terminal_growth_rate"]), values["projection_years"])
    assert terminal.terminal_value.value == Decimal(values["terminal_value"])
    assert terminal_value(Decimal("110"), Decimal("0.02"), Decimal("0.02"), 2).terminal_value.status == UNAVAILABLE
    fair = fair_value(
        present_value_rows=rows,
        present_value_terminal_value=Decimal("1000"),
        shares_outstanding=Decimal("10"),
        margin_of_safety=Decimal("0.50"),
        market_price=Decimal("60"),
    )
    assert fair.equity_value.value == rows[0].present_value.value + rows[1].present_value.value + Decimal("1000")
    assert fair.fair_value_after_safety_margin.value == fair.fair_value_per_share.value * Decimal("0.50")


def test_multiplicator_method_formula() -> None:
    result = fair_pe_from_components(
        base_pe=Decimal("7.5"),
        financial_stability_addon=Decimal("2"),
        porter_scores={key: Decimal("3") for key in PORTER_KEYS},
        market_position_addon=Decimal("2.2"),
        profitability_multiplier=Decimal("2"),
        growth_addon=Decimal("0.8"),
        individuality_addon=Decimal("2"),
        forecast_net_income=Decimal("1000"),
        shares_outstanding=Decimal("100"),
    )
    assert result.market_position_points.value == Decimal("15")
    assert result.market_profitability_addon.value == Decimal("4.4")
    assert result.fair_pe.value == Decimal("16.7")
    assert result.forecast_eps.value == Decimal("10")
    assert result.fair_price_per_share.value == Decimal("167.0")
