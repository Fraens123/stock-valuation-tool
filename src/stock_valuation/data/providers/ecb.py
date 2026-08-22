from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from io import StringIO

import requests


ECB_DATA_API = "https://data-api.ecb.europa.eu/service/data"
FLOW = "YC"
SERIES_KEY = "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y"
FULL_SERIES_KEY = f"{FLOW}.{SERIES_KEY}"


@dataclass(frozen=True)
class RiskFreeRateObservation:
    series_key: str
    observation_date: date
    percent_per_annum: Decimal
    rate_decimal: Decimal
    provider: str = "ecb"
    retrieved_at: datetime | None = None


def parse_ecb_latest_csv(text: str, *, retrieved_at: datetime | None = None) -> RiskFreeRateObservation:
    rows = list(csv.DictReader(StringIO(text)))
    valid = [row for row in rows if row.get("TIME_PERIOD") and row.get("OBS_VALUE")]
    if not valid:
        raise ValueError("ECB-Antwort enthält keine verwertbare Beobachtung.")

    row = valid[-1]
    value = Decimal(str(row["OBS_VALUE"]))
    return RiskFreeRateObservation(
        series_key=row.get("KEY") or FULL_SERIES_KEY,
        observation_date=date.fromisoformat(row["TIME_PERIOD"]),
        percent_per_annum=value,
        rate_decimal=value / Decimal("100"),
        retrieved_at=retrieved_at or datetime.now(timezone.utc),
    )


class ECBRiskFreeRateProvider:
    """Fetch the latest Euro-area AAA 10-year spot yield from the ECB Data API."""

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def get_latest_eur_aaa_10y(self) -> RiskFreeRateObservation:
        response = requests.get(
            f"{ECB_DATA_API}/{FLOW}/{SERIES_KEY}",
            params={"format": "csvdata", "lastNObservations": 1},
            timeout=self.timeout,
            headers={"Accept": "text/csv"},
        )
        response.raise_for_status()
        return parse_ecb_latest_csv(response.text)
