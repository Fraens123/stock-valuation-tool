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

**Entscheidung:** `depreciation_amortization` wird bei Alpha Vantage aus `INCOME_STATEMENT.depreciationAndAmortization` normalisiert. Das Cashflow-Feld wird als `depreciation_amortization_cashflow_crosscheck` getrennt gespeichert. Die lokale Prüfung bestätigt danach ein freigegebenes D&A-Gate und eine 2025 EBITDA-Marge von ca. 37,74 %.

## Cash-Komponenten

Das Provider-Aggregat `cashAndShortTermInvestments` wird **nicht** als Quelle für die Cash-Brücke verwendet.

Die getrennten Komponenten sind dagegen brauchbar:

- `cashAndCashEquivalentsAtCarryingValue`
  - wird separat gegen `cash_and_equivalents` geprüft.
- `shortTermInvestments`
  - 2025 Alpha Vantage ca. `405.7 Mio. EUR`; offizieller Komponentenwert ca. `405.9 Mio. EUR`.
  - 2024 Alpha Vantage `5.4 Mio. EUR`; offizieller Komponentenwert `5.4 Mio. EUR`.

**Entscheidung:** Cash + Short-Term Investments wird später intern aus den freigegebenen Komponenten gebildet. Das fertige Provider-Aggregat bleibt Cross-Check und darf die Komponenten nicht überschreiben.

## Cashflow-Statement: systematisches Skalierungsmuster

Die lokale Rohfelddiagnose zeigt ein starkes Statement-weites Muster. Mehrere voneinander unabhängige Cashflow-Zeilen weichen innerhalb desselben Jahres nahezu mit **demselben Faktor** vom offiziellen ASML-US-GAAP-Wert ab:

### 2025

- Operating Cash Flow: Alpha Vantage / ASML ≈ `0.960532`
- PP&E CAPEX: Alpha Vantage / ASML ≈ `0.960536`
- Dividenden: Alpha Vantage / ASML ≈ `0.960514`

Das entspricht jeweils ungefähr `-3.95 %`.

### 2024

- Operating Cash Flow: Alpha Vantage / ASML ≈ `1.044590`
- PP&E CAPEX: Alpha Vantage / ASML ≈ `1.044601`
- Dividenden: Alpha Vantage / ASML ≈ `1.044600`

Das entspricht jeweils ungefähr `+4.46 %`.

**Bewertung:** Das ist starke Evidenz für ein Provider-/Normalisierungsproblem auf Statement-Ebene und nicht für zufällig unabhängige Abweichungen einzelner Cashflow-Zeilen. Ein rechnerischer Korrekturfaktor ist ausdrücklich **nicht zulässig**, weil Ursache und historische Stabilität nicht bewiesen sind.

**Entscheidung:** Für ASML werden Alpha-Vantage-Cashflow-Zeilen wie OCF, CAPEX und Dividenden als Fallback-/Auditwerte behandelt, nicht als maßgebliche 2024/2025-Datenbasis.

## Offizielle ASML-US-GAAP-Excel als Primärquelle

Offizielle 2025 US-GAAP Financial Statements Excel:
`https://ourbrand.asml.com/m/6cd86f972a9dfd24/original/2025-US-GAAP-Financial-Statements.xlsx`

Der lokale Workbook-Scan bestätigt eindeutige Zeilen in `Balance Sheets` und `Cash Flow`.

Der deterministische Import verwendet für 2024/2025:

### Balance Sheets
- `Cash and cash equivalents`
- `Short-term investments`
- `Accounts receivable, net`
- `Inventories, net`
- `Property, plant and equipment, net`
- `Short-term borrowings and current portion of long-term debt`

### Cash Flow
- `Net cash provided by operating activities`
- `Purchase of property, plant and equipment`
- `Purchase of intangible assets`
- `Dividend paid`

Die importierten Werte werden unter `provider=asml_primary` und `source_type=primary_source` separat im Snapshot gespeichert. Alpha-Vantage-Zeilen bleiben erhalten.

### Quellenpriorität

Für dasselbe interne Feld und dasselbe Geschäftsjahr gilt im Resolver:

1. `asml_primary`
2. `alphavantage`
3. `eodhd`

Der Daten-Gate und die Kennzahlenengine verwenden dieselbe zentrale Source-Resolution. Ein offizieller ASML-Fakt kann somit ein zuvor wegen Alpha Vantage blockiertes 2024/2025-Feld freigeben, ohne den abweichenden API-Wert zu löschen.

## Problematische Alpha-Vantage-Bilanzfelder

### `accounts_receivable`

Alpha-Vantage-Feld: `currentNetReceivables`.

Beobachtung:
- 2025 Provider ca. `4,164.2 Mio. EUR`
- ASML Accounts receivable, net `3,023.0 Mio. EUR`
- 2024 Provider ca. `5,443.3 Mio. EUR`
- ASML Accounts receivable, net `4,477.5 Mio. EUR`

Bewertung als Alpha-Vantage-Feld: **blocked**. Nach Primärquellenimport wird für 2024/2025 stattdessen die offizielle Bilanzzeile verwendet.

### `inventory`

- 2025 Alpha Vantage ca. `11,424.4 Mio. EUR`; ASML `11,429.3 Mio. EUR`.
- 2024 Alpha Vantage ca. `11,707.1 Mio. EUR`; ASML `10,891.5 Mio. EUR`.

Bewertung als Alpha-Vantage-Feld: **blocked**. Offizielle 2024/2025-Bilanzzeilen stehen im Primärquellenimport zur Verfügung.

### `ppe_net`

Providerfeld `propertyPlantEquipment` war im ASML-Live-Payload für 2024/2025 `None`.

Bewertung als Alpha-Vantage-Feld: **blocked / missing**. Die offizielle Bilanzzeile wird importiert.

### `short_term_debt`

- 2025 `currentDebt` und `shortTermDebt` fehlen.
- 2024 `shortTermDebt` liegt bei ca. `1,078.9 Mio. EUR` gegenüber offiziell `1,010.3 Mio. EUR`.

Bewertung als Alpha-Vantage-Feld: **blocked**. Für 2024/2025 steht die offizielle Bilanzzeile im Primärquellenimport zur Verfügung. Die endgültige Net-Debt-/EV-Brücke bleibt dennoch eine separate Methodikentscheidung.

## Konsequenz für Phase 3

Phase 3 darf feldweise fortgesetzt werden.

- EBIT-Marge ist aktiv.
- EBITDA-Marge ist aktiv.
- ROE, Umsatzrendite, Kapitalumschlag, Gesamtkapitalrendite, ROCE und Umsatzverdienstrate warten weiterhin auf die jeweilige Buchdefinition.
- Die 2024/2025-Datenbasis für Forderungen, Vorräte, PP&E, kurzfristige Schulden, OCF, CAPEX und Dividenden kann über die offizielle ASML-Primärquelle hergestellt werden.
- Working-Capital- und DCF-**Historien** bleiben so lange eingeschränkt, bis eine ausreichende Primärquellen-/validierte Providerhistorie für ältere Jahre vorliegt.

## Architekturentscheidung

Die Datenpipeline bleibt providerunabhängig und revisionssicher. Primärquelle und Drittanbieter werden parallel gespeichert. Downstream-Logik fragt nicht mehr direkt „Alpha Vantage“ ab, sondern nutzt den zentralen Source Resolver. Dadurch können später weitere offizielle Jahresdateien oder alternative Provider ergänzt werden, ohne Kennzahlenformeln umzuschreiben.
