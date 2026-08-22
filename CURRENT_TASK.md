# Current Task

## Phase 1.2 – Buchvalidierung, Normalisierung und ASML-Datenbedarf

Phase 0 ist implementiert. Phase 1.1 hat das bestehende Excel fachlich inventarisiert und die maschinenlesbaren Kataloge angelegt.

## Vor Beginn lesen

1. `AGENTS.md`
2. `ROADMAP.md`
3. `docs/PHASE_1_METRIC_INVENTORY.md`
4. `docs/RAW_DATA_SCHEMA.md`
5. `docs/BOOK_MAPPING.md`
6. `docs/QUALITATIVE_ANALYSIS_SPEC.md`
7. `docs/METHODOLOGY_OPEN_QUESTIONS.md`
8. `docs/DCF_METHOD.md`
9. `src/stock_valuation/knowledge/metrics.yaml`
10. `src/stock_valuation/knowledge/qualitative.yaml`

## Stand Phase 1.1

Erledigt:

- bestehendes Excel von Rohdaten über Kennzahlen, Multiples, DCF und Fair-KGV inventarisiert
- aktuelle Excel-Formeln und relevante Zellbereiche dokumentiert
- fehlende Buchkennzahlen identifiziert
- Kennzahlen in `keep`, `add`, `adjust`, `special` bzw. `verify` klassifiziert
- Kindle-Seiten aus der Nutzer-Ausgabe übernommen
- umfangreiche eigene `ⓘ`-Erklärungen angelegt
- qualitative Kapitel-5-Struktur und Porter-/Fair-KGV-Kriterien katalogisiert
- normalisiertes Rohdatenwörterbuch als Entwurf angelegt
- methodische Abweichungen des Alt-Excel explizit dokumentiert

## Ziel Phase 1.2

Vor Beginn der produktiven Datenprovider müssen die **Zieldefinitionen** ausreichend stabil sein.

### A. Buchdefinitionen verifizieren

Priorität:

1. ROE – Kindle 94
2. Gesamtkapitalrendite – 109
3. ROCE – 111
4. Gearing – 124
5. Dynamischer Verschuldungsgrad – 129
6. Sachinvestitionsquote – 136
7. Anlagenabnutzungsgrad – 141
8. Wachstumsquote – 144
9. Debitoren/Kreditoren – 158
10. Inventory Turnover / DIO – 171
11. Equity-DCF – ab 295
12. Faires KGV – ab 351

Wenn Buchtext nicht zuverlässig verfügbar ist, **nicht raten**. Offenen Punkt in `docs/METHODOLOGY_OPEN_QUESTIONS.md` belassen.

### B. Rohdatenschema finalisieren

Für jede Zielkennzahl prüfen:

- welcher Rohdatenwert benötigt wird
- ob EODHD ihn direkt liefert
- ob er aus anderen Rohdaten ableitbar ist
- ob ASML IR / Geschäftsbericht nötig ist
- ob Aktienfinder manuell sinnvoll ist
- ob die Kennzahl nur bei bestimmten Geschäftsmodellen angezeigt wird

### C. ASML-Datenbedarf definieren

Eine Mapping-Tabelle erstellen:

`internal_key -> EODHD field -> ASML annual-report field -> fallback/manual -> unit/currency`

Noch keine blinde Providerimplementierung.

### D. Jahresabschlussbereinigung spezifizieren

Relevante Kindle-Stellen:
- 8.3 Jahresabschlussbereinigung – 422
- 8.3.1 Pro-forma-Abschlüsse und Sondereffekte – 427

Festlegen, wie historische und prognostizierte Werte als `reported` und `normalized` gespeichert werden sollen.

## Noch NICHT tun

- keine endgültige Kennzahlenengine
- keine produktive DCF-Engine
- keine Fair-KGV-Punkte erfinden
- keine Risiko-Dropdown-Prozentwerte festlegen
- keine Analystenschätzungen ohne Quellenmetadaten speichern

## Definition of Done Phase 1.2

- Ziel-Rohdatenschema für Industrieunternehmen ist ausreichend stabil.
- ASML-Feldmapping für Phase 2 ist definiert.
- alle noch offenen Buch-/Methodikfragen sind explizit markiert.
- Normalisierung/Sondereffekte sind konzeptionell definiert.
- danach kann Phase 2 (Datenprovider) kontrolliert beginnen.
