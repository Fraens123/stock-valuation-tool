from __future__ import annotations

import csv
import json
import sys
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stock_valuation.market.engine import derive_market_metrics
from stock_valuation.market.models import (
    AVAILABLE,
    FXRate,
    ListingData,
    MarketDataSnapshot,
    NetDebtInput,
    NormalizedMarketQuote,
    NormalizedShareData,
)


CALC_CSV = ROOT / "diagnostics" / "calculation_engine_results.csv"
FINAL_GATE_CSV = ROOT / "diagnostics" / "final_data_gate_report.csv"
OUT_MD = ROOT / "diagnostics" / "MARKET_DATA_LAYER_AUDIT.md"
OUT_JSON = ROOT / "diagnostics" / "MARKET_DATA_LAYER_AUDIT.json"
OUT_CSV = ROOT / "diagnostics" / "market_data_results.csv"
ANALYSIS_AS_OF_DATE = date(2026, 8, 23)
RETRIEVED_AT = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)


def _d(value: str) -> Decimal:
    return Decimal(value)


def _decimal(value: str) -> Decimal | None:
    if value in {"", "None", "null"}:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return None


REGRESSION_MARKET_INPUTS = {
    "AAPL": {
        "company": "Apple Inc.",
        "listing": ListingData("AAPL", "NASDAQ", "USD", "ordinary_share", True, "US0378331005", provider="regression_fixture", source_url="https://www.nasdaq.com/market-activity/stocks/aapl"),
        "quote": ("AAPL", "NASDAQ", "USD", "275.25", date(2026, 8, 21), "regression_fixture", "AAPL"),
        "shares": ("AAPL", "14840390000", "14948100000", "14773000000", 2025, date(2025, 10, 17), date(2025, 10, 31), "dei:EntityCommonStockSharesOutstanding"),
        "provider_market_cap": "4084737347500",
    },
    "ADBE": {
        "company": "Adobe Inc.",
        "listing": ListingData("ADBE", "NASDAQ", "USD", "ordinary_share", True, "US00724F1012", provider="regression_fixture", source_url="https://www.nasdaq.com/market-activity/stocks/adbe"),
        "quote": ("ADBE", "NASDAQ", "USD", "358.40", date(2026, 8, 21), "regression_fixture", "ADBE"),
        "shares": ("ADBE", "421000000", "428000000", "424000000", 2025, date(2026, 1, 16), date(2026, 1, 23), "dei:EntityCommonStockSharesOutstanding"),
        "provider_market_cap": "150886400000",
    },
    "ASML": {
        "company": "ASML Holding N.V.",
        "listing": ListingData("ASML.AS", "Euronext Amsterdam", "EUR", "ordinary_share", True, "NL0010273215", provider="regression_fixture", source_url="https://www.euronext.com/en/products/equities/NL0010273215-XAMS"),
        "quote": ("ASML.AS", "Euronext Amsterdam", "EUR", "910.20", date(2026, 8, 21), "regression_fixture", "ASML.AS"),
        "shares": ("ASML.AS", "393000000", "394500000", "393800000", 2025, date(2026, 1, 28), date(2026, 2, 11), "official_annual_report:shares_outstanding"),
        "provider_market_cap": "357708600000",
    },
    "MSFT": {
        "company": "Microsoft Corporation",
        "listing": ListingData("MSFT", "NASDAQ", "USD", "ordinary_share", True, "US5949181045", provider="regression_fixture", source_url="https://www.nasdaq.com/market-activity/stocks/msft"),
        "quote": ("MSFT", "NASDAQ", "USD", "586.10", date(2026, 8, 21), "regression_fixture", "MSFT"),
        "shares": ("MSFT", "7430000000", "7460000000", "7435000000", 2026, date(2026, 7, 20), date(2026, 7, 30), "dei:EntityCommonStockSharesOutstanding"),
        "provider_market_cap": "4352723000000",
    },
    "TSM": {
        "company": "Taiwan Semiconductor Manufacturing Company Limited",
        "listing": ListingData("TSM", "NYSE", "USD", "ADR", False, "US8740391003", adr_ratio=_d("1"), underlying_share_ratio=_d("5"), provider="regression_fixture", source_url="https://www.nyse.com/quote/XNYS:TSM"),
        "quote": ("TSM", "NYSE", "USD", "320.00", date(2026, 8, 21), "regression_fixture", "TSM"),
        "shares": ("TSM", "25930380458", "25930380458", "25930380458", 2025, date(2025, 12, 31), date(2026, 4, 16), "official_20f:ordinary_shares"),
        "fx": FXRate("TWD", "USD", _d("0.032"), date(2026, 8, 21), "regression_fixture_fx", "https://example.invalid/fx"),
        "provider_market_cap": "1659544349312",
    },
}


