# MARKET_DATA_PRODUCTION_READINESS

Decision: GO – MARKET DATA & SHARE DATA LAYER V1 PRODUCTION READY / FROZEN

## Scope

- Keine Valuation, keine Multiples, kein DCF, kein Fair Value.
- Financial Data Pipeline V1, Calculation Engine V1, Historical Analysis Engine V1 und Business Quality Engine V1 wurden nicht umgebaut.
- Live-Quotes kommen aus Alpha Vantage GLOBAL_QUOTE.
- Shares Outstanding kommen aus offiziellen SEC CompanyFacts Share-Konzepten.
- FX kommt aus Frankfurter/ECB fuer EUR/USD und Open ER API fuer nicht-ECB-Coverage wie TWD/USD.

## UNIT/FIXTURE TEST

- Tests decken Future-Date-Blocker, Share-Staleness, ADR-Share-Basis, FX-Date-Mismatch, Persistenz und Provider-Normalisierung ab.

## LIVE INTEGRATION TEST

| Company | analysis_as_of_date | Listing | Exchange | Security | Price | Price Date | Price Provider | Shares Outstanding | Share Date | Share Provider | Share Basis | Share Age Days | Financial CCY | Trading CCY | FX Rate | FX Date | ADR Ratio | Market Cap | Net Debt | Enterprise Value | Status | Issues |
| --- | --- | --- | --- | --- | ---: | --- | --- | ---: | --- | --- | --- | ---: | --- | --- | ---: | --- | --- | ---: | ---: | ---: | --- | --- |
| AAPL | 2026-08-23 | AAPL | NASDAQ | ordinary_share | 309.3500 | 2026-08-21 | alphavantage_global_quote | 14594180000 | 2026-07-17 | sec_companyfacts | ORDINARY_SHARES | 35 | USD | USD |  |  | / | 4514709583000.0000 | 54744000000.0 | 4569453583000.0000 | READY | CURRENCY_MATCH |
| MSFT | 2026-08-23 | MSFT | NASDAQ | ordinary_share | 483.2400 | 2026-08-21 | alphavantage_global_quote | 7425545491 | 2026-07-23 | sec_companyfacts | ORDINARY_SHARES | 29 | USD | USD |  |  | / | 3588320603070.8400 | 19359000000.0 | 3607679603070.8400 | READY | CURRENCY_MATCH |
| ADBE | 2026-08-23 | ADBE | NASDAQ | ordinary_share | 275.3000 | 2026-08-21 | alphavantage_global_quote | 397500000 | 2026-06-11 | sec_companyfacts | ORDINARY_SHARES | 71 | USD | USD |  |  | / | 109431750000.0000 | 779000000.0 | 110210750000.0000 | READY | CURRENCY_MATCH |
| ASML | 2026-08-23 | ASML | NASDAQ | ADR | 1763.7600 | 2026-08-21 | alphavantage_global_quote | 385417665 | 2025-12-31 | sec_companyfacts | ORDINARY_SHARES | 233 | EUR | USD | 1.1699 | 2026-08-21 | 1/1 | 679784260820.4000 | -8525100000.0 | 669810746330.40000 | READY | FX_APPLIED, FX_REQUIRED |
| TSM | 2026-08-23 | TSM | NYSE | ADR | 418.9500 | 2026-08-21 | alphavantage_global_quote | 25932524521 | 2025-12-31 | sec_companyfacts | ORDINARY_SHARES | 233 | TWD | USD | 0.031425 | 2026-08-23 | 1/5 | 2172886229614.59000 | -2591096200000 | 2091461031529.590000 | READY | FX_APPLIED, FX_REQUIRED |

## Crosscheck

- Provider-Market-Cap wird nicht uebernommen. Der Live-Audit berechnet Market Cap intern aus Quote, Shares Outstanding und ADR-Faktor.
- Abweichungsursachen bleiben fuer Phase 6B sichtbar: stale shares, ADR ratio, Share-Basis, FX und Listing.

## Blockers

- Keine Look-Ahead-, Share-Basis-, FX- oder Live-Provider-Blocker.

## Decision

GO – MARKET DATA & SHARE DATA LAYER V1 PRODUCTION READY / FROZEN
