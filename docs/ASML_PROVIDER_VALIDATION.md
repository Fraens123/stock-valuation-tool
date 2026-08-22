# ASML Provider Validation

## Zweck

Bevor ein automatischer Provider als Rohdatenbasis der Kennzahlenengine freigegeben wird, werden seine normalisierten Felder gegen veröffentlichte Primärquellen geprüft.

Referenzunternehmen: **ASML Holding N.V.**  
Referenzstandard für den ersten Gate: **US GAAP**  
Referenzjahre: **2025 und 2024**

Primärquelle:
- ASML 2025 Annual Report based on US GAAP
- https://ourbrand.asml.com/m/71076aaad607de4d/original/asml-2025-annual-report-based-on-us-gaap.pdf

Die Kontrollwerte sind ausschließlich Test-/Validierungsdaten. Sie dürfen fehlende Providerwerte nicht automatisch ersetzen.

## Providerstatus

### EODHD

- Free-Key erfolgreich erstellt.
- `ASML.AS` Fundamentals v1.1 liefert mit dem getesteten Free-Tarif HTTP 403.
- Schlussfolgerung: technischer Adapter bleibt erhalten, aber EODHD wird ohne bezahlten Fundamentals-Tarif nicht als V1-Livequelle eingesetzt.

### Alpha Vantage

- Free-Key funktioniert.
- `ASML.AMS` liefert beim `INCOME_STATEMENT`-Fundamentals-Endpunkt keine Reports.
- `ASML` liefert die konsolidierten ASML-Holding-Abschlüsse in EUR.
- Lokaler Test des Nutzers: 20 Jahresberichte und 81 Quartalsberichte erkannt.
- Letzter Umsatz 2025: 32,6673 Mrd. EUR und damit identisch mit ASML US GAAP.
- Vollimport wurde lokal erfolgreich durchgeführt: 720 Financial-Fact-Zeilen über 20 Geschäftsjahre; Missing-Felder bleiben explizit sichtbar.

**Status:** Kandidat, noch nicht vollständig freigegeben. Primärquellen-Gate muss die kritischen Felder bestehen bzw. Abweichungen müssen fachlich erklärt und neu gemappt werden.

## Gate-Regeln

Automatische Vergleichslogik in `stock_valuation.validation.service`:

- relative Abweichung <= 0,5 % -> `PASS`
- > 0,5 % bis 2,0 % -> `WARN`
- > 2,0 % -> `FAIL`
- kein Providerwert -> `MISSING`

Ein Provider-Gate gilt nur dann als bestanden, wenn es bei allen als `critical` markierten Referenzfeldern weder `FAIL` noch `MISSING` gibt.

Cross-Check-Felder dürfen abweichen, bleiben aber sichtbar.

## Kontrollfelder 2025/2024

Die maschinenlesbaren Referenzwerte stehen in:

`src/stock_valuation/validation/asml_reference.py`

Geprüft werden u. a.:

- Total net sales
- Total cost of sales
- Gross profit
- R&D
- Income from operations
- Income before tax
- Net income
- Total/current assets
- Cash and cash equivalents
- Accounts receivable
- Inventory
- PP&E net
- Goodwill
- Total/current liabilities
- Accounts payable
- Long-term debt
- Shareholders' equity
- Operating cash flow
- Purchases of PP&E (CAPEX)
- Depreciation and amortization

## Bereits im ersten lokalen Screenshot sichtbare Punkte

Diese Beobachtungen sind noch keine endgültigen Mappingentscheidungen. Sie werden durch den automatischen Gate bestätigt oder widerlegt.

### Treffer

2025:
- Revenue: Alpha Vantage 32,6673 Mrd. EUR; ASML US GAAP 32,6673 Mrd. EUR.
- Accounts payable: Alpha Vantage 3,5218 Mrd. EUR; ASML US GAAP 3,5218 Mrd. EUR.
- Cash and cash equivalents: Alpha Vantage ca. 12,9105 Mrd. EUR vs. ASML 12,9160 Mrd. EUR; geringe Abweichung innerhalb der Gate-Toleranz.
- Current assets: Alpha Vantage ca. 30,6031 Mrd. EUR vs. ASML 30,6161 Mrd. EUR; geringe Abweichung.

### Fachlich zu prüfen

#### `accounts_receivable`

Erster Alpha-Vantage-Wert 2025: ca. 4,1642 Mrd. EUR.  
ASML US-GAAP `Accounts receivable, net`: 3,0230 Mrd. EUR.

Die Abweichung ist zu groß für Rundung. Vermutung: `currentNetReceivables` entspricht bei ASML einem breiteren Receivables-Aggregat. Das Feld darf erst nach semantischer Klärung für Debitorenlaufzeit/Working Capital genutzt werden.

#### `capital_expenditures`

Erster Alpha-Vantage-Wert 2025: ca. 1,5115 Mrd. EUR.  
ASML US-GAAP purchases of property, plant and equipment: 1,5736 Mrd. EUR.  
ASML purchases of PP&E + intangible assets: 1,6312 Mrd. EUR.

Der Alpha-Wert entspricht keiner der beiden offiziellen Größen exakt. Vor Nutzung in FCF, Sachinvestitionsquote oder Owner Earnings muss die Providersemantik geklärt werden.

#### `cash_and_short_term_investments`

Erster Alpha-Vantage-Wert 2025 war ungefähr identisch mit dem reinen Cash-Feld, obwohl ASML zusätzlich 405,9 Mio. EUR Short-Term Investments ausweist.

Das Feld ist deshalb nur als Cross-Check markiert. Für Netto-Cash/EV werden später die Komponenten `cash_and_equivalents` und `short_term_investments` transparent zusammengesetzt.

## Analyst Estimates

Alpha Vantage liefert neben aktuellen Schätzungen auch lange historische Estimate-/Revisionsreihen. Diese bleiben aus Auditgründen im Snapshot gespeichert.

Normale UI:
- standardmäßig nur Perioden ab dem Analyse-Stichtag anzeigen
- historische Estimate-Historie optional einblendbar

DCF-Nutzung wird erst in Phase 8 definiert. Historische Estimate-Datensätze dürfen nicht versehentlich als Zukunftsforecast genutzt werden.

## Nächster Schritt

1. Lokal `git pull` und `pytest -q`.
2. Bestehende ASML-Analyse öffnen; kein neuer API-Import nötig.
3. Auf `Datenimport` den neuen Abschnitt `ASML Primärquellen-Validierung` prüfen.
4. FAIL/WARN/MISSING-Tabelle dokumentieren.
5. Erst danach problematische Alpha-Vantage-Felder gezielt neu mappen oder als nicht belastbar markieren.
6. Phase 3 startet erst, wenn die Kennzahlen jeweils nur auf validierte Rohdaten zugreifen.
