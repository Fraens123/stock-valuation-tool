# Current Task

## Phase 2.2 – Feldweise ASML-Datenfreigabe und Vorbereitung Phase 3A

Der erste echte lokale ASML-Import ist erfolgreich gelaufen.

### Verifizierter Live-Stand

- Alpha-Vantage-Free-Key funktioniert.
- Fundamentals-Symbol `ASML` liefert konsolidierte ASML-Holding-Abschlüsse in EUR.
- `ASML.AMS` lieferte beim Fundamentals-Probe keine Statements und wird dafür nicht verwendet.
- Probe: 20 Jahresberichte, 81 Quartalsberichte.
- erster Snapshot: 720 normalisierte jährliche Rohdatenpunkte.
- EODHD-Free-Key bleibt für Fundamentals gesperrt (`403 Forbidden`).
- Primärquellencheck 2024/2025 gegen ASML US GAAP ist implementiert.
- mehrere Felder bestehen exakt/nahezu exakt; andere Felder sind nachweislich ungeeignet oder missing.

Siehe `docs/ASML_ALPHA_VANTAGE_VALIDATION.md`.

## Verbindliche Regel

Alpha Vantage wird nicht pauschal freigegeben. Jedes interne Rohdatenfeld erhält einen Feld-Gate:

- `approved`: alle vorhandenen Primärquellenchecks PASS
- `review`: WARN, aber kein FAIL/MISSING
- `blocked`: mindestens ein FAIL oder MISSING

Downstream-Kennzahlen dürfen nur auf fachlich freigegebenen Rohdatenfeldern aufbauen.

## Vor Beginn lesen

1. `AGENTS.md`
2. `ROADMAP.md`
3. `docs/RAW_DATA_SCHEMA.md`
4. `docs/ASML_DATA_MAPPING.md`
5. `docs/ASML_ALPHA_VANTAGE_VALIDATION.md`
6. `docs/NORMALIZATION_POLICY.md`
7. `docs/METHODOLOGY_OPEN_QUESTIONS.md`
8. `src/stock_valuation/validation/service.py`

## Aktueller Arbeitsblock

### A. Feld-Gates stabilisieren

- Feldfreigabe aus 2024/2025-Checks anzeigen.
- Ein FAIL/MISSING sperrt das Feld auch dann, wenn das andere Jahr PASS ist.
- problematische Felder nicht still ersetzen.
- `accounts_receivable`, `inventory`, `ppe_net`, `short_term_debt`, `operating_cash_flow`, `capital_expenditures` und `depreciation_amortization` bleiben bis zur Klärung blockiert.

### B. Phase-3A-Datenbereitschaft

Automatisch anzeigen, welche Kennzahlen bereits eine freigegebene Rohdatenbasis besitzen:

- Eigenkapitalrendite
- Umsatzrendite
- EBIT-Marge
- Kapitalumschlag
- ROCE-Datenbasis
- EBITDA-Marge-Datenbasis

Dies ist nur ein Daten-Gate. Offene Buchdefinitionen bleiben separat blockierend.

### C. Nächster Implementierungsschritt

Wenn die lokalen Feld-Gates bestätigen, dass `revenue`, `net_income`, `operating_income`, `total_assets`, `shareholders_equity` und ggf. `current_liabilities` approved sind:

1. Phase 3A mit den eindeutig möglichen Kennzahlen beginnen.
2. noch gesperrte Kennzahlen sichtbar als `nicht berechenbar / Datenbasis nicht freigegeben` darstellen.
3. keine Ersatzwerte aus offiziellen ASML-Kontrollzahlen in die normale Providerhistorie schreiben.

## Noch NICHT tun

- keine DCF-Engine
- keine FCF-/Owner-Earnings-Berechnung aus blockiertem OCF/CAPEX
- keine Working-Capital-Kennzahlen aus `currentNetReceivables`
- keine Fair-KGV-Punkte erfinden
- keine offenen Schmidlin-Formeln eigenmächtig festlegen

## Definition of Done dieses Blocks

- lokale Seite `Datenqualität` zeigt Feld-Gates reproduzierbar.
- Phase-3A-Datenbereitschaft ist sichtbar.
- Tests für PASS/WARN/FAIL/MISSING-Gating bestehen.
- problematische ASML-Felder sind dokumentiert.
- danach kann Phase 3A feldweise beginnen.
