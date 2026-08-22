# ASML – Datenmapping für Phase 2

## Zweck

ASML ist das Referenzunternehmen für die Datenpipeline. Bevor die Kennzahlenengine gebaut wird, wird jeder benötigte interne Rohdatenwert einer automatischen Providerquelle und einer Primärquelle zur Validierung zugeordnet.

**Primärlisting für die spätere Marktpreisbewertung:** Euronext Amsterdam  
**Unternehmen:** ASML Holding N.V.  
**Bewertungswährung:** EUR  
**Alpha-Vantage-Fundamentals-Symbol:** `ASML`

Wichtig: Provider-Symbole für Kursdaten und Fundamentaldaten dürfen unterschiedlich sein. `ASML.AMS` lieferte im Live-Test keine Fundamentals-Reports; `ASML` liefert die konsolidierten ASML-Holding-Abschlüsse in EUR.

## Quellenhierarchie

Für veröffentlichte historische Zahlen gilt:

1. **ASML Annual Report / offizielle Financial Statements**
2. **für das konkrete Feld validierter automatischer Provider**
3. optionaler zweiter Provider als Cross-Check
4. **Aktienfinder** als manuelle Ergänzung

Für Prognosen gilt:

1. **Management Guidance** separat
2. **Analystenkonsens Low / Average / High** separat
3. eigene Annahme / Override

Aktueller Live-Provider-Kandidat ist Alpha Vantage. EODHD bleibt als integrierter optionaler Fallback erhalten, ist mit dem getesteten Free-Tarif für Fundamentals jedoch gesperrt.

---

## 1. Live-Status

### Alpha Vantage

Erfolgreich getestet:

- `ASML` -> 20 Jahresberichte
- `ASML` -> 81 Quartalsberichte
- Berichtswährung EUR
- 2025 `totalRevenue` = 32,6673 Mrd. EUR
- vollständiger lokaler Snapshot-Import: 720 Financial-Fact-Zeilen über 20 Geschäftsjahre

Noch offen:

- semantische Feldabweichungen vollständig bereinigen
- kritische Felder müssen den ASML-Primärquellen-Gate bestehen

### EODHD

- `ASML.AS` mit gültigem Free-Key getestet
- Fundamentals v1.1 -> HTTP 403
- kein bezahlter Tarif wird für die Entwicklung vorausgesetzt

---

## 2. GuV – Alpha Vantage

Endpoint: `INCOME_STATEMENT`

| Internal key | Alpha-Vantage-Feld | ASML Primärquellen-Check | Status/Policy |
|---|---|---|---|
| `revenue` | `totalRevenue` | Total net sales | validieren; 2025 bereits exakter Treffer |
| `cost_of_revenue` | `costOfRevenue` | Total cost of sales | validieren |
| `gross_profit` | `grossProfit` | Gross profit | validieren |
| `operating_income` | `operatingIncome` | Income from operations | zentrale EBIT-nahe operative Größe |
| `ebit` | `ebit` | gegen Income from operations / EBIT-Definition prüfen | Providerwert nicht blind mit operating income gleichsetzen |
| `ebitda` | `ebitda` | intern zusätzlich aus EBIT + D&A plausibilisieren | Cross-Check |
| `pretax_income` | `incomeBeforeTax` | Income before income taxes | validieren |
| `income_tax_expense` | `incomeTaxExpense` | Income tax expense | Vorzeichen prüfen |
| `net_income` | `netIncome` | Net income | validieren |
| `interest_expense` | `interestExpense` | Interest/finance notes | Definition prüfen |
| `research_and_development` | `researchAndDevelopment` | R&D costs | validieren |

### US-GAAP-Kontrollwerte 2025

- Revenue: 32,6673 Mrd. EUR
- Cost of sales: 15,4093 Mrd. EUR
- Gross profit: 17,2580 Mrd. EUR
- R&D: 4,6988 Mrd. EUR
- Income from operations: 11,3014 Mrd. EUR
- Income before taxes: 11,4061 Mrd. EUR
- Net income: 9,6094 Mrd. EUR

Die vollständigen 2025/2024 Kontrollwerte stehen maschinenlesbar in `src/stock_valuation/validation/asml_reference.py`.

---

## 3. Bilanz – Alpha Vantage

Endpoint: `BALANCE_SHEET`

