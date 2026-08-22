from io import BytesIO

from openpyxl import Workbook

from stock_valuation.data.providers.asml_primary import scan_financial_statement_workbook


def _workbook_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Consolidated statements"
    sheet.append([None, "2025", "2024"])
    sheet.append(["Accounts receivable, net", 3023.0, 4477.5])
    sheet.append(["Inventories, net", 11429.3, 10891.5])
    sheet.append(["Property, plant and equipment, net", 7893.8, 6846.8])
    sheet.append(["Net cash provided by operating activities", 12658.5, 11166.2])
    sheet.append(["Purchases of property, plant and equipment", 1573.6, 2067.2])

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

    assert receivable["sheet"] == "Consolidated statements"
    assert receivable["row"] == 2
    assert "A2=Accounts receivable, net" in receivable["row_values"]
    assert "B2=3023" in receivable["row_values"]
    assert "B1=2025" in receivable["header_minus_1"]
