# Phase 2 - EdgarTools Integration

## Ergebnis

Produktionsumschaltung auf reines EdgarTools: **NO-GO**.

Produktive Integration als zusaetzlicher Importpfad mit SEC-Fallbacks: **GO**.

Der neue EdgarToolsProvider ist implementiert und im Source Router als erster SEC-Kandidat eingebunden. Der alte SEC Company-Facts-/Original-Filing-Pfad bleibt aktiv und fuellt fehlende Felder. ASML besteht die REQUIRED-Gates fuer FY2023-FY2025, aber der Dual-Run ueber AAPL, MSFT, TSM und ADBE zeigt noch offene REQUIRED-Gates fuer einen vollstaendigen Ersatz. Daher: Importpfad ja, kompletter Austausch nein.

## Implementiert

- Isolierter Provider: `src/stock_valuation/data/providers/edgartools_provider.py`
- Mapping auf `NormalizedFinancialFact`
- REQUIRED/DERIVED/OPTIONAL-Katalog: `src/stock_valuation/data/metric_requirements.py`
- Restatement-Policy im Adapter:
  - gruppiert nach `period_end.year`
  - latest official filed comparative/restated value wins
  - historische Versionen bleiben im `historical_versions`-Ergebnis erhalten
- Explizite Regeln:
  - `short_term_debt`: Aggregation kurzfristiger zinstragender Debt-Komponenten; Ausschluss von Trade Payables und Lease Liabilities
  - `depreciation_amortization`: nur D&A-spezifische Konzepte; breite `and other`/Non-Cash-Catch-all-Zeilen werden verworfen
  - `ppe_net`: PPE ohne separat ausgewiesene Right-of-Use-/Lease-Assets
- Untersuchung fehlender Felder:
  - `short_term_investments`: abdeckbar ueber `AvailableForSaleSecuritiesDebtSecuritiesCurrent`
  - `dividends_paid`: abdeckbar ueber Cash-Dividend-Tags mit Jahres-Duration-Filter, bleibt OPTIONAL
  - `intangible_purchases`: bei ASML als Standard-Cashflow-Fact nicht immer stabil verfuegbar, bleibt OPTIONAL
- Immutable Review Packages:
  - neue Tabelle `ai_review_package_snapshots`
  - Import validiert gegen den exportierten Paket-Snapshot
  - spaeter geaenderte Live-Snapshots blockieren den Import nicht mehr, sondern markieren den Run als stale
- Router-Integration:
  - `edgartools` wird vor `sec_companyfacts` gespeichert
  - `sec_companyfacts` und `sec_filing_xbrl` bleiben als Fallback/Ergaenzung aktiv
  - ESEF wird erst versucht, wenn die SEC-Familie insgesamt nicht nutzbar ist
  - Preferred Data priorisiert `edgartools`, nutzt aber alte SEC-Fakten fuer fehlende Metrik/Jahr-Kombinationen

## Dual-Run

Artefakte:

- `diagnostics/edgartools_dual_run.csv`
- `diagnostics/EDGARTOOLS_DUAL_RUN.json`

Ergebnis:

| Unternehmen | Jahre | Klassen | REQUIRED Missing | Gate |
| --- | --- | --- | ---: | --- |
| ASML | 2023-2025 | 57 VALUE_MATCH | 0 | PASS |
| AAPL | 2023-2025 | 56 VALUE_MATCH, 1 VALUE_MISMATCH | 0 | FAIL |
| MSFT | 2024-2026 | 54 VALUE_MATCH, 3 MISSING_BOTH | 3 | FAIL |
| TSM | 2022-2024 | 42 VALUE_MATCH, 15 MISSING_BOTH | 15 | FAIL |
| ADBE | 2023-2025 | 49 VALUE_MATCH, 6 MISSING_BOTH, 1 EDGARTOOLS_ONLY, 1 VALUE_MISMATCH | 6 | FAIL |

## Tests

Neue Regressionen:

- `tests/test_edgartools_provider.py`
- Erweiterung in `tests/test_ai_review_service.py`

Abgedeckt:

- ASML FY2023-FY2025 konkrete Werte fuer Revenue, Net Income, Assets, Equity, OCF, PPE und D&A
- Restatement-Policy mit historischer Versionserhaltung
- `short_term_debt`-Aggregation
- D&A-Catch-all-Ausschluss
- PPE/Right-of-Use-Ausschluss
- `short_term_investments` und `dividends_paid`
- Immutable Review Package Import gegen stale Live-Snapshot

## Entscheidung

SEC-Umschaltung auf reines EdgarTools: **NO-GO jetzt**.

EdgarTools als zusaetzlicher SEC-Importpfad mit Fallbacks: **GO**.

Grund: ASML ist gruen, aber das Zieluniversum nicht. AAPL hat noch einen VALUE_MISMATCH, MSFT/TSM/ADBE haben fehlende REQUIRED-Felder. Der produktive `source_router.py` wurde deshalb nicht auf EdgarTools-only umgestellt, sondern um einen Fallback-faehigen EdgarTools-first-Pfad erweitert.

## Naechste Schritte

1. Dual-Run-Abweichungen je Nicht-ASML-Unternehmen untersuchen.
2. REQUIRED-Katalog fuer branchen- bzw. issuer-spezifische Nichtverfuegbarkeit pruefen, besonders TSM/FPI.
3. Fehlende REQUIRED-Felder im EdgarToolsProvider gezielt erweitern oder als explizit nicht anwendbar modellieren.
4. Erst danach eine EdgarTools-only-Umschaltung pruefen.
