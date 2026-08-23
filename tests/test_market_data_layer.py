from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from stock_valuation.market.engine import derive_market_metrics
from stock_valuation.market.listing_policy import choose_listing, listing_policy_status
from stock_valuation.market.models import (
    ADR_RATIO_REQUIRED,
    AVAILABLE,
    DATE_MISMATCH,
    FX_REQUIRED,
    FX_UNAVAILABLE,
    INVALID_SHARE_COUNT,
    LISTING_REVIEW_REQUIRED,
    LOOKAHEAD_BLOCKED,
    MISSING_PRICE,
    SHARE_BASIS_ADR_UNITS,
    SHARE_BASIS_ORDINARY,
    SHARE_COUNT_STALE,
    STALE,
    ListingData,
    MarketDataSnapshot,
    NetDebtInput,
    NormalizedMarketQuote,
    NormalizedShareData,
    FXRate,
)
from stock_valuation.market.providers import (
    AlphaVantageQuoteProvider,
    FrankfurterFXProvider,
    SECShareDataProvider,
    StooqQuoteProvider,
)
from stock_valuation.market.snapshot_service import (
    ImmutableMarketSnapshotStore,
    persist_market_snapshot,
)
from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.database.models import Base, MarketDataSnapshotRecord


def _listing(security_type: str = "ordinary_share", adr_ratio=None, underlying_share_ratio=None) -> ListingData:
    return ListingData(
        ticker="EXM",
        exchange="NASDAQ",
        trading_currency="USD",
        security_type=security_type,
        primary_listing=True,
        adr_ratio=Decimal(str(adr_ratio)) if adr_ratio is not None else None,
        underlying_share_ratio=Decimal(str(underlying_share_ratio)) if underlying_share_ratio is not None else None,
        provider="test",
    )


def _quote(price: str | None = "10", price_date: date | None = date(2026, 8, 21)) -> NormalizedMarketQuote:
    return NormalizedMarketQuote(
        ticker="EXM",
        exchange="NASDAQ",
        listing_currency="USD",
        price=Decimal(price) if price is not None else None,
        price_date=price_date,
        retrieved_at=datetime(2026, 8, 23, tzinfo=UTC),
        provider="test_quote",
        provider_symbol="EXM",
        source_url="https://example.test/quote",
    )


def _shares(value: str | None = "100", diluted: str | None = "125") -> NormalizedShareData:
    return NormalizedShareData(
        ticker="EXM",
        shares_outstanding=Decimal(value) if value is not None else None,
        diluted_weighted_average_shares=Decimal(diluted) if diluted is not None else None,
        basic_weighted_average_shares=Decimal("110"),
        fiscal_year=2025,
        share_date=date(2026, 8, 20),
        filing_date=date(2026, 2, 1),
        provider="test_shares",
        source="official_filing",
        provider_field="EntityCommonStockSharesOutstanding",
        source_url="https://example.test/filing",
    )


def _snapshot(**overrides) -> MarketDataSnapshot:
    base = MarketDataSnapshot(
        company="Example",
        analysis_as_of_date=date(2026, 8, 23),
        listing=_listing(),
        quote=_quote(),
        share_data=_shares(),
        financial_statement_currency="USD",
        net_debt=NetDebtInput(2025, Decimal("50"), "USD", "calculation_engine", "netdebt-hash"),
    )
    return replace(base, **overrides)


def _metric(snapshot: MarketDataSnapshot, metric_id: str):
    return next(item for item in derive_market_metrics(snapshot) if item.metric_id == metric_id)


def test_market_cap_uses_shares_outstanding_not_diluted_shares() -> None:
    market_cap = _metric(_snapshot(), "market_cap")

    assert market_cap.status == AVAILABLE
    assert market_cap.value == Decimal("1000")


def test_adr_conversion_requires_ratio_and_applies_ratio_when_present() -> None:
    missing = _metric(_snapshot(listing=_listing("ADR")), "market_cap")
    converted = _metric(
        _snapshot(listing=_listing("ADR", adr_ratio="1", underlying_share_ratio="5")),
        "market_cap",
    )

    assert missing.status == ADR_RATIO_REQUIRED
    assert ADR_RATIO_REQUIRED in missing.issues
    assert converted.value == Decimal("200")


def test_currency_mismatch_requires_fx_for_enterprise_value() -> None:
    snapshot = _snapshot(
        quote=replace(_quote(), listing_currency="USD"),
        financial_statement_currency="EUR",
        net_debt=NetDebtInput(2025, Decimal("50"), "EUR", "calculation_engine", "netdebt-hash"),
    )

    market_cap, enterprise_value = derive_market_metrics(snapshot)

    assert market_cap.status == AVAILABLE
    assert FX_REQUIRED in market_cap.issues
    assert enterprise_value.status == FX_REQUIRED
    assert enterprise_value.value is None


