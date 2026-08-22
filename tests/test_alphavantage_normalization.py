from stock_valuation.data.normalization_alphavantage import (
    normalize_alphavantage_estimates,
    normalize_alphavantage_financials,
)
from stock_valuation.data.providers.alphavantage import extract_matching_annual_fields


def test_alphavantage_financials_map_and_normalize_outflows() -> None:
    payloads = {
        "income_statement": {
            "annualReports": [
                {
                    "fiscalDateEnding": "2025-12-31",
                    "reportedCurrency": "EUR",
                    "totalRevenue": "1000",
                    "operatingIncome": "300",
                    "netIncome": "200",
                }
            ]
        },
        "balance_sheet": {
            "annualReports": [
                {
                    "fiscalDateEnding": "2025-12-31",
                    "reportedCurrency": "EUR",
                    "totalAssets": "5000",
                    "totalShareholderEquity": "3000",
                }
            ]
        },
        "cash_flow": {
            "annualReports": [
                {
                    "fiscalDateEnding": "2025-12-31",
                    "reportedCurrency": "EUR",
                    "operatingCashflow": "400",
                    "capitalExpenditures": "-150",
                    "dividendPayout": "-80",
                }
            ]
        },
    }

    facts = normalize_alphavantage_financials(payloads)
    by_metric = {fact.metric: fact for fact in facts}

    assert by_metric["revenue"].value == 1000
    assert by_metric["operating_income"].value == 300
    assert by_metric["shareholders_equity"].value == 3000
    assert by_metric["capital_expenditures"].provider_value == -150
    assert by_metric["capital_expenditures"].value == 150
    assert by_metric["dividends_paid"].value == 80


def test_alphavantage_estimates_map_low_average_high() -> None:
    payload = {
        "estimates": [
            {
                "date": "2027-12-31",
                "horizon": "next fiscal year",
                "eps_estimate_low": "30.0",
                "eps_estimate_average": "32.0",
                "eps_estimate_high": "35.0",
                "eps_estimate_analyst_count": "20",
                "revenue_estimate_low": "40000000000",
                "revenue_estimate_average": "42000000000",
                "revenue_estimate_high": "45000000000",
                "revenue_estimate_analyst_count": "18",
            }
        ]
    }

    estimates = normalize_alphavantage_estimates(payload)
    by_metric = {item.metric: item for item in estimates}

    assert by_metric["eps"].average == 32
    assert by_metric["eps"].analyst_count == 20
    assert by_metric["revenue"].low == 40000000000
    assert by_metric["revenue"].analyst_count == 18


def test_extract_matching_annual_fields_keeps_raw_values_and_latest_two_years() -> None:
    payload = {
        "annualReports": [
            {
                "fiscalDateEnding": "2025-12-31",
                "reportedCurrency": "EUR",
                "depreciationAndAmortization": "1025900000",
                "otherField": "1",
            },
            {
                "fiscalDateEnding": "2024-12-31",
                "reportedCurrency": "EUR",
                "depreciationDepletionAndAmortization": "918600000",
            },
            {
                "fiscalDateEnding": "2023-12-31",
                "reportedCurrency": "EUR",
                "depreciation": "700000000",
            },
        ]
    }

    rows = extract_matching_annual_fields(
        payload,
        statement="cash_flow",
        keywords=("depreci", "amorti", "depletion"),
        max_reports=2,
    )

    assert len(rows) == 2
    assert rows[0]["fiscal_date"] == "2025-12-31"
    assert rows[0]["field"] == "depreciationAndAmortization"
    assert rows[0]["value"] == "1025900000"
    assert rows[1]["fiscal_date"] == "2024-12-31"
    assert rows[1]["field"] == "depreciationDepletionAndAmortization"
