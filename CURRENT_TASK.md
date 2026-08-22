# Current Task

## Phase 2/3 Übergang – sauberer Neustart mit Preferred Data

ASML bleibt Referenzfall für Datenqualität, ist aber **keine Voraussetzung** für Suche, Import, Prüfung oder Speicherung neuer Aktien.

## Verifizierter Stand

- ASML und Microsoft wurden bereits als Referenzfälle für Import und Datenqualität verwendet.
- Der erste echte Microsoft-ChatGPT-Dateiprüflauf zeigte, warum Providerwerte nicht direkt als Berechnungsbasis dienen dürfen.
- Preferred Data ist als verbindliche Berechnungsschicht implementiert.
- Einzelne Unternehmen können jetzt vollständig aus der lokalen Datenbank entfernt werden.
- Zusätzlich kann der komplette lokale Unternehmens-/Analysedatenbestand geleert werden, ohne DB-Schema oder Anwendung zu löschen.

## Sichtbarer Standardablauf

1. **Übersicht** – alle Unternehmen/Revisionen verwalten und vergleichen.
2. **Unternehmen** – Aktie suchen, Analyse anlegen und bei Bedarf lokale Unternehmen vollständig löschen.
3. **Finanzdaten**
   - `Daten laden / aktualisieren` (Alpha Vantage),
   - kostenlose interne Plausibilitätschecks,
   - ChatGPT-Prüfpaket herunterladen,
   - Prüfpaket im normalen ChatGPT mit Websuche prüfen lassen,
   - JSON-Ergebnisdatei zurück in das Tool laden,
   - WARN/FAIL/UNKLAR prüfen,
   - pro sicherer Abweichung `Übernehmen` oder `Verwerfen`,
   - optional manuell korrigieren.
4. **Manuelle Daten** – Aktienfinder, Management Guidance, risikofreier Zins.
5. **Kennzahlen** – ausschließlich **berechnungsbereite Preferred Data** verwenden.

Später folgen Geschäftsmodell, Bewertung, Investmentthese und Report.

## Unternehmen vollständig löschen

Implementiert in:
- `src/stock_valuation/companies/deletion.py`
- `pages/0_Unternehmen.py`
- `tests/test_company_deletion.py`

### Einzellöschung

Unter `Unternehmen -> Datenverwaltung – Unternehmen löschen` kann ein Unternehmen ausgewählt werden.
Zur Bestätigung muss der Ticker eingegeben werden.

Gelöscht werden zusammen mit dem Unternehmen insbesondere:
- alle Analysen und Revisionen,
- Finanzdaten und Adjustments,
- Analystenschätzungen und Guidance,
- manuelle Inputs/Overrides,
- operative Daten,
- Kennzahlen-Snapshots,
- qualitative Einschätzungen,
- Bewertungsannahmen und -ergebnisse,
- Investmentthese,
- ChatGPT-Prüfläufe und Findings,
- providerbezogene Symbole.

### Alle Unternehmen löschen

Im selben Bereich gibt es `Alle Unternehmen`.
Zur Bestätigung muss exakt `ALLE LÖSCHEN` eingegeben werden.
Die Datenbankstruktur bleibt bestehen; danach kann ein Unternehmen wieder frisch als R1 angelegt werden.

## Preferred Data / Calculation Readiness

Implementiert in:
- `src/stock_valuation/data/resolution.py` – wählt den bevorzugten gespeicherten Wert,
- `src/stock_valuation/data/preferred_data.py` – bewertet separat, ob dieser Wert berechnungsbereit ist,
- `src/stock_valuation/metrics/service.py` – verwendet nur berechnungsbereite Preferred Data,
- `pages/4_Kennzahlen.py` – zeigt Datenfreigabestatus sichtbar an.

### Source Resolution

Priorität für dasselbe Feld/Jahr:

1. bestätigter `manual_override`,
2. offizielle Primärquelle (`asml_primary`, SEC, ESEF/iXBRL),
3. Alpha Vantage,
4. weitere Fallback-Provider.

Die niedrigeren Quellen bleiben vollständig gespeichert und auditierbar.

### Calculation Readiness

Berechnungsbereit:
- bestätigter Override,
- eindeutig gemappte Primärquelle,
- Providerwert mit ChatGPT-Review `PASS`,
- bestehendes ASML-Referenzgate mit Primärquellenfreigabe.

