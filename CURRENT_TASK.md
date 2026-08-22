# Current Task

## Phase 2/3 Übergang – Import, KI-Prüfung und Bedienung vereinfachen

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
   - `KI-Prüfung starten` gegen offizielle Webquellen,
   - WARN/FAIL/UNKLAR prüfen,
   - pro sicherer Abweichung `Übernehmen` oder `Verwerfen`,
   - optional manuell korrigieren.
4. **Manuelle Daten** – Aktienfinder, Management Guidance, risikofreier Zins.
5. **Kennzahlen** – nur gespeicherte Snapshot-Daten verwenden.

Später folgen Geschäftsmodell, Bewertung, Investmentthese und Report.

## Direkte KI-Prüfung

Implementiert in:
- `src/stock_valuation/analyses/ai_review_service.py`
- `src/stock_valuation/database/ai_review_models.py`
- `pages/1_Datenimport.py`

### Technischer Ablauf

- OpenAI Responses API mit eingebautem `web_search`.
- Konfiguration lokal über:
  - `OPENAI_API_KEY`
  - optional `OPENAI_REVIEW_MODEL` (Default `gpt-5.4`).
- Standardprüfung: letzte 3 Geschäftsjahre; UI erlaubt 2 / 3 / 5 Jahre.
- Nur nicht als Cross-Check markierte FY-Fakten aus GuV, Bilanz und Cashflow werden eingereicht.
- Web-Recherche priorisiert Annual Report, 10-K/20-F, regulatorische Filings und offizielle Investor-Relations-Unterlagen.
- Structured Outputs erzwingen pro eingereichtem `fact_id` ein Ergebnis.
- Status: `PASS`, `WARN`, `FAIL`, `UNKLAR`.
- API-Response wird mit `store=False` angefordert; der benötigte Review-Output wird lokal in SQLite gespeichert.

### Review-Persistenz

`ai_review_runs`
- Modell, geprüfte Jahre, Response-ID, Summary, Zeitstempel.

`ai_review_findings`
- Jahr/Periode, interner Schlüssel, importierter Wert, offizieller Wert,
- Abweichung, Verdict, offizielle Bezeichnung, Quellen-URL, Begründung,
- Entscheidung `pending / accepted / rejected`.

### Sicherheitsregel

Die KI ändert **niemals selbst Finanzdaten**.

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
4. `.env` ergänzen:
   - `OPENAI_API_KEY=<dein API-Key>`
   - optional `OPENAI_REVIEW_MODEL=gpt-5.4`
5. `streamlit run app.py`
6. Microsoft unter `Finanzdaten` öffnen; kein neuer Alpha-Vantage-Import nötig.
7. Unter `Daten prüfen` zunächst 2 oder 3 Geschäftsjahre auswählen.
8. `KI-Prüfung starten` drücken.
9. Prüfen: Summary + PASS/WARN/FAIL/UNKLAR erscheinen; Standardansicht blendet PASS aus.
10. Bei einem sicheren WARN/FAIL:
    - offizielle Quelle öffnen,
    - einmal `Übernehmen` testen,
    - prüfen, dass ein bestätigter Override erscheint und der Alpha-Vantage-Originalwert erhalten bleibt.
11. Einen anderen Vorschlag `Verwerfen`; Finanzwert darf sich nicht ändern.

## Noch offene Import-/Prüfthemen

- realen Microsoft-KI-Lauf testen und Prompt/Schema anhand der Ergebnisse nachschärfen,
- Kosten-/Tokenanzeige aus API-Usage später ergänzen,
- Review ggf. in kleinere Batches teilen, falls große 5-Jahres-Prüfungen zu langsam/teuer werden,
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
