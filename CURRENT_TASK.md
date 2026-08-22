# Current Task

## Phase 2/3 Übergang – Universellen Unternehmensimport fertigstellen

ASML bleibt der Referenzfall für Datenqualitätsprüfungen, darf aber **keine Voraussetzung** für den normalen Import sein. Das Tool muss neue Aktien ohne Codeänderung suchen, anlegen und importieren können.

## Bereits funktionierend

- Alpha Vantage liefert für unterstützte Symbole GuV, Bilanz, Cashflow und Analystenschätzungen.
- der Import schreibt reproduzierbar in den Analyse-Snapshot.
- ASML ist als Referenzunternehmen primärquellenvalidiert.
- offizielle ASML-Fakten stehen separat neben Providerdaten.
- zentrale Source Resolution bevorzugt Primärquelle vor API-Provider.
- EBIT-/EBITDA-Marge funktionieren für den Referenzfall.

## Neu generalisiert

### Universelle Unternehmenssuche

`pages/0_Unternehmen.py`

- explizite Alpha-Vantage-Online-Suche über `SYMBOL_SEARCH` (1 Request),
- Treffer werden nicht im Code hinterlegt,
- aus einem Treffer kann direkt eine neue Analyse angelegt werden,
- das gewählte Alpha-Vantage-Symbol wird dauerhaft gespeichert.

### Provider-spezifische Symbole

Neue Tabelle `company_provider_symbols`.

Ein Unternehmen kann getrennte Identifikatoren besitzen für:

- Provider,
- Zweck (`fundamentals`, später `market_price`, `estimates`),
- Börse/Region,
- Währung.

Damit wird `Company.ticker` nicht mehr fälschlich als universeller Provider-Identifier verwendet.

### Generischer Datenimport

`pages/1_Datenimport.py`

- funktioniert für jede gespeicherte Analyse,
- nimmt bevorzugt das gespeicherte Alpha-Vantage-Fundamentals-Symbol,
- 1-Request-Probe prüft, ob Jahresabschlüsse vorhanden sind,
- erfolgreicher Ticker wird dauerhaft gespeichert,
- vollständiger Import verwendet 4 Requests,
- ASML-Sonderlogik ist keine Voraussetzung mehr für den Import.

### Generische Importqualität

`pages/3_Importqualitaet.py`

- funktioniert für alle Unternehmen,
- zeigt bevorzugte Fakten, Quellenmix und Kernfelder der letzten zwei Geschäftsjahre,
- unterscheidet `PRIMÄRQUELLE`, `API – NICHT PRIMÄRVALIDIERT` und `FEHLT`,
- importierte Daten werden nicht fälschlich als offiziell validiert dargestellt.

### Unternehmensidentität

- bevorzugt ISIN, wenn vorhanden,
- sonst Ticker + Börse/Region,
- gleiche Ticker auf unterschiedlichen Börsen werden nicht mehr automatisch zusammengeführt.

## Nächster technischer Block

Der Import muss anschließend auch bei schwacher/fehlender Alpha-Vantage-Coverage einen sauberen Fallback haben.

Priorität:

1. SEC Company Facts / XBRL als generischer Primärquellenadapter für SEC-reporting Unternehmen,
2. generischer offizieller XLSX/CSV/XBRL-Import für Investor-Relations-Dokumente,
3. europäische ESEF/XBRL-Strategie,
4. zweiter automatischer Fundamentals-Provider nur wenn technisch/finanziell sinnvoll.

Ziel ist **breite Unternehmensabdeckung**, nicht ein eigener hart codierter Parser je Aktie.

## Lokaler Abnahmetest jetzt

1. `git pull`
2. `pip install -e ".[dev]"`
3. `pytest -q`
4. `streamlit run app.py`
5. Seite `Unternehmen` öffnen.
6. Eine andere Aktie als ASML suchen, z. B. Microsoft.
7. Provider-Treffer auswählen und Analyse anlegen.
8. `Datenimport` öffnen.
9. `Fundamentals testen (1 Request)`.
10. Wenn Jahresberichte gefunden werden, `Finanzdaten und Schätzungen importieren (4 Requests)`.
11. `Importqualität` öffnen und prüfen, ob historische Daten und Kernfelder sichtbar sind.

## Noch offene Kapitel-2-Methodik

Weiterhin Buchverifikation erforderlich:

- ROE — Kindle S. 94
- Umsatzrendite — Kindle S. 101
- Kapitalumschlag — Kindle S. 107
- Gesamtkapitalrendite — Kindle S. 109
- ROCE — Kindle S. 111
- Umsatzverdienstrate — Kindle S. 114

Keine dieser Formeln eigenmächtig festlegen.

## Definition of Done des Universal-Import-Blocks

- eine neue Aktie kann ohne Codeänderung online gefunden werden,
- Analyse kann direkt aus Provider-Treffer angelegt werden,
- Fundamentals-Symbol ist providerbezogen persistiert,
- Import funktioniert ohne ASML-Sonderfall,
- Datenqualität für nicht-ASML-Unternehmen ist sichtbar,
- fehlende Provider-Coverage führt zu einem klaren Fallback-Pfad statt zu einem toten Ende.
