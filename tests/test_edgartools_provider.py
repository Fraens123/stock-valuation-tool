from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from stock_valuation.data.metric_requirements import (
    MetricRequirement,
    conditional_metrics,
    core_required_metrics,
    gate_metrics,
    metric_policy,
)
from stock_valuation.data.providers.edgartools_provider import normalize_edgartools_facts


@dataclass
class Fact:
    concept: str
    numeric_value: Decimal | int
    unit: str = "EUR"
    fiscal_year: int = 2025
    period_end: date = date(2025, 12, 31)
    period_start: date | None = date(2025, 1, 1)
    fiscal_period: str = "FY"
    filing_date: date = date(2026, 2, 25)
    accession: str = "0001628280-26-011378"
    form_type: str = "20-F"
    label: str = ""
    taxonomy: str = ""
    is_dimensioned: bool = False
    value: Decimal | int | None = None

    def __post_init__(self) -> None:
        if self.value is None:
            self.value = self.numeric_value


def instant(concept: str, value: int, year: int = 2025, *, filed: date | None = None, label: str = "") -> Fact:
    return Fact(
        concept=concept,
        numeric_value=Decimal(value),
        fiscal_year=year,
        period_end=date(year, 12, 31),
        period_start=None,
        filing_date=filed or date(year + 1, 2, 25),
        label=label,
    )


def duration(concept: str, value: int, year: int = 2025, *, filed: date | None = None, label: str = "") -> Fact:
    return Fact(
        concept=concept,
        numeric_value=Decimal(value),
        fiscal_year=year,
        period_end=date(year, 12, 31),
        period_start=date(year, 1, 1),
        filing_date=filed or date(year + 1, 2, 25),
        label=label,
    )


def test_metric_requirement_catalog_classifies_required_derived_optional() -> None:
    assert metric_policy("revenue").requirement == MetricRequirement.REQUIRED
    assert metric_policy("inventory").requirement == MetricRequirement.CONDITIONAL
    assert metric_policy("ebitda").requirement == MetricRequirement.DERIVED
    assert metric_policy("dividends_paid").requirement == MetricRequirement.OPTIONAL
    assert "inventory" not in core_required_metrics()
    assert "inventory" in conditional_metrics()
    assert "inventory" in gate_metrics()


def test_asml_fy2023_2025_core_regression_values_from_edgartools_facts() -> None:
    raw = [
        duration("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", 27558500000, 2023),
        duration("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", 28262900000, 2024),
        duration("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", 32667300000, 2025),
        duration("us-gaap:NetIncomeLoss", 7839000000, 2023),
        duration("us-gaap:NetIncomeLoss", 7571600000, 2024),
        duration("us-gaap:NetIncomeLoss", 9609400000, 2025),
        instant("us-gaap:Assets", 50566600000, 2025),
        instant("us-gaap:StockholdersEquity", 19612200000, 2025),
        duration("us-gaap:NetCashProvidedByUsedInOperatingActivities", 12658500000, 2025),
        instant("us-gaap:PropertyPlantAndEquipmentNet", 7893800000, 2025),
        duration("us-gaap:DepreciationDepletionAndAmortization", 1025900000, 2025),
    ]

    result = normalize_edgartools_facts(raw)
    by_key = {(fact.metric, fact.period_end.year): fact for fact in result.facts}

    assert by_key[("revenue", 2023)].value == Decimal("27558500000")
    assert by_key[("revenue", 2024)].value == Decimal("28262900000")
    assert by_key[("revenue", 2025)].value == Decimal("32667300000")
    assert by_key[("net_income", 2025)].value == Decimal("9609400000")
    assert by_key[("total_assets", 2025)].value == Decimal("50566600000")
    assert by_key[("shareholders_equity", 2025)].value == Decimal("19612200000")
    assert by_key[("operating_cash_flow", 2025)].value == Decimal("12658500000")
    assert by_key[("ppe_net", 2025)].value == Decimal("7893800000")
    assert by_key[("depreciation_amortization", 2025)].provider_field == "us-gaap:DepreciationDepletionAndAmortization"


def test_latest_official_filed_restatement_wins_and_versions_are_retained() -> None:
    old = duration("us-gaap:NetIncomeLoss", 100, 2025, filed=date(2026, 2, 1))
    restated = duration("us-gaap:NetIncomeLoss", 110, 2025, filed=date(2026, 3, 1))

    result = normalize_edgartools_facts([old, restated])
    net_income = next(fact for fact in result.facts if fact.metric == "net_income")

    assert net_income.value == Decimal("110")
    assert net_income.filing_date == date(2026, 3, 1)
    versions = [item for item in result.historical_versions if item.metric == "net_income"]
    assert len(versions) == 2
    assert [item.selected for item in versions].count(True) == 1
    assert any(item.value == Decimal("100") and not item.selected for item in versions)


