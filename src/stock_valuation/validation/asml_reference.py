from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


ASML_2025_US_GAAP_SOURCE = (
    "https://ourbrand.asml.com/m/71076aaad607de4d/original/"
    "asml-2025-annual-report-based-on-us-gaap.pdf"
)


@dataclass(frozen=True)
class PrimarySourceReference:
    metric: str
    period_end: date
    value: Decimal
    label: str
    source_url: str
    critical: bool = True
    note: str | None = None


def _eur(metric: str, year: int, millions: str, label: str, *, critical: bool = True, note: str | None = None) -> PrimarySourceReference:
    return PrimarySourceReference(
        metric=metric,
        period_end=date(year, 12, 31),
        value=Decimal(millions) * Decimal("1000000"),
        label=label,
        source_url=ASML_2025_US_GAAP_SOURCE,
        critical=critical,
        note=note,
    )


# Historical control values only. These values are not valuation assumptions and are
# never used to fill missing provider data. They exist exclusively to validate whether
# provider fields mean what our internal schema says they mean.
ASML_US_GAAP_REFERENCES: tuple[PrimarySourceReference, ...] = (
    # 2025 income statement
    _eur("revenue", 2025, "32667.3", "Total net sales"),
    _eur("cost_of_revenue", 2025, "15409.3", "Total cost of sales"),
    _eur("gross_profit", 2025, "17258.0", "Gross profit"),
    _eur("research_and_development", 2025, "4698.8", "R&D costs"),
    _eur("operating_income", 2025, "11301.4", "Income from operations"),
    _eur("pretax_income", 2025, "11406.1", "Income before income taxes"),
    _eur("net_income", 2025, "9609.4", "Net income"),
    # 2025 balance sheet
    _eur("total_assets", 2025, "50566.6", "Total assets"),
    _eur("current_assets", 2025, "30616.1", "Total current assets"),
    _eur("cash_and_equivalents", 2025, "12916.0", "Cash and cash equivalents"),
    _eur(
        "cash_and_short_term_investments",
        2025,
        "13321.9",
        "Cash and cash equivalents + short-term investments",
        critical=False,
        note="Cross-check field; provider definitions can differ and must not replace the components.",
    ),
    _eur(
        "accounts_receivable",
        2025,
        "3023.0",
        "Accounts receivable, net",
        note="Provider field must represent trade/accounts receivable and not a broader receivables aggregate.",
    ),
    _eur("inventory", 2025, "11429.3", "Inventories, net"),
    _eur("ppe_net", 2025, "7893.8", "Property, plant and equipment, net"),
    _eur("goodwill", 2025, "4588.6", "Goodwill"),
    _eur("total_liabilities", 2025, "30954.4", "Total liabilities"),
    _eur("current_liabilities", 2025, "24263.9", "Total current liabilities"),
    _eur("accounts_payable", 2025, "3521.8", "Accounts payable"),
    _eur(
        "short_term_debt",
        2025,
        "1681.9",
        "Short-term borrowings and current portion of long-term debt",
        critical=False,
    ),
    _eur("long_term_debt", 2025, "2709.0", "Long-term debt"),
    _eur("shareholders_equity", 2025, "19612.2", "Total shareholders' equity"),
    # 2025 cash flow
    _eur("operating_cash_flow", 2025, "12658.5", "Net cash provided by operating activities"),
    _eur(
        "capital_expenditures",
        2025,
        "1573.6",
        "Purchases of property, plant and equipment",
        note="Official PP&E cash purchases. Intangible purchases are intentionally excluded here.",
    ),
    _eur("depreciation_amortization", 2025, "1025.9", "Depreciation and amortization"),
    _eur("dividends_paid", 2025, "2550.3", "Dividend paid", critical=False),
    # 2024 income statement
    _eur("revenue", 2024, "28262.9", "Total net sales"),
    _eur("cost_of_revenue", 2024, "13770.9", "Total cost of sales"),
    _eur("gross_profit", 2024, "14492.0", "Gross profit"),
    _eur("research_and_development", 2024, "4303.7", "R&D costs"),
    _eur("operating_income", 2024, "9022.6", "Income from operations"),
    _eur("pretax_income", 2024, "9042.4", "Income before income taxes"),
    _eur("net_income", 2024, "7571.6", "Net income"),
    # 2024 balance sheet
    _eur("total_assets", 2024, "48589.6", "Total assets"),
    _eur("current_assets", 2024, "30737.4", "Total current assets"),
    _eur("cash_and_equivalents", 2024, "12735.9", "Cash and cash equivalents"),
    _eur(
        "cash_and_short_term_investments",
        2024,
        "12741.3",
        "Cash and cash equivalents + short-term investments",
        critical=False,
    ),
    _eur("accounts_receivable", 2024, "4477.5", "Accounts receivable, net"),
    _eur("inventory", 2024, "10891.5", "Inventories, net"),
    _eur("ppe_net", 2024, "6846.8", "Property, plant and equipment, net"),
    _eur("goodwill", 2024, "4588.6", "Goodwill"),
    _eur("total_liabilities", 2024, "30112.8", "Total liabilities"),
    _eur("current_liabilities", 2024, "20051.4", "Total current liabilities"),
    _eur("accounts_payable", 2024, "3500.4", "Accounts payable"),
    _eur(
        "short_term_debt",
        2024,
        "1010.3",
        "Short-term borrowings and current portion of long-term debt",
        critical=False,
    ),
    _eur("long_term_debt", 2024, "3677.3", "Long-term debt"),
    _eur("shareholders_equity", 2024, "18476.8", "Total shareholders' equity"),
    # 2024 cash flow
    _eur("operating_cash_flow", 2024, "11166.2", "Net cash provided by operating activities"),
    _eur("capital_expenditures", 2024, "2067.2", "Purchases of property, plant and equipment"),
    _eur("depreciation_amortization", 2024, "918.6", "Depreciation and amortization"),
    _eur("dividends_paid", 2024, "2452.9", "Dividend paid", critical=False),
)
