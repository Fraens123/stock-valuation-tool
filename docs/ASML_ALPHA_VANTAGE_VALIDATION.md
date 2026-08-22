# ASML – Alpha-Vantage-Validierung

## Zweck

Dieses Dokument hält die Ergebnisse der Primärquellenprüfung für den ASML-Referenzfall fest. Es ist **keine** Bewertungsmethodik, sondern ein Datenqualitätsprotokoll.

Primärquelle: ASML Annual Report 2025 based on US GAAP / offizielle Financial Statements.

Automatischer Provider: Alpha Vantage, Fundamentals-Symbol `ASML`.

## Grundentscheidung

Alpha Vantage wird **nicht pauschal als vollständig vertrauenswürdiger Fundamentals-Provider freigegeben**. Stattdessen wird jedes interne Rohdatenfeld separat validiert.

Feld-Gate:
- `approved`: alle vorhandenen Primärquellenchecks PASS
- `review`: mindestens WARN, aber kein FAIL/MISSING
- `blocked`: mindestens ein FAIL oder MISSING

Ein grünes Jahr darf ein problematisches zweites Jahr nicht verdecken.

## Bestätigte Beobachtungen aus dem lokalen Live-Import

Der lokale Import lieferte für ASML:
- 20 Jahresberichte
- 81 Quartalsberichte beim Income-Statement-Probe
- Berichtswährung EUR
- 2025 Revenue `32,667.3 Mio. EUR`, exakt im Einklang mit ASML US GAAP
- insgesamt 720 normalisierte jährliche Datenpunkte im ersten Snapshot

## Freigegebene D&A-Definition

Die gezielte Rohfelddiagnose am 22.08.2026 zeigte:

- `INCOME_STATEMENT.depreciationAndAmortization`
  - 2025: `1,025.9 Mio. EUR`
  - 2024: `918.6 Mio. EUR`
  - beide Werte stimmen exakt mit den ASML-US-GAAP-Kontrollwerten überein.

- `CASH_FLOW.depreciationDepletionAndAmortization`
  - 2025: `1,025.9 Mio. EUR`
  - 2024: ca. `1,030.8 Mio. EUR`
  - 2024 weicht deutlich ab und wird deshalb nur als Cross-Check-Feld geführt.

**Entscheidung:** `depreciation_amortization` wird bei Alpha Vantage aus `INCOME_STATEMENT.depreciationAndAmortization` normalisiert. Das Cashflow-Feld wird als `depreciation_amortization_cashflow_crosscheck` getrennt gespeichert. Damit kann die EBITDA-Marge nach Aktualisierung der D&A-Serie feldweise freigegeben werden.

## Problematische Felder

### `accounts_receivable`

Alpha-Vantage-Feld: `currentNetReceivables`.

Beobachtung:
- 2025 Provider ca. `4,164.2 Mio. EUR`
- ASML Accounts receivable, net `3,023.0 Mio. EUR`
- 2024 Provider ca. `5,443.3 Mio. EUR`
- ASML Accounts receivable, net `4,477.5 Mio. EUR`

Bewertung: **blocked**.

`currentNetReceivables` ist semantisch breiter als reine Trade/Accounts Receivable. Das Feld darf nicht für DSO oder andere Working-Capital-Kennzahlen verwendet werden, solange kein engeres Primärquellen-/Providerfeld vorhanden ist.

### `capital_expenditures`

Beobachtung:
- 2025 Provider ca. `1,511.5 Mio. EUR`; ASML PP&E purchases `1,573.6 Mio. EUR`
- 2024 Provider ca. `2,159.4 Mio. EUR`; ASML PP&E purchases `2,067.2 Mio. EUR`

Bewertung: **blocked**.

Die Alpha-Vantage-Definition ist nicht hinreichend identisch mit dem für ASML benötigten PP&E-CAPEX. Für FCF/Owner Earnings wird später die explizite Primärquellen-Aufteilung in `capex_ppe` und `capex_intangibles` bevorzugt.

### `operating_cash_flow`

Beobachtung:
- 2025 Provider ca. `12,158.9 Mio. EUR`; ASML US GAAP `12,658.5 Mio. EUR`
- 2024 Provider ca. `11,664.1 Mio. EUR`; ASML US GAAP `11,166.2 Mio. EUR`

Bewertung: **blocked**.

Die Abweichung ist zu groß für Rundung und tritt in beiden Jahren mit wechselnder Richtung auf. Für DCF/FCF darf dieser Providerwert bei ASML vorerst nicht verwendet werden.

### `inventory`

2024 zeigte eine deutliche Abweichung, obwohl 2025 plausibler sein kann. Bewertung: **blocked**, weil der Feld-Gate beide Jahre berücksichtigt.

### `ppe_net`

Providerfeld war im ASML-Live-Snapshot für 2024/2025 `None`. Bewertung: **blocked / missing**.

### `short_term_debt`

Mindestens ein Referenzjahr ist missing bzw. weicht ab. Das Feld bleibt für Net-Debt-/EV-Berechnungen gesperrt, bis die Debt-Bridge aus geeigneten Einzelpositionen aufgebaut wird.

## Cash und Short-Term Investments

`cashAndShortTermInvestments` weicht vom offiziellen Komponentenwert ab. Das Feld ist bereits als Cross-Check zu behandeln. Für Net Debt / EV sollen die offiziellen bzw. validierten Komponenten `cash_and_equivalents` und `short_term_investments` verwendet werden.

## Konsequenz für Phase 3

Phase 3 darf **feldweise** beginnen.

Zulässig sind Kennzahlen nur dann, wenn alle dafür benötigten Rohdatenfelder den Feld-Gate `approved` besitzen und die jeweilige Formel fachlich bereits festgelegt ist.

- EBIT-Marge ist aktiv.
- EBITDA-Marge ist methodisch freigegeben und wird nach Aktualisierung der D&A-Serie aus dem validierten Income-Statement-Feld aktiv.
- ROE, Umsatzrendite, Kapitalumschlag, Gesamtkapitalrendite, ROCE und Umsatzverdienstrate warten weiterhin auf die jeweilige Buchdefinition.
- Working-Capital-Kennzahlen bleiben blockiert, solange Accounts Receivable / Inventory nicht sauber validiert sind.
- DCF/FCF bleibt blockiert, solange OCF und CAPEX nicht sauber aus Primärquellen oder einem besser passenden Provider stammen.

## Architekturentscheidung

Die Datenpipeline bleibt providerunabhängig. Für einzelne problematische Felder können später Primärquellenadapter oder alternative Provider eingesetzt werden, ohne die Kennzahlenengine neu zu definieren.
