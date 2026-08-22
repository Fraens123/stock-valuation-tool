# Current Task

## Phase 3A – Kapitel 2 fachlich fertigstellen

Der erste echte lokale ASML-Import, die feldweise Primärquellenprüfung und die erste Kennzahlenengine laufen.

## Verifizierter Datenstand

- Alpha Vantage `ASML` liefert konsolidierte ASML-Holding-Abschlüsse in EUR.
- erster Snapshot: 720 normalisierte jährliche Rohdatenpunkte über 20 Geschäftsjahre.
- 2024/2025-Primärquellen-Gate ist aktiv.
- EBIT-Marge ist aktiv und lokal plausibilisiert.
- D&A-Rohfelddiagnose ist abgeschlossen:
  - `INCOME_STATEMENT.depreciationAndAmortization` trifft ASML 2025 = 1.025,9 Mio. EUR exakt.
  - dasselbe Feld trifft ASML 2024 = 918,6 Mio. EUR exakt.
  - das Cashflow-D&A-Feld weicht 2024 deutlich ab und bleibt nur Cross-Check.
- Mapping ist deshalb auf das Income-Statement-D&A-Feld umgestellt.
- gezielte D&A-Aktualisierung benötigt nur 1 Alpha-Vantage-Request und ersetzt keine anderen Snapshot-Rohdaten.
- EBITDA-Marge ist im Code implementiert und kann nach der D&A-Aktualisierung berechnet werden.

## Vor Beginn lesen

1. `AGENTS.md`
2. `ROADMAP.md`
3. `docs/OPEN_ITEMS.md`
4. `docs/METHODOLOGY_OPEN_QUESTIONS.md`
5. `docs/ASML_ALPHA_VANTAGE_VALIDATION.md`
6. `src/stock_valuation/knowledge/metrics.yaml`
7. `src/stock_valuation/metrics/engine.py`
8. `src/stock_valuation/metrics/service.py`

## Lokaler nächster Schritt

1. `git pull`
2. `pytest -q`
3. `streamlit run app.py`
4. `Datenqualität` öffnen.
5. `D&A-Mapping anwenden (1 Request)` genau einmal ausführen.
6. Prüfen, dass `depreciation_amortization` danach im Feld-Gate freigegeben ist und die EBITDA-Marge-Datenbasis `BEREIT` zeigt.
7. `Kennzahlen` öffnen.
8. `Aktive Kennzahlen aus Snapshot berechnen` ausführen — 0 API-Requests.
9. Prüfen, dass EBIT- und EBITDA-Marge als 10-Jahres-Serie erscheinen.

## Noch offene Kapitel-2-Methodik

Für die folgenden Kennzahlen ist die Rohdatenbasis grundsätzlich vorhanden, die konkrete Schmidlin-Definition aber noch zu verifizieren:

- Eigenkapitalrendite (ROE) — Kindle S. 94
- Umsatzrendite — Kindle S. 101
- Kapitalumschlag — Kindle S. 107
- Gesamtkapitalrendite — Kindle S. 109
- ROCE — Kindle S. 111
- Umsatzverdienstrate — Kindle S. 114

Nutzer liefert jeweils nur Formel-/Definitionsabschnitt als Screenshot. Keine Formel erfinden.

## Weiterhin datenblockiert für spätere Phasen

- `accounts_receivable`
- `inventory`
- `ppe_net`
- `short_term_debt`
- `operating_cash_flow`
- `capital_expenditures`
- Teile der Cash-/Debt-Brücke

Deshalb weiterhin noch nicht starten:

- Working-Capital-Kennzahlen aus den gesperrten Feldern
- FCF / Owner Earnings / DCF
- Net-Debt-/EV-Logik auf ungeklärten Debt-Feldern

## Definition of Done nächster Block

- D&A-Serie im lokalen Snapshot auf `depreciationAndAmortization` aktualisiert.
- D&A-Gate 2024/2025 PASS.
- EBITDA-Marge als versionierte 10-Jahres-Kennzahl sichtbar.
- restliche Kapitel-2-Kennzahlen bleiben bis zur Buchverifikation blockiert.
