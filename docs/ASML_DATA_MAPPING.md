# ASML – Datenmapping für Phase 2

## Zweck

ASML ist das Referenzunternehmen für die Datenpipeline. Bevor die Kennzahlenengine gebaut wird, wird jeder benötigte interne Rohdatenwert einer Providerquelle und einer Primärquelle zur Validierung zugeordnet.

**Primärlisting:** `ASML.AS`  
**Unternehmen:** ASML Holding N.V.  
**Bewertungswährung:** EUR

## Quellenhierarchie

Für veröffentlichte historische Zahlen gilt:

1. **ASML Annual Report / offizielle Financial Statements**
2. **EODHD Fundamentals v1.1** als automatisierter Datenprovider
3. optionaler zweiter Provider als Cross-Check
4. **Aktienfinder** als manuelle Ergänzung, nicht als automatische Grundquelle

Für Prognosen gilt:

1. **Management Guidance** separat
2. **Analystenkonsens Low / Average / High** separat
3. eigene Annahme / Override

Die offizielle ASML-Downloadseite stellt sowohl US-GAAP- als auch IFRS-Geschäftsberichte sowie Financial-Statements-Exceldateien bereit. Für den Referenzfall werden diese Dateien als Kontrollquelle verwendet.

---

## 1. Unternehmensstammdaten

| Interner Schlüssel | EODHD v1.1 | ASML / Fallback | Ziel |
|---|---|---|---|
| `name` | `General::Name` | ASML IR | Stammdaten |
| `ticker` | `General::Code` | `ASML` | Stammdaten |
| `provider_symbol` | Request-Symbol | `ASML.AS` | Provider-ID |
| `isin` | `General::ISIN` | offizielle Unternehmensunterlagen | Identifikation |
| `exchange` | `General::Exchange` | Euronext Amsterdam | Listing |
| `currency` | `General::CurrencyCode` | EUR | Kurswährung |
| `country` | `General::CountryName` | Netherlands | Stammdaten |
| `sector` | `General::Sector` | optional manuell validieren | Klassifikation |
| `industry` | `General::Industry` | optional manuell validieren | Klassifikation |

Andere Listings/ADRs werden nicht mit dem Primärlisting vermischt. Mehrfachlistings erhalten später eine separate Listing-Entität.

---

## 2. GuV

Pfad EODHD: `Financials::Income_Statement::yearly` bzw. `quarterly`.

| Internal key | EODHD-Feld | Primärquellen-Check | Bemerkung |
|---|---|---|---|
| `revenue` | `totalRevenue` | ASML Total net sales | Pflicht |
| `cost_of_goods_sold` | `costOfRevenue` | Cost of sales | wichtig für DIO/DPO |
| `gross_profit` | `grossProfit` | Sales minus Cost of sales | Cross-Check |
| `operating_expenses` | `totalOperatingExpenses` | ASML GuV | nur Plausibilisierung; Providerdefinition prüfen |
| `ebit` | `ebit` bevorzugt, `operatingIncome` als Cross-Check | Income from operations | Pflicht |
| `ebitda` | `ebitda` | intern zusätzlich `EBIT + D&A` prüfen | fertigen Providerwert nicht blind verwenden |
| `interest_expense` | `interestExpense` | Finance costs / interest | Pflicht für Zinsdeckung / ROA |
| `income_before_tax` | `incomeBeforeTax` | Income before income taxes | Steueranalyse |
| `income_tax_expense` | `incomeTaxExpense` / `taxProvision` nach realem Payload prüfen | Income tax expense | nachhaltige Steuerquote |
| `net_income` | `netIncome` | Net income | Pflicht |
| `net_income_attributable` | `netIncomeApplicableToCommonShares` sofern vorhanden | Gewinn für Common Shareholders | Fallback `net_income` bei ASML prüfen |
| `diluted_eps` | Earnings/Income Statement je nach Payload | diluted EPS | Validierung gegen ASML EPS |
| `research_and_development` | `researchDevelopment` | R&D costs | für ASML qualitativ wichtig |

### ASML Kontrollwerte 2025

Die offizielle 2025-Berichterstattung nennt unter anderem:
- Total net sales: **€32.7 Mrd.**
- Gross margin: **52.8 %**
- R&D: **€4.7 Mrd.**
- Basic EPS: **€24.73**

Diese Werte dienen nicht als hart codierte Programmdaten, sondern als Plausibilitätsanker für den ersten Importtest.

---

## 3. Bilanz

Pfad EODHD: `Financials::Balance_Sheet::yearly` bzw. `quarterly`.

