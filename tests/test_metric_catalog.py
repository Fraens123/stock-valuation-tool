from stock_valuation.knowledge.catalog import get_metric_info, load_metric_catalog


REQUIRED_FIELDS = {
    "group",
    "title_de",
    "chapter",
    "kindle_page",
    "status",
    "excel_location",
    "excel_formula",
    "target_formula",
    "raw_data",
    "definition",
    "meaning",
    "interpretation",
    "pitfalls",
    "related",
}


def test_roe_uses_verified_kindle_page() -> None:
    info = get_metric_info("roe")
    assert info is not None
    assert info["kindle_page"] == 94


def test_pe_uses_verified_kindle_page() -> None:
    info = get_metric_info("pe")
    assert info is not None
    assert info["kindle_page"] == 226


def test_dcf_and_fair_pe_use_user_kindle_pages() -> None:
    assert get_metric_info("owner_earnings")["kindle_page"] == 295
    assert get_metric_info("fair_pe")["kindle_page"] == 351
    assert get_metric_info("margin_of_safety")["kindle_page"] == 438


def test_catalog_contains_book_and_excel_extension_metrics() -> None:
    catalog = load_metric_catalog()
    assert len(catalog) >= 40
    assert "capital_turnover" in catalog
    assert "cash_conversion_cycle" in catalog
    assert "interest_coverage" in catalog
    assert "ev_fcf" in catalog


def test_every_metric_has_complete_info_schema() -> None:
    catalog = load_metric_catalog()
    for metric_id, info in catalog.items():
        missing = REQUIRED_FIELDS - set(info)
        assert not missing, f"{metric_id} missing fields: {sorted(missing)}"
        assert info["definition"].strip()
        assert info["meaning"].strip()
        assert info["interpretation"].strip()
        assert isinstance(info["raw_data"], list)
        assert isinstance(info["pitfalls"], list)
        assert isinstance(info["related"], list)


def test_unverified_excel_extensions_do_not_invent_book_pages() -> None:
    catalog = load_metric_catalog()
    for info in catalog.values():
        if info["group"] == "excel_extension":
            assert info["kindle_page"] is None or info["chapter"] is not None
