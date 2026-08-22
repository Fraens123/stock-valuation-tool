# Stock Valuation Tool

Geführtes Aktienanalyse- und Unternehmensbewertungstool in Python/Streamlit.

Die Methodik orientiert sich an der Reihenfolge des bestehenden Excel-Modells und an Nicolas Schmidlin, **Unternehmensbewertung & Kennzahlenanalyse**. Das Tool soll nicht nur einen Fair Value ausgeben, sondern den gesamten Analyseprozess dokumentieren und reproduzierbar machen.

## Kernfunktionen

- Unternehmen über Name, Ticker oder ISIN auswählen
- neue Analyse starten oder ältere Analyse öffnen
- 5–10 Jahre historische Rohdaten laden
- Aktienfinder-Daten zentral manuell ergänzen
- Kennzahlen intern und nachvollziehbar berechnen
- `ⓘ`-Erklärung je Kennzahl mit Bedeutung, Formel, Interpretation, Fallstricken und Kindle-Seite
- qualitative Geschäftsmodellanalyse mit eigener Begründung und Quellen
- Equity- und Enterprise-Value-Multiplikatoren
- faires KGV nach Schmidlin-Logik
- Equity-DCF / Owner Earnings
- Worst/Base/Best und später probabilistische Szenarien
- Analyse-Snapshots und Revisionen
- Vergleich alter und neuer Analysen mit Änderungsübersicht
- PDF-Kurzreport und vollständiger Analysebericht

## Referenzunternehmen

**ASML Holding N.V. (`ASML.AS`)** ist das Referenzunternehmen für Entwicklung, Tests und Plausibilisierung.

## Technischer Stack

- Python 3.12+
- Streamlit
- SQLAlchemy + SQLite lokal
- pandas / numpy
- requests
- Plotly
- ReportLab für PDF V1
- pytest / ruff
- GitHub + Codex/Copilot

## Projektsteuerung

- `AGENTS.md` – verbindliche Regeln für Codex/Copilot
- `ROADMAP.md` – vollständige Entwicklungsreihenfolge
- `docs/` – Fachmethodik, Datenmodell, DCF, Quellen, Report-Spezifikation

## Geplanter Nutzer-Workflow

1. Unternehmen suchen/auswählen
2. Neue Analyse starten oder bestehende Analyse öffnen
3. Daten aktualisieren
4. Kennzahlen analysieren
5. Geschäftsmodell und qualitative Kriterien dokumentieren
6. Bewertungskennzahlen prüfen
7. faires KGV bestimmen
8. DCF und Szenarien rechnen
9. Investmentthese und Risiken dokumentieren
10. Analyse abschließen/frieren
11. optional mit älterer Revision vergleichen
12. PDF-Report exportieren

## Lokaler Start nach dem Clone

```bash
git clone https://github.com/Fraens123/stock-valuation-tool.git
cd stock-valuation-tool
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
streamlit run app.py
```

API-Keys gehören ausschließlich in `.env` und niemals ins Repository.
