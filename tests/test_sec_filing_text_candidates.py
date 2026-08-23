from decimal import Decimal

from stock_valuation.data.providers.sec_text import parse_filing_table_candidates


HTML = """
<table>
<tr><td>EUR in millions</td><td></td><td></td></tr>
<tr><th></th><th>2025</th><th>2024</th></tr>
<tr><td>Net cash provided by operating activities</td><td>12,658.5</td><td>11,166.2</td></tr>
<tr><td>Dividends paid</td><td>(2,500.5)</td><td>(2,200.0)</td></tr>
<tr><td>Current portion of long-term debt</td><td>990.2</td><td>1,010.3</td></tr>
<tr><td>Proposed dividend</td><td>3,000.0</td><td>2,500.0</td></tr>
</table>
"""


def test_table_candidates_use_year_column_and_million_scale() -> None:
    result = parse_filing_table_candidates(
        HTML,
        metrics={"operating_cash_flow", "dividends_paid", "short_term_debt"},
        year=2025,
    )

    assert result["operating_cash_flow"].value == Decimal("12658500000.0")
    assert result["dividends_paid"].value == Decimal("-2500500000.0")
    assert result["short_term_debt"].value == Decimal("990200000.0")


def test_proposed_dividend_is_not_used_for_dividends_paid() -> None:
    result = parse_filing_table_candidates(HTML, metrics={"dividends_paid"}, year=2025)

    assert result["dividends_paid"].label == "Dividends paid"
