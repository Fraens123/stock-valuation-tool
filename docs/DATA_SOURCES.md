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

ASML stellt für 2025 sowohl US-GAAP- als auch IFRS-Berichte und Financial-Statements-Exceldateien bereit. Diese Dateien werden für die Validierung des automatischen EODHD-Imports verwendet.

### 2. EODHD Fundamentals v1.1 — primärer automatisierter Rohdatenprovider

Referenzsymbol: `ASML.AS`.

Verwendung:
- Unternehmensstammdaten
- historische GuV
- Bilanz
- Cashflow
- Shares
- Dividenden
- Earnings History
- Analystenschätzungen, sofern die benötigten Felder für den Titel vorhanden sind

Warum EODHD als V1-Kandidat:
- internationale Börsenabdeckung
- non-US Fundamentaldaten
- jährliche und quartalsweise Statements
- v1.1 trennt Annual und Quarterly Earnings Trend sauber
- Rohdatenfelder für die meisten benötigten Schmidlin-Kennzahlen vorhanden

Wichtige Regel: Provider-ROE, Provider-EV oder ähnliche fertige Kennzahlen werden höchstens als Cross-Check genutzt. Unser Modell rechnet aus den Rohdaten selbst.

Dokumentation:
- `https://eodhd.com/financial-apis/stock-etfs-fundamental-data-feeds`
- `https://eodhd.com/financial-academy/financial-faq/fundamentals-glossary-common-stock`

Das konkrete ASML-Feldmapping steht in `docs/ASML_DATA_MAPPING.md`.

### 3. ECB Data API — risikofreier EUR-Zins

Für EUR-Unternehmen soll die Euro-Area-AAA-Zinskurve verwendet werden, z. B. der 10-jährige Punkt als risikofreie Näherung.

Zu speichern:
- Wert
- Beobachtungsdatum
- Abrufdatum
- genaue ECB-Serie
- manuelles Override optional

Der Zins wird Teil des Analyse-Snapshots; eine alte Analyse verwendet bei späterem Öffnen nicht den heutigen Zins.

### 4. Aktienfinder.de — zentrale manuelle Ergänzung

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

Für ASML ist sie besonders nützlich, weil das Unternehmen konkrete Umsatz-/Margenkorridore veröffentlicht.

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
2. EODHD
3. optionaler Cross-Check-Provider
4. manuelle Ergänzung

### Zukunftsdaten

Priorität:
1. Management Guidance als eigener Korridor
2. Analystenkonsens
3. eigene Annahmen
4. historische Extrapolation nur als letzter Anker

### Keine stillen Ersatzwerte

Wenn z. B. `costOfRevenue` fehlt, wird DPO/DIO nicht still mit Umsatz berechnet. Der Wert wird als `missing` markiert und eine fachlich definierte Alternative muss explizit gewählt werden.

### Keine gemischten Definitionen

ROE, Gearing, ROCE, FCF usw. werden zentral definiert und aus denselben normalisierten Rohdaten berechnet. Nicht ROE von Provider A, Gearing von Provider B und FCF von einer Website ohne gemeinsame Definitionsbasis.

---

## Cross-Checks / spätere Provider

### Alpha Vantage

Möglicher Fallback für Statements und Earnings Estimates.

### Financial Modeling Prep

Interessant für Analyst Estimates und zusätzliche Fundamental APIs. Tarif- und globale Abdeckung müssen vor Nutzung geprüft werden.

Andere Provider werden nur hinter dem gemeinsamen Provider-Interface integriert.

---

## ASML-Referenzwerte für ersten Importtest

Die offizielle ASML-2025-Berichterstattung nennt als erste Plausibilitätsanker unter anderem:

- 2025 Total net sales: €32.7 Mrd.
- Gross margin: 52.8 %
- R&D: €4.7 Mrd.
- Basic EPS: €24.73

Für 2026 nennt ASML einen Umsatzkorridor von €34–39 Mrd. und eine erwartete Bruttomarge von 51–53 %. Für 2030 beschreibt ASML eine Umsatzchance von ungefähr €44–60 Mrd. und 56–60 % Bruttomarge.

Diese Werte werden nicht hart in die Bewertungsengine codiert. Sie dienen als referenzierte Test- und Guidance-Daten im ASML-Snapshot.

---

## Verwandte Dokumente

- `docs/RAW_DATA_SCHEMA.md`
- `docs/ASML_DATA_MAPPING.md`
- `docs/NORMALIZATION_POLICY.md`
- `docs/DCF_METHOD.md`