| Internal key | Alpha-Vantage-Feld | Primärquellen-Check | Status/Policy |
|---|---|---|---|
| `total_assets` | `totalAssets` | Total assets | validieren |
| `current_assets` | `totalCurrentAssets` | Total current assets | validieren |
| `cash_and_equivalents` | `cashAndCashEquivalentsAtCarryingValue` | Cash and cash equivalents | primäres Cash-Feld |
| `short_term_investments` | `shortTermInvestments` | Short-term investments | separat halten |
| `cash_and_short_term_investments` | `cashAndShortTermInvestments` | Summe Cash + ST investments | nur Cross-Check; Komponenten bevorzugen |
| `inventory` | `inventory` | Inventories, net | validieren |
| `current_assets` | `totalCurrentAssets` | Current assets | validieren |
| `ppe_net` | `propertyPlantEquipment` | PP&E net | validieren |
| `intangible_assets` | `intangibleAssets` | Intangibles | Goodwill-Überlappung beachten |
| `goodwill` | `goodwill` | Goodwill | validieren |
| `total_liabilities` | `totalLiabilities` | Total liabilities | validieren |
| `current_liabilities` | `totalCurrentLiabilities` | Total current liabilities | validieren |
| `accounts_payable` | `currentAccountsPayable` | Accounts payable | validieren; 2025 bereits exakter Treffer |
| `short_term_debt` | `shortTermDebt` | reine Short-term borrowings | nicht mit gesamtem Current Debt verwechseln |
| `current_debt` | `currentDebt` | Short-term borrowings + current portion long-term debt | für spätere Debt-Bridge semantisch passender |
| `long_term_debt` | `longTermDebt` | Long-term debt | validieren |
| `shareholders_equity` | `totalShareholderEquity` | Total shareholders' equity | validieren |

### `accounts_receivable` – wichtiger Sonderfall

Das bisherige Alpha-Vantage-Mapping verwendet `currentNetReceivables`.

Alpha Vantage definiert `currentNetReceivables` als **Receivables, Net, Current, Total**. Dieses Feld umfasst neben Trade Accounts Receivable ausdrücklich auch Notes, Loans und weitere kurzfristige Forderungen.

Damit ist es **nicht semantisch identisch** mit ASML `Accounts receivable, net` und darf nicht ungeprüft als `accounts_receivable` für DSO/Working Capital verwendet werden.

Erster lokaler 2025-Vergleich:
- Alpha `currentNetReceivables`: ca. 4,1642 Mrd. EUR
- ASML `Accounts receivable, net`: 3,0230 Mrd. EUR

Folge: Das Feld bleibt bis zur gezielten Mappingkorrektur für DSO/Working Capital gesperrt. Wenn Alpha kein engeres Trade-Receivables-Feld liefert, kommt dieser Rohwert aus ASML Primärquelle/manueller strukturierter Ergänzung oder einem anderen Provider.

### Debt-Semantik

Alpha dokumentiert:
- `shortTermDebt` = Short-term borrowings mit ursprünglicher kurzer Laufzeit
- `currentDebt` = gesamte Current Debt inklusive current maturities of long-term debt
- `longTermDebt` = Long-term debt total

Die spätere Net-Debt-/EV-Bridge muss diese Komponenten explizit definieren; `shortTermDebt` allein reicht nicht.

---

## 4. Cashflow – Alpha Vantage

Endpoint: `CASH_FLOW`

| Internal key | Alpha-Vantage-Feld | Primärquellen-Check | Policy |
|---|---|---|---|
| `operating_cash_flow` | `operatingCashflow` | Net cash provided by operating activities | Pflicht |
| `depreciation_amortization` | `depreciationDepletionAndAmortization` | D&A cashflow reconciliation | validieren |
| `capital_expenditures` | `capitalExpenditures` | ASML PP&E / PP&E+intangibles | semantisch prüfen, nicht blind DCF-CAPEX |
| `dividends_paid` | `dividendPayout` | Dividend paid | validieren |
| `share_repurchases` | `paymentsForRepurchaseOfCommonStock` | Share buyback cash flow | validieren |
| `change_in_operating_assets` | `changeInOperatingAssets` | Cashflow reconciliation | optional/cross-check |
| `change_in_operating_liabilities` | `changeInOperatingLiabilities` | Cashflow reconciliation | optional/cross-check |

### `capitalExpenditures` – wichtiger Sonderfall

Alpha Vantage dokumentiert dieses Feld als `PaymentsToAcquireProductiveAssets`: Cash outflows für PP&E, Software und weitere immaterielle produktive Assets.

