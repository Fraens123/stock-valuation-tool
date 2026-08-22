from datetime import date

from stock_valuation.analyses.estimate_service import relevant_estimates
from stock_valuation.database.models import EstimateSnapshot


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
