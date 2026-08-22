# Current Task

## Phase 2/3 Übergang – Import, Prüfung und Bedienung vereinfachen

ASML bleibt Referenzfall für Datenqualität, ist aber **keine Voraussetzung** für Suche, Import oder Speicherung neuer Aktien.

## Verifizierter Stand

- ASML wurde erfolgreich importiert und gegen offizielle Primärquellen geprüft.
- Microsoft wurde als zweite, nicht hart codierte Aktie erfolgreich importiert.
- Microsoft-Snapshot: 740 Finanzdatenpunkte über 20 Geschäftsjahre; 32/32 definierte Core-Felder der letzten zwei Geschäftsjahre vorhanden.
- Analystenschätzungen wurden ebenfalls erfolgreich geladen.

Damit ist bestätigt: Der automatische Fundamentals-Import funktioniert unternehmensunabhängig für von Alpha Vantage unterstützte Symbole.

## Sichtbarer Standardablauf

1. **Übersicht**
   - alle Unternehmen und Analyse-Revisionen sehen,
   - Analyse verwalten / abschließen / neue Revision anlegen,
   - Revisionen vergleichen.
2. **Unternehmen**
   - Aktie suchen,
   - Haupt-/Provider-Treffer auswählen,
   - Analyse anlegen.
3. **Finanzdaten**
   - ein Button `Daten laden / aktualisieren`,
   - intern GuV + Bilanz + Cashflow + Estimates,
   - gespeicherten Datenstand sehen,
   - automatische Plausibilitätsprüfung,
   - KI-Prüfpaket erzeugen,
   - einzelne Werte nachvollziehbar korrigieren.
4. **Manuelle Daten**
   - Aktienfinder/zusätzliche Inputs,
   - Management Guidance,
   - risikofreier Zins.
5. **Kennzahlen**
   - ausschließlich Snapshot-Daten verwenden.

Später folgen Geschäftsmodell, Bewertung, Investmentthese und Report.

## Navigation / UI

- Streamlits automatische Dateinavigation wird ausgeblendet.
- eigene fachliche Sidebar: `Übersicht`, `Unternehmen`, `Finanzdaten`, `Manuelle Daten`, `Kennzahlen`.
- technische Diagnosewerkzeuge bleiben im Repository, sind aber kein normaler Arbeitsschritt.
- die frühere `app`-Startseite wurde zu einer echten Übersicht über **alle** Unternehmen und Analysen umgebaut; keine ASML-only-Startlogik mehr.

## Datenprüfung

### Deterministische Prüfung

`src/stock_valuation/data/audit.py`

Prüft ohne Netzwerkzugriff u. a.:
- Gross Profit = Revenue - Cost of Revenue,
- Bilanzsumme ungefähr Liabilities + Equity,
- Current Assets <= Total Assets,
- Current Liabilities <= Total Liabilities,
- Cash <= Current Assets.

Diese Checks erkennen Inkonsistenzen, ersetzen aber keine Primärquellenprüfung.

### KI-Prüfung

Die Anwendung kann aus dem Snapshot einen ausführlichen, reproduzierbaren Prüf-Prompt erzeugen. Dieser fordert eine web-/quellenbasierte Prüfung gegen Annual Reports, 10-K/20-F bzw. IR-Unterlagen und verlangt strukturierte PASS/WARN/FAIL/UNKLAR-Ergebnisse plus Quellen.

Aktuell wird das Prüf-Paket erzeugt, aber **nicht automatisch an einen kostenpflichtigen KI-API-Provider gesendet**. Direkte Ausführung wird später als optionaler Provider angebunden. Es darf nie still eine kostenpflichtige Abhängigkeit vorausgesetzt werden.

KI-Ergebnisse dürfen nur Korrekturvorschläge liefern. Kein Wert wird automatisch überschrieben.

## Manuelle Korrekturen importierter Finanzwerte

Finanzdaten können direkt auf der Seite **Finanzdaten** korrigiert werden.

Regeln:
- Originalwert von Alpha Vantage/Primärquelle bleibt erhalten.
- Korrektur wird separat als `provider=manual_override` gespeichert.
- Quelle und Begründung sind erforderlich bzw. sichtbar.
- Source Resolution priorisiert `manual_override` vor Primärquelle/API.
- Override kann wieder entfernt werden; dann greift automatisch wieder die darunterliegende Quelle.
- abgeschlossene Snapshots bleiben unveränderlich.

## Estimate-Logik

Alpha Vantage `EARNINGS_ESTIMATES` enthält Jahres- und Quartalsschätzungen im selben Endpoint.

- Geschäftsjahresende wird aus den FY-Abschlussdaten abgeleitet,
- Standardansicht zeigt nur Jahresschätzungen,
- Quartale und historische Historie sind optional einblendbar,
- spätere DCF-Logik verwendet Jahresschätzungen als Jahresinput.

## Lokaler Abnahmetest jetzt

1. `git pull`
2. `pip install -e ".[dev]"`
3. `pytest -q`
4. `streamlit run app.py`
5. Sidebar prüfen: nur `Übersicht`, `Unternehmen`, `Finanzdaten`, `Manuelle Daten`, `Kennzahlen`.
6. `Übersicht`: ASML **und** Microsoft bzw. alle gespeicherten Analysen müssen sichtbar sein.
7. Microsoft unter `Finanzdaten` öffnen.
8. Bestehende 740 Datenpunkte müssen ohne Neuimport sichtbar bleiben.
9. Plausibilitätsprüfung öffnen; Checks müssen ohne API-Requests laufen.
10. `KI-Prüfprompt erstellen` testen; es darf kein API-Request ausgelöst werden.
11. Optional einen unwichtigen Testwert manuell überschreiben und prüfen, dass der Originalwert in Rohdaten erhalten bleibt; danach Override wieder entfernen.

## Noch offene Import-/Prüfthemen

- direkte optionale KI-Ausführung mit Web-/Quellenzugriff hinter Provider-Interface,
- KI-Ergebnis als strukturierte Review-Tabelle statt Freitext,
- bestätigte KI-Korrekturen über dieselbe `manual_override`-Logik übernehmen,
- aktueller Marktpreis automatisch laden und korrekt nach Listing/Währung trennen,
- automatische Primärquellen-Discovery dort ergänzen, wo zuverlässig möglich,
- SEC-/ESEF-Mappings erweitern,
- ISIN/LEI-Anreicherung verbessern,
- optional zweiter breiter Fundamentals-Provider als Fallback prüfen.

## Noch offene Kapitel-2-Methodik

Weiterhin Buchverifikation erforderlich:

- ROE — Kindle S. 94
- Umsatzrendite — Kindle S. 101
- Kapitalumschlag — Kindle S. 107
- Gesamtkapitalrendite — Kindle S. 109
- ROCE — Kindle S. 111
- Umsatzverdienstrate — Kindle S. 114

Keine dieser Formeln eigenmächtig festlegen.