| Internal key | EODHD-Feld | Primärquellen-Check | Policy |
|---|---|---|---|
| `cash_and_short_term_investments` | `cashAndShortTermInvestments`, alternativ Komponenten | Cash and cash equivalents + short-term investments | Komponenten und Gesamtfeld gegeneinander prüfen |
| `accounts_receivable` | `netReceivables` | Current receivables / A/R | Pflicht WC |
| `inventory` | `inventory` | Inventories | Pflicht WC |
| `current_assets` | `totalCurrentAssets` | Current assets | Pflicht |
| `ppe_net` | `propertyPlantAndEquipmentNet` | Property, plant and equipment | Anlagenanalyse |
| `ppe_gross` | `propertyPlantAndEquipmentGross` | falls offiziell verfügbar | Anlagenabnutzung |
| `accumulated_depreciation` | `accumulatedDepreciation` | falls offiziell verfügbar | Anlagenabnutzung |
| `intangible_assets` | `intangibleAssets` | Intangible assets | Goodwill-Überlappung prüfen |
| `goodwill` | Providerfeld im realen Payload prüfen | Goodwill im Annual Report | niemals aus Intangibles schätzen |
| `non_current_assets` | `nonCurrentAssetsTotal` | Non-current assets | Anlagenintensität |
| `total_assets` | `totalAssets` | Total assets | Pflicht |
| `accounts_payable` | `accountsPayable` | Accounts payable | Pflicht WC |
| `current_liabilities` | `totalCurrentLiabilities` | Current liabilities | Pflicht |
| `short_term_debt` | `shortTermDebt` | Current debt | Net Debt |
| `long_term_debt` | `longTermDebtTotal` / `longTermDebt` | Non-current borrowings | Net Debt |
| `interest_bearing_debt` | intern normalisieren; EODHD `shortLongTermDebtTotal` als Cross-Check | offizielle Debt Notes | zentrale Debt-Policy |
| `long_term_liabilities` | `nonCurrentLiabilitiesTotal` | Non-current liabilities | Anlagendeckung II |
| `total_liabilities` | `totalLiab` | Total liabilities | ergänzende Kennzahlen |
| `total_equity` | `totalStockholderEquity` | Total shareholders' equity | Pflicht |

### Net-Debt-Regel

EODHD dokumentiert `netDebt` und `shortLongTermDebtTotal`. Für das Tool wird Net Debt trotzdem aus den normalisierten Einzelpositionen nachvollziehbar berechnet. Provider-`netDebt` ist ein Cross-Check, keine Blackbox-Grundlage.

---

## 4. Cashflow

Pfad EODHD: `Financials::Cash_Flow::yearly` bzw. `quarterly`.

| Internal key | EODHD-Feld | Primärquellen-Check | Policy |
|---|---|---|---|
| `operating_cash_flow` | `totalCashFromOperatingActivities` | Net cash provided by operating activities | Pflicht |
| `depreciation_amortization` | `depreciation`; zusätzlich IS `depreciationAndAmortization` | D&A / Cashflow reconciliation | Cross-Check |
| `capex_ppe` | `capitalExpenditures` | Purchases of PPE | Vorzeichen normalisieren |
| `capex_intangibles` | kein universell verlässliches Standardfeld | ASML Cashflow / Notes | bei Bedarf Primärquelle/manual |
| `capex_total` | intern aus definierter Policy | Primärquelle | DCF-relevante Definition |
| `change_in_working_capital_provider` | `changeInWorkingCapital` | Cashflow reconciliation | nur Cross-Check zur eigenen WC-Logik |
| `stock_based_compensation` | `stockBasedCompensation` | Notes / cashflow reconciliation | Non-cash analysis |
| `other_non_cash_items` | `otherNonCashItems` | Primärquelle | DCF-Prüfung |
| `dividends_paid` | `dividendsPaid` | Financing cash flow | Ausschüttung |
| `share_repurchases_net_cashflow` | `salePurchaseOfStock` | Share buyback disclosures | Vorzeichen/Issuance prüfen |
| `free_cash_flow_provider` | `freeCashFlow` | intern OCF - Capex gegenprüfen | Provider-FCF nur Cross-Check |

EODHD definiert `freeCashFlow` als Operating Cash Flow minus `capitalExpenditures`. Für das Tool wird die verwendete FCF-Definition explizit gespeichert, damit Analyse-FCF, Owner Earnings und später FCFF nicht vermischt werden.

---

## 5. Aktienzahl und Bewertung

| Internal key | EODHD | Primärquelle | Policy |
|---|---|---|---|
| `shares_outstanding_point_in_time` | `outstandingShares` / SharesStats | ASML share data | für historische Market Cap |
| `diluted_weighted_average_shares` | Income Statement / `commonStockSharesOutstanding` nur nach Prüfung | ASML EPS note | Fair Value je Aktie / EPS |
| `market_cap` | `Highlights::MarketCapitalization` als Cross-Check | selbst aus Kurs × passender Aktienzahl | intern rechnen |
| `market_price` | EOD-/Price API, nicht Fundamentals | Börsenkurs am Analyse-Stichtag | Snapshot speichern |

