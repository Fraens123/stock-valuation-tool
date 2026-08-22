# Current Task

## Phase 2/3 Übergang – Universellen Unternehmensimport fertigstellen

ASML bleibt der Referenzfall für Datenqualität, ist aber **keine Voraussetzung** für Suche, Import oder Speicherung neuer Aktien.

## Bereits generalisiert

### 1. Universelle Unternehmenssuche

`pages/0_Unternehmen.py`

- Alpha-Vantage-`SYMBOL_SEARCH` auf bewussten Klick (1 Request),
- neue Unternehmen werden nicht im Code hinterlegt,
- aus einem Provider-Treffer kann direkt eine Analyse angelegt werden,
- ausgewählter Fundamentals-Ticker wird gespeichert.

### 2. Provider-spezifische Identifikatoren

Neue Tabelle `company_provider_symbols`.

Ein Unternehmen kann unterschiedliche Symbole/IDs besitzen für:

- Alpha Vantage Fundamentals,
- später Marktpreis,
- SEC CIK,
- weitere Provider.

Unternehmensidentität bevorzugt ISIN, sonst Ticker + Börse/Region.

### 3. Generischer Alpha-Vantage-Import

`pages/1_Datenimport.py`

- 1 Request: Fundamentals-Verfügbarkeit prüfen,
- 3 Requests: GuV + Bilanz + Cashflow,
- 1 Request separat: Analystenschätzungen,
- fehlende Estimates blockieren die Finanzabschlüsse nicht mehr,
- erfolgreiche Provider-Symbole werden dauerhaft gespeichert.

### 4. Generische Importqualität

`pages/3_Importqualitaet.py`

Für alle Unternehmen:

- Geschäftsjahre,
- bevorzugte Fakten,
- Quellenmix,
- Kernfelder der letzten zwei Jahre,
- Status `PRIMÄRQUELLE`, `API – NICHT PRIMÄRVALIDIERT`, `FEHLT`.

### 5. Generischer offizieller SEC-Fallback

`src/stock_valuation/data/providers/sec.py`
`pages/1_Offizielle_Daten.py`

Für SEC-reporting Unternehmen:

- SEC-Ticker -> CIK auflösen,
- offizieller `companyfacts`-XBRL-Abruf,
- kein API-Key,
- `SEC_USER_AGENT` lokal erforderlich,
- standardisierte US-GAAP- und IFRS-Konzepte werden auf interne Rohdatenschlüssel normalisiert,
- offizielle Fakten werden als `provider=sec_companyfacts`, `source_type=primary_source` gespeichert,
- Source Resolution priorisiert `sec_companyfacts` vor Alpha Vantage,
- Alpha-Vantage-Werte bleiben parallel auditierbar.

### 6. Generischer Europa-Fallback: ESEF / Inline XBRL

`src/stock_valuation/data/providers/esef.py`
`pages/1_Offizielle_Daten.py`

Für europäische IFRS-Emittenten:

- `.xhtml`, `.html`, `.htm` und ESEF-`.zip` werden lokal verarbeitet,
- standardisierte `ifrs-full`-Tags werden auf interne Rohdatenfelder gemappt,
- nicht-dimensionale Hauptabschluss-Kontexte werden bevorzugt,
- Jahresperioden werden von Quartals-/Segmentkontexten getrennt,
- Zahlenformat, Scale, Sign und Währung werden normalisiert,
- offizielle Fakten werden als `provider=esef_ixbrl`, `source_type=primary_source` gespeichert,
- ESEF wird in der Source Resolution vor SEC/Alpha Vantage priorisiert,
- Upload benötigt keine Alpha-Vantage-Requests.

Das zentrale ESAP sammelt seit Juli 2026 Daten, ist laut ESMA für die Öffentlichkeit aber erst spätestens Juli 2027 vorgesehen. V1 ist deshalb nicht von einer heute noch nicht öffentlichen ESAP-Suche abhängig.

## Lokaler Abnahmetest

1. `git pull`
2. `pip install -e ".[dev]"`
3. `pytest -q`
4. `streamlit run app.py`
5. Seite `Unternehmen` öffnen.
6. Eine andere Aktie als ASML suchen, zuerst sinnvoll: `Microsoft`.
7. Analyse anlegen.
8. `Datenimport`:
   - `Fundamentals testen (1 Request)`,
   - `Finanzabschlüsse importieren (3 Requests)`,
   - Estimates optional separat (1 Request).
9. `Importqualität` prüfen.
10. Für SEC-Test lokal `.env` ergänzen:
    `SEC_USER_AGENT=Dein Name deine@email.at`
11. `Offizielle Daten` öffnen.
12. `SEC-Registrierung prüfen (1 Request)`.
13. Falls gefunden: `SEC Company Facts in Snapshot importieren (1 SEC Request)`.
14. `Importqualität` erneut öffnen: SEC-Fakten müssen als Primärquelle vor Alpha Vantage erscheinen.
15. Optional europäischen Fall testen: offiziellen ESEF-XHTML/ZIP-Bericht hochladen, Vorschau prüfen und in Snapshot übernehmen.

## Noch offene Importthemen

- automatische Discovery offizieller ESEF/IR-Dokumente für europäische Emittenten,
- später öffentliche ESAP-Suche/API ergänzen, sobald verfügbar,
- Mapping weiterer IFRS-/US-GAAP-Standardtags erweitern,
- unternehmensspezifische XBRL-Extension-Tags nur kontrolliert und nachvollziehbar behandeln,
- aktueller Marktpreis als eigener Provider-Pfad,
- ISIN/LEI-Anreicherung aus zusätzlichen Referenzquellen,
- optional zweiter breiter Fundamentals-Provider als Fallback, wenn Kosten/Nutzen passt.

## Noch offene Kapitel-2-Methodik

Weiterhin Buchverifikation erforderlich:

- ROE — Kindle S. 94
- Umsatzrendite — Kindle S. 101
- Kapitalumschlag — Kindle S. 107
- Gesamtkapitalrendite — Kindle S. 109
- ROCE — Kindle S. 111
- Umsatzverdienstrate — Kindle S. 114

Keine dieser Formeln eigenmächtig festlegen.

## Definition of Done Universal-Import

- neue Aktie ohne Codeänderung online auffindbar,
- Analyse direkt aus Treffer anlegbar,
- providerbezogene Identifikatoren persistiert,
- Alpha-Vantage-Finanzabschlüsse unabhängig von Estimates importierbar,
- SEC-offizielle Daten für SEC-reporting Unternehmen importierbar,
- ESEF/iXBRL für europäische IFRS-Berichte importierbar,
- Datenqualität für jede Aktie sichtbar,
- kein hart codierter Unternehmensparser als Voraussetzung für den normalen Workflow.
