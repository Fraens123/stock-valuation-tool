from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook

from stock_valuation.data.providers.asml_primary import (
    parse_primary_source_facts,
    scan_financial_statement_workbook,
)


def _workbook_bytes() -> bytes:
    workbook = Workbook()
    balance = workbook.active
    balance.title = "Balance Sheets"
    balance.append([None, "2024", "2025"])
    balance.append(["Cash and cash equivalents", 12735.9, 12916.0])
    balance.append(["Short-term investments", 5.4, 405.9])
    balance.append(["Accounts receivable, net", 4477.5, 3023.0])
    balance.append(["Inventories, net", 10891.5, 11429.3])
    balance.append(["Property, plant and equipment, net", 6846.8, 7893.8])
    balance.append(
        ["Short-term borrowings and current portion of long-term debt", 1010.3, 1681.9]
    )

    cash_flow = workbook.create_sheet("Cash Flow")
    cash_flow.append([None, "2023", "2024", "2025"])
    cash_flow.append(["Net cash provided by operating activities", 5443.4, 11166.2, 12658.5])
    cash_flow.append(["Purchase of property, plant and equipment", -2155.6, -2067.2, -1573.6])
    cash_flow.append(["Purchase of intangible assets", -40.6, -15.9, -57.6])
    cash_flow.append(["Dividend paid", -2348.3, -2452.9, -2550.3])

    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def test_scanner_finds_official_financial_statement_rows() -> None:
    matches = scan_financial_statement_workbook(_workbook_bytes())
    targets = {row["target"] for row in matches}

    assert "accounts_receivable" in targets
    assert "inventory" in targets
    assert "ppe_net" in targets
    assert "operating_cash_flow" in targets
    assert "capital_expenditures" in targets


def test_scanner_preserves_coordinates_and_header_context() -> None:
    matches = scan_financial_statement_workbook(_workbook_bytes())
    receivable = next(row for row in matches if row["target"] == "accounts_receivable")

    assert receivable["sheet"] == "Balance Sheets"
    assert receivable["row"] == 4
    assert "A4=Accounts receivable, net" in receivable["row_values"]


def test_primary_parser_imports_only_2024_2025_and_normalizes_units_and_outflows() -> None:
    facts = parse_primary_source_facts(_workbook_bytes())
    by_key = {(fact.metric, fact.period_end.year): fact for fact in facts}

    assert set(year for _, year in by_key) == {2024, 2025}
    assert by_key[("accounts_receivable", 2025)].value == Decimal("3023000000.0")
    assert by_key[("operating_cash_flow", 2024)].value == Decimal("11166200000.0")
    assert by_key[("capital_expenditures", 2025)].value == Decimal("1573600000.0")
    assert by_key[("capital_expenditures", 2025)].provider_value == Decimal("-1573.6")
    assert by_key[("dividends_paid", 2024)].value == Decimal("2452900000.0")
    assert all(fact.provider == "asml_primary" for fact in facts)


def test_primary_parser_keeps_balance_and_cashflow_rows_separate() -> None:
    facts = parse_primary_source_facts(_workbook_bytes())
    by_metric = {}
    for fact in facts:
        by_metric.setdefault(fact.metric, set()).add(fact.statement)

    assert by_metric["accounts_receivable"] == {"balance_sheet"}
    assert by_metric["inventory"] == {"balance_sheet"}
    assert by_metric["operating_cash_flow"] == {"cash_flow"}
    assert by_metric["intangible_purchases"] == {"cash_flow"}
