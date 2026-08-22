# Current Task

## Phase 3A – Erste Kennzahlenengine auf validierten ASML-Rohdaten

Der erste echte lokale ASML-Import und die feldweise Primärquellenprüfung sind erfolgreich gelaufen.

## Verifizierter Datenstand

- Alpha Vantage `ASML` liefert konsolidierte ASML-Holding-Abschlüsse in EUR.
- erster Snapshot: 720 normalisierte jährliche Rohdatenpunkte über 20 Geschäftsjahre.
- 2024/2025-Primärquellen-Gate ist aktiv.
- lokale Nutzerprüfung bestätigt:
  - `revenue`, `net_income`, `operating_income`, `total_assets`, `shareholders_equity` und `current_liabilities` besitzen eine freigegebene Datenbasis für Phase 3A.
  - `depreciation_amortization`, `accounts_receivable`, `inventory`, `ppe_net`, `operating_cash_flow`, `capital_expenditures` u. a. bleiben blockiert.
- Working-Capital- und DCF-Kennzahlen bleiben deshalb weiterhin gesperrt.

## Neu implementiert

- `src/stock_valuation/metrics/engine.py`: reine, testbare Verhältnis-/EBIT-Margen-Logik.
- `src/stock_valuation/metrics/service.py`: Daten-Gate, Berechnung, Input-Hash und versionierte `MetricSnapshot`-Persistenz.
- `pages/4_Kennzahlen.py`: erstes Kapitel-2-UI mit 10-Jahres-Historie, 5J Ø/Median, 10J Median und `ⓘ`.
- `tests/test_phase3a_metrics.py`: Formel-, Daten-Gate-, Snapshot- und Freeze-Tests.
- Berechnung verursacht **keine API-Requests**; sie verwendet ausschließlich gespeicherte Snapshot-Rohdaten.

## Aktiver Kennzahlenstatus

### Aktiv

- **EBIT-Marge**
  - Zieldefinition: EBIT / Umsatz.
  - ASML-V1-Input: validiertes `Income from operations / Total net sales`.
  - provider-/unternehmensspezifische Zuordnung ist in `docs/DECISIONS.md` dokumentiert.

### Rohdaten bereit, Methodik noch verifizieren

- Eigenkapitalrendite (ROE) — Kindle S. 94
- Umsatzrendite — Kindle S. 101
- Kapitalumschlag — Kindle S. 107
- Gesamtkapitalrendite — Kindle S. 109
- ROCE — Kindle S. 111
- Umsatzverdienstrate — Kindle S. 114

### Daten blockiert

- EBITDA-Marge — `depreciation_amortization` ist im ASML-Gate gesperrt.

## Lokaler Abnahmeschritt

Nach `git pull`:

1. `pytest -q`
2. `streamlit run app.py`
3. Seite `Kennzahlen` öffnen.
4. bestehende ASML-Analyse auswählen.
5. `Kennzahlen aus Snapshot berechnen` klicken — **0 API-Requests**.
6. prüfen, dass eine 10-Jahres-EBIT-Margen-Historie erscheint.
7. aktuellen 2025-Wert auf ungefähr 34,6 % plausibilisieren.
8. prüfen, dass methodisch offene Kennzahlen nicht berechnet werden.

## Noch NICHT tun

- keine offenen Schmidlin-Formeln eigenmächtig festlegen
- keine EBITDA-Marge mit blockiertem D&A
- keine Working-Capital-Kennzahlen aus gesperrten Forderungs-/Vorratsfeldern
- keine FCF-/Owner-Earnings-/DCF-Logik aus blockiertem OCF/CAPEX
- keine Fair-KGV-Punkte oder Risikoaufschläge erfinden

## Nächster fachlicher Input

Für die restlichen Phase-3A-Kennzahlen werden die relevanten Buchseiten benötigt, insbesondere Kindle S. 94, 101, 107, 109, 111 und 114. Es reichen Screenshots der jeweiligen Formel-/Definitionsabschnitte; keine langen Buchpassagen übernehmen.

## Definition of Done Phase 3A erster Block

- lokale Tests bestehen.
- EBIT-Marge wird reproduzierbar aus gespeicherten Rohdaten berechnet und als `MetricSnapshot` gespeichert.
- 10-Jahres-UI funktioniert.
- abgeschlossene Analysen können die Kennzahl nicht neu überschreiben.
- methodisch offene oder datenblockierte Kennzahlen bleiben sichtbar gesperrt.

Danach werden die Buchdefinitionen schrittweise freigegeben und die restlichen Kapitel-2-Kennzahlen ergänzt.
