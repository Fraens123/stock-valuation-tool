# Normalisiertes Rohdatenschema

## Ziel

Die neue Anwendung soll möglichst wenige fertige Kennzahlen von Datenprovidern übernehmen. Stattdessen werden Rohdaten einmal normalisiert und daraus sämtliche Kennzahlen konsistent berechnet.

Jeder Datenpunkt erhält mindestens:

- `metric`
- `period_end`
- `period_type` (`FY`, `Q1`, `Q2`, `Q3`, `Q4`, `TTM`)
- `value`
- `currency`
- `unit`
- `provider`
- `source_url`
- `retrieved_at`
- `is_manual_override`
- optional `note`

## GuV

| Schlüssel | Beschreibung | Wichtig für |
|---|---|---|
| `revenue` | Umsatz | Wachstum, Margen, DCF, KUV/EV Sales |
| `cost_of_goods_sold` | Wareneinsatz/COGS | Kreditorenlaufzeit, DIO, Lagerumschlag |
| `gross_profit` | Bruttoergebnis | Geschäftsmodell/Margen |
| `operating_expenses` | operative Aufwendungen | Plausibilisierung |
| `ebit` | operatives Ergebnis | EBIT-Marge, ROA/ROCE, EV/EBIT |
| `ebitda` | EBITDA, falls direkt verfügbar | Cross-Check; primär selbst aus Komponenten ableiten |
| `interest_expense` | Zinsaufwand | ROA, Zinsdeckung, DCF-/EV-Crosschecks |
| `income_before_tax` | Ergebnis vor Steuern | Steuerquote |
| `income_tax_expense` | Steueraufwand | nachhaltige Steuerquote |
| `net_income` | Jahresüberschuss | ROE, DCF, Fair-KGV |
| `net_income_attributable` | den Stammaktionären zurechenbarer Gewinn | EPS/Umsatzrendite, falls erforderlich |
| `basic_eps` | unverwässertes EPS | Historie |
| `diluted_eps` | verwässertes EPS | Bewertung |

## Bilanz

| Schlüssel | Beschreibung | Wichtig für |
|---|---|---|
| `cash_and_short_term_investments` | liquide Mittel + sehr kurzfristige Anlagen | Net Debt, EV, Liquidität |
| `accounts_receivable` | Forderungen aus LuL | DSO, Working Capital |
| `inventory` | Vorräte | Working Capital, DIO |
| `current_assets` | Umlaufvermögen | Current Ratio, Umlaufintensität |
| `ppe_net` | Sachanlagen netto | Anlagenanalyse |
| `ppe_gross` | Sachanlagen brutto, falls verfügbar | Anlagenabnutzungsgrad |
| `accumulated_depreciation` | kumulierte Abschreibung, falls verfügbar | Anlagenabnutzungsgrad |
| `intangible_assets` | immaterielle Vermögenswerte ohne/mit Goodwill gemäß Provider-Mapping | Bilanzqualität |
| `goodwill` | Goodwill separat | Goodwill-Anteil |
| `non_current_assets` | langfristige Vermögenswerte | Anlagenintensität/-deckung |
| `total_assets` | Bilanzsumme | ROA, Quoten |
| `accounts_payable` | Lieferantenverbindlichkeiten | DPO, Working Capital |
| `current_liabilities` | kurzfristige Verbindlichkeiten | Liquidität, ROCE |
| `short_term_debt` | kurzfristige zinstragende Schulden | Net Debt |
| `long_term_debt` | langfristige zinstragende Schulden | Net Debt |
| `lease_liabilities_current` | kurzfristige Leasingverbindlichkeiten, falls relevant | EV/Net Debt Policy |
| `lease_liabilities_non_current` | langfristige Leasingverbindlichkeiten | EV/Net Debt Policy |
| `interest_bearing_debt` | normalisierte Summe der definierten zinstragenden Schulden | Gearing, Net Debt, EV |
| `long_term_liabilities` | langfristige Gesamtverbindlichkeiten | Anlagendeckung II |
| `total_liabilities` | Gesamtverbindlichkeiten | ergänzende Excel-Kennzahlen |
| `total_equity` | Eigenkapital | ROE, EK-Quote, KBV |