def test_semantic_priority_wins_before_later_broader_restatement() -> None:
    result = normalize_edgartools_facts(
        [
            instant(
                "us-gaap:CashAndCashEquivalentsAtCarryingValue",
                29965000000,
                2023,
                filed=date(2024, 11, 1),
            ),
            instant(
                "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
                30737000000,
                2023,
                filed=date(2025, 10, 31),
            ),
        ]
    )
    cash = next(fact for fact in result.facts if fact.metric == "cash_and_equivalents")

    assert cash.value == Decimal("29965000000")
    assert cash.provider_field == "us-gaap:CashAndCashEquivalentsAtCarryingValue"


def test_short_term_debt_aggregates_interest_bearing_components_and_excludes_leases() -> None:
    result = normalize_edgartools_facts(
        [
            instant("us-gaap:ShortTermBorrowings", 100, label="Short-term borrowings"),
            instant("us-gaap:LongTermDebtCurrent", 40, label="Current portion of long-term debt"),
            instant("us-gaap:OperatingLeaseLiabilityCurrent", 999, label="Operating lease liability current"),
            instant("us-gaap:AccountsPayableCurrent", 888, label="Trade payables"),
        ]
    )
    debt = next(fact for fact in result.facts if fact.metric == "short_term_debt")

    assert debt.value == Decimal("140")
    assert debt.provider_field == "aggregation:us-gaap:ShortTermBorrowings+us-gaap:LongTermDebtCurrent"
    assert "OperatingLease" not in debt.note


def test_short_term_debt_uses_total_before_components_to_avoid_double_counting() -> None:
    result = normalize_edgartools_facts(
        [
            instant("us-gaap:DebtCurrent", 1499, label="Debt, current"),
            instant("us-gaap:LongTermDebtCurrent", 1500, label="Long-term debt, current maturities"),
        ]
    )
    debt = next(fact for fact in result.facts if fact.metric == "short_term_debt")

    assert debt.value == Decimal("1499")
    assert debt.provider_field == "us-gaap:DebtCurrent"


def test_depreciation_amortization_rejects_broad_other_noncash_rows() -> None:
    result = normalize_edgartools_facts(
        [
            duration(
                "us-gaap:DepreciationAndAmortization",
                999,
                label="Depreciation, amortization and other non-cash items",
            ),
            duration("us-gaap:DepreciationDepletionAndAmortization", 120, label="Depreciation and amortization"),
        ]
    )
    fact = next(row for row in result.facts if row.metric == "depreciation_amortization")
    assert fact.value == Decimal("120")


def test_depreciation_amortization_aggregates_standard_split_components() -> None:
    result = normalize_edgartools_facts(
        [
            duration("us-gaap:Depreciation", 15200, label="Depreciation"),
            duration("us-gaap:AmortizationOfIntangibleAssets", 4800, label="Amortization of intangible assets"),
            duration("us-gaap:FinanceLeaseRightOfUseAssetAmortization", 1800, label="Finance lease right-of-use asset amortization"),
        ]
    )
    fact = next(row for row in result.facts if row.metric == "depreciation_amortization")

    assert fact.value == Decimal("20000")
    assert fact.provider_field == "aggregation:us-gaap:Depreciation+us-gaap:AmortizationOfIntangibleAssets"


def test_ifrs_trade_payables_aggregate_supplier_and_related_party_components() -> None:
    result = normalize_edgartools_facts(
        [
            instant("ifrs-full:TradeAndOtherCurrentPayablesToTradeSuppliers", 54879700000, label="Trade suppliers"),
            instant("ifrs-full:TradeAndOtherCurrentPayablesToRelatedParties", 1642600000, label="Related parties"),
        ]
    )
    fact = next(row for row in result.facts if row.metric == "accounts_payable")

    assert fact.value == Decimal("56522300000")


def test_ppe_net_excludes_right_of_use_assets() -> None:
    result = normalize_edgartools_facts(
        [
            instant("us-gaap:PropertyPlantAndEquipmentNet", 700, label="Property, plant and equipment, net"),
            instant("us-gaap:PropertyPlantAndEquipmentNet", 900, label="Right-of-use lease assets"),
        ]
    )
    fact = next(row for row in result.facts if row.metric == "ppe_net")
    assert fact.value == Decimal("700")


def test_missing_field_investigation_rules_cover_short_term_investments_and_dividends() -> None:
    result = normalize_edgartools_facts(
        [
            instant("us-gaap:AvailableForSaleSecuritiesDebtSecuritiesCurrent", 405900000),
            duration("us-gaap:DividendsCommonStockCash", -2550300000),
        ]
    )
    by_metric = {fact.metric: fact for fact in result.facts}

    assert by_metric["short_term_investments"].value == Decimal("405900000")
    assert by_metric["dividends_paid"].value == Decimal("2550300000")
    assert "intangible_purchases" not in by_metric
