from stock_valuation.companies.discovery import discover_companies
from stock_valuation.data.providers.gleif import LEICandidate
from stock_valuation.data.providers.sec import SECCompanyCandidate


class FakeSEC:
    def search_companies(self, query: str, *, limit: int = 10):
        assert query == "Example"
        return [SECCompanyCandidate(cik="0000123456", ticker="EXM", name="Example N.V.")]


class FakeGLEIF:
    def search_by_name(self, name: str, *, limit: int = 10):
        assert name == "Example"
        return [
            LEICandidate(
                lei="52990000000000000000",
                legal_name="Example NV",
                country="NL",
                registration_status="ISSUED",
            )
        ]


def test_discovery_merges_sec_cik_and_gleif_lei_for_same_issuer() -> None:
    candidates, notes = discover_companies(
        "Example",
        sec_provider=FakeSEC(),
        gleif_provider=FakeGLEIF(),
    )

    assert notes == []
    assert len(candidates) == 1
    row = candidates[0]
    assert row.ticker == "EXM"
    assert row.sec_cik == "0000123456"
    assert row.lei == "52990000000000000000"
    assert row.country == "NL"
    assert row.currency == "EUR"
    assert row.sources == ("GLEIF", "SEC")
