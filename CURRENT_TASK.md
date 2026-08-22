# Current Task

## Phase 2/3 Übergang – Universellen Unternehmensimport fertigstellen

ASML bleibt Referenzfall für Datenqualität, ist aber **keine Voraussetzung** für Suche, Import oder Speicherung neuer Aktien.

## Verifizierter Stand

- ASML wurde erfolgreich importiert und gegen offizielle Primärquellen geprüft.
- Microsoft wurde als zweite, nicht hart codierte Aktie erfolgreich importiert.
- Microsoft-Snapshot: 740 Finanzdatenpunkte über 20 Geschäftsjahre; 32/32 definierte Core-Felder der letzten zwei Geschäftsjahre vorhanden.
- Analystenschätzungen wurden ebenfalls erfolgreich geladen.

Damit ist bestätigt: Der automatische Fundamentals-Import funktioniert unternehmensunabhängig für von Alpha Vantage unterstützte Symbole.

## Vereinfachter Anwender-Workflow

Der normale Workflow darf keine Diagnosekette sein.

### Sichtbarer Standardablauf

1. `Unternehmen`
   - Aktie online suchen,
   - richtigen Provider-Treffer auswählen,
   - Analyse anlegen.
2. `Datenimport` / Finanzdaten
   - **ein Button: `Daten laden / aktualisieren`**,
   - intern 3 Requests für GuV/Bilanz/Cashflow,
   - intern 1 Request für Analystenschätzungen,
   - Finanzabschlüsse werden zuerst gespeichert; ein Estimate-Fehler löscht sie nicht.
3. `Kennzahlen`
   - gespeicherte Snapshot-Daten verwenden.
4. später Geschäftsmodell, Bewertung, Investmentthese und Report.

### Diagnose nicht im normalen Menü

Die früher sichtbaren Seiten

- Offizielle Daten,
- Datenqualität,
- Importqualität

wurden aus der normalen `pages/`-Navigation entfernt. Technische Werkzeuge liegen nun unter `diagnostics/` und sind kein notwendiger Arbeitsschritt.

## Estimate-Logik

Alpha Vantage `EARNINGS_ESTIMATES` enthält Jahres- und Quartalsschätzungen im selben Endpoint.

Neu:
- Geschäftsjahresende wird aus den gespeicherten FY-Abschlussdaten des Unternehmens abgeleitet,
- Estimates mit diesem Geschäftsjahresende werden als `Jahr` klassifiziert,
- andere datierte Estimates als `Quartal`,
- normale Ansicht zeigt standardmäßig nur Jahresschätzungen,
- Quartale und historische Estimate-Historie sind optional einblendbar,
- spätere DCF-/Forecast-Logik darf nur die Jahresschätzungen automatisch als Jahresinput verwenden.

Beispiel Microsoft:
- Geschäftsjahresende 30.06.,
- 2026-09-30 / 2026-12-31 = Quartal,
- 2027-06-30 / 2028-06-30 = Jahr.

## Universelle Datenarchitektur

### Alpha Vantage

- `SYMBOL_SEARCH` für Unternehmenssuche,
- providerbezogene Fundamentals-Symbole werden persistiert,
- 20+ Jahre Abschlusshistorie möglich,
- Estimates separat speicherbar.

### Offizielle Primärquellen

Nicht notwendiger manueller Standardschritt, sondern Qualitäts-/Fallback-Schicht:

- SEC Company Facts/XBRL für SEC-reporting Unternehmen,
- ESEF/iXBRL für europäische IFRS-Berichte,
- ASML-spezifischer Parser bleibt ausschließlich Referenz-/Testadapter.

Zentrale Source Resolution bewahrt Providerdaten und bevorzugt vorhandene Primärquellenfakten.

## Lokaler Abnahmetest jetzt

1. `git pull`
2. `pip install -e ".[dev]"`
3. `pytest -q`
4. `streamlit run app.py`
5. Microsoft-Analyse unter `Datenimport` öffnen.
6. Prüfen, dass prominent nur `Daten laden / aktualisieren` angeboten wird.
7. Abschnitt `Erweitert / Diagnose` bleibt standardmäßig geschlossen.
8. Bei Analystenschätzungen müssen standardmäßig nur volle Geschäftsjahre erscheinen; Quartale sind optional einblendbar.
9. Sidebar darf die technischen Seiten `Offizielle Daten`, `Datenqualität` und `Importqualität` nicht mehr anzeigen.

## Noch offene Importthemen

- aktueller Marktpreis automatisch laden und korrekt nach Listing/Währung trennen,
- automatische Primärquellen-Discovery dort ergänzen, wo zuverlässig möglich,
- SEC-/ESEF-Mappings erweitern,
- ISIN/LEI-Anreicherung verbessern,
- optional zweiter breiter Fundamentals-Provider als Fallback prüfen,
- UI-Hauptseite `app` später in einen fachlichen Namen/Analysebereich überführen.

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
- Analyse direkt aus Provider-Treffer anlegbar,
- providerbezogene Identifikatoren persistiert,
- normaler Import ist ein 1-Klick-Workflow,
- Estimate-Quartale und -Jahre werden getrennt,
- technische Diagnoseseiten sind aus dem normalen Anwenderworkflow entfernt,
- fehlende Estimates oder einzelne Primärquellen blockieren den historischen Standardimport nicht,
- kein hart codierter Unternehmensparser ist Voraussetzung für normale Analysen.
