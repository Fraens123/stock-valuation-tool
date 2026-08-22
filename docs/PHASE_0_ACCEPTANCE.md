# Phase 0 – Acceptance Test

Phase 0 ist abgeschlossen, wenn der folgende Workflow lokal ohne manuelle Datenbankeingriffe funktioniert.

## Vorbereitung

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
pytest -q
streamlit run app.py
```

Die SQLite-Datei wird automatisch unter `data/stock_valuation.db` angelegt und ist durch `.gitignore` vom Repository ausgeschlossen.

## Manueller Abnahmetest

### 1. Unternehmen finden

1. Startseite öffnen.
2. Nach `ASML` suchen.
3. Prüfen:
   - ASML Holding N.V.
   - Ticker `ASML`
   - ISIN `NL0010273215`
   - Euronext Amsterdam
   - EUR
   - Provider-Symbol `ASML.AS`

### 2. Erste Analyse erstellen

1. `Neue Analyse` öffnen.
2. ASML auswählen.
3. Analyse-Stichtag setzen.
4. optional Aktienkurs und Notizen erfassen.
5. Analyse anlegen.
6. Erwartung: Revision `R1`, Status `Entwurf`.

### 3. Analyse bearbeiten

1. `Analyse öffnen`.
2. R1 auswählen.
3. Titel, Aktienkurs oder Notizen ändern.
4. speichern.
5. Status auf `In Bearbeitung` setzen.
6. Seite neu laden und prüfen, dass die Daten erhalten bleiben.

### 4. Analyse abschließen / Freeze

1. `Analyse abschließen und einfrieren` wählen.
2. Erwartung: Status `Abgeschlossen`.
3. Eingabefelder dürfen nicht mehr editierbar sein.
4. Es darf nur noch eine neue Revision erstellt werden.

### 5. Neue Revision erstellen

1. Aus R1 `Neue Revision erstellen`.
2. neuen Stichtag wählen.
3. qualitative Einschätzungen optional übernehmen.
4. Bewertungsannahmen standardmäßig nicht übernehmen.
5. Erwartung:
   - neue Revision `R2`
   - Status `Entwurf`
   - `previous_analysis_id` verweist auf R1
   - alter Aktienkurs wird **nicht** übernommen
   - historische/API-Daten werden **nicht** übernommen
   - R1 bleibt unverändert

### 6. Revision verändern

1. R2 öffnen.
2. neuen Aktienkurs eintragen.
3. Notiz/These ändern.
4. speichern.

### 7. Vergleich

1. `Analysen vergleichen` öffnen.
2. ASML auswählen.
3. R1 und R2 auswählen.
4. Erwartung:
   - geänderter Aktienkurs wird angezeigt
   - geänderte Notiz wird angezeigt
   - später vorhandene Fundamentaldaten, Prognosen, qualitative Bewertungen und Bewertungsergebnisse werden in eigenen Kategorien verglichen

### 8. PDF-Snapshot

1. eine gespeicherte Analyse öffnen.
2. `PDF-Report herunterladen`.
3. Erwartung:
   - PDF lässt sich öffnen
   - Dateiname enthält Ticker, Stichtag und Revision
   - Report zeigt Stammdaten und Snapshot-Informationen
   - Report lädt **keine Live-Daten** nach

## Automatisierte Tests

Phase 0 wird durch folgende Tests abgedeckt:

- `tests/test_company_search.py`
- `tests/test_analysis_lifecycle.py`
- `tests/test_analysis_comparison.py`
- `tests/test_pdf_report.py`

## Nicht Teil von Phase 0

Bewusst noch nicht enthalten:

- produktive Unternehmenssuche per API
- automatische ASML-Finanzdaten
- Aktienfinder-Eingabemaske
- Kennzahlenberechnung
- DCF-/Fair-KGV-Formeln
- fertiger Analysebericht

Diese Punkte folgen in den nachfolgenden Roadmap-Phasen.
