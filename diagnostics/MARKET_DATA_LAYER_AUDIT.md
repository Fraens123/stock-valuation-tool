# MARKET_DATA_LAYER_AUDIT

## 1. Executive Summary

Decision: GO – MARKET DATA & SHARE DATA LAYER V1 FROZEN

Phase 6A implementiert eine getrennte Markt- und Aktiendaten-Schicht. Es wurden keine Bewertungsmultiples, kein DCF, kein Fair Value, keine Margin of Safety und keine Kauf-/Verkaufsempfehlung implementiert.

## 2. Bestehende Markt-/Share-Logik

- `Company` besitzt Ticker, ISIN, Exchange und Currency, aber noch keine getrennte Listing-/Share-/Quote-Schicht.
- `Analysis.market_price` und `market_price_currency` existieren als Legacy-Feld, werden fuer V1 nicht als Marktdaten-Snapshot verwendet.
- EODHD-Mapping enthaelt geplante Felder wie diluted_shares_provider und market_cap, aber keine freigegebene Market-Data-Layer.
- `net_debt` existiert in Calculation Engine V1 und wird fuer Enterprise Value technisch eingebunden; keine neue Debt-Berechnung.

## 3. Gewaehlte Datenquellen

- V1-Architektur ist providerunabhaengig. Regression nutzt reproduzierbare Reviewed Fixtures.
- Kandidat Alpha Vantage: geeignet fuer Quotes/Historie/Shares, aber API-Key und Rate Limits.
- Kandidat Stooq: geeignet fuer historische Schlusskurse bei persoenlicher Nutzung, aber Symbol-/Coverage-Pruefung noetig.
- Kandidat Yahoo/yfinance: breite Coverage, aber Lizenz-/Terms-Risiko; nicht als Default gewaehlt.
- SEC/XBRL: geeignet fuer offizielle Share-Facts, nicht fuer Preise.

## 4. Providervergleich

| Provider | Coverage | Historie | Rate Limits | Waehrungen | ADR | Kosten/Lizenz | V1-Rolle |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Alpha Vantage | Global equities | Daily/weekly/monthly plus fundamentals | Free tier quota-limited | Providerfelder | teilweise | API-Key, Free/Premium | Kandidat fuer Adapter |
| Stooq | Viele US/EU/World-Symbole | Historische EOD-Daten | Web/CAPTCHA bei Bulk | symbolabhaengig | begrenzt | persoenliche Nutzung | Kandidat fuer historische Preise |
| Yahoo/yfinance | breit | breit | inoffiziell | breit | breit | Terms pruefen | nicht Default |
| SEC/XBRL | SEC-Filer Share-Facts | Filing-historisch | SEC Fair Access | Reporting units | FPI abhaengig | offiziell/frei | Share-Adapter-Kandidat |

## 5. Datenmodell

- `ListingData`: Ticker, Exchange, Trading Currency, ISIN, Security Type, ADR/ADS Ratio.
- `NormalizedMarketQuote`: Preis, Preisdatum, Provider, Provider-Symbol, Quelle.
- `NormalizedShareData`: Shares Outstanding, Basic WA Shares, Diluted WA Shares, Filing-/Share-Date.
- `MarketDataSnapshot`: immutable Analyse-Snapshot mit Quote, Shares, Listing, Net Debt und FX.
- `DerivedMarketMetric`: market_cap und enterprise_value mit Provenienz und inputs_hash.

## 6. Shares-Definition

- Shares Outstanding wird fuer Market Cap verwendet.
- Basic Weighted Average Shares und Diluted Weighted Average Shares bleiben getrennt.
- Diluted Shares werden nicht fuer Market Cap verwendet.

## 7. Listing-Policy

1. Wirtschaftliches Primary Listing ohne ADR/ADS bevorzugen.
2. Sonst geeignetes liquides Sekundaerlisting.
3. ADR/ADS nur mit bekanntem ADR-Verhaeltnis.

## 8. Currency-/FX-Policy

- Market Cap wird in Trading Currency berechnet.
- EV benoetigt Net Debt aus Calculation Engine V1.
- Bei Financial Currency != Trading Currency ist FX erforderlich.
- FX Rate missing != 1.

## 9. ADR-/ADS-Policy

- ADR Ratio missing != 1.
- ADR/ADS Market Cap nutzt den expliziten Conversion Factor adr_ratio / underlying_share_ratio.
- Ohne verlaessliches Verhaeltnis: ADR_RATIO_REQUIRED / VALUATION_NOT_READY.

## 10. Market-Cap-Berechnung

Market Cap = Share Price x Shares Outstanding x ADR/ADS Conversion Factor.

## 11. Enterprise-Value-Berechnung

Enterprise Value = Market Cap + Net Debt. Net Debt kommt ausschliesslich aus Calculation Engine V1.

## 12. Snapshot-/As-of-Date-Policy

- Jeder Preis hat `price_date`, jeder Snapshot `analysis_as_of_date` und `retrieved_at`.
- Neue Preise erzeugen neue Snapshots und ueberschreiben alte Analysen nicht.
- Historische Point-in-Time-Analysen duerfen spaeter bekannte Daten nicht still verwenden.

## 13-17. Regressionen

| Company | Primary Listing | Ticker | Exchange | Security Type | Trading Currency | Financial Currency | Latest Price | Price Date | Shares Outstanding | Share Date | ADR Ratio | Market Cap | Net Debt | Enterprise Value | Status | Issues |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- | ---: | --- | --- | ---: | ---: | ---: | --- | --- |
| ASML | True | ASML.AS | Euronext Amsterdam | ordinary_share | EUR | EUR | 910.20 | 2026-08-21 | 393000000 | 2026-01-28 | / | 357708600000.00 | -8525100000.0 | 349183500000.00 | READY | CURRENCY_MATCH |
| AAPL | True | AAPL | NASDAQ | ordinary_share | USD | USD | 275.25 | 2026-08-21 | 14840390000 | 2025-10-17 | / | 4084817347500.00 | 54744000000.0 | 4139561347500.00 | READY | CURRENCY_MATCH |
| MSFT | True | MSFT | NASDAQ | ordinary_share | USD | USD | 586.10 | 2026-08-21 | 7430000000 | 2026-07-20 | / | 4354723000000.00 | 19359000000.0 | 4374082000000.00 | READY | CURRENCY_MATCH |
| TSM | False | TSM | NYSE | ADR | USD | TWD | 320.00 | 2026-08-21 | 25930380458 | 2025-12-31 | 1/5 | 1659544349312.000 | -2591096200000 | 1576629270912.000 | READY | FX_APPLIED, FX_REQUIRED |
| ADBE | True | ADBE | NASDAQ | ordinary_share | USD | USD | 358.40 | 2026-08-21 | 421000000 | 2026-01-16 | / | 150886400000.00 | 779000000.0 | 151665400000.00 | READY | CURRENCY_MATCH |

## 18. Offene Probleme

- Keine blockierenden Probleme in der Phase-6A-Regression.

## 19. Tests

- Market Cap Berechnung.
- Shares Outstanding vs Diluted Shares.
- ADR Conversion und fehlende ADR Ratio.
- Currency Mismatch, fehlende FX Rate und FX-Anwendung.
- Price Date, Stale Price und fehlender Aktienkurs.
- Snapshot Immutability.
- Negative/0 Share Count.
- Provenienz, inputs_hash und reproduzierbare Berechnung.

## 20. GO/NO-GO

GO – MARKET DATA & SHARE DATA LAYER V1 FROZEN
