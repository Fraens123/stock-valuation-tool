from __future__ import annotations

import csv
import json
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stock_valuation.market.engine import derive_market_metrics
from stock_valuation.market.models import (
    AVAILABLE,
    FXRate,
    ListingData,
    MarketDataSnapshot,
    NetDebtInput,
    SHARE_BASIS_ORDINARY,
)
from stock_valuation.market.providers import (
    AlphaVantageQuoteProvider,
    FrankfurterFXProvider,
    MarketProviderError,
    OpenExchangeRateFXProvider,
    SECShareDataProvider,
)


CALC_CSV = ROOT / "diagnostics" / "calculation_engine_results.csv"
FINAL_GATE_CSV = ROOT / "diagnostics" / "final_data_gate_report.csv"
OUT_MD = ROOT / "diagnostics" / "MARKET_DATA_PRODUCTION_READINESS.md"
OUT_JSON = ROOT / "diagnostics" / "MARKET_DATA_PRODUCTION_READINESS.json"
OUT_CSV = ROOT / "diagnostics" / "market_data_live_results.csv"
ANALYSIS_AS_OF_DATE = date(2026, 8, 23)


LIVE_COMPANIES = {
    "AAPL": {
        "company": "Apple Inc.",
        "cik": "0000320193",
        "quote_symbol": "AAPL",
        "listing": ListingData("AAPL", "NASDAQ", "USD", "ordinary_share", True, liquidity_priority=1, isin="US0378331005", provider="phase6a1_listing_review"),
    },
    "MSFT": {
        "company": "Microsoft Corporation",
        "cik": "0000789019",
        "quote_symbol": "MSFT",
        "listing": ListingData("MSFT", "NASDAQ", "USD", "ordinary_share", True, liquidity_priority=1, isin="US5949181045", provider="phase6a1_listing_review"),
    },
    "ADBE": {
        "company": "Adobe Inc.",
        "cik": "0000796343",
        "quote_symbol": "ADBE",
        "listing": ListingData("ADBE", "NASDAQ", "USD", "ordinary_share", True, liquidity_priority=1, isin="US00724F1012", provider="phase6a1_listing_review"),
    },
    "ASML": {
        "company": "ASML Holding N.V.",
        "cik": "0000937966",
        "quote_symbol": "ASML",
        "listing": ListingData("ASML", "NASDAQ", "USD", "ADR", False, liquidity_priority=1, isin="USN070592100", adr_ratio=Decimal("1"), underlying_share_ratio=Decimal("1"), provider="phase6a1_listing_review", note="Liquid secondary ADR with documented ratio required before valuation."),
    },
    "TSM": {
        "company": "Taiwan Semiconductor Manufacturing Company Limited",
        "cik": "0001046179",
        "quote_symbol": "TSM",
        "listing": ListingData("TSM", "NYSE", "USD", "ADR", False, liquidity_priority=1, isin="US8740391003", adr_ratio=Decimal("1"), underlying_share_ratio=Decimal("5"), provider="phase6a1_listing_review", note="ADR represents one fifth of an ordinary share basis in V1 metadata."),
    },
}


def _load_env() -> None:
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT.parent / ".env")


def _decimal(value: str) -> Decimal | None:
    if value in {"", "None", "null"}:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return None


def _latest_net_debt() -> dict[str, NetDebtInput]:
    rows: dict[str, NetDebtInput] = {}
    with CALC_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["metric_id"] != "net_debt" or row["status"] != AVAILABLE:
                continue
            year = int(row["fiscal_year"])
            ticker = row["ticker"]
            existing = rows.get(ticker)
            if existing is not None and existing.fiscal_year >= year:
                continue
            rows[ticker] = NetDebtInput(
                fiscal_year=year,
                value=_decimal(row["value"]),
                currency=_financial_currency(ticker, year),
                source="calculation_engine_v1",
                inputs_hash=row["inputs_hash"] or None,
            )
    return rows


def _financial_currency(ticker: str, year: int) -> str | None:
    with FINAL_GATE_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["ticker"] == ticker and int(row["fiscal_year"]) == year and row["final_currency"]:
                return row["final_currency"]
    return None


def _fx_for(snapshot_currency: str, trading_currency: str, price_date: date | None):
    if snapshot_currency == trading_currency or price_date is None:
        return None
    if snapshot_currency in {"EUR", "USD"} and trading_currency in {"EUR", "USD"}:
        try:
            return FrankfurterFXProvider().rate(snapshot_currency, trading_currency, price_date)
        except Exception:
            pass
    return OpenExchangeRateFXProvider().latest_rate(snapshot_currency, trading_currency)


