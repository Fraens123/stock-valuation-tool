from decimal import Decimal

from stock_valuation.data.providers.ecb import FULL_SERIES_KEY, parse_ecb_latest_csv


def test_parse_ecb_latest_aaa_10y_csv() -> None:
    csv_text = (
        "KEY,TIME_PERIOD,OBS_VALUE\n"
        f"{FULL_SERIES_KEY},2026-08-20,3.125000\n"
    )
    obs = parse_ecb_latest_csv(csv_text)
    assert obs.series_key == FULL_SERIES_KEY
    assert obs.observation_date.isoformat() == "2026-08-20"
    assert obs.percent_per_annum == Decimal("3.125000")
    assert obs.rate_decimal == Decimal("0.031250")
