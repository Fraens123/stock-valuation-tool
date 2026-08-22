from stock_valuation.knowledge.catalog import get_metric_info


def test_roe_uses_verified_kindle_page() -> None:
    info = get_metric_info("roe")
    assert info is not None
    assert info["kindle_page"] == 94


def test_pe_uses_verified_kindle_page() -> None:
    info = get_metric_info("pe")
    assert info is not None
    assert info["kindle_page"] == 226