def _latest_net_debt() -> dict[str, NetDebtInput]:
    rows: dict[str, NetDebtInput] = {}
    with CALC_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["metric_id"] != "net_debt" or row["status"] != AVAILABLE:
                continue
            ticker = row["ticker"]
            year = int(row["fiscal_year"])
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


def _snapshot(ticker: str, net_debt: NetDebtInput | None) -> MarketDataSnapshot:
    payload = REGRESSION_MARKET_INPUTS[ticker]
    quote = payload["quote"]
    shares = payload["shares"]
    return MarketDataSnapshot(
        company=payload["company"],
        analysis_as_of_date=ANALYSIS_AS_OF_DATE,
        listing=payload["listing"],
        quote=NormalizedMarketQuote(
            ticker=quote[0],
            exchange=quote[1],
            listing_currency=quote[2],
            price=_d(quote[3]),
            price_date=quote[4],
            retrieved_at=RETRIEVED_AT,
            provider=quote[5],
            provider_symbol=quote[6],
            source_url=payload["listing"].source_url,
            original_value=_d(quote[3]),
            security_type=payload["listing"].security_type,
        ),
        share_data=NormalizedShareData(
            ticker=shares[0],
            shares_outstanding=_d(shares[1]),
            diluted_weighted_average_shares=_d(shares[2]),
            basic_weighted_average_shares=_d(shares[3]),
            fiscal_year=shares[4],
            share_date=shares[5],
            filing_date=shares[6],
            provider="regression_fixture_shares",
            source="official_or_provider_reviewed_share_data",
            provider_field=shares[7],
            source_url=payload["listing"].source_url,
            provenance="Phase 6A reviewed regression fixture; not a valuation assumption.",
        ),
        financial_statement_currency=net_debt.currency if net_debt and net_debt.currency else quote[2],
        net_debt=net_debt,
        fx_rate=payload.get("fx"),
        snapshot_id=f"{ticker}:{ANALYSIS_AS_OF_DATE}:phase6a",
    )


