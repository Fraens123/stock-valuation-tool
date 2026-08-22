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
| `ebit` | Ergebnis vor Zinsen und Steuern; bei fehlender direkter Zeile nur aus eindeutig verifizierten Komponenten ableiten | EBIT-Marge, ROA/ROCE, EV/EBIT |
| `ebitda` | abgeleitete Kennzahl; Providerwert nur Cross-Check, primär selbst aus freigegebenem EBIT + freigegebenem D&A berechnen | EBITDA-Marge, EV/EBITDA |
| `interest_expense` | Zinsaufwand | ROA, Zinsdeckung, DCF-/EV-Crosschecks |
| `income_before_tax` | Ergebnis vor Steuern | Steuerquote |
| `income_tax_expense` | Steueraufwand | nachhaltige Steuerquote |
| `net_income` | Jahresüberschuss | ROE, DCF, Fair-KGV |
| `net_income_attributable` | den Stammaktionären zurechenbarer Gewinn | EPS/Umsatzrendite, falls erforderlich |
| `basic_eps` | unverwässertes EPS | Historie |
| `diluted_eps` | verwässerte Aktienzahl für Fair Value je Aktie | Bewertung |

## Bilanz

| Schlüssel | Beschreibung | Wichtig für |
|---|---|---|
| `cash_and_short_term_investments` | liquide Mittel + sehr kurzfristige Anlagen | Net Debt, EV, Liquidität |
| `accounts_receivable` | Forderungen aus LuL | DSO, Working Capital |
| `inventory` | Vorräte | Working Capital, DIO |
| `current_assets` | Umlaufvermögen | Current Ratio, Umlaufintensität |
| `ppe_net` | Netto-Sachanlagen (Property, Plant & Equipment); separat ausgewiesene Operating-Lease-Right-of-Use-Assets sind **nicht** Bestandteil | Anlagenanalyse |
| `ppe_gross` | Sachanlagen brutto, falls verfügbar | Anlagenabnutzungsgrad |
| `accumulated_depreciation` | kumulierte Abschreibung, falls verfügbar | Anlagenabnutzungsgrad |
| `intangible_assets` | immaterielle Vermögenswerte ohne/mit Goodwill gemäß Provider-Mapping | Bilanzqualität |
| `goodwill` | Goodwill separat | Goodwill-Anteil |
| `non_current_assets` | langfristige Vermögenswerte | Anlagenintensität/-deckung |
| `total_assets` | Bilanzsumme | ROA, Quoten |
| `accounts_payable` | Lieferantenverbindlichkeiten | DPO, Working Capital |
| `current_liabilities` | kurzfristige Verbindlichkeiten | Liquidität, ROCE |
| `short_term_debt` | zinstragende Finanzschulden mit Fälligkeit innerhalb von 12 Monaten **einschließlich Current Portion of Long-Term Debt**; Lieferanten- und Leasingverbindlichkeiten bleiben getrennt | Net Debt |
| `long_term_debt` | langfristige zinstragende Schulden nach Abzug der separat kurzfristig ausgewiesenen Fälligkeiten | Net Debt |
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
| `depreciation_amortization` | Abschreibungen auf Sachanlagen + Amortisation immaterieller Vermögenswerte; unspezifische zusätzliche Non-Cash-Posten wie `and other` werden nicht automatisch einbezogen | EBITDA, DCF |
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

## Preferred Data / Berechnungsfreigabe

Das Vorhandensein eines normalisierten Providerwerts bedeutet **nicht**, dass er automatisch für Kennzahlen verwendet werden darf.

Für jeden Schlüssel/Jahr werden zwei Fragen getrennt behandelt:

1. **Welcher gespeicherte Wert hat Quellenpriorität?** (`manual_override` → Primärquelle → Provider-Fallback)
2. **Ist dieser Wert für Berechnungen freigegeben?**

Berechnungsbereit sind:
- bestätigte Overrides,
- eindeutig gemappte Primärquellenwerte,
- Providerwerte mit explizitem Primärquellen-PASS (ChatGPT-Dateiprüfung oder bestehendes ASML-Referenzgate).

Nicht berechnungsbereit sind:
- ungeprüfte Providerwerte,
- `WARN`/`FAIL` mit offener oder verworfener Korrektur,
- `UNKLAR`,
- veraltete Prüfergebnisse,
- Provider-EBITDA als fertige Kennzahl.

Die Rohdaten bleiben in allen Fällen gespeichert und auditierbar.

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
