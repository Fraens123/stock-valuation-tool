from __future__ import annotations

import pytest

from stock_valuation.data.providers.alphavantage import AlphaVantageProvider
from stock_valuation.data.providers.base import ProviderRateLimitError


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_second_identical_request_is_served_from_disk_cache(monkeypatch, tmp_path) -> None:
    calls: list[dict] = []

    def fake_get(url, *, params, timeout):
        calls.append(params)
        return FakeResponse(
            {
                "symbol": "MSFT",
                "annualReports": [
                    {
                        "fiscalDateEnding": "2025-06-30",
                        "reportedCurrency": "USD",
                        "totalRevenue": "100",
                    }
                ],
                "quarterlyReports": [],
            }
        )

    monkeypatch.setattr("stock_valuation.data.providers.alphavantage.requests.get", fake_get)
    first = AlphaVantageProvider(
        api_key="SECRET",
        min_request_interval_seconds=0,
        cache_root=tmp_path,
    )
    assert first.probe_income_statement("MSFT")["annual_report_count"] == 1
    assert first.network_requests == 1
    assert first.cache_hits == 0
    assert len(calls) == 1

    def must_not_call_network(*args, **kwargs):
        raise AssertionError("network should not be called for cached request")

    monkeypatch.setattr(
        "stock_valuation.data.providers.alphavantage.requests.get",
        must_not_call_network,
    )
    second = AlphaVantageProvider(
        api_key="SECRET",
        min_request_interval_seconds=0,
        cache_root=tmp_path,
    )
    probe = second.probe_income_statement("MSFT")
    assert probe["latest_revenue"] == "100"
    assert second.cache_hits == 1
    assert second.network_requests == 0


def test_rate_limit_error_never_echoes_api_key(monkeypatch, tmp_path) -> None:
    def fake_get(url, *, params, timeout):
        return FakeResponse(
            {
                "Information": (
                    "We have detected your API key as SECRET and our standard API rate limit "
                    "is 25 requests per day."
                )
            }
        )

    monkeypatch.setattr("stock_valuation.data.providers.alphavantage.requests.get", fake_get)
    provider = AlphaVantageProvider(
        api_key="SECRET",
        min_request_interval_seconds=0,
        cache_root=tmp_path,
    )

    with pytest.raises(ProviderRateLimitError) as exc_info:
        provider.get_income_statement("MSFT")

    assert "SECRET" not in str(exc_info.value)
    assert "***" in str(exc_info.value)
