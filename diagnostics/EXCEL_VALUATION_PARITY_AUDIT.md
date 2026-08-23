# Excel Valuation Parity Audit

Ergebnis: GO - EXAKTE EXCEL-/BUCH-BEWERTUNGSSTRUKTUR V1

Datum: 2026-08-23

## Scope

Die eingefrorenen Engines wurden nicht ersetzt. Ergänzt wurde eine getrennte, versionierte Excel-/Buch-Bewertungsmethodik:

```text
BOOK_VALUATION_VERSION = excel-book-valuation-v1.0
```

Neue Schicht:

```text
src/stock_valuation/book_valuation/
```

## Warum Market Cap im Nutzerfall nicht verfügbar war

Der normale Workflow nutzte Market Data nur, wenn für die konkrete Analysis bereits ein persistierter `MarketDataSnapshotRecord` existierte. Die Analyse-Seite zeigte den fehlenden Wert, bot aber keinen produktiven Button, der diesen Snapshot für die normale Nutzeranalyse erzeugt.

Zusätzlich benötigt Market Cap zwei bestätigte Inputs:

- Aktienkurs
- Anzahl Aktien zum Stichtag

Bei europäischen Titeln wie KONE kann die App Listing, Börsenplatz, Provider-Symbol und Aktienzahl nicht zuverlässig erraten. Deshalb wird jetzt eine explizite Nutzerprüfung angeboten.

## Neuer Market-Data-Flow

Auf der Analyse-Seite gibt es jetzt im Bewertungsbereich:

```text
Marktdaten aktualisieren
```

Eigenschaften:

- kein externer Request beim normalen Streamlit-Rerun
- Provider-/Market-Refresh nur nach Nutzerklick
- persistiert einen `MarketDataSnapshotRecord`
- aktualisiert danach die lokalen Workflow-Stages
- unterstützt manuell bestätigten Kurs und bestätigte Aktienzahl
- bei fehlender Listing-/Symbolklarheit wird die UI-Prüfung sichtbar

## Implementierte Bewertungskennzahlen

Equity-Multiples funktionieren unabhängig von EV:

- KGV = Marktkapitalisierung / Jahresüberschuss
- KBV = Marktkapitalisierung / Eigenkapital
- KCV = Marktkapitalisierung / operativer Cashflow
- Kurs-FCF = Marktkapitalisierung / Free Cash Flow

EV-Multiples bleiben abhängig von EV:

- EV/EBIT
- EV/EBITDA
- EV/Sales
- EV/FCF

EV/FCF verwendet bewusst nicht Equity-FCF, sondern:

```text
Entity FCF nach Excel-/Buchmethode
= operativer Cashflow + Zinsaufwand - Sachinvestitionen
```

Wenn `interest_expense` fehlt, bleibt EV/FCF nicht verfügbar.

## Owner Earnings

Owner Earnings ist jetzt eine echte berechnete Methode:

```text
Owner Earnings
= Jahresüberschuss
+ Abschreibungen
- Owner-Earnings-CAPEX
- Veränderung Operating Working Capital
```

Operating Working Capital ist getrennt von allgemeinem Working Capital:

```text
Operating Working Capital
= Vorräte
+ Forderungen aus Lieferungen und Leistungen
- Verbindlichkeiten aus Lieferungen und Leistungen
```

Owner-Earnings-CAPEX:

```text
Sachinvestitionen + Käufe immaterieller Anlagewerte
```

Fehlende immaterielle Investitionen werden nicht als 0 gesetzt.

## DCF-Struktur

Die Analyse-Seite zeigt jetzt sichtbar:

```text
11. DCF-Bewertung
Equity-Methode
1. Bestimmung Owner Earnings
2. Bestimmung des Diskontierungsfaktors
3. Bestimmung der Ewigen Rente
4. Fairen Aktienkurs bestimmen
```

Diskontierungsfaktor nach Excel-/Buchmethode:

```text
Risikoaufschlag = 1 / Faires KGV
Eigenkapitalkosten = risikofreier Zins + Risikoaufschlag + Mindestaufschlag
Mindestverzinsung: 7 %
```

Ewige Rente:

```text
Terminal Value = Owner Earnings letztes Planjahr * (1 + g) / (r - g)
Barwert Terminal Value = Terminal Value / (1 + r)^n
```

Gate:

```text
g < r
```

Fairer Aktienkurs:

```text
Wert des Eigenkapitals = Barwert Owner Earnings + Barwert Ewige Rente
Fairer Aktienkurs = Wert des Eigenkapitals / Anzahl Aktien
Fairer Aktienkurs nach Sicherheitsmarge = Fairer Aktienkurs * (1 - Sicherheitsmarge)
```

## Multiplikatorenmethode

Der bisherige Business-Quality-Ersatz wurde ersetzt/erweitert durch:

```text
12. Multiplikatorenmethode
Sockel-KGV
Finanzielle Stabilität
Marktposition
Rentabilität
Wachstum
Individualität
Bewertung
```

Formel:

```text
Faires KGV
= Sockel-KGV
+ Finanzielle Stabilität
+ Marktposition * Rentabilitätsmultiplikator
+ Wachstum
+ Individualität
```

Fairer Preis je Aktie:

```text
Prognose-Gewinn je Aktie = Prognose-Jahresüberschuss / Anzahl Aktien
Fairer Preis je Aktie = Faires KGV * Prognose-Gewinn je Aktie
```

Porter-Punkte sind bewusst manuelle qualitative Eingaben und werden persistent gespeichert.

## Persistenz

Manuelle Excel-/Buchannahmen werden über die bestehende Tabelle `ValuationAssumption` gespeichert:

- `analysis_id`
- `method = excel_book_valuation`
- `key`
- `value`
- `note`
- `source_type = excel-book-valuation-v1.0`

Reopen-Test ist vorhanden.

## Review-Gates

Nicht automatisch erfunden:

- keine automatische Porter-Bewertung
- keine automatische Individualitätsbewertung
- keine stille Annahme `intangible_purchases = 0`
- keine stille Annahme `interest_expense = 0`
- keine Monte-Carlo-Simulation

Simulation:

```text
SIMULATION_METHOD_REVIEW_REQUIRED
```

Begründung: Die sichtbaren MAX/MIN/AVERAGE/STDEV-Zellen sind dokumentiert, aber die VBA-/Szenario-Erzeugung ist aus der Arbeitsmappe nicht eindeutig genug für eine saubere automatische Nachbildung.

## Artefakte

```text
docs/EXCEL_VALUATION_FORMULA_MAP.md
diagnostics/EXCEL_VALUATION_PARITY_AUDIT.md
diagnostics/EXCEL_VALUATION_PARITY_AUDIT.json
tests/fixtures/book_valuation_excel_fixture.json
```

## Tests

Ausgeführt:

```text
.venv\Scripts\python.exe -m pytest -q
```

Ergebnis:

```text
229 passed in 2.56s
```

App-Smoke:

```text
streamlit run app.py -> HTTP 200 auf localhost:8512
```

## Entscheidung

GO - EXAKTE EXCEL-/BUCH-BEWERTUNGSSTRUKTUR V1
