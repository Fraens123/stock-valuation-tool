# Architektur

## Ziel

Die Anwendung besteht aus klar getrennten Schichten. Streamlit ist nur die Oberfläche; Bewertungslogik und Datenmodell müssen unabhängig davon testbar bleiben.

```text
app.py
  |
  v
ui/ -------------------------------> reports/
  |                                    |
  v                                    v
services/analysis_service.py       PDF aus Snapshot
  |
  +--> companies/
  +--> analyses/
  +--> metrics/
  +--> valuation/
  |
  v
database/repositories.py
  |
  v
SQLite

Externe Daten:
data/providers/ -> normalizer -> Snapshot-Tabellen
```

## Zielstruktur

```text
stock-valuation-tool/
├── AGENTS.md
├── ROADMAP.md
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── app.py
├── docs/
│   ├── ARCHITECTURE.md
│   ├── ANALYSIS_LIFECYCLE.md
│   ├── DATA_MODEL.md
│   ├── DATA_SOURCES.md
│   ├── BOOK_MAPPING.md
│   ├── DCF_METHOD.md
│   ├── REPORT_SPEC.md
│   └── DECISIONS.md
├── src/stock_valuation/
│   ├── companies/
│   ├── analyses/
│   ├── database/
│   ├── data/providers/
│   ├── metrics/
│   ├── valuation/
│   ├── knowledge/
│   ├── reports/
│   └── ui/
├── tests/
└── data/
    └── .gitkeep
```

## Schichten

### Domain
Unternehmen, Analyse, Snapshot, Szenario und Bewertungsobjekte ohne Streamlit-Abhängigkeit.

### Provider
Jeder externe Anbieter wird hinter einem Interface gekapselt. Provider-Rohfelder dürfen nicht direkt in Bewertungsformeln verwendet werden; zuerst normalisieren.

### Database
SQLite V1. Repositories kapseln SQLAlchemy. Domain-Services sollen nicht von konkretem SQLite-Code abhängen.

### Metrics
Reine, testbare Funktionen/Klassen für Kennzahlen.

### Valuation
DCF, Multiples, faires KGV, Szenarien. Keine UI-Aufrufe.

### UI
Streamlit zeigt Domain-Ergebnisse, sammelt Eingaben und ruft Services auf.

### Reports
PDF wird ausschließlich aus einem gespeicherten Snapshot erzeugt. Keine Live-API-Aufrufe beim Report-Rendering.
