from datetime import date

from stock_valuation.analyses.estimate_service import (
    annual_estimates,
    estimate_period_type,
    infer_fiscal_year_end_month_day,
    relevant_estimates,
)
from stock_valuation.database.models import EstimateSnapshot, FinancialFactSnapshot


def test_relevant_estimates_hide_stale_dates_but_keep_unknown_period_labels() -> None:
    rows = [
        EstimateSnapshot(analysis_id=1, metric="eps", period="2017-12-31"),
        EstimateSnapshot(analysis_id=1, metric="eps", period="2026-09-30"),
        EstimateSnapshot(analysis_id=1, metric="revenue", period="2027-12-31"),
        EstimateSnapshot(analysis_id=1, metric="eps", period="next fiscal year"),
    ]

    filtered = relevant_estimates(rows, as_of_date=date(2026, 8, 22))

    assert [row.period for row in filtered] == [
        "2026-09-30",
        "2027-12-31",
        "next fiscal year",
    ]


def test_microsoft_estimates_are_split_into_quarters_and_fiscal_years() -> None:
    annual_facts = [
        FinancialFactSnapshot(
            analysis_id=1,
            statement="income_statement",
            metric="revenue",
            period_end=date(year, 6, 30),
            period_type="FY",
            value=1,
        )
        for year in range(2022, 2027)
    ]
    fiscal_year_end = infer_fiscal_year_end_month_day(annual_facts)
    assert fiscal_year_end == (6, 30)

    estimates = [
        EstimateSnapshot(analysis_id=1, metric="eps", period="2026-09-30"),
        EstimateSnapshot(analysis_id=1, metric="eps", period="2026-12-31"),
        EstimateSnapshot(analysis_id=1, metric="eps", period="2027-06-30"),
        EstimateSnapshot(analysis_id=1, metric="revenue", period="2028-06-30"),
    ]

    assert estimate_period_type("2026-09-30", fiscal_year_end=fiscal_year_end) == "Quartal"
    assert estimate_period_type("2027-06-30", fiscal_year_end=fiscal_year_end) == "Jahr"
    assert [row.period for row in annual_estimates(estimates, fiscal_year_end=fiscal_year_end)] == [
        "2027-06-30",
        "2028-06-30",
    ]


def test_calendar_year_company_uses_december_31_as_annual_estimate() -> None:
    assert estimate_period_type("2026-12-31", fiscal_year_end=(12, 31)) == "Jahr"
    assert estimate_period_type("2026-09-30", fiscal_year_end=(12, 31)) == "Quartal"
