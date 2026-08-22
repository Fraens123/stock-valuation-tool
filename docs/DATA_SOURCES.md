# Datenquellen

## Ziel

Möglichst wenige, konsistente Rohdatenquellen. Kennzahlen werden intern berechnet. Jede Zahl wird mit Quelle, Zeitraum und Datenstand gespeichert.

## Verbindliche V1-Hierarchie

### 1. Offizielle Unternehmensberichte — Primärquelle für veröffentlichte Zahlen

Für den Referenzfall ASML:

- Annual Reports
- Financial Statements Excel
- Quartalsberichte
- Investor-Day-Unterlagen
- Management Guidance

Offizielle Unternehmensangaben haben bei historischen veröffentlichten Zahlen Vorrang vor einem normalisierten Sekundärprovider.

### 2. Alpha Vantage — aktueller automatisierter V1-Testkandidat

Referenzsymbol für ASML Amsterdam: `ASML.AMS`.

Geplante Verwendung:
- historische GuV über `INCOME_STATEMENT`
- Bilanz über `BALANCE_SHEET`
- Cashflow über `CASH_FLOW`
- Analystenschätzungen über `EARNINGS_ESTIMATES`
- Unternehmenssuche über `SYMBOL_SEARCH`

Warum jetzt zuerst Alpha Vantage getestet wird:
- der Anbieter stellt für den Free-Tier aktuell 25 Requests pro Tag bereit
- laut Anbieter ist der Großteil der API-Endpunkte im Free-Tier nutzbar
- Fundamentaldaten-Endpunkte sind öffentlich dokumentiert
- globale Ticker werden unterstützt; `ASML.AMS` wird als Amsterdam-Listing verwendet

Ein ASML-Import benötigt mehrere Requests (GuV, Bilanz, Cashflow, Estimates). Der Free-Tier ist daher für Entwicklung, Tests und wenige Analysen pro Tag geeignet, nicht für Massen-Screening.

**Qualitäts-Gate:** Alpha Vantage wird erst als produktiver Primärprovider freigegeben, wenn die ASML-Daten gegen offizielle ASML-Berichte plausibilisiert wurden.

Dokumentation:
- `https://www.alphavantage.co/documentation/`
- `https://www.alphavantage.co/support/`

### 3. EODHD — integrierter Fallback, Fundamentals im Free-Tier nicht verfügbar

Referenzsymbol: `ASML.AS`.

Der lokale Test am 22.08.2026 mit einem gültigen kostenlosen EODHD-Key ergab beim Fundamentals-v1.1-Abruf für ASML:

- HTTP `403 Forbidden`
- API-Key wurde erkannt
- der kostenlose Tarif schaltet Fundamentals für diesen Abruf nicht frei

EODHD dokumentiert, dass Fundamentals-Abfragen 10 API Calls kosten und bestimmte Datentypen im Free-Tier nicht zugänglich sind. Der Fundamentals Data Feed ist kostenpflichtig.

**Entscheidung:** Vorläufig keinen EODHD-Fundamentals-Tarif kaufen. Adapter bleibt im Projekt, damit EODHD später optional als bezahlter Provider/Cross-Check genutzt werden kann.

### 4. ECB Data API — risikofreier EUR-Zins

Für EUR-Unternehmen wird die Euro-Area-AAA-Zinskurve verwendet, z. B. der 10-jährige Punkt als risikofreie Näherung.

Zu speichern:
- Wert
- Beobachtungsdatum
- Abrufdatum
- genaue ECB-Serie
- manuelles Override optional

Der Zins wird Teil des Analyse-Snapshots; eine alte Analyse verwendet bei späterem Öffnen nicht den heutigen Zins.

### 5. Aktienfinder.de — zentrale manuelle Ergänzung

Keine Abhängigkeit von einer undokumentierten API.

Manuell erfassbar:
- Prognosen/Schätzungen, wenn dort besser aufbereitet
- Spezialinformationen, die unser Provider nicht zuverlässig liefert
- Kontrollwerte
- eigene Notizen

Pflichtmetadaten:
- Wert
- Zeitraum/Geschäftsjahr
- Quelle = Aktienfinder
- Eingabedatum
- Einheit/Währung
- Kommentar optional

Ein manueller Wert darf einen API-Wert überschreiben, muss dann aber im UI, Vergleich und Report als Override erkennbar sein.

---

## Zukunftsschätzungen für DCF

### Management Guidance

Management Guidance wird **separat** gespeichert und nicht mit Analystenschätzungen vermischt.

### Analystenkonsens

Für die ersten DCF-Jahre sollen professionelle Schätzungen genutzt werden, wenn Datenqualität und Analystenzahl ausreichend sind.

Zielschema:
- Low
- Average / Consensus
- High
- Analyst Count
- Provider
- Abrufdatum
- Geschäftsjahr

### DCF-Priorität

**Jahr 1**
1. Management Guidance
2. Analystenkonsens
3. eigene Einschätzung

**Jahre 2–3**
1. Analyst Low / Average / High
2. Management-Langfristziele als Plausibilitätsrahmen
3. eigene Overrides

**Jahre 4–5**
- eigene fundamentale Forecasts
- Übergang von kurzfristigem Konsens zu nachhaltigen Annahmen

**Jahre 6–10**
- Fade / Mean Reversion

**ab Jahr 11**
- Terminalphase

Analystenwerte sind Input-Evidenz, keine automatische Wahrheit.

---

## Datenqualitätsregeln

### Historische Zahlen

Priorität:
1. offizieller Geschäftsbericht / Filing
2. freigegebener automatischer Provider
3. optionaler Cross-Check-Provider
4. manuelle Ergänzung

### Keine stillen Ersatzwerte

Wenn z. B. `costOfRevenue` fehlt, wird DPO/DIO nicht still mit Umsatz berechnet. Der Wert wird als `missing` markiert und eine fachlich definierte Alternative muss explizit gewählt werden.

### Keine gemischten Definitionen

ROE, Gearing, ROCE, FCF usw. werden zentral definiert und aus denselben normalisierten Rohdaten berechnet. Nicht ROE von Provider A, Gearing von Provider B und FCF von einer Website ohne gemeinsame Definitionsbasis.

---

## Weitere mögliche Provider

### Financial Modeling Prep

Interessant für Analyst Estimates und zusätzliche Fundamental APIs. Tarif- und globale Abdeckung müssen vor Nutzung geprüft werden.

Andere Provider werden nur hinter dem gemeinsamen Provider-Interface integriert.

---

## ASML-Referenzwerte für ersten Importtest

Die offizielle ASML-2025-Berichterstattung dient als Plausibilitätsanker für Umsatz, Margen, Gewinn, Bilanz und Cashflow. Diese Werte werden nicht hart in die Bewertungsengine codiert, sondern als referenzierte Test-/Guidance-Daten verwendet.

---

## Verwandte Dokumente

- `docs/RAW_DATA_SCHEMA.md`
- `docs/ASML_DATA_MAPPING.md`
- `docs/NORMALIZATION_POLICY.md`
- `docs/DCF_METHOD.md`
