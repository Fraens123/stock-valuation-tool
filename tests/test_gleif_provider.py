from stock_valuation.data.providers.gleif import GLEIFProvider, LEICandidate


class FakeGLEIF(GLEIFProvider):
    def __init__(self, candidates):
        self._candidates = candidates

    def search_by_name(self, name: str, *, limit: int = 10):
        return list(self._candidates)


def test_gleif_resolver_accepts_exact_normalized_legal_name() -> None:
    provider = FakeGLEIF(
        [
            LEICandidate(
                lei="52990000000000000000",
                legal_name="Example N.V.",
                country="NL",
                registration_status="ISSUED",
            )
        ]
    )

    result = provider.resolve_lei("Example NV", country="NL")

    assert result is not None
    assert result.lei == "52990000000000000000"


def test_gleif_resolver_does_not_guess_between_multiple_exact_entities() -> None:
    provider = FakeGLEIF(
        [
            LEICandidate("52990000000000000000", "Example NV", "NL", "ISSUED"),
            LEICandidate("52990000000000000001", "Example N.V.", "BE", "ISSUED"),
        ]
    )

    assert provider.resolve_lei("Example NV") is None
    assert provider.resolve_lei("Example NV", country="NL").lei == "52990000000000000000"
