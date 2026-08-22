# Current Task

## Phase 2/3 Übergang – Import, ChatGPT-Prüfung und Bedienung vereinfachen

ASML bleibt Referenzfall für Datenqualität, ist aber **keine Voraussetzung** für Suche, Import oder Speicherung neuer Aktien.

## Verifizierter Stand

- ASML wurde erfolgreich importiert und gegen offizielle Primärquellen geprüft.
- Microsoft wurde als zweite, nicht hart codierte Aktie erfolgreich importiert.
- Microsoft-Snapshot: 740 Finanzdatenpunkte über 20 Geschäftsjahre; 32/32 definierte Core-Felder der letzten zwei Geschäftsjahre vorhanden.
- Analystenschätzungen wurden ebenfalls erfolgreich geladen.
- Alpha-Vantage-Import ist damit für unterstützte Symbole unternehmensunabhängig bestätigt.

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
5. **Kennzahlen** – nur gespeicherte Snapshot-Daten verwenden.

Später folgen Geschäftsmodell, Bewertung, Investmentthese und Report.

## ChatGPT-Dateiprüfung ohne separate API-Abrechnung

Implementiert in:
- `src/stock_valuation/analyses/ai_review_service.py`
- `src/stock_valuation/database/ai_review_models.py`
- `pages/1_Datenimport.py`
- `docs/AI_DATA_REVIEW.md`

### Technischer Ablauf

- **keine OpenAI Responses API im normalen Workflow**,
- kein `OPENAI_API_KEY` erforderlich,
- keine `openai`-Python-Abhängigkeit,
- UI erlaubt 2 / 3 / 5 tief zu prüfende Geschäftsjahre,
- nur nicht als Cross-Check markierte FY-Fakten aus GuV, Bilanz und Cashflow kommen ins Prüfpaket,
- Prüfpaket enthält Unternehmensidentität, Fact-IDs, Providerfelder, Werte, lokale Plausibilitätschecks und einen ausführlichen verbindlichen Prüfauftrag,
- Web-Recherche in ChatGPT soll Annual Report, 10-K/20-F, regulatorische Filings und offizielle Investor-Relations-Unterlagen priorisieren,
- ChatGPT soll eine strikt strukturierte JSON-Ergebnisdatei erzeugen,
- Rückimport validiert Schema-Version, Package-ID, Ticker, Stichtag, Revision und Fact-IDs.

### Package-ID / Snapshot-Sicherheit

Die Package-ID ist ein SHA-256-Hash des exportierten Datenpakets.

Wenn nach dem Export:
- Daten geändert werden,
- eine andere Revision gewählt wird,
- ein anderes Unternehmen gewählt wird,

passt die zurückgeladene Ergebnisdatei nicht mehr und wird abgelehnt.

### Review-Persistenz

`ai_review_runs`
- geprüfte Jahre, Package-ID, Summary, Zeitstempel,
- `model=chatgpt_file_review` als Herkunftskennzeichnung.

`ai_review_findings`
- Jahr/Periode, interner Schlüssel, importierter Wert, offizieller Wert,
- Abweichung, Verdict, offizielle Bezeichnung, Quellen-URL, Begründung,
- Entscheidung `pending / accepted / rejected`.

### Sicherheitsregel

ChatGPT ändert **niemals selbst Finanzdaten**.

`Übernehmen`:
- erzeugt einen separaten `manual_override`,
- Original-Providerwert bleibt erhalten,
- Quellen-URL und Begründung werden gespeichert,
- Source Resolution verwendet danach den bestätigten Override.

`Verwerfen`:
- ändert keinen Finanzwert,
- speichert nur die Entscheidung im Review-Finding.

## UI / Navigation

- eigene Sidebar: `Übersicht`, `Unternehmen`, `Finanzdaten`, `Manuelle Daten`, `Kennzahlen`.
- technische Diagnosewerkzeuge sind kein normaler Arbeitsschritt.
- `app.py` ist die Übersicht über alle Unternehmen und Analyse-Snapshots, keine ASML-Sonderseite.

## Estimate-Logik

Alpha Vantage `EARNINGS_ESTIMATES` enthält Jahres- und Quartalsschätzungen im selben Endpoint.
- Geschäftsjahresende wird aus FY-Daten abgeleitet,
- Standardansicht zeigt nur Jahresschätzungen,
- Quartale/Historie optional,
- spätere DCF-Logik nutzt Jahreswerte.

## Lokaler Abnahmetest jetzt

1. `git pull`
2. `pip install -e ".[dev]"`
3. `pytest -q`
4. `streamlit run app.py`
5. Microsoft unter `Finanzdaten` öffnen; kein neuer Alpha-Vantage-Import nötig.
6. Unter `Daten prüfen` zunächst 2 Geschäftsjahre auswählen.
7. `ChatGPT-Prüfpaket herunterladen`.
8. Prüfpaket in ChatGPT hochladen und schreiben: `Führe die Prüfung aus und erstelle die angeforderte JSON-Ergebnisdatei.`
9. Von ChatGPT erzeugte JSON-Datei herunterladen.
10. JSON unter `ChatGPT-Prüfergebnis hochladen` auswählen und `Prüfergebnis einlesen`.
11. Prüfen: Summary + PASS/WARN/FAIL/UNKLAR erscheinen; Standardansicht blendet PASS aus.
12. Bei einem sicheren WARN/FAIL:
    - offizielle Quelle öffnen,
    - einmal `Übernehmen` testen,
    - prüfen, dass ein bestätigter Override erscheint und der Alpha-Vantage-Originalwert erhalten bleibt.
13. Einen anderen Vorschlag `Verwerfen`; Finanzwert darf sich nicht ändern.

## Noch offene Import-/Prüfthemen

- ersten echten Microsoft-Dateiprüflauf durchführen und Prompt/Schema nachschärfen,
- entscheiden, welche Kernfelder standardmäßig tief geprüft werden sollen,
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
