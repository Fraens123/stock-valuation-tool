# Current Task

## Phase 2/3 Übergang – Preferred Data als verbindliche Berechnungsbasis

ASML bleibt Referenzfall für Datenqualität, ist aber **keine Voraussetzung** für Suche, Import, Prüfung oder Speicherung neuer Aktien.

## Verifizierter Stand

- ASML wurde erfolgreich importiert und gegen offizielle Primärquellen geprüft.
- Microsoft wurde als zweite, nicht hart codierte Aktie erfolgreich importiert.
- Microsoft-Snapshot: 740 Finanzdatenpunkte über 20 Geschäftsjahre; 32/32 definierte Core-Felder der letzten zwei Geschäftsjahre vorhanden.
- Analystenschätzungen wurden erfolgreich geladen.
- Erster echter Microsoft-ChatGPT-Dateiprüflauf durchgeführt: 92 Fakten, 81 PASS, 2 FAIL (`ppe_net` 2024/2025), 9 UNKLAR (`short_term_debt`, D&A, EBITDA über drei Jahre).
- Alpha-Vantage-Import ist damit für unterstützte Symbole unternehmensunabhängig bestätigt, aber Providerwerte werden nicht pauschal als berechnungsbereit betrachtet.

## Sichtbarer Standardablauf

1. **Übersicht** – alle Unternehmen/Revisionen verwalten und vergleichen.
2. **Unternehmen** – Aktie suchen und Analyse anlegen.
3. **Finanzdaten**
   - `Daten laden / aktualisieren` (Alpha Vantage, normalerweise 4 Requests),
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

Diese Definitionen werden in neue ChatGPT-Prüfpakete eingebettet. Die Package-ID basiert weiterhin auf Snapshot-Identität und Fakten, damit bereits erzeugte Ergebnisdateien bei unverändertem Snapshot kompatibel bleiben.

## Kennzahlenengine

- Berechnungsversion: `3a-0.3`.
- EBIT-Marge:
  - ASML: validiertes `operating_income` / Revenue gemäß D-012,
  - andere Unternehmen: freigegebenes internes `ebit` / Revenue; `operating_income` wird nicht still gleichgesetzt.
- EBITDA-Marge:
  - (freigegebenes EBIT + freigegebenes D&A) / Revenue,
  - Provider-EBITDA wird nicht direkt verwendet.
- Für Microsoft kann nach Import des Prüfergebnisses die EBIT-Marge aus den geprüften Jahren berechnet werden.
- Microsoft-EBITDA-Marge bleibt bewusst blockiert, solange D&A `UNKLAR` ist.

## ChatGPT-Dateiprüfung ohne separate API-Abrechnung

- keine OpenAI Responses API im normalen Workflow,
- kein `OPENAI_API_KEY` erforderlich,
- keine `openai`-Python-Abhängigkeit,
- UI erlaubt 2 / 3 / 5 tief zu prüfende Geschäftsjahre,
- Prüfpaket enthält Unternehmensidentität, Fact-IDs, Providerfelder, Werte, lokale Plausibilitätschecks, interne Felddefinitionen und verbindlichen Prüfauftrag,
- Rückimport validiert Schema-Version, Package-ID, Ticker, Stichtag, Revision und Fact-IDs,
- Ergebnisse werden lokal als `AIReviewRun` und `AIReviewFinding` gespeichert.

## Lokaler Abnahmetest jetzt

1. `git pull`
2. `pip install -e ".[dev]"`
3. `pytest -q`
4. `streamlit run app.py`
5. Microsoft unter `Finanzdaten` öffnen.
6. Bereits erzeugte Microsoft-JSON-Datei einlesen, falls noch nicht erfolgt.
7. Die beiden `ppe_net`-FAIL-Vorschläge 2024/2025 prüfen und bei bestätigter Quelle `Übernehmen`.
8. `Kennzahlen` öffnen.
9. Preferred-Data-Status prüfen: PASS-Inputs müssen berechnungsbereit sein; D&A/EBITDA müssen blockiert bleiben.
10. `Aktive Kennzahlen aus Preferred Data berechnen` drücken.
11. Erwartung Microsoft: EBIT-Marge für die verifizierten Jahre wird erzeugt; EBITDA-Marge bleibt 0/blockiert.
12. Prüfen, dass Rohdaten von Alpha Vantage weiterhin sichtbar/gespeichert bleiben und die PP&E-Overrides separat existieren.

## Noch offene Import-/Prüfthemen

- realen Microsoft-Rückimport lokal testen und Preferred-Data-UI anhand der Anzeige nachschärfen,
- nächste Microsoft-Prüfung mit den neuen Felddefinitionen testen; `short_term_debt` sollte dadurch eindeutiger klassifizierbar sein,
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