Nicht berechnungsbereit:
- ungeprüfter Providerwert,
- `WARN`/`FAIL` ohne akzeptierten Override,
- `UNKLAR`,
- veralteter Review, der nicht mehr exakt zum Preferred Fact passt,
- fertiges Provider-EBITDA (`derive_required`).

Ein verworfener ChatGPT-Korrekturvorschlag bestätigt den alten Providerwert **nicht automatisch**.

## Interne Felddefinitionen

Zentral in `src/stock_valuation/data/preferred_data.py` und `docs/RAW_DATA_SCHEMA.md`:

- `ppe_net`: reine Netto-Sachanlagen; separat ausgewiesene Operating-Lease-ROU-Assets ausgeschlossen.
- `short_term_debt`: zinstragende Schulden mit Fälligkeit <= 12 Monate einschließlich Current Portion of Long-Term Debt; AP und Lease Liabilities getrennt.
- `depreciation_amortization`: reine Abschreibungen + Amortisation; kein automatisches `and other`.
- `ebitda`: selbst aus freigegebenem EBIT + freigegebenem D&A berechnen; Provider-EBITDA nur Cross-Check.

Diese Definitionen werden in neue ChatGPT-Prüfpakete eingebettet.

## Kennzahlenengine

- Berechnungsversion: `3a-0.3`.
- EBIT-Marge:
  - ASML: validiertes `operating_income` / Revenue gemäß D-012,
  - andere Unternehmen: freigegebenes internes `ebit` / Revenue; `operating_income` wird nicht still gleichgesetzt.
- EBITDA-Marge:
  - (freigegebenes EBIT + freigegebenes D&A) / Revenue,
  - Provider-EBITDA wird nicht direkt verwendet.

## ChatGPT-Dateiprüfung ohne separate API-Abrechnung

- keine OpenAI Responses API im normalen Workflow,
- kein `OPENAI_API_KEY` erforderlich,
- keine `openai`-Python-Abhängigkeit,
- Prüfpaket enthält Unternehmensidentität, Fact-IDs, Providerfelder, Werte, lokale Plausibilitätschecks, interne Felddefinitionen und verbindlichen Prüfauftrag,
- Rückimport validiert Schema-Version, Package-ID, Ticker, Stichtag, Revision und Fact-IDs,
- Ergebnisse werden lokal als `AIReviewRun` und `AIReviewFinding` gespeichert.

## Lokaler Abnahmetest jetzt – kompletter ASML-Neustart

1. `git pull`
2. `pytest -q`
3. `streamlit run app.py`
4. `Unternehmen` öffnen.
5. `Datenverwaltung – Unternehmen löschen` aufklappen.
6. Tab `Alle Unternehmen` öffnen.
7. `ALLE LÖSCHEN` eingeben und Löschung ausführen.
8. Prüfen: `Gespeicherte Unternehmen` ist leer; Übersicht zeigt 0 Unternehmen / 0 Analysen.
9. ASML neu suchen und als frische Analyse R1 anlegen.
10. Unter `Finanzdaten` den Alpha-Vantage-Import neu durchführen.
11. Danach ein neues ChatGPT-Prüfpaket erzeugen und den kompletten neuen Datenpfad testen.

## Noch offene Import-/Prüfthemen

- kompletten ASML-Neustart lokal durchführen,
- ASML-Neuimport mit Preferred-Data-Status prüfen,
- neue ChatGPT-Prüfung mit den zentralen Felddefinitionen testen,
- weitere semantisch kritische Rohfelder schrittweise in `FIELD_DEFINITIONS` aufnehmen,
- aktuellen Marktpreis automatisch laden und Listing/Währung sauber trennen,
- automatische Primärquellen-Discovery dort ergänzen, wo zuverlässig möglich,
- SEC-/ESEF-Mappings erweitern,
- ISIN/LEI-Anreicherung verbessern,
- optional zweiten breiten Fundamentals-Provider als Fallback prüfen.

## Noch offene Kapitel-2-Methodik

Weiterhin Buchverifikation erforderlich:
- ROE — Kindle S. 94
- Umsatzrendite — Kindle S. 101
- Kapitalumschlag — Kindle S. 107
- Gesamtkapitalrendite — Kindle S. 109
- ROCE — Kindle S. 111
- Umsatzverdienstrate — Kindle S. 114

Keine dieser Formeln eigenmächtig festlegen.
