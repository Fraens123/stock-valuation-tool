from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from stock_valuation.companies.provider_symbols import get_provider_symbol
from stock_valuation.database.models import Analysis
from stock_valuation.market.models import (
    ListingData,
    MarketDataSnapshot,
    NetDebtInput,
    NormalizedMarketQuote,
    NormalizedShareData,
    SHARE_BASIS_ORDINARY,
)
from stock_valuation.market.providers import MarketProviderError, StooqQuoteProvider
from stock_valuation.market.providers import SECShareDataProvider
from stock_valuation.market.snapshot_service import persist_market_snapshot
from stock_valuation.workflow.persistence import canonical_hash, latest_stage_snapshot, payload_from_stage
from stock_valuation.workflow.service import refresh_local_analysis_stages


def refresh_market_snapshot_for_analysis(
    session: Session,
    analysis: Analysis,
    *,
    quote_provider: StooqQuoteProvider | None = None,
    share_provider: SECShareDataProvider | None = None,
    manual_price: Decimal | None = None,
    manual_shares_outstanding: Decimal | None = None,
    provider_symbol: str | None = None,
    exchange: str | None = None,
    trading_currency: str | None = None,
) -> str:
    symbol_row = get_provider_symbol(session, analysis.company, provider="stooq", purpose="quote")
    symbol = (provider_symbol or (symbol_row.symbol if symbol_row else None) or analysis.company.provider_symbol or analysis.company.ticker).strip()
    currency = (trading_currency or (symbol_row.currency if symbol_row else None) or analysis.market_price_currency or analysis.company.currency).upper()
    listing = ListingData(
        ticker=analysis.company.ticker,
        exchange=exchange or (symbol_row.exchange if symbol_row else None) or analysis.company.exchange or "UNKNOWN",
        trading_currency=currency,
        security_type="ordinary_share",
        primary_listing=True,
        provider="stooq" if quote_provider is not None else "manual_or_stored",
        note="Vom Nutzer ausgelöster Marktdaten-Refresh; keine automatische Abfrage beim Streamlit-Rerun.",
    )
    if manual_price is not None:
        quote = NormalizedMarketQuote(
            ticker=analysis.company.ticker,
            exchange=listing.exchange,
            listing_currency=currency,
            price=manual_price,
            price_date=analysis.as_of_date,
            retrieved_at=datetime.now(UTC),
            provider="manual_user_input",
            provider_symbol=symbol,
            source_url=None,
            original_value=manual_price,
        )
    else:
        provider = quote_provider or StooqQuoteProvider()
        quote = provider.latest_quote(
            symbol,
            ticker=analysis.company.ticker,
            exchange=listing.exchange,
            currency=currency,
            security_type=listing.security_type,
        )
    shares = _share_data(session, analysis, manual_shares_outstanding=manual_shares_outstanding, share_provider=share_provider)
    net_debt = _net_debt_from_calculation(session, analysis)
    snapshot = MarketDataSnapshot(
        company=analysis.company.name,
        analysis_as_of_date=analysis.as_of_date,
        listing=listing,
        quote=quote,
        share_data=shares,
        financial_statement_currency=analysis.company.currency,
        net_debt=net_debt,
    )
    inputs_hash = canonical_hash(
        {
            "symbol": symbol,
            "price": str(quote.price),
            "price_date": quote.price_date.isoformat() if quote.price_date else None,
            "shares": str(manual_shares_outstanding) if manual_shares_outstanding is not None else None,
            "calculation_net_debt": str(net_debt.value) if net_debt and net_debt.value is not None else None,
            "currency": currency,
        }
    )
    snapshot_id = persist_market_snapshot(session, analysis, snapshot, inputs_hash=inputs_hash)
    refresh_local_analysis_stages(session, analysis)
    return snapshot_id


def market_refresh_missing_reason(exc: Exception) -> str:
    if isinstance(exc, MarketProviderError):
        return str(exc)
    return "Marktdaten konnten nicht geladen werden. Börsenplatz, Handelssymbol und Aktienzahl prüfen."


def _share_data(
    session: Session,
    analysis: Analysis,
    *,
    manual_shares_outstanding: Decimal | None,
    share_provider: SECShareDataProvider | None,
) -> NormalizedShareData:
    if manual_shares_outstanding is not None:
        return NormalizedShareData(
            ticker=analysis.company.ticker,
            shares_outstanding=manual_shares_outstanding,
            diluted_weighted_average_shares=None,
            basic_weighted_average_shares=None,
            fiscal_year=analysis.as_of_date.year,
            share_date=analysis.as_of_date,
            filing_date=None,
            provider="manual_user_input",
            source="user_confirmed",
            provenance="Aktienzahl vom Nutzer bestätigt.",
            share_basis=SHARE_BASIS_ORDINARY,
        )
    existing = _latest_existing_share_data(session, analysis)
    if existing is not None:
        return existing
    cik = get_provider_symbol(session, analysis.company, provider="sec", purpose="cik")
    if cik is not None:
        provider = share_provider or SECShareDataProvider()
        return provider.latest_share_data(cik.symbol, ticker=analysis.company.ticker, as_of_date=analysis.as_of_date)
    return NormalizedShareData(
        ticker=analysis.company.ticker,
        shares_outstanding=None,
        diluted_weighted_average_shares=None,
        basic_weighted_average_shares=None,
        fiscal_year=analysis.as_of_date.year,
        share_date=None,
        filing_date=None,
        provider="missing",
        source="not_loaded",
        provenance="Keine bestätigte Aktienzahl vorhanden.",
        share_basis=SHARE_BASIS_ORDINARY,
    )


def _latest_existing_share_data(session: Session, analysis: Analysis) -> NormalizedShareData | None:
    from sqlalchemy import select
    from stock_valuation.database.models import MarketDataSnapshotRecord

    row = session.scalar(
        select(MarketDataSnapshotRecord)
        .where(MarketDataSnapshotRecord.analysis_id == analysis.id, MarketDataSnapshotRecord.shares_outstanding.is_not(None))
        .order_by(MarketDataSnapshotRecord.retrieved_at.desc(), MarketDataSnapshotRecord.id.desc())
        .limit(1)
    )
    if row is None:
        return None
    return NormalizedShareData(
        ticker=analysis.company.ticker,
        shares_outstanding=row.shares_outstanding,
        diluted_weighted_average_shares=None,
        basic_weighted_average_shares=None,
        fiscal_year=row.share_date.year if row.share_date else analysis.as_of_date.year,
        share_date=row.share_date,
        filing_date=row.filing_date,
        provider="previous_market_snapshot",
        source="persisted_snapshot",
        provenance="Aktienzahl aus vorhandenem Market Snapshot übernommen.",
        share_basis=row.share_basis or SHARE_BASIS_ORDINARY,
    )


def _net_debt_from_calculation(session: Session, analysis: Analysis) -> NetDebtInput | None:
    row = latest_stage_snapshot(session, analysis, "CALCULATION")
    payload = payload_from_stage(row)
    latest = None
    for item in payload.get("results", []):
        if item.get("metric_id") == "net_debt" and item.get("status") == "AVAILABLE" and item.get("value") is not None:
            if latest is None or int(item.get("fiscal_year") or 0) > latest[0]:
                latest = (int(item["fiscal_year"]), Decimal(str(item["value"])), item.get("inputs_hash"))
    if latest is None:
        return NetDebtInput(analysis.as_of_date.year, None, analysis.company.currency, "calculation_not_available")
    return NetDebtInput(latest[0], latest[1], analysis.company.currency, "calculation_stage", latest[2])
