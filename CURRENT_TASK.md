# Current Task

## Phase 3A – ASML-Primärquellenwerte in Snapshot integrieren

Der ASML-Liveimport, die feldweise Datenqualitätsprüfung sowie EBIT-/EBITDA-Margen funktionieren lokal.

## Verifizierter Datenstand

- Alpha Vantage `ASML` liefert 20 Jahresberichte und eine breite historische Datenbasis in EUR.
- EBIT-Marge ist aktiv und plausibilisiert.
- D&A wurde auf `INCOME_STATEMENT.depreciationAndAmortization` korrigiert.
- EBITDA-Marge ist aktiv; 2025 lokal ca. 37,74 %.
- Alpha-Vantage-Cashflow ist für ASML nicht als Primärbasis freigegeben.
- die offizielle ASML-2025-US-GAAP-XLSX kann lokal gelesen werden.
- das reale Workbook-Layout wurde bestätigt:
  - `Balance Sheets`: eindeutige Bilanzzeilen für 2024/2025.
  - `Cash Flow`: eindeutige Cashflow-Zeilen für 2023/2024/2025.

## Neu implementiert

### Deterministischer ASML-Primärquellenparser

`src/stock_valuation/data/providers/asml_primary.py` importiert aus dem offiziellen Workbook bewusst nur eindeutige 2024/2025-Zeilen:

- `cash_and_equivalents`
- `short_term_investments`
- `accounts_receivable`
- `inventory`
- `ppe_net`
- `short_term_debt`
- `operating_cash_flow`
- `capital_expenditures`
- `intangible_purchases`
- `dividends_paid`

Bei Cashflow-Abflüssen bleibt der Originalwert in Mio. EUR auditierbar; `value` folgt der internen positiven Outflow-Konvention und wird auf EUR normalisiert.

### Separate Persistenz

`sync_asml_primary_source_2024_2025()` schreibt die offiziellen Werte unter:

- `provider = asml_primary`
- `source_type = primary_source`

Alpha-Vantage-Werte werden **nicht** gelöscht oder überschrieben.

### Quellenpriorität

Für dasselbe Feld/Jahr gilt:

1. `asml_primary`
2. `alphavantage`
3. `eodhd`

`src/stock_valuation/data/resolution.py` kapselt diese Auswahl zentral.

Der ASML-Daten-Gate verwendet ebenfalls `asml_primary` vor Alpha Vantage. Dadurch kann ein zuvor rotes API-Feld nach dem offiziellen Import freigegeben werden, während der alte Providerwert auditierbar erhalten bleibt.

Die bestehende Kennzahlenengine verwendet jetzt ebenfalls den zentralen Source Resolver.

## Lokaler nächster Schritt

1. `git pull`
2. `pip install -e ".[dev]"`
3. `pytest -q`
4. `streamlit run app.py`
5. `Datenqualität` öffnen.
6. `Offizielle ASML-2025-US-GAAP-Excel prüfen (0 AV Requests)` ausführen.
7. Im Abschnitt `Deterministischer Importvorschlag` kontrollieren, dass je Feld 2024/2025 plausible Werte erscheinen.
8. `ASML-Primärquellenwerte 2024/2025 in Snapshot übernehmen (0 AV Requests)` genau einmal ausführen.
9. Nach dem Rerun prüfen:
   - `ASML-Primärfakten` > 0,
   - zuvor problematische 2024/2025-Felder wie Forderungen, Vorräte, PP&E, OCF und CAPEX werden im Gate aus `asml_primary` bewertet,
   - Alpha-Vantage-Daten bleiben im Snapshot erhalten.

## Danach

Nach erfolgreicher lokaler Abnahme wird der nächste Datenblock geplant:

- historische Primärquellenstrategie für ältere Geschäftsjahre,
- Komponentenlogik für `cash + short_term_investments`,
- vorbereitende Datenbasis für Working Capital und spätere DCF-Felder.

## Noch offene Kapitel-2-Methodik

Weiterhin Buchverifikation erforderlich:

- ROE — Kindle S. 94
- Umsatzrendite — Kindle S. 101
- Kapitalumschlag — Kindle S. 107
- Gesamtkapitalrendite — Kindle S. 109
- ROCE — Kindle S. 111
- Umsatzverdienstrate — Kindle S. 114

Keine dieser Formeln eigenmächtig festlegen.

## Weiterhin nicht vorziehen

- kein Working Capital mit ungeklärter historischen Datenbasis
- kein FCF / Owner Earnings / DCF
- keine endgültige Net-Debt-/EV-Brücke
- keine Fair-KGV-Punkte oder Risikostufen erfinden

## Definition of Done dieses Teilblocks

- offizieller 2024/2025-Primärquellenimport läuft lokal.
- offizielle Fakten stehen separat neben Alpha Vantage im Snapshot.
- Daten-Gate priorisiert Primärquelle korrekt.
- zentrale Source-Resolution ist getestet.
- EBIT-/EBITDA-Marge funktionieren unverändert.
