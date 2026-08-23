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
from stock_valuation.market.snapshot_service import persist_market_snapshot
from stock_valuation.workflow.persistence import canonical_hash
from stock_valuation.workflow.service import refresh_local_analysis_stages


def refresh_market_snapshot_for_analysis(
    session: Session,
    analysis: Analysis,
    *,
    quote_provider: StooqQuoteProvider | None = None,
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
    shares = NormalizedShareData(
        ticker=analysis.company.ticker,
        shares_outstanding=manual_shares_outstanding,
        diluted_weighted_average_shares=None,
        basic_weighted_average_shares=None,
        fiscal_year=analysis.as_of_date.year,
        share_date=analysis.as_of_date if manual_shares_outstanding is not None else None,
        filing_date=None,
        provider="manual_user_input" if manual_shares_outstanding is not None else "missing",
        source="user_confirmed" if manual_shares_outstanding is not None else "not_loaded",
        provenance="Aktienzahl vom Nutzer bestätigt." if manual_shares_outstanding is not None else "Keine bestätigte Aktienzahl vorhanden.",
        share_basis=SHARE_BASIS_ORDINARY,
    )
    snapshot = MarketDataSnapshot(
        company=analysis.company.name,
        analysis_as_of_date=analysis.as_of_date,
        listing=listing,
        quote=quote,
        share_data=shares,
        financial_statement_currency=analysis.company.currency,
        net_debt=NetDebtInput(analysis.as_of_date.year, None, analysis.company.currency, "not_available"),
    )
    inputs_hash = canonical_hash(
        {
            "symbol": symbol,
            "price": str(quote.price),
            "price_date": quote.price_date.isoformat() if quote.price_date else None,
            "shares": str(manual_shares_outstanding) if manual_shares_outstanding is not None else None,
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