Stichtags-Aktienzahl und gewichtete durchschnittliche Aktienzahl sind unterschiedliche Größen und dürfen nicht austauschbar verwendet werden.

---

## 6. Analystenschätzungen

EODHD Fundamentals v1.1 enthält unter `Earnings::Trend` getrennte Annual-/Quarterly-Schätzungen. Erwartete Felder umfassen unter anderem:

- `earningsEstimateAvg`
- `earningsEstimateLow`
- `earningsEstimateHigh`
- `revenueEstimateAvg`
- EPS-Trend-/Revisionsdaten

Beim realen ASML-Payload wird geprüft, welche Revenue-Low/High- und Analyst-Count-Felder tatsächlich geliefert werden. Nicht vorhandene Felder werden nicht erfunden.

### DCF-Verwendung

- **Jahr 1:** Management-Guidance + Analystenkonsens
- **Jahre 2–3:** Low / Average / High als Szenarioanker
- **Jahre 4–5:** eigene fundamentale Annahmen
- **Jahre 6–10:** Fade / Mean Reversion

Analystenschätzungen werden mit `provider`, `retrieved_at`, Zeitraum und Analystenzahl gespeichert.

---

## 7. Management Guidance für ASML

Guidance wird **nicht** als Analystenschätzung gespeichert.

Für den 2025 Annual Report / Blick auf 2026 wurden offiziell genannt:

- 2026 Total net sales: **€34–39 Mrd.**
- 2026 Gross margin: **51–53 %**
- annualisierte effektive Steuerquote ungefähr **17 %** nach US GAAP

Langfristige 2030-Chance:

- Revenue: **ca. €44–60 Mrd.**
- Gross margin: **ca. 56–60 %**

Diese Korridore sind wertvolle DCF-Evidenz, aber keine automatisch zu erzwingenden Base-/Best-Case-Werte. Die langfristigen Ziele werden als Management-Szenario gespeichert und mit Analysten- und eigenen Annahmen verglichen.

---

## 8. Unternehmensspezifische ASML-Daten

Für die qualitative Analyse und spätere Forecast-Qualität werden optional gespeichert:

- Net system sales
- Net service and field option sales
- Logic / Memory sales
- bookings / order intake, soweit veröffentlicht
- backlog, soweit veröffentlicht
- System-/Technologie-Mix (EUV, non-EUV etc.)
- R&D
- Installed-base-bezogene Informationen

Diese Daten sind **nicht Teil des universellen Industrie-Rohdatenschemas**, sondern ASML-spezifische `operating facts`.

---

## 9. 10-Jahres-Validierungsplan

Für ASML sollen die letzten zehn abgeschlossenen Geschäftsjahre geladen werden.

Validierung:

1. EODHD v1.1 laden.
2. Berichtsperioden auf ASML-Fiscal-Year-End ausrichten.
3. Währung und Einheiten normalisieren.
4. Für 2025 alle Kernfelder gegen offizielles ASML Financial-Statements-Excel prüfen.
5. Stichproben für ältere Jahre durchführen.
6. Abweichungen oberhalb definierter Toleranzen protokollieren.
7. Keine stillen Feldsubstitutionen.

### Toleranzprinzip

Toleranzen dienen nur Rundungs-/Darstellungsunterschieden. Eine semantische Abweichung darf nie als 'innerhalb Toleranz' kaschiert werden.

---

## 10. Phase-2-Akzeptanzkriterien für ASML

Phase 2 gilt für ASML erst dann als erfolgreich, wenn:

- mindestens zehn Jahresperioden soweit verfügbar importiert werden,
- GuV, Bilanz und Cashflow eindeutig den Perioden zugeordnet sind,
- Umsatz, EBIT, Net Income, Equity, Assets, Cash, Debt, OCF, Capex, D&A, A/R, Inventory und A/P verfügbar oder explizit als missing markiert sind,
- 2025-Kernwerte gegen die offizielle ASML-Quelle plausibilisiert sind,
- Estimates und Guidance getrennt gespeichert werden,
- jede Zahl Quelle und Abrufzeit besitzt,
- kein fertiger Provider-ROE/ROCE ungeprüft in die Kennzahlenengine gelangt.

## Quellen

- EODHD Fundamentals API v1.1: `https://eodhd.com/financial-apis/stock-etfs-fundamental-data-feeds`
- EODHD Fundamentals Glossary: `https://eodhd.com/financial-academy/financial-faq/fundamentals-glossary-common-stock`
- ASML Annual Report 2025 Downloads: `https://www.asml.com/investors/annual-report/2025/downloads`
- ASML Annual Report 2025 Financials: `https://www.asml.com/en/investors/annual-report/2025/financials`
