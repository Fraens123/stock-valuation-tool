# Lokaler Workflow mit Codex in VS Code

## Einmalige Einrichtung

```bash
git clone https://github.com/Fraens123/stock-valuation-tool.git
cd stock-valuation-tool
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
pytest -q
streamlit run app.py
```

Danach `.env.example` nach `.env` kopieren und später API-Keys nur lokal eintragen.

## Wichtigste Datei für Codex

`AGENTS.md` ist die verbindliche Projektanweisung. Codex soll sie vor Änderungen lesen.

Zusätzlich gilt:
- `ROADMAP.md` sagt, **was** als Nächstes gebaut wird.
- `docs/` sagt, **wie und warum** es fachlich gebaut wird.

## Empfohlene Prompts

### Nächsten Roadmap-Punkt bearbeiten

> Lies zuerst AGENTS.md, ROADMAP.md und die relevanten Dateien in docs/. Bearbeite ausschließlich Roadmap Phase 0.2. Erstelle vor Änderungen einen kurzen Plan. Implementiere Tests. Ändere Bewertungsmethodik nicht ohne DECISIONS.md zu aktualisieren. Führe am Ende pytest aus und fasse geänderte Dateien und offene Punkte zusammen.

### Bestehende Implementierung prüfen

> Prüfe den aktuellen Stand gegen AGENTS.md und ROADMAP.md. Nenne zuerst Abweichungen, Bugs und fehlende Tests. Nimm noch keine methodischen Änderungen vor.

### Fachliche Berechnungslogik implementieren

> Implementiere nur die in docs/EXCEL_MAPPING.md und der entsprechenden Methodikdatei spezifizierte Kennzahl. Keine alternative Definition erfinden. Wenn die Definition nicht eindeutig ist, stoppe und markiere die Frage als fachlich offen.

## Branch-/Commit-Empfehlung

Für größere Schritte:

```text
feature/phase-0-company-search
feature/phase-2-eodhd
feature/phase-3-roe
feature/phase-7-dcf-v1
```

Ein Commit sollte einen klaren fachlichen/technischen Schritt abbilden.

## Was niemals ins Repository darf

- `.env`
- API-Keys
- Aktienfinder-Zugangsdaten
- Cookies/Sessions
- lokale SQLite-Datenbanken mit persönlichen Analysen
- exportierte private Analyse-PDFs, sofern nicht bewusst als anonymisierte Testfixtures vorgesehen
