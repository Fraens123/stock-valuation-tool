# Current Task

## Phase 2.1 – ASML-Datenimport und Snapshot-Persistenz

Phase 0 ist implementiert. Phase 1 hat das bestehende Excel fachlich inventarisiert, den Kennzahlen-/Qualitativkatalog aufgebaut, das Rohdatenschema definiert und offene Methodikfragen ausdrücklich markiert.

Exakte Buchfragen, die ohne vollständigen Text nicht sicher auflösbar sind, bleiben in `docs/METHODOLOGY_OPEN_QUESTIONS.md` offen und dürfen die Datenpipeline nicht zu erfundenen Definitionen verleiten.

## Vor Beginn lesen

1. `AGENTS.md`
2. `ROADMAP.md`
3. `docs/PHASE_1_METRIC_INVENTORY.md`
4. `docs/RAW_DATA_SCHEMA.md`
5. `docs/ASML_DATA_MAPPING.md`
6. `docs/NORMALIZATION_POLICY.md`
7. `docs/DATA_SOURCES.md`
8. `docs/METHODOLOGY_OPEN_QUESTIONS.md`
9. `src/stock_valuation/data/mappings/eodhd.yaml`

## Bereits vorbereitet

- EODHD Fundamentals v1.1 Adapter
- maschinenlesbares EODHD-Feldmapping
- Provider-unabhängige Datentypen
- Normalisierung für GuV, Bilanz und Cashflow
- Normalisierung für Annual Analyst Estimates
- Snapshot-Service zum reproduzierbaren Import in eine offene Analyse
- Provenienzfelder im Datenmodell
- Tests mit lokalem Beispielpayload; keine Tests benötigen einen Live-API-Key

## Ziel dieses Blocks

### A. EODHD Live-Import lokal validieren

Mit lokalem `EODHD_API_KEY`:

1. `ASML.AS` Fundamentals v1.1 laden.
2. tatsächlichen Payload gegen `eodhd.yaml` prüfen.
3. mindestens zehn Jahresperioden, soweit Provider verfügbar, erfassen.
4. fehlende Felder explizit protokollieren.
5. keine stillen Ersatzfelder erfinden.

### B. ASML-Primärquellenvalidierung

- 2025 EODHD-Daten gegen offizielles ASML Financial-Statements-Excel / Annual Report prüfen.
- Kernfelder: Revenue, EBIT/Operating Income, Net Income, Assets, Equity, Cash, Debt, OCF, Capex, D&A, Receivables, Inventory, Payables.
- semantische Abweichungen dokumentieren.

### C. Datenimport in Streamlit anbinden

Auf einer editierbaren Analyse:

- Button `Finanzdaten aktualisieren`
- Quelle und Abrufzeit anzeigen
- Importstatistik anzeigen
- bei fehlendem API-Key verständliche Meldung
- auf abgeschlossenen Analysen kein Refresh möglich

### D. Analystenschätzungen prüfen

Für ASML prüfen, welche Annual Trend-Felder tatsächlich verfügbar sind:
- EPS low / average / high
- Revenue low / average / high
- analyst count
- Revisionsdaten optional

Nur tatsächlich gelieferte Werte persistieren.

### E. Management Guidance

Noch nicht automatisch scrapen. Für V1 zentrale manuelle/strukturierte Eingabe vorbereiten:
- Metric
- Period
- Low / Point / High
- Unit / Currency
- Publication Date
- Source URL
- Note

## Noch NICHT tun

- keine Kennzahlenengine aus den importierten Daten bauen
- keine DCF-Engine
- keine Fair-KGV-Punkte erfinden
- keine Risiko-Dropdown-Prozentwerte festlegen
- keine ASML-Schätzung hart codieren

## Definition of Done Phase 2.1

- ASML-Fundamentaldaten können mit API-Key reproduzierbar geladen und in einen Analyse-Snapshot geschrieben werden.
- Providerfeld und Originalwert bleiben auditierbar.
- EODHD-Import ist gegen offizielle ASML-Daten stichprobenartig validiert.
- Estimates werden getrennt gespeichert.
- abgeschlossene Analysen bleiben unveränderlich.
- Live-Import besitzt Tests ohne externe Netzwerkabhängigkeit plus einen dokumentierten manuellen Integrationstest.

Danach: Phase 2.2 ECB-Risikozins, manuelle Aktienfinder-/Guidance-Zentrale und Abschluss der Datenversorgung.