## Cashflow

| Schlüssel | Beschreibung | Wichtig für |
|---|---|---|
| `operating_cash_flow` | Cashflow aus operativer Tätigkeit | FCF, Sachinvestitionsquote |
| `depreciation_amortization` | Abschreibungen/Amortisation | EBITDA, DCF |
| `capex_ppe` | Sachinvestitionen | DCF, Wachstumsquote |
| `capex_intangibles` | zahlungswirksame Investitionen in immaterielle Assets | DCF |
| `capex_total` | `capex_ppe + capex_intangibles` gemäß DCF-Policy | DCF/FCF |
| `acquisitions` | Unternehmenskäufe netto | gesonderte Kapitalallokation, nicht Standard-CAPEX |
| `dividends_paid` | gezahlte Dividenden | Ausschüttung |
| `share_repurchases` | Rückkäufe | Kapitalallokation |
| `share_issuance` | Aktienemissionen/Stock Compensation Cashflow soweit verfügbar | Netto-Rückkäufe |
| `free_cash_flow` | intern berechnet: OCF - definierter CAPEX | zentrale Kennzahl |

## Aktienzahl / Markt

| Schlüssel | Beschreibung |
|---|---|
| `basic_shares` | durchschnittliche oder Stichtags-Aktienzahl, Feldtyp separat kennzeichnen |
| `diluted_shares` | verwässerte Aktienzahl für Fair Value je Aktie |
| `market_price` | Kurs am Analyse-Stichtag |
| `market_cap` | Marktpreis × passende Aktienzahl; Berechnung dokumentieren |

## Unternehmensspezifische operative Daten

Nicht jede Firma braucht dieselben Kennzahlen. Deshalb werden solche Daten als optionale Fakten unterstützt:

- `order_intake`
- `order_backlog`
- `book_to_bill`
- Segmentumsätze/-margen
- installierte Basis / Service-Anteil
- Stückzahlen / ASPs / Kapazität, sofern für Investmentthese relevant

Für ASML sind insbesondere Auftragseingang, Backlog, Systemumsätze, Installed Base Management und Management-Guidance potenziell relevant.

## Prognosedaten

Analystenschätzungen werden **nicht** als historische Raw Facts gespeichert, sondern als `EstimateSnapshot`:

- `metric`
- `period`
- `low`
- `average`
- `high`
- `analyst_count`
- `provider`
- `retrieved_at`

Geplante Kernmetriken:
- Revenue
- EPS
- Net Income, falls verfügbar
- EBIT/EBITDA, falls Provider verlässlich

Management Guidance wird getrennt als `GuidanceSnapshot` gespeichert.

## Manuelle Aktienfinder-Daten

`ManualInputSnapshot` bleibt absichtlich generisch. Ein manueller Wert muss mindestens enthalten:

- Metrik
- Periode
- Wert
- Einheit/Währung
- Quelle = Aktienfinder
- Eingabedatum
- Kommentar optional

Manuelle Eingaben dürfen einen automatisch geladenen Wert überschreiben, aber der Override muss in UI und Report sichtbar bleiben.

## Offene Normalisierungsentscheidungen für Phase 2

1. Behandlung von IFRS-16-Leasing im Net Debt / EV.
2. Stichtags- vs. Durchschnitts-Aktienzahl je Kennzahl.
3. Definition des FCF und DCF-CAPEX.
4. Umgang mit Goodwill innerhalb Provider-Intangibles.
5. COGS/Materialaufwand bei Unternehmen, die andere GuV-Schemata verwenden.
6. Banken/Versicherungen bekommen später ein separates Schema und nicht erzwungene Industriekennzahlen.