ASML US GAAP 2025:
- PP&E purchases: 1,5736 Mrd. EUR
- intangible purchases: 0,0576 Mrd. EUR
- PP&E + intangible purchases: 1,6312 Mrd. EUR

Erster Alpha-Vantage-Wert: ca. 1,5115 Mrd. EUR.

Der Providerwert entspricht keiner offiziellen ASML-Größe exakt. Er darf daher noch nicht als `capex_ppe` oder `capex_total` in FCF/Owner Earnings eingehen. Die DCF-CAPEX-Policy bleibt ein eigener fachlicher Schritt.

---

## 5. Primärquellen-Gate

Implementiert in:

- `src/stock_valuation/validation/asml_reference.py`
- `src/stock_valuation/validation/service.py`
- Streamlit `Datenimport -> ASML Primärquellen-Validierung`

Regeln:

- <= 0,5 % Abweichung -> PASS
- > 0,5 % bis 2 % -> WARN
- > 2 % -> FAIL
- kein Providerwert -> MISSING

Kritische FAIL/MISSING-Felder blockieren die Freigabe dieses Provider-Mappings. Cross-Check-Felder blockieren nicht automatisch.

Kontrollwerte werden niemals als stille Ersatzdaten in den Snapshot geschrieben.

---

## 6. Analystenschätzungen

Endpoint: `EARNINGS_ESTIMATES`

Alpha Vantage liefert annual/quarterly EPS- und Revenue-Schätzungen sowie Analystenzahl und Revisionshistorie.

Gespeichert werden:

- EPS Low / Average / High
- Revenue Low / Average / High
- Analyst Count
- Provider
- Abrufzeit
- Periodenlabel

Der Provider liefert auch lange historische Estimate-/Revisionsreihen. Diese bleiben im Snapshot erhalten, werden in der normalen UI aber standardmäßig ausgeblendet, wenn die Periode vor dem Analyse-Stichtag liegt.

Für die DCF-Verwendung wird später zusätzlich eindeutig zwischen annual und quarterly/horizon unterschieden. Bis dahin werden historische Estimate-Reihen nicht als Zukunftsforecast interpretiert.

---

## 7. Management Guidance für ASML

Guidance wird **nicht** als Analystenschätzung gespeichert.

Offizielle Referenzbeispiele:

- 2026 Total net sales: 34–39 Mrd. EUR
- 2026 Gross margin: 51–53 %
- 2030 Revenue Opportunity: ca. 44–60 Mrd. EUR
- 2030 Gross margin opportunity: ca. 56–60 %

Diese Korridore sind Evidenz für Szenarien, keine automatisch erzwungenen DCF-Annahmen.

---

## 8. Unternehmensspezifische ASML-Daten

Optionale `operating facts`:

- Net system sales
- Net service and field option sales
- Logic / Memory sales
- bookings / order intake
- backlog
- System-/Technologie-Mix
- Installed-base-bezogene Informationen
- R&D

Diese Daten sind nicht Teil des universellen Industrie-Rohdatenschemas.

---

## 9. Phase-2-Akzeptanzkriterien für ASML

Phase 2 gilt für die automatische ASML-Datenbasis erst dann als ausreichend validiert, wenn:

- mindestens zehn Jahresperioden verfügbar sind,
- GuV, Bilanz und Cashflow eindeutig den Perioden zugeordnet sind,
- Kernfelder gegen ASML 2025/2024 geprüft sind,
- semantisch breitere Providerfelder nicht unter zu engen internen Namen geführt werden,
- Debt-Komponenten explizit definiert sind,
- CAPEX-Basis vor DCF/FCF geklärt ist,
- Estimates und Guidance getrennt gespeichert werden,
- jede Zahl Providerfeld, Originalwert und Abrufzeit besitzt,
- kein fertiger Provider-ROE/ROCE ungeprüft in die Kennzahlenengine gelangt.

## Quellen

- Alpha Vantage API: `https://www.alphavantage.co/documentation/`
- Alpha Vantage Fundamental field definitions: `https://documentation.alphavantage.co/FundamentalDataDocs/index.html`
- ASML Annual Report 2025 US GAAP: `https://ourbrand.asml.com/m/71076aaad607de4d/original/asml-2025-annual-report-based-on-us-gaap.pdf`
- ASML Annual Report 2025 Downloads: `https://www.asml.com/en/investors/annual-report/2025/downloads`
- EODHD Fundamentals API (optional fallback): `https://eodhd.com/financial-apis/stock-etfs-fundamental-data-feeds`
