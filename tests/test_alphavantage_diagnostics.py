from stock_valuation.data.providers.alphavantage import extract_candidate_annual_fields


def test_extract_candidate_annual_fields_labels_possible_targets_without_mapping() -> None:
    payload = {
        "annualReports": [
            {
                "fiscalDateEnding": "2025-12-31",
                "reportedCurrency": "EUR",
                "currentNetReceivables": "4164200000",
                "inventory": "11429300000",
                "propertyPlantEquipment": "None",
                "shortTermDebt": "None",
            },
            {
                "fiscalDateEnding": "2024-12-31",
                "reportedCurrency": "EUR",
                "currentNetReceivables": "5443300000",
                "inventory": "11707100000",
                "propertyPlantEquipment": "None",
                "shortTermDebt": "1078900000",
            },
        ]
    }
    candidates = {
        "accounts_receivable": ("receiv",),
        "inventory": ("invent",),
        "ppe_net": ("property", "plant", "equipment"),
        "short_term_debt": ("shorttermdebt", "currentdebt", "borrow"),
    }

    rows = extract_candidate_annual_fields(
        payload,
        statement="balance_sheet",
        candidates=candidates,
        max_reports=2,
    )

    assert any(
        row["candidate_for"] == "accounts_receivable"
        and row["field"] == "currentNetReceivables"
        and row["fiscal_date"] == "2025-12-31"
        for row in rows
    )
    assert any(
        row["candidate_for"] == "inventory"
        and row["field"] == "inventory"
        and row["fiscal_date"] == "2024-12-31"
        for row in rows
    )
    assert any(
        row["candidate_for"] == "ppe_net"
        and row["field"] == "propertyPlantEquipment"
        for row in rows
    )
    assert any(
        row["candidate_for"] == "short_term_debt"
        and row["field"] == "shortTermDebt"
        for row in rows
    )


def test_extract_candidate_annual_fields_limits_history() -> None:
    payload = {
        "annualReports": [
            {"fiscalDateEnding": "2025-12-31", "reportedCurrency": "EUR", "inventory": "1"},
            {"fiscalDateEnding": "2024-12-31", "reportedCurrency": "EUR", "inventory": "2"},
            {"fiscalDateEnding": "2023-12-31", "reportedCurrency": "EUR", "inventory": "3"},
        ]
    }

    rows = extract_candidate_annual_fields(
        payload,
        statement="balance_sheet",
        candidates={"inventory": ("invent",)},
        max_reports=2,
    )

    assert {row["fiscal_date"] for row in rows} == {"2025-12-31", "2024-12-31"}
