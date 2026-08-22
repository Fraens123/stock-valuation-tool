from decimal import Decimal

from stock_valuation.data.providers.sec import normalize_sec_companyfacts


def _entry(value: int, end: str, filed: str, form: str = "10-K") -> dict:
    return {
        "val": value,
        "end": end,
        "filed": filed,
        "form": form,
        "fp": "FY",
        "accn": "0000000000-00-000001",
    }


def test_sec_normalizer_maps_standard_us_gaap_concepts() -> None:
    payload = {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            _entry(1000, "2024-12-31", "2025-02-01"),
                            _entry(1200, "2025-12-31", "2026-02-01"),
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {"USD": [_entry(200, "2025-12-31", "2026-02-01")]}
                },
                "Assets": {
                    "units": {"USD": [_entry(5000, "2025-12-31", "2026-02-01")]}
                },
                "PaymentsToAcquirePropertyPlantAndEquipment": {
                    "units": {"USD": [_entry(-300, "2025-12-31", "2026-02-01")]}
                },
            }
        }
    }

    facts = normalize_sec_companyfacts(payload)
    by_key = {(fact.metric, fact.period_end.year): fact for fact in facts}

    assert by_key[("revenue", 2025)].value == Decimal("1200")
    assert by_key[("net_income", 2025)].value == Decimal("200")
    assert by_key[("total_assets", 2025)].value == Decimal("5000")
    assert by_key[("capital_expenditures", 2025)].value == Decimal("300")
    assert by_key[("capital_expenditures", 2025)].provider_value == Decimal("-300")
    assert by_key[("revenue", 2025)].provider == "sec_companyfacts"


def test_sec_normalizer_uses_latest_filed_value_for_same_period() -> None:
    payload = {
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            _entry(100, "2025-12-31", "2026-01-20"),
                            _entry(110, "2025-12-31", "2026-03-01", form="10-K/A"),
                        ]
                    }
                }
            }
        }
    }

    facts = normalize_sec_companyfacts(payload)
    net_income = next(fact for fact in facts if fact.metric == "net_income")
    assert net_income.value == Decimal("110")
    assert str(net_income.filing_date) == "2026-03-01"
