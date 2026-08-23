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


def test_sec_normalizer_uses_lower_priority_standard_tag_for_uncovered_years() -> None:
    payload = {
        "facts": {
            "us-gaap": {
                "PaymentsOfDividends": {
                    "units": {
                        "EUR": [
                            _entry(-100, "2017-12-31", "2018-02-01", form="20-F"),
                            _entry(-110, "2018-12-31", "2019-02-01", form="20-F"),
                        ]
                    }
                },
                "PaymentsOfDividendsCommonStock": {
                    "units": {
                        "EUR": [
                            _entry(-120, "2019-12-31", "2020-02-01", form="20-F"),
                            _entry(-130, "2020-12-31", "2021-02-01", form="20-F"),
                        ]
                    }
                },
            }
        }
    }

    facts = [fact for fact in normalize_sec_companyfacts(payload) if fact.metric == "dividends_paid"]
    by_year = {fact.period_end.year: fact for fact in facts}

    assert set(by_year) == {2017, 2018, 2019, 2020}
    assert by_year[2018].provider_field == "us-gaap:PaymentsOfDividends"
    assert by_year[2019].provider_field == "us-gaap:PaymentsOfDividendsCommonStock"
    assert by_year[2020].value == Decimal("130")


def test_sec_normalizer_keeps_higher_priority_tag_when_same_period_has_multiple_candidates() -> None:
    payload = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {"USD": [_entry(1000, "2025-12-31", "2026-02-01")]}
                },
                "SalesRevenueNet": {
                    "units": {"USD": [_entry(999, "2025-12-31", "2026-02-02")]}
                },
            }
        }
    }

    facts = [fact for fact in normalize_sec_companyfacts(payload) if fact.metric == "revenue"]
    assert len(facts) == 1
    assert facts[0].value == Decimal("1000")
    assert facts[0].provider_field == "us-gaap:Revenues"


def test_sec_normalizer_uses_complete_d_and_a_total_concept() -> None:
    payload = {
        "facts": {
            "us-gaap": {
                "DepreciationAndAmortization": {
                    "units": {"USD": [_entry(100, "2025-12-31", "2026-02-01")]}
                }
            }
        }
    }

    facts = [fact for fact in normalize_sec_companyfacts(payload) if fact.metric == "depreciation_amortization"]

    assert len(facts) == 1
    assert facts[0].value == Decimal("100")
    assert facts[0].provider_field == "us-gaap:DepreciationAndAmortization"


def test_sec_normalizer_aggregates_complete_d_and_a_components() -> None:
    payload = {
        "facts": {
            "us-gaap": {
                "Depreciation": {
                    "units": {"USD": [_entry(70, "2025-12-31", "2026-02-01")]}
                },
                "AmortizationOfIntangibleAssets": {
                    "units": {"USD": [_entry(30, "2025-12-31", "2026-02-01")]}
                },
            }
        }
    }

    facts = [fact for fact in normalize_sec_companyfacts(payload) if fact.metric == "depreciation_amortization"]

    assert len(facts) == 1
    assert facts[0].value == Decimal("100")
    assert facts[0].provider_field == "aggregation:us-gaap:Depreciation+us-gaap:AmortizationOfIntangibleAssets"


def test_sec_normalizer_does_not_create_d_and_a_from_depreciation_only() -> None:
    payload = {
        "facts": {
            "us-gaap": {
                "Depreciation": {
                    "units": {"USD": [_entry(70, "2025-12-31", "2026-02-01")]}
                }
            }
        }
    }

    facts = [fact for fact in normalize_sec_companyfacts(payload) if fact.metric == "depreciation_amortization"]

    assert facts == []


def test_sec_normalizer_does_not_create_d_and_a_from_amortization_only() -> None:
    payload = {
        "facts": {
            "us-gaap": {
                "AmortizationOfIntangibleAssets": {
                    "units": {"USD": [_entry(30, "2025-12-31", "2026-02-01")]}
                }
            }
        }
    }

    facts = [fact for fact in normalize_sec_companyfacts(payload) if fact.metric == "depreciation_amortization"]

    assert facts == []
