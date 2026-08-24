# ONE CLICK ANALYSIS WORKFLOW AUDIT

Status: GO - ONE-CLICK-ANALYSE-WORKFLOW V1

## Scope

Phase 9F wurde als Produkt-/Workflow-Schicht umgesetzt. Es wurden keine neuen
Finanz-, Kennzahlen-, Historical-, Quality-, Market- oder Valuation-Engines gebaut
und keine Bewertungsformeln dupliziert. Der neue Runner orchestriert vorhandene
Services und leitet nutzerverstaendliche Review Tasks aus persistierten Daten ab.

## Implementierte Komponenten

- Zentraler Orchestrator: `src/stock_valuation/workflow/analysis_runner.py`
- Review-Task-Ableitung: `src/stock_valuation/workflow/review_tasks.py`
- Neue Startseite: `app.py`
- Reduzierte Navigation: `src/stock_valuation/ui/navigation.py`
- Regressionstests: `tests/test_one_click_analysis_runner.py`

## Neuer Hauptworkflow

Normaler Nutzerflow:

1. Unternehmen auswaehlen oder suchen.
2. Analyse-Stichtag setzen.
3. `Analyse starten / aktualisieren` klicken.
4. Die App fuehrt Import, Historie, Missing-Data-Suche, Preferred Data,
   Kennzahlen, Marktdaten, Annahmen und Bewertungsvorbereitung zentral aus.
5. Danach sieht der Nutzer entweder `Analyse fertig` oder konkrete Review Tasks.
6. `Analyse ansehen` zeigt einen linearen Bericht statt technischer Stage-Listen.

## Runner-Verhalten

`run_complete_analysis(...)` fuehrt zentral aus:

- Analysis anlegen oder passende offene Revision wiederverwenden
- Analyse auf `In Bearbeitung` setzen
- Finanzdaten ueber vorhandenen Source Router laden
- SEC-History-/Missing-Data-Kandidaten ueber vorhandene Infrastruktur suchen
- lokale Workflow-Stages refreshen
- Marktdaten nur nach explizitem Klick aktualisieren
- Book-/Excel-Valuation-Grundlagen vorbereiten
- Review Tasks aus persistiertem Zustand ableiten

Providerfehler brechen den Workflow nicht komplett ab. Sie werden als Warnung
oder Marktdaten-Review Task ausgegeben.

## Review Tasks

Eingefuehrtes Modell:

- `id`
- `analysis_id`
- `category`
- `title_de`
- `description_de`
- `metric`
- `fiscal_year`
- `severity`
- `blocking_for`
- `suggested_value`
- `source`
- `actions`

Kategorien:

- Daten pruefen
- Marktdaten pruefen
- Prognose ergaenzen
- DCF-Annahme pruefen
- Multiplikatorenannahme pruefen

Prioritaet:

- A: blockiert aktuelle Bewertung
- B: beeinflusst aktuelle Bewertung
- C: weiterer Datenhinweis

Historische Detailwarnungen werden nicht als technische Hauptblocker angezeigt,
sondern unter `Weitere Datenhinweise` zusammengefasst.

## Keine stillen Freigaben

Der One-Click-Workflow gibt keine unsicheren Daten automatisch frei:

- Short-Term-Debt-Kandidaten bleiben pruefpflichtig, wenn die Vollstaendigkeit
  nicht eindeutig ist.
- Nicht separat berichtete Werte werden nicht still als 0 verwendet.
- Bewertungsannahmen werden als Vorschlag angezeigt und muessen uebernommen
  oder angepasst werden.
- Forecasts werden nicht aus Ist-Daten fortgeschrieben.

## UI

Die neue Startseite zeigt standardmaessig:

- Unternehmen
- Analyse-Stichtag
- `Analyse starten / aktualisieren`
- kompakte Fortschrittsanzeige
- konkrete Review-Karten
- `Pruefungen bearbeiten`
- `Analyse ansehen`
- `Details anzeigen`

Die alten Seiten bleiben erhalten, sind aber in der Navigation unter `Erweitert`
einsortiert:

- Unternehmen
- Finanzdaten
- Analyse
- Manuelle Daten
- Kennzahlen-Details

## Real-ASML-Test

Ausgefuehrt:

- ASML aus lokaler Datenbank gewaehlt
- One-Click-Runner fuer Stichtag `2026-08-24` gestartet
- Ergebnis persistiert als Analyse `id=3`

Ergebnis:

- Status: `Pruefung erforderlich`
- `ready_for_final`: false
- Prioritaets-Review-Tasks: 5
- Weitere Datenhinweise: 8
- Warnungen: 1

Prioritaetsaufgaben:

1. Bewertungsannahmen bestaetigen
2. Abschreibungen und Amortisation 2025 pruefen
3. Kurzfristige Finanzschulden 2025 pruefen
4. Marktdaten pruefen
5. Jahresueberschuss 2027e ergaenzen

Warnung:

- Marktdaten konnten nicht geladen werden; Boersenplatz, Handelssymbol und
  Aktienzahl muessen geprueft werden.

Der Lauf zeigt keine technischen Stage-Namen als normale Nutzeraufgaben.
Historische Altjahre werden nicht als Hauptblocker praesentiert.

## Tests

Ausgefuehrt:

- `python -m py_compile app.py pages/0_Unternehmen.py pages/1_Datenimport.py pages/2_Manuelle_Daten.py pages/3_Analyse.py pages/4_Kennzahlen.py src/stock_valuation/workflow/analysis_runner.py src/stock_valuation/workflow/review_tasks.py src/stock_valuation/ui/navigation.py`
- `pytest -q`
- `streamlit run app.py --server.headless true --server.port 8503`

Ergebnis:

- Bytecode-Compile erfolgreich
- `263 passed, 1 warning`
- Streamlit startet ohne sofortigen Startup-Crash

## Entscheidung

GO - ONE-CLICK-ANALYSE-WORKFLOW V1
