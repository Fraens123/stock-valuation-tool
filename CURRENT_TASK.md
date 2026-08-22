# Current Task

## Phase 3A – Kapitel 2 fachlich fertigstellen und gesperrte Rohfelder bereinigen

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
- D&A-Mapping wurde lokal angewendet; `depreciation_amortization` ist im Feld-Gate freigegeben.
- EBITDA-Marge ist aktiv und lokal als 10-Jahres-Serie sichtbar; 2025 ca. 37,74 %.

## Vor Beginn lesen

1. `AGENTS.md`
2. `ROADMAP.md`
3. `docs/OPEN_ITEMS.md`
4. `docs/METHODOLOGY_OPEN_QUESTIONS.md`
5. `docs/ASML_ALPHA_VANTAGE_VALIDATION.md`
6. `src/stock_valuation/knowledge/metrics.yaml`
7. `src/stock_valuation/metrics/engine.py`
8. `src/stock_valuation/metrics/service.py`
9. `src/stock_valuation/data/providers/alphavantage.py`
10. `pages/3_Datenqualitaet.py`

## Aktueller technischer Schritt

Die nächsten gesperrten Rohfelder werden mit genau zwei Diagnose-Requests untersucht:

- `BALANCE_SHEET`
- `CASH_FLOW`

Die neue Diagnose zeigt mögliche Provider-Rohfelder für:

- `accounts_receivable`
- `inventory`
- `ppe_net`
- `short_term_debt`
- `cash_and_short_term_investments`
- `operating_cash_flow`
- `capital_expenditures`
- `dividends_paid`

Daneben werden die offiziellen ASML-Kontrollwerte 2024/2025 und die rechnerische Abweichung angezeigt. Die Diagnose verändert den Snapshot nicht.

## Lokaler nächster Schritt

1. `git pull`
2. `pytest -q`
3. `streamlit run app.py`
4. `Datenqualität` öffnen.
5. Ganz unten `Gesperrte Felder prüfen (2 Requests)` genau einmal ausführen.
6. Ergebnis erfassen/screenshotten.
7. Nur Kandidaten weiterverfolgen, die in beiden Jahren numerisch eng an ASML liegen **und** fachlich dieselbe Bilanz-/Cashflow-Zeile darstellen.
8. Kein Mapping allein wegen ähnlicher Größenordnung freigeben.

## Noch offene Kapitel-2-Methodik

Für die folgenden Kennzahlen ist die Rohdatenbasis grundsätzlich vorhanden, die konkrete Schmidlin-Definition aber noch zu verifizieren:

- Eigenkapitalrendite (ROE) — Kindle S. 94
- Umsatzrendite — Kindle S. 101
- Kapitalumschlag — Kindle S. 107
- Gesamtkapitalrendite — Kindle S. 109
- ROCE — Kindle S. 111
- Umsatzverdienstrate — Kindle S. 114

Nutzer liefert jeweils nur Formel-/Definitionsabschnitt als Screenshot. Keine Formel erfinden.

## Weiterhin nicht vorziehen

- keine Working-Capital-Kennzahlen aus gesperrten Feldern
- kein FCF / Owner Earnings / DCF
- keine Net-Debt-/EV-Logik auf ungeklärten Debt-Feldern
- keine Fair-KGV-Punkte oder Risikostufen erfinden

## Definition of Done dieses Teilblocks

- Kandidaten der gesperrten Balance-Sheet-/Cashflow-Felder sind sichtbar.
- numerisch und semantisch geeignete Providerfelder sind identifiziert oder als nicht vorhanden dokumentiert.
- Mapping-Änderungen erfolgen erst nach Primärquellenvergleich.
- EBIT- und EBITDA-Marge bleiben reproduzierbar aus dem Snapshot berechenbar.
