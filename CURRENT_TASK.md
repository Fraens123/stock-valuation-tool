# Current Task

## Phase 1.1 – Excel-Inventarisierung und fachlicher Kennzahlenkatalog

Phase 0 (Application Foundation) ist implementiert. Der nächste Block ist bewusst **fachlich**, nicht DCF-Programmierung.

## Vor Beginn lesen

- `AGENTS.md`
- `ROADMAP.md`
- `docs/PROJECT_CHARTER.md`
- `docs/EXCEL_MAPPING.md`
- `docs/BOOK_MAPPING.md`
- `docs/DATA_MODEL.md`
- `docs/DCF_METHOD.md`
- `reference/README.md`

## Lokale Referenzdatei

Wenn vorhanden, liegt die bestehende Excel-Datei lokal unter:

```text
reference/private/Aktien Bewertungs Tool.xlsm
```

Diese Datei darf analysiert, aber **nicht committed** werden.

## Ziel

Eine vollständige fachliche Spezifikation erstellen, bevor Kennzahlen oder Bewertungsformeln in Python implementiert werden.

Für jeden Analyseparameter benötigen wir mindestens:

1. stabile interne ID
2. Anzeigeüberschrift, z. B. `Eigenkapitalrendite (Return on Equity, ROE)`
3. Buchkapitel und verifizierte Kindle-Seite, soweit vorhanden
4. exakte fachliche Definition
5. benötigte Rohdaten
6. Formel / Rechenweg
7. Einheit
8. Bedeutung
9. Interpretation
10. typische Fallstricke
11. Zusammenhang mit anderen Kennzahlen
12. primäre Datenquelle
13. Excel-Referenz / bisherige Position oder Formel
14. Entscheidung: `keep`, `add`, `special_case`, `drop`

## Aufgaben

### 1. Excel vollständig inventarisieren

- alle fachlichen Abschnitte in Reihenfolge aufnehmen
- alle Eingabefelder identifizieren
- alle berechneten Kennzahlen identifizieren
- Equitymultiplikatoren und Enterprise-Value-Ansatz getrennt erfassen
- DCF-Schritte getrennt erfassen
- Multiplikatorenmethode / Fair-KGV-Blöcke getrennt erfassen

### 2. Maschinenlesbaren Kennzahlenkatalog anlegen

Zieldatei:

```text
src/stock_valuation/knowledge/metrics.yaml
```

Noch **keine** Rechenengine daraus bauen.

### 3. Mapping-Dokument vervollständigen

`docs/EXCEL_MAPPING.md` aktualisieren mit:

- Excel-Reihenfolge
- Kennzahl
- Inputs
- Formel
- Buchreferenz
- Datenquelle
- Statusentscheidung

### 4. Informationssystem vorbereiten

Für jedes spätere `ⓘ` muss die Struktur vorbereitet sein:

- Kurzdefinition
- ausführliche Bedeutung
- Interpretation
- Fallstricke
- Kindle-Seite

Keine längeren Buchpassagen kopieren; Erklärungen werden eigenständig formuliert.

### 5. Offene methodische Fragen markieren

Wenn Excel und Buch nicht eindeutig sind oder Definitionen abweichen:

- nicht eigenständig entscheiden
- in `docs/METHODOLOGY_OPEN_QUESTIONS.md` dokumentieren
- konkrete Entscheidung vom Nutzer anfordern

## Noch ausdrücklich NICHT tun

- keine ROE-/ROCE-/Working-Capital-Berechnungsengine implementieren
- keine DCF-Formeln implementieren
- keine Risiko-Stufenwerte festlegen
- keine Fair-KGV-Formel verändern
- keine API-Feldzuordnung finalisieren, bevor der Rohdatenbedarf vollständig ist
- keine langen Buchtexte übernehmen

## Definition of Done

Phase 1.1 ist fertig, wenn alle Kennzahlen und Bewertungsblöcke des bestehenden Excel in einem strukturierten Katalog erfasst sind und für jeden Punkt eindeutig ist:

- was er bedeutet,
- wie er berechnet wird,
- welche Rohdaten benötigt werden,
- wo er im Buch zu finden ist,
- und ob er im neuen Tool erhalten bleibt.

Danach folgt die Implementierung der Datenquellen und anschließend die Kennzahlenengine.