def test_fx_rate_is_required_and_validated_before_ev_conversion() -> None:
    bad_fx = _metric(
        _snapshot(
            financial_statement_currency="EUR",
            net_debt=NetDebtInput(2025, Decimal("50"), "EUR", "calculation_engine", "netdebt-hash"),
            fx_rate=FXRate("EUR", "USD", None, date(2026, 8, 23)),
        ),
        "enterprise_value",
    )
    good_fx = _metric(
        _snapshot(
            financial_statement_currency="EUR",
            net_debt=NetDebtInput(2025, Decimal("50"), "EUR", "calculation_engine", "netdebt-hash"),
            fx_rate=FXRate("EUR", "USD", Decimal("1.2"), date(2026, 8, 23), "test_fx"),
        ),
        "enterprise_value",
    )

    assert bad_fx.status == FX_UNAVAILABLE
    assert good_fx.value == Decimal("1060.0")


def test_stale_price_and_missing_price_block_market_cap() -> None:
    stale = _metric(_snapshot(quote=_quote(price_date=date(2026, 8, 1))), "market_cap")
    missing = _metric(_snapshot(quote=_quote(price=None)), "market_cap")

    assert stale.status == STALE
    assert stale.value is None
    assert missing.status == MISSING_PRICE


def test_invalid_share_count_blocks_without_zero_imputation() -> None:
    market_cap = _metric(_snapshot(share_data=_shares("0")), "market_cap")

    assert market_cap.status == INVALID_SHARE_COUNT
    assert market_cap.value is None


def test_inputs_hash_and_provenance_are_reproducible() -> None:
    first = _metric(_snapshot(), "market_cap")
    second = _metric(_snapshot(), "market_cap")

    assert first.inputs_hash == second.inputs_hash
    assert any(ref.startswith("quote:") for ref in first.input_refs)
    assert any(ref.startswith("shares:") for ref in first.input_refs)


def test_snapshot_store_is_append_only_and_immutable() -> None:
    store = ImmutableMarketSnapshotStore()
    first = _snapshot()
    first_id = store.add(first)
    second_id = store.add(_snapshot(quote=_quote("12", date(2026, 8, 22))))

    assert store.get(first_id).quote.price == Decimal("10")
    assert store.get(second_id).quote.price == Decimal("12")
    with pytest.raises(ValueError):
        store.add(replace(first, snapshot_id=first_id))


def test_listing_policy_prefers_primary_ordinary_then_adr_with_known_ratio() -> None:
    adr = _listing("ADR", adr_ratio="1", underlying_share_ratio="5")
    secondary = replace(_listing(), ticker="EXM.SEC", primary_listing=False)
    primary = replace(_listing(), ticker="EXM.PRIM", primary_listing=True)

    assert choose_listing([adr, secondary, primary]) == primary
    assert choose_listing([adr]) == adr
    assert choose_listing([_listing("ADR")]) is None


def test_future_price_share_filing_and_fx_dates_are_blocked() -> None:
    future_price = _metric(
        _snapshot(analysis_as_of_date=date(2025, 12, 31), quote=_quote(price_date=date(2026, 1, 2))),
        "market_cap",
    )
    future_share = _metric(
        _snapshot(analysis_as_of_date=date(2025, 12, 31), share_data=_shares()),
        "market_cap",
    )
    future_filing = _metric(
        _snapshot(
            analysis_as_of_date=date(2026, 1, 1),
            share_data=replace(_shares(), share_date=date(2025, 12, 31), filing_date=date(2026, 1, 2)),
        ),
        "market_cap",
    )
    future_fx = _metric(
        _snapshot(
            financial_statement_currency="EUR",
            net_debt=NetDebtInput(2025, Decimal("50"), "EUR", "calculation_engine", "netdebt-hash"),
            fx_rate=FXRate("EUR", "USD", Decimal("1.2"), date(2026, 8, 24)),
        ),
        "enterprise_value",
    )

    assert LOOKAHEAD_BLOCKED in future_price.issues
    assert LOOKAHEAD_BLOCKED in future_share.issues
    assert LOOKAHEAD_BLOCKED in future_filing.issues
    assert future_fx.status == LOOKAHEAD_BLOCKED


def test_stale_and_current_share_counts_are_distinguished() -> None:
    stale = _metric(
        _snapshot(share_data=replace(_shares(), share_date=date(2024, 1, 1), filing_date=date(2024, 2, 1))),
        "market_cap",
    )
    current = _metric(
        _snapshot(share_data=replace(_shares(), share_date=date(2026, 7, 1), filing_date=date(2026, 7, 15))),
        "market_cap",
    )

    assert stale.status == SHARE_COUNT_STALE
    assert current.status == AVAILABLE


