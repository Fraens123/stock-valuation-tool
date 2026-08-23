from decimal import Decimal

from stock_valuation.data.providers.esef_registry import normalize_esef_xbrl_json


def _fact(concept: str, value: str, period: str, unit: str = "iso4217:EUR", **dimensions):
    return {
        "value": value,
        "dimensions": {
            "concept": concept,
            "entity": "scheme:ENTITY",
            "period": period,
            "unit": unit,
            **dimensions,
        },
    }


def test_esef_xbrl_json_normalizes_standard_ifrs_group_facts() -> None:
    payload = {
        "facts": {
            "f1": _fact("ifrs-full:Revenue", "1000", "2024-01-01T00:00:00/2025-01-01T00:00:00"),
            "f2": _fact("ifrs-full:Assets", "5000", "2024-12-31T00:00:00"),
            "f3": _fact(
                "ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
                "-300",
                "2024-01-01T00:00:00/2025-01-01T00:00:00",
            ),
        }
    }

    facts = normalize_esef_xbrl_json(payload, source_note="test filing")
    by_metric = {fact.metric: fact for fact in facts}

    assert by_metric["revenue"].value == Decimal("1000")
    assert str(by_metric["revenue"].period_end) == "2024-12-31"
    assert by_metric["total_assets"].value == Decimal("5000")
    assert by_metric["capital_expenditures"].provider_value == Decimal("-300")
    assert by_metric["capital_expenditures"].value == Decimal("300")
    assert by_metric["revenue"].provider == "esef_xbrl_json"
    assert by_metric["revenue"].currency == "EUR"


def test_esef_xbrl_json_ignores_segment_and_quarter_duration_facts() -> None:
    payload = {
        "facts": {
            "segment": _fact(
                "ifrs-full:Revenue",
                "400",
                "2024-01-01T00:00:00/2025-01-01T00:00:00",
                **{"axis:Segment": "member:Cloud"},
            ),
            "quarter": _fact(
                "ifrs-full:Revenue",
                "250",
                "2024-10-01T00:00:00/2025-01-01T00:00:00",
            ),
            "annual": _fact(
                "ifrs-full:Revenue",
                "1000",
                "2024-01-01T00:00:00/2025-01-01T00:00:00",
            ),
        }
    }

    facts = normalize_esef_xbrl_json(payload)

    assert len(facts) == 1
    assert facts[0].metric == "revenue"
    assert facts[0].value == Decimal("1000")