def main() -> int:
    net_debt_by_ticker = _latest_net_debt()
    result_rows: list[dict[str, object]] = []
    summaries: dict[str, object] = {}
    blockers: list[str] = []
    for ticker in ("ASML", "AAPL", "MSFT", "TSM", "ADBE"):
        snapshot = _snapshot(ticker, net_debt_by_ticker.get(ticker))
        derived = derive_market_metrics(snapshot)
        by_metric = {item.metric_id: item for item in derived}
        market_cap = by_metric["market_cap"]
        enterprise_value = by_metric["enterprise_value"]
        provider_market_cap = _d(REGRESSION_MARKET_INPUTS[ticker]["provider_market_cap"])
        market_cap_delta = (
            None
            if market_cap.value is None
            else market_cap.value - provider_market_cap
        )
        status = "READY" if market_cap.status == AVAILABLE and enterprise_value.status == AVAILABLE else "VALUATION_NOT_READY"
        if status != "READY":
            blockers.append(f"{ticker}: {market_cap.status}/{enterprise_value.status}")
        summaries[ticker] = {
            "company": snapshot.company,
            "primary_listing": snapshot.listing.primary_listing,
            "ticker": snapshot.listing.ticker,
            "exchange": snapshot.listing.exchange,
            "security_type": snapshot.listing.security_type,
            "trading_currency": snapshot.listing.trading_currency,
            "financial_currency": snapshot.financial_statement_currency,
            "latest_price": str(snapshot.quote.price),
            "price_date": snapshot.quote.price_date.isoformat() if snapshot.quote.price_date else None,
            "shares_outstanding": str(snapshot.share_data.shares_outstanding),
            "share_date": snapshot.share_data.share_date.isoformat() if snapshot.share_data.share_date else None,
            "adr_ratio": str(snapshot.listing.adr_ratio) if snapshot.listing.adr_ratio else None,
            "underlying_share_ratio": str(snapshot.listing.underlying_share_ratio) if snapshot.listing.underlying_share_ratio else None,
            "market_cap": str(market_cap.value) if market_cap.value is not None else None,
            "provider_market_cap": str(provider_market_cap),
            "market_cap_delta": str(market_cap_delta) if market_cap_delta is not None else None,
            "net_debt": str(snapshot.net_debt.value) if snapshot.net_debt and snapshot.net_debt.value is not None else None,
            "enterprise_value": str(enterprise_value.value) if enterprise_value.value is not None else None,
            "status": status,
            "issues": tuple(sorted(set((*market_cap.issues, *enterprise_value.issues)))),
        }
        for metric in derived:
            result_rows.append(
                {
                    "ticker": ticker,
                    "company": snapshot.company,
                    "metric_id": metric.metric_id,
                    "status": metric.status,
                    "value": str(metric.value) if metric.value is not None else "",
                    "currency": metric.currency or "",
                    "issues": ";".join(metric.issues),
                    "input_refs": ";".join(metric.input_refs),
                    "inputs_hash": metric.inputs_hash,
                    "market_data_version": metric.market_data_version,
                    "analysis_as_of_date": ANALYSIS_AS_OF_DATE.isoformat(),
                    "price_date": snapshot.quote.price_date.isoformat() if snapshot.quote.price_date else "",
                    "share_date": snapshot.share_data.share_date.isoformat() if snapshot.share_data.share_date else "",
                    "filing_date": snapshot.share_data.filing_date.isoformat() if snapshot.share_data.filing_date else "",
                    "security_type": snapshot.listing.security_type,
                    "trading_currency": snapshot.listing.trading_currency,
                    "financial_currency": snapshot.financial_statement_currency,
                }
            )
    decision = "GO – MARKET DATA & SHARE DATA LAYER V1 FROZEN" if not blockers else "NO-GO"
    payload = {
        "decision": decision,
        "inputs": [str(CALC_CSV), str(FINAL_GATE_CSV)],
        "source_research": {
            "Alpha Vantage": "Quote/time-series APIs plus SHARES_OUTSTANDING; quota-limited, API key required.",
            "Stooq": "Free historical/current data for personal use; useful low-cost historical source, coverage needs symbol mapping.",
            "Yahoo/yfinance": "Broad coverage but terms/licensing require caution; not selected as default V1 source.",
            "SEC/XBRL": "Useful for official share facts; not a market price source.",
        },
        "companies": summaries,
        "blockers": blockers,
    }
    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result_rows[0]))
        writer.writeheader()
        writer.writerows(result_rows)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# MARKET_DATA_LAYER_AUDIT",
        "",
        "## 1. Executive Summary",
        "",
        f"Decision: {decision}",
        "",
        "Phase 6A implementiert eine getrennte Markt- und Aktiendaten-Schicht. Es wurden keine Bewertungsmultiples, kein DCF, kein Fair Value, keine Margin of Safety und keine Kauf-/Verkaufsempfehlung implementiert.",
        "",
        "## 2. Bestehende Markt-/Share-Logik",
        "",
        "- `Company` besitzt Ticker, ISIN, Exchange und Currency, aber noch keine getrennte Listing-/Share-/Quote-Schicht.",
        "- `Analysis.market_price` und `market_price_currency` existieren als Legacy-Feld, werden fuer V1 nicht als Marktdaten-Snapshot verwendet.",
        "- EODHD-Mapping enthaelt geplante Felder wie diluted_shares_provider und market_cap, aber keine freigegebene Market-Data-Layer.",
        "- `net_debt` existiert in Calculation Engine V1 und wird fuer Enterprise Value technisch eingebunden; keine neue Debt-Berechnung.",
        "",
        "## 3. Gewaehlte Datenquellen",
        "",
        "- V1-Architektur ist providerunabhaengig. Regression nutzt reproduzierbare Reviewed Fixtures.",
        "- Kandidat Alpha Vantage: geeignet fuer Quotes/Historie/Shares, aber API-Key und Rate Limits.",
        "- Kandidat Stooq: geeignet fuer historische Schlusskurse bei persoenlicher Nutzung, aber Symbol-/Coverage-Pruefung noetig.",
        "- Kandidat Yahoo/yfinance: breite Coverage, aber Lizenz-/Terms-Risiko; nicht als Default gewaehlt.",
        "- SEC/XBRL: geeignet fuer offizielle Share-Facts, nicht fuer Preise.",
        "",
        "## 4. Providervergleich",
        "",
        "| Provider | Coverage | Historie | Rate Limits | Waehrungen | ADR | Kosten/Lizenz | V1-Rolle |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
        "| Alpha Vantage | Global equities | Daily/weekly/monthly plus fundamentals | Free tier quota-limited | Providerfelder | teilweise | API-Key, Free/Premium | Kandidat fuer Adapter |",
        "| Stooq | Viele US/EU/World-Symbole | Historische EOD-Daten | Web/CAPTCHA bei Bulk | symbolabhaengig | begrenzt | persoenliche Nutzung | Kandidat fuer historische Preise |",
        "| Yahoo/yfinance | breit | breit | inoffiziell | breit | breit | Terms pruefen | nicht Default |",
        "| SEC/XBRL | SEC-Filer Share-Facts | Filing-historisch | SEC Fair Access | Reporting units | FPI abhaengig | offiziell/frei | Share-Adapter-Kandidat |",
        "",
        "## 5. Datenmodell",
        "",
        "- `ListingData`: Ticker, Exchange, Trading Currency, ISIN, Security Type, ADR/ADS Ratio.",
        "- `NormalizedMarketQuote`: Preis, Preisdatum, Provider, Provider-Symbol, Quelle.",
        "- `NormalizedShareData`: Shares Outstanding, Basic WA Shares, Diluted WA Shares, Filing-/Share-Date.",
        "- `MarketDataSnapshot`: immutable Analyse-Snapshot mit Quote, Shares, Listing, Net Debt und FX.",
        "- `DerivedMarketMetric`: market_cap und enterprise_value mit Provenienz und inputs_hash.",
        "",
        "## 6. Shares-Definition",
        "",
        "- Shares Outstanding wird fuer Market Cap verwendet.",
        "- Basic Weighted Average Shares und Diluted Weighted Average Shares bleiben getrennt.",
        "- Diluted Shares werden nicht fuer Market Cap verwendet.",
        "",
        "## 7. Listing-Policy",
        "",
        "1. Wirtschaftliches Primary Listing ohne ADR/ADS bevorzugen.",
        "2. Sonst geeignetes liquides Sekundaerlisting.",
        "3. ADR/ADS nur mit bekanntem ADR-Verhaeltnis.",
        "",
        "## 8. Currency-/FX-Policy",
        "",
        "- Market Cap wird in Trading Currency berechnet.",
        "- EV benoetigt Net Debt aus Calculation Engine V1.",
        "- Bei Financial Currency != Trading Currency ist FX erforderlich.",
        "- FX Rate missing != 1.",
        "",
        "## 9. ADR-/ADS-Policy",
        "",
        "- ADR Ratio missing != 1.",
        "- ADR/ADS Market Cap nutzt den expliziten Conversion Factor adr_ratio / underlying_share_ratio.",
        "- Ohne verlaessliches Verhaeltnis: ADR_RATIO_REQUIRED / VALUATION_NOT_READY.",
        "",
        "## 10. Market-Cap-Berechnung",
        "",
        "Market Cap = Share Price x Shares Outstanding x ADR/ADS Conversion Factor.",
        "",
        "## 11. Enterprise-Value-Berechnung",
        "",
        "Enterprise Value = Market Cap + Net Debt. Net Debt kommt ausschliesslich aus Calculation Engine V1.",
        "",
        "## 12. Snapshot-/As-of-Date-Policy",
        "",
        "- Jeder Preis hat `price_date`, jeder Snapshot `analysis_as_of_date` und `retrieved_at`.",
        "- Neue Preise erzeugen neue Snapshots und ueberschreiben alte Analysen nicht.",
        "- Historische Point-in-Time-Analysen duerfen spaeter bekannte Daten nicht still verwenden.",
        "",
        "## 13-17. Regressionen",
        "",
        "| Company | Primary Listing | Ticker | Exchange | Security Type | Trading Currency | Financial Currency | Latest Price | Price Date | Shares Outstanding | Share Date | ADR Ratio | Market Cap | Net Debt | Enterprise Value | Status | Issues |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: | --- | ---: | --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for ticker, item in summaries.items():
        lines.append(
            f"| {ticker} | {item['primary_listing']} | {item['ticker']} | {item['exchange']} | "
            f"{item['security_type']} | {item['trading_currency']} | {item['financial_currency']} | "
            f"{item['latest_price']} | {item['price_date']} | {item['shares_outstanding']} | "
            f"{item['share_date']} | {item['adr_ratio'] or ''}/{item['underlying_share_ratio'] or ''} | "
            f"{item['market_cap']} | {item['net_debt']} | {item['enterprise_value']} | "
            f"{item['status']} | {', '.join(item['issues'])} |"
        )
    lines.extend(["", "## 18. Offene Probleme", ""])
    if blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- Keine blockierenden Probleme in der Phase-6A-Regression.")
    lines.extend(
        [
            "",
            "## 19. Tests",
            "",
            "- Market Cap Berechnung.",
            "- Shares Outstanding vs Diluted Shares.",
            "- ADR Conversion und fehlende ADR Ratio.",
            "- Currency Mismatch, fehlende FX Rate und FX-Anwendung.",
            "- Price Date, Stale Price und fehlender Aktienkurs.",
            "- Snapshot Immutability.",
            "- Negative/0 Share Count.",
            "- Provenienz, inputs_hash und reproduzierbare Berechnung.",
            "",
            "## 20. GO/NO-GO",
            "",
            decision,
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_MD}")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_CSV}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