def main() -> int:
    _load_env()
    quote_provider = AlphaVantageQuoteProvider()
    share_provider = SECShareDataProvider()
    net_debt = _latest_net_debt()
    rows: list[dict[str, object]] = []
    summary: dict[str, object] = {}
    blockers: list[str] = []

    for ticker, config in LIVE_COMPANIES.items():
        listing = config["listing"]
        issues: list[str] = []
        try:
            quote = quote_provider.latest_quote(
                config["quote_symbol"],
                ticker=listing.ticker,
                exchange=listing.exchange,
                currency=listing.trading_currency,
                security_type=listing.security_type,
            )
        except Exception as exc:
            quote = None
            issues.append(f"QUOTE_UNAVAILABLE:{type(exc).__name__}:{exc}")
        try:
            shares = share_provider.latest_share_data(
                config["cik"],
                ticker=listing.ticker,
                as_of_date=ANALYSIS_AS_OF_DATE,
            )
        except Exception as exc:
            shares = None
            issues.append(f"SHARES_UNAVAILABLE:{type(exc).__name__}:{exc}")
        nd = net_debt.get(ticker)
        if nd is None or nd.value is None or nd.currency is None:
            issues.append("NET_DEBT_UNAVAILABLE")
        if quote is None or shares is None or nd is None or nd.currency is None:
            blockers.append(f"{ticker}: {'; '.join(issues)}")
            summary[ticker] = {"status": "NO-GO", "issues": tuple(issues)}
            continue
        shares = shares.__class__(**{**shares.__dict__, "share_basis": SHARE_BASIS_ORDINARY})
        fx = _fx_for(nd.currency, listing.trading_currency, quote.price_date)
        snapshot = MarketDataSnapshot(
            company=config["company"],
            analysis_as_of_date=ANALYSIS_AS_OF_DATE,
            listing=listing,
            quote=quote,
            share_data=shares,
            financial_statement_currency=nd.currency,
            net_debt=nd,
            fx_rate=fx,
            snapshot_id=f"{ticker}:{ANALYSIS_AS_OF_DATE}:live",
        )
        derived = derive_market_metrics(snapshot)
        by_metric = {metric.metric_id: metric for metric in derived}
        market_cap = by_metric["market_cap"]
        ev = by_metric["enterprise_value"]
        all_issues = tuple(sorted(set((*issues, *market_cap.issues, *ev.issues))))
        status = "READY" if market_cap.status == AVAILABLE and ev.status == AVAILABLE else "VALUATION_NOT_READY"
        if status != "READY":
            blockers.append(f"{ticker}: {market_cap.status}/{ev.status}: {all_issues}")
        share_age = (
            (quote.price_date - shares.share_date).days
            if quote.price_date is not None and shares.share_date is not None
            else None
        )
        summary[ticker] = {
            "company": config["company"],
            "analysis_as_of_date": ANALYSIS_AS_OF_DATE.isoformat(),
            "listing": listing.ticker,
            "exchange": listing.exchange,
            "security_type": listing.security_type,
            "price": str(quote.price),
            "price_date": quote.price_date.isoformat() if quote.price_date else None,
            "price_provider": quote.provider,
            "shares_outstanding": str(shares.shares_outstanding) if shares.shares_outstanding is not None else None,
            "share_date": shares.share_date.isoformat() if shares.share_date else None,
            "share_provider": shares.provider,
            "share_basis": shares.share_basis,
            "share_age_days": share_age,
            "financial_currency": nd.currency,
            "trading_currency": listing.trading_currency,
            "fx_rate": str(fx.rate) if fx and fx.rate is not None else None,
            "fx_date": fx.fx_date.isoformat() if fx and fx.fx_date else None,
            "adr_ratio": str(listing.adr_ratio) if listing.adr_ratio is not None else None,
            "underlying_share_ratio": str(listing.underlying_share_ratio) if listing.underlying_share_ratio is not None else None,
            "market_cap": str(market_cap.value) if market_cap.value is not None else None,
            "net_debt": str(nd.value),
            "enterprise_value": str(ev.value) if ev.value is not None else None,
            "status": status,
            "issues": all_issues,
        }
        for metric in derived:
            rows.append(
                {
                    "ticker": ticker,
                    "company": config["company"],
                    "analysis_as_of_date": ANALYSIS_AS_OF_DATE.isoformat(),
                    "listing": listing.ticker,
                    "exchange": listing.exchange,
                    "security_type": listing.security_type,
                    "price": str(quote.price),
                    "price_date": quote.price_date.isoformat() if quote.price_date else "",
                    "price_provider": quote.provider,
                    "shares_outstanding": str(shares.shares_outstanding) if shares.shares_outstanding is not None else "",
                    "share_date": shares.share_date.isoformat() if shares.share_date else "",
                    "share_provider": shares.provider,
                    "share_basis": shares.share_basis,
                    "share_age_days": share_age if share_age is not None else "",
                    "financial_currency": nd.currency,
                    "trading_currency": listing.trading_currency,
                    "fx_rate": str(fx.rate) if fx and fx.rate is not None else "",
                    "fx_date": fx.fx_date.isoformat() if fx and fx.fx_date else "",
                    "adr_ratio": str(listing.adr_ratio) if listing.adr_ratio is not None else "",
                    "underlying_share_ratio": str(listing.underlying_share_ratio) if listing.underlying_share_ratio is not None else "",
                    "metric_id": metric.metric_id,
                    "value": str(metric.value) if metric.value is not None else "",
                    "currency": metric.currency or "",
                    "status": metric.status,
                    "issues": ";".join(metric.issues),
                    "input_refs": ";".join(metric.input_refs),
                    "inputs_hash": metric.inputs_hash,
                }
            )
    decision = (
        "GO – MARKET DATA & SHARE DATA LAYER V1 PRODUCTION READY / FROZEN"
        if not blockers
        else "NO-GO"
    )
    payload = {
        "decision": decision,
        "analysis_as_of_date": ANALYSIS_AS_OF_DATE.isoformat(),
        "companies": summary,
        "blockers": blockers,
        "unit_fixture_test_status": "pytest tests/test_market_data_layer.py",
        "live_integration_test_status": "generated by this audit with real providers",
    }
    if rows:
        with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    else:
        OUT_CSV.write_text("", encoding="utf-8")
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# MARKET_DATA_PRODUCTION_READINESS",
        "",
        f"Decision: {decision}",
        "",
        "## Scope",
        "",
        "- Keine Valuation, keine Multiples, kein DCF, kein Fair Value.",
        "- Financial Data Pipeline V1, Calculation Engine V1, Historical Analysis Engine V1 und Business Quality Engine V1 wurden nicht umgebaut.",
        "- Live-Quotes kommen aus Alpha Vantage GLOBAL_QUOTE.",
        "- Shares Outstanding kommen aus offiziellen SEC CompanyFacts Share-Konzepten.",
        "- FX kommt aus Frankfurter/ECB fuer EUR/USD und Open ER API fuer nicht-ECB-Coverage wie TWD/USD.",
        "",
        "## UNIT/FIXTURE TEST",
        "",
        "- Tests decken Future-Date-Blocker, Share-Staleness, ADR-Share-Basis, FX-Date-Mismatch, Persistenz und Provider-Normalisierung ab.",
        "",
        "## LIVE INTEGRATION TEST",
        "",
        "| Company | analysis_as_of_date | Listing | Exchange | Security | Price | Price Date | Price Provider | Shares Outstanding | Share Date | Share Provider | Share Basis | Share Age Days | Financial CCY | Trading CCY | FX Rate | FX Date | ADR Ratio | Market Cap | Net Debt | Enterprise Value | Status | Issues |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- | ---: | --- | --- | --- | ---: | --- | --- | ---: | --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for ticker, item in summary.items():
        if item.get("status") == "NO-GO":
            lines.append(f"| {ticker} | {ANALYSIS_AS_OF_DATE} |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | NO-GO | {'; '.join(item['issues'])} |")
            continue
        lines.append(
            f"| {ticker} | {item['analysis_as_of_date']} | {item['listing']} | {item['exchange']} | "
            f"{item['security_type']} | {item['price']} | {item['price_date']} | {item['price_provider']} | "
            f"{item['shares_outstanding']} | {item['share_date']} | {item['share_provider']} | {item['share_basis']} | "
            f"{item['share_age_days']} | {item['financial_currency']} | {item['trading_currency']} | "
            f"{item['fx_rate'] or ''} | {item['fx_date'] or ''} | "
            f"{item['adr_ratio'] or ''}/{item['underlying_share_ratio'] or ''} | "
            f"{item['market_cap']} | {item['net_debt']} | {item['enterprise_value']} | "
            f"{item['status']} | {', '.join(item['issues'])} |"
        )
    lines.extend(["", "## Crosscheck", ""])
    lines.append("- Provider-Market-Cap wird nicht uebernommen. Der Live-Audit berechnet Market Cap intern aus Quote, Shares Outstanding und ADR-Faktor.")
    lines.append("- Abweichungsursachen bleiben fuer Phase 6B sichtbar: stale shares, ADR ratio, Share-Basis, FX und Listing.")
    lines.extend(["", "## Blockers", ""])
    if blockers:
        lines.extend(f"- {blocker}" for blocker in blockers)
    else:
        lines.append("- Keine Look-Ahead-, Share-Basis-, FX- oder Live-Provider-Blocker.")
    lines.extend(["", "## Decision", "", decision])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_MD}")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_CSV}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
