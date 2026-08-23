# Architektur

## Ziel

Die Anwendung besteht aus klar getrennten Schichten. Streamlit ist nur die Oberfläche; Bewertungslogik und Datenmodell müssen unabhängig davon testbar bleiben.

```text
app.py / pages/
  |
  v
ui/ -------------------------------> reports/
  |                                    |
  v                                    v
Domain-/Application-Services       PDF aus Snapshot
  |
  +--> companies/
  +--> analyses/
  +--> data/source_router.py
  +--> metrics/
  +--> valuation/
  |
  v
database / SQLAlchemy
  |
  v
SQLite
```

## Externe Datenarchitektur

Historische Finanzdaten laufen nicht direkt von einem Provider in Berechnungen.

```text
Unternehmenssuche
  ↓
Identity Resolver
  ├─ SEC: Ticker/Name → CIK
  └─ GLEIF: Legal Name → LEI
  ↓
Source Router
  ├─ SEC Company Facts
  ├─ ESEF / xBRL-JSON
  └─ Alpha Vantage optionaler Fallback
  ↓
Provider-spezifischer Parser
  ↓
NormalizedFinancialFact
  ↓
FinancialFactSnapshot + Provenienz
  ↓
Source Resolution
  ↓
Calculation Readiness / Preferred Data
  ↓
Kennzahlen / Bewertung
```

### Identity Layer

Ticker, CIK, LEI, ISIN und Provider-Symbole sind getrennte Identifikatoren. `CompanyProviderSymbol` speichert provider-/zweckspezifische Kennungen, ohne `Company.ticker` zu überladen.

### Source Router

`data/source_router.py` entscheidet, welche kohärente historische Quelle für einen Analyse-Snapshot genutzt wird. Standardreihenfolge:

1. SEC Company Facts
2. ESEF
3. Alpha Vantage nur als expliziter Fallback

Der Router darf nicht still einzelne Felder verschiedener Provider zu einem scheinbar einheitlichen Abschluss zusammensetzen.

### Provider

Jeder externe Anbieter wird hinter einer eigenen Adapter-/Parser-Schicht gekapselt. Provider-Rohfelder dürfen nicht direkt in Bewertungsformeln verwendet werden.

Aktuelle Bausteine:
- `data/providers/sec.py`
- `data/providers/gleif.py`
- `data/providers/esef_registry.py`
- `data/providers/esef.py` für ESEF-XHTML/ZIP-Parsing
- `data/providers/alphavantage.py`
- weitere Adapter/Fallbacks

### Normalisierung

Alle Quellen werden in `NormalizedFinancialFact` überführt. Gespeichert bleiben insbesondere:
- internes Feld
- Original-/Providerwert
- Original-XBRL-/Providerfeld
- Periode
- Währung / Einheit
- Filing-/Abrufdatum
- Quelle / konkrete URL, soweit verfügbar
- Provider / Source Type

### Source Resolution vs. Calculation Readiness

Diese zwei Schritte sind absichtlich getrennt:

- **Source Resolution** bestimmt den bevorzugten gespeicherten Fakt für `(metric, period)`.
- **Calculation Readiness** entscheidet, ob seine Semantik ausreichend sicher ist, um Kennzahlen/Bewertungen zu speisen.

Eine offizielle Primärquelle ist also nicht automatisch ein Freibrief für jedes XBRL-Mapping. Bekannte mehrdeutige Zuordnungen bleiben bis zur semantischen Prüfung blockiert.

## Zielstruktur

```text
stock-valuation-tool/
├── AGENTS.md
├── ROADMAP.md
├── CURRENT_TASK.md
├── app.py
├── pages/
├── docs/
├── src/stock_valuation/
│   ├── companies/
│   │   ├── discovery.py
│   │   └── provider_symbols.py
│   ├── analyses/
│   ├── database/
│   ├── data/
│   │   ├── source_router.py
│   │   ├── preferred_data.py
│   │   ├── resolution.py
│   │   └── providers/
│   ├── metrics/
│   ├── valuation/
│   ├── knowledge/
│   ├── reports/
│   └── ui/
├── tests/
└── data/
    └── cache/   # gitignored
```

## Schichten

### Domain
Unternehmen, Analyse, Snapshot, Szenario und Bewertungsobjekte ohne Streamlit-Abhängigkeit.

### Database
SQLite V1. Repositories/Services kapseln SQLAlchemy. Domain-Services sollen nicht von konkretem SQLite-Code abhängen.

### Metrics
Reine, testbare Funktionen/Klassen für Kennzahlen. Nur calculation-ready Preferred Data verwenden.

### Valuation
DCF, Multiples, faires KGV, Szenarien. Keine UI-Aufrufe und keine direkten Providerzugriffe.

### UI
Streamlit zeigt Domain-Ergebnisse, sammelt Eingaben und ruft Services auf. Providerentscheidungen sollen im Normalfall automatisch erfolgen; technische Details werden nur bei Bedarf eingeblendet.

### Reports
PDF wird ausschließlich aus einem gespeicherten Snapshot erzeugt. Keine Live-API-Aufrufe beim Report-Rendering.