def test_adr_share_basis_must_match_conversion() -> None:
    ordinary_basis = _metric(
        _snapshot(
            listing=_listing("ADR", adr_ratio="1", underlying_share_ratio="5"),
            share_data=replace(_shares(), share_basis=SHARE_BASIS_ORDINARY),
        ),
        "market_cap",
    )
    adr_unit_basis = _metric(
        _snapshot(
            listing=_listing("ADR", adr_ratio="1", underlying_share_ratio="5"),
            share_data=replace(_shares(), share_basis=SHARE_BASIS_ADR_UNITS),
        ),
        "market_cap",
    )

    assert ordinary_basis.value == Decimal("200")
    assert "ADR_SHARE_BASIS_MISMATCH" in adr_unit_basis.issues


def test_fx_date_mismatch_blocks_enterprise_value() -> None:
    ev = _metric(
        _snapshot(
            financial_statement_currency="EUR",
            net_debt=NetDebtInput(2025, Decimal("50"), "EUR", "calculation_engine", "netdebt-hash"),
            fx_rate=FXRate("EUR", "USD", Decimal("1.2"), date(2026, 8, 1)),
        ),
        "enterprise_value",
    )

    assert ev.status == DATE_MISMATCH
    assert "FX_DATE_MISMATCH" in ev.issues


def test_secondary_listing_without_liquidity_metadata_requires_review() -> None:
    secondary = replace(_listing(), ticker="EXM.SEC", primary_listing=False)
    liquid_secondary = replace(secondary, liquidity_priority=1)

    assert choose_listing([secondary]) is None
    assert listing_policy_status([secondary]) == LISTING_REVIEW_REQUIRED
    assert choose_listing([liquid_secondary]) == liquid_secondary


def test_persistent_market_snapshot_is_append_only() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(session, name="Example", ticker="EXM", currency="USD")
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        market_cap = _metric(_snapshot(), "market_cap")
        snapshot_id = persist_market_snapshot(
            session,
            analysis,
            _snapshot(),
            inputs_hash=market_cap.inputs_hash,
        )
        row = session.query(MarketDataSnapshotRecord).filter_by(snapshot_id=snapshot_id).one()

        assert row.price == Decimal("10.00000000")
        with pytest.raises(ValueError):
            persist_market_snapshot(session, analysis, _snapshot(snapshot_id=snapshot_id), inputs_hash=market_cap.inputs_hash)


def test_live_provider_normalization_from_stooq_sec_and_fx_payloads(monkeypatch) -> None:
    class Response:
        def __init__(self, text="", payload=None):
            self.text = text
            self._payload = payload or {}

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, **kwargs):
        if "stooq.com" in url:
            return Response("Symbol,Date,Time,Close\r\nAAPL.US,2026-08-21,22:00:00,275.25\r\n")
        if "alphavantage" in url:
            return Response(
                payload={
                    "Global Quote": {
                        "01. symbol": "AAPL",
                        "05. price": "275.25",
                        "07. latest trading day": "2026-08-21",
                    }
                }
            )
        if "frankfurter" in url:
            return Response(payload={"date": "2026-08-21", "rates": {"USD": 1.2}})
        return Response(
            payload={
                "facts": {
                    "dei": {
                        "EntityCommonStockSharesOutstanding": {
                            "units": {
                                "shares": [
                                    {"end": "2026-08-20", "filed": "2026-08-21", "val": 100, "form": "10-Q"}
                                ]
                            }
                        }
                    },
                    "us-gaap": {
                        "WeightedAverageNumberOfSharesOutstandingBasic": {
                            "units": {"shares": [{"end": "2025-12-31", "filed": "2026-02-01", "val": 95, "form": "10-K"}]}
                        },
                        "WeightedAverageNumberOfDilutedSharesOutstanding": {
                            "units": {"shares": [{"end": "2025-12-31", "filed": "2026-02-01", "val": 105, "form": "10-K"}]}
                        },
                    },
                }
            }
        )

    monkeypatch.setattr("requests.get", fake_get)

    quote = StooqQuoteProvider(use_cache=False).latest_quote(
        "aapl.us", ticker="AAPL", exchange="NASDAQ", currency="USD"
    )
    alpha_quote = AlphaVantageQuoteProvider(api_key="demo", use_cache=False).latest_quote(
        "AAPL", ticker="AAPL", exchange="NASDAQ", currency="USD"
    )
    shares = SECShareDataProvider(user_agent="test@example.com", use_cache=False).latest_share_data(
        "0000320193", ticker="AAPL", as_of_date=date(2026, 8, 23)
    )
    fx = FrankfurterFXProvider(use_cache=False).rate("EUR", "USD", date(2026, 8, 21))

    assert quote.price == Decimal("275.25")
    assert quote.price_date == date(2026, 8, 21)
    assert alpha_quote.price == Decimal("275.25")
    assert shares.shares_outstanding == Decimal("100")
    assert shares.basic_weighted_average_shares == Decimal("95")
    assert shares.diluted_weighted_average_shares == Decimal("105")
    assert fx.rate == Decimal("1.2")
