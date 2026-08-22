from __future__ import annotations

from io import BytesIO
from typing import Any

import requests
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter


ASML_2025_US_GAAP_XLSX = (
    "https://ourbrand.asml.com/m/6cd86f972a9dfd24/original/"
    "2025-US-GAAP-Financial-Statements.xlsx"
)


class ASMLPrimarySourceError(RuntimeError):
    """Raised when an official ASML primary-source workbook cannot be loaded or inspected."""


TARGET_PATTERNS: dict[str, tuple[str, ...]] = {
    "cash_and_equivalents": ("cash and cash equivalents",),
    "short_term_investments": ("short-term investments", "short term investments"),
    "accounts_receivable": ("accounts receivable, net", "accounts receivable"),
    "inventory": ("inventories, net", "inventories"),
    "ppe_net": (
        "property, plant and equipment, net",
        "property plant and equipment, net",
    ),
    "short_term_debt": (
        "short-term borrowings",
        "short term borrowings",
        "current portion of long-term debt",
        "current portion of long term debt",
    ),
    "operating_cash_flow": (
        "net cash provided by operating activities",
        "net cash from operating activities",
    ),
    "capital_expenditures": (
        "purchases of property, plant and equipment",
        "purchase of property, plant and equipment",
        "purchases of property plant and equipment",
    ),
    "intangible_purchases": (
        "purchases of intangible assets",
        "purchase of intangible assets",
    ),
    "dividends_paid": ("dividend paid", "dividends paid"),
}


def download_2025_us_gaap_workbook(*, timeout: int = 30) -> bytes:
    """Download ASML's official 2025 US-GAAP financial-statements workbook.

    This request goes directly to ASML and does not use an Alpha Vantage API quota.
    """
    try:
        response = requests.get(
            ASML_2025_US_GAAP_XLSX,
            timeout=timeout,
            headers={"User-Agent": "stock-valuation-tool/0.1"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ASMLPrimarySourceError(
            "Die offizielle ASML-US-GAAP-Excel-Datei konnte nicht geladen werden."
        ) from exc

    content = response.content
    if not content.startswith(b"PK"):
        raise ASMLPrimarySourceError(
            "ASML lieferte keine erkennbare XLSX-Datei zurück."
        )
    return content


def _row_text(values: tuple[Any, ...]) -> str:
    return " | ".join(str(value).strip() for value in values if value not in (None, ""))


def _row_cells(values: tuple[Any, ...], row_number: int) -> str:
    parts: list[str] = []
    for index, value in enumerate(values, start=1):
        if value in (None, ""):
            continue
        coordinate = f"{get_column_letter(index)}{row_number}"
        parts.append(f"{coordinate}={value}")
    return " | ".join(parts)


def scan_financial_statement_workbook(content: bytes) -> list[dict[str, Any]]:
    """Find relevant official ASML rows without assuming a fixed workbook layout.

    The first iteration is deliberately diagnostic: it returns matched labels plus the
    complete matching row and nearby header rows. No financial fact is persisted yet.
    Once the live workbook layout is confirmed, a deterministic importer can be added.
    """
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises several format-specific exceptions
        raise ASMLPrimarySourceError("Die ASML-XLSX-Datei konnte nicht gelesen werden.") from exc

    matches: list[dict[str, Any]] = []
    for sheet in workbook.worksheets:
        rows = [tuple(row) for row in sheet.iter_rows(values_only=True)]
        for index, values in enumerate(rows):
            joined = _row_text(values).lower()
            if not joined:
                continue
            for target, patterns in TARGET_PATTERNS.items():
                matched_pattern = next((pattern for pattern in patterns if pattern in joined), None)
                if matched_pattern is None:
                    continue

                row_number = index + 1
                previous_1 = rows[index - 1] if index >= 1 else tuple()
                previous_2 = rows[index - 2] if index >= 2 else tuple()
                matches.append(
                    {
                        "target": target,
                        "sheet": sheet.title,
                        "row": row_number,
                        "matched_pattern": matched_pattern,
                        "row_values": _row_cells(values, row_number),
                        "header_minus_1": _row_cells(previous_1, row_number - 1),
                        "header_minus_2": _row_cells(previous_2, row_number - 2),
                    }
                )
                break

    workbook.close()
    return matches
