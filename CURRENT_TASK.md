# Current Task

## Phase 3A – Kapitel 2 fachlich fertigstellen und Primärquellen-Import vorbereiten

Der erste echte lokale ASML-Import, die feldweise Primärquellenprüfung und die erste Kennzahlenengine laufen.

## Verifizierter Datenstand

- Alpha Vantage `ASML` liefert konsolidierte ASML-Holding-Abschlüsse in EUR.
- erster Snapshot: 720 normalisierte jährliche Rohdatenpunkte über 20 Geschäftsjahre.
- 2024/2025-Primärquellen-Gate ist aktiv.
- EBIT-Marge ist aktiv und lokal plausibilisiert.
- D&A wurde auf `INCOME_STATEMENT.depreciationAndAmortization` korrigiert und ist freigegeben.
- EBITDA-Marge ist aktiv und lokal als 10-Jahres-Serie sichtbar; 2025 ca. 37,74 %.
- `short_term_investments` ist als eigene Komponente validierbar; Cash + Short-Term Investments soll später aus den Komponenten gebildet werden.

## Neue Erkenntnis aus der Balance-Sheet-/Cashflow-Diagnose

Bilanz:
- `accounts_receivable`: vorhandenes Alpha-Vantage-Feld ist semantisch/quantitativ ungeeignet.
- `inventory`: 2025 sehr gut, 2024 deutlich abweichend; bleibt blockiert.
- `ppe_net`: Providerfeld ist 2024/2025 missing.
- `short_term_debt`: 2025 missing, 2024 abweichend; bleibt blockiert.

Cashflow:
- OCF, PP&E-CAPEX und Dividenden zeigen innerhalb eines Jahres nahezu denselben Skalierungsfaktor gegenüber ASML.
- 2025 ca. -3,95 % bei allen drei Zeilen.
- 2024 ca. +4,46 % bei allen drei Zeilen.
- Das ist starke Evidenz für ein Provider-/Normalisierungsproblem auf Statement-Ebene.
- Kein Korrekturfaktor verwenden.
- Alpha-Vantage-Cashflow bleibt für ASML blockiert.

Siehe `docs/ASML_ALPHA_VANTAGE_VALIDATION.md`.

## Vor Beginn lesen

1. `AGENTS.md`
2. `ROADMAP.md`
3. `docs/OPEN_ITEMS.md`
4. `docs/METHODOLOGY_OPEN_QUESTIONS.md`
5. `docs/ASML_ALPHA_VANTAGE_VALIDATION.md`
6. `src/stock_valuation/knowledge/metrics.yaml`
7. `src/stock_valuation/data/providers/asml_primary.py`
8. `src/stock_valuation/validation/asml_reference.py`
9. `pages/3_Datenqualitaet.py`

## Aktueller technischer Schritt

Die offizielle **ASML 2025 US-GAAP Financial Statements Excel** wird als Primärquelle untersucht.

Quelle:
`https://ourbrand.asml.com/m/6cd86f972a9dfd24/original/2025-US-GAAP-Financial-Statements.xlsx`

Neu implementiert:
- `openpyxl` als Projektabhängigkeit.
- `src/stock_valuation/data/providers/asml_primary.py`.
- direkter Download von ASML; **0 Alpha-Vantage-Requests**.
- layoutunabhängiger Scanner für relevante Bilanz-/Cashflow-Zeilen.
- zunächst nur Diagnose, noch keine Persistenz.

Gesuchte Originalzeilen:
- Cash and cash equivalents
- Short-term investments
- Accounts receivable, net
- Inventories, net
- Property, plant and equipment, net
- Short-term borrowings / current portion of long-term debt
- Net cash provided by operating activities
- Purchases of property, plant and equipment
- Purchases of intangible assets
- Dividends paid

## Lokaler nächster Schritt

Nach dem nächsten `git pull` wegen neuer Abhängigkeit einmal:

1. `pip install -e ".[dev]"`
2. `pytest -q`
3. `streamlit run app.py`
4. `Datenqualität` öffnen.
5. Ganz unten `Offizielle ASML-2025-US-GAAP-Excel prüfen (0 AV Requests)` ausführen.
6. Tabelle mit Tabellenblatt, Zeile, Originalzeile und Kopfzeilen screenshotten.
7. Danach aus dem bestätigten Workbook-Layout einen deterministischen Primärquellen-Importer bauen.

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

- offizielles ASML-Workbook kann lokal automatisch geladen und gescannt werden.
- benötigte Originalzeilen und Jahres-Spalten sind eindeutig identifiziert.
- danach werden die Primärquellenwerte kontrolliert in den Snapshot importierbar gemacht.
- Alpha-Vantage-Cashflow bleibt bis dahin blockiert.
- EBIT- und EBITDA-Marge bleiben reproduzierbar aus dem Snapshot berechenbar.
