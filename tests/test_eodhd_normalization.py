from decimal import Decimal

from stock_valuation.data.normalization import (
    normalize_eodhd_company,
    normalize_eodhd_estimates,
    normalize_eodhd_financials,
)


SAMPLE = {
    "General": {
        "Code": "ASML",
        "Name": "ASML Holding N.V.",
        "Exchange": "AS",
        "CurrencyCode": "EUR",
        "CountryName": "Netherlands",
        "ISIN": "NL0010273215",
        "Sector": "Technology",
        "Industry": "Semiconductor Equipment",
    },
    "Financials": {
        "Income_Statement": {
            "currency_symbol": "EUR",
            "yearly": {
                "2025-12-31": {
                    "date": "2025-12-31",
                    "filing_date": "2026-02-11",
                    "totalRevenue": "32700",
                    "costOfRevenue": "15434",
                    "grossProfit": "17266",
                    "ebit": "10500",
                    "netIncome": "9600",
                    "interestExpense": "100",
                    "researchDevelopment": "4700",
                }
            },
        },
        "Balance_Sheet": {
            "currency_symbol": "EUR",
            "yearly": {
                "2025-12-31": {
                    "date": "2025-12-31",
                    "totalAssets": "50000",
                    "totalLiab": "30000",
                    "totalStockholderEquity": "20000",
                    "cashAndShortTermInvestments": "8000",
                    "netReceivables": "7000",
                    "inventory": "9000",
                    "accountsPayable": "5000",
                    "shortTermDebt": "1000",
                    "longTermDebtTotal": "3000",
                }
            },
        },
        "Cash_Flow": {
            "currency_symbol": "EUR",
            "yearly": {
                "2025-12-31": {
                    "date": "2025-12-31",
                    "totalCashFromOperatingActivities": "12000",
                    "capitalExpenditures": "-2500",
                    "depreciation": "1500",
                    "dividendsPaid": "-2600",
                    "freeCashFlow": "9500",
                }
            },
        },
    },
    "Earnings": {
        "Trend": {
            "Annual": {
                "2026-12-31": {
                    "date": "2026-12-31",
                    "earningsEstimateAvg": "26.5",
                    "earningsEstimateLow": "24.0",
                    "earningsEstimateHigh": "29.0",
                    "earningsEstimateNumberOfAnalysts": 31,
                    "revenueEstimateAvg": "36500",
                    "revenueEstimateLow": "34000",
                    "revenueEstimateHigh": "39000",
                    "revenueEstimateNumberOfAnalysts": 28,
                }
            }
        }
    },
}


def test_company_normalization() -> None:
    company = normalize_eodhd_company(SAMPLE)
    assert company.name == "ASML Holding N.V."
    assert company.ticker == "ASML"
    assert company.provider_symbol == "ASML.AS"
    assert company.currency == "EUR"
    assert company.isin == "NL0010273215"


def test_financial_mapping_uses_stable_internal_keys() -> None:
    facts = normalize_eodhd_financials(SAMPLE)
    by_metric = {fact.metric: fact for fact in facts}

    assert by_metric["revenue"].value == Decimal("32700")
    assert by_metric["total_equity"].value == Decimal("20000")
    assert by_metric["accounts_payable"].value == Decimal("5000")
    assert by_metric["operating_cash_flow"].value == Decimal("12000")
    assert by_metric["revenue"].provider_field == "totalRevenue"


def test_cash_outflows_are_normalized_to_positive_magnitude_but_raw_value_is_preserved() -> None:
    facts = normalize_eodhd_financials(SAMPLE)
    by_metric = {fact.metric: fact for fact in facts}

    capex = by_metric["capex_ppe"]
    assert capex.provider_value == Decimal("-2500")
    assert capex.value == Decimal("2500")

    dividends = by_metric["dividends_paid"]
    assert dividends.provider_value == Decimal("-2600")
    assert dividends.value == Decimal("2600")


def test_missing_provider_fields_remain_missing() -> None:
    facts = normalize_eodhd_financials(SAMPLE)
    by_metric = {fact.metric: fact for fact in facts}
    assert by_metric["goodwill"].value is None
    assert by_metric["goodwill"].note == "optional provider field"


def test_annual_estimates_keep_low_average_high_and_analyst_count() -> None:
    estimates = normalize_eodhd_estimates(SAMPLE)
    by_metric = {estimate.metric: estimate for estimate in estimates}

    eps = by_metric["eps"]
    assert eps.low == Decimal("24.0")
    assert eps.average == Decimal("26.5")
    assert eps.high == Decimal("29.0")
    assert eps.analyst_count == 31

    revenue = by_metric["revenue"]
    assert revenue.low == Decimal("34000")
    assert revenue.average == Decimal("36500")
    assert revenue.high == Decimal("39000")
    assert revenue.analyst_count == 28
