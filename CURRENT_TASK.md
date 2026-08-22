# Current Task

## Phase 2.2 – ASML Primärquellen-Gate und Provider-Mapping bereinigen

Phase 0 ist implementiert. Phase 1 ist fachlich ausreichend spezifiziert. Die Datenpipeline wurde lokal mit echten API-Keys getestet.

## Aktueller Live-Stand

### EODHD

- Free-Key gültig.
- `ASML.AS` Fundamentals v1.1 liefert HTTP 403, weil der getestete Free-Tarif Fundamentals nicht freischaltet.
- Adapter bleibt erhalten, ist aber derzeit **nicht V1-Livequelle**.

### Alpha Vantage

- Free-Key gültig.
- `ASML.AMS` liefert beim Fundamentals-Endpoint 0 Reports.
- `ASML` liefert konsolidierte ASML-Holding-Abschlüsse in EUR.
- Lokaler Nutzer-Test: 20 Jahresberichte, 81 Quartalsberichte.
- Vollimport erfolgreich: 720 Financial-Fact-Datenpunkte über 20 Geschäftsjahre.
- Estimate-Historie wurde ebenfalls importiert.

Alpha Vantage ist damit **V1-Kandidat**, aber erst nach Primärquellenprüfung freizugeben.

## Vor Beginn lesen

1. `AGENTS.md`
2. `ROADMAP.md`
3. `docs/RAW_DATA_SCHEMA.md`
4. `docs/ASML_DATA_MAPPING.md`
5. `docs/ASML_PROVIDER_VALIDATION.md`
6. `docs/NORMALIZATION_POLICY.md`
7. `docs/DATA_SOURCES.md`
8. `src/stock_valuation/validation/asml_reference.py`
9. `src/stock_valuation/validation/service.py`
10. `src/stock_valuation/data/normalization_alphavantage.py`

## Bereits implementiert

- Alpha-Vantage-Adapter mit Free-Tier-Pacing
- 1-Request-Diagnosetest
- Alpha-Vantage-Normalisierung für GuV/Bilanz/Cashflow/Estimates
- Snapshot-Persistenz
- EODHD-Zugriffsfehler als verständliche Providerfehlermeldung
- ASML-US-GAAP-Referenzwerte 2025/2024
- automatisches Primärquellen-Gate mit PASS/WARN/FAIL/MISSING
- Streamlit-Validierungstabelle
- historische Analystenschätzungen bleiben gespeichert, werden aber standardmäßig aus der normalen Ansicht ausgeblendet
- Tests für Validierung und Estimate-Filter

## Jetzt lokal prüfen

Nach `git pull` und `pytest -q`:

1. Bestehende ASML-Analyse öffnen. **Kein neuer API-Import nötig.**
2. `Datenimport` öffnen.
3. Abschnitt `ASML Primärquellen-Validierung` prüfen.
4. PASS/WARN/FAIL/MISSING-Ausgabe erfassen.
5. Besonders prüfen:
   - `accounts_receivable`
   - `capital_expenditures`
   - `cash_and_short_term_investments`
   - Debt-Felder
   - D&A
   - Inventory
6. Problemfelder anhand der Providersemantik und ASML-US-GAAP-Primärquelle neu mappen oder explizit als nicht belastbar markieren.

## Gate-Regel

Phase 3 darf für eine konkrete Kennzahl nur validierte Rohdaten verwenden.

- <= 0,5 % Abweichung: PASS
- > 0,5 % bis 2 %: WARN
- > 2 %: FAIL
- kein Wert: MISSING

Cross-Check-only-Felder blockieren den Provider nicht automatisch.

## Noch NICHT tun

- keine Kennzahlenengine auf ungeprüfte Felder loslassen
- keine DCF-Engine
- keine Fair-KGV-Punkte erfinden
- keine Risiko-Dropdown-Prozentwerte festlegen
- keine fehlenden Providerwerte mit ASML-Referenzwerten automatisch auffüllen

## Definition of Done dieses Blocks

- ASML 2025/2024 Kernfelder gegen US GAAP automatisch geprüft.
- alle kritischen FAIL/MISSING-Felder fachlich geklärt oder aus der automatischen Datenbasis ausgeschlossen.
- Providerfeld-Semantik dokumentiert.
- Alpha Vantage entweder für definierte Rohdatenfelder freigegeben oder durch eine bessere Quelle ersetzt.
- Estimate-Ansicht zeigt standardmäßig keine veralteten historischen Perioden.

Danach kann Phase 3A mit den ersten **validierten** Ertrags-/Rentabilitätskennzahlen beginnen.
