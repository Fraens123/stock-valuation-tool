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

Für ASML muss zwischen Kurs- und Fundamentals-Symbol unterschieden werden:

- lokales Amsterdam-Listing / Marktpreis: später separat auf Euronext-Basis behandeln
- Alpha-Vantage-Fundamentals: `ASML`

Der lokale Live-Test zeigte:

- `ASML.AMS` liefert beim `INCOME_STATEMENT`-Fundamentals-Endpunkt 0 Reports.
- `ASML` liefert die konsolidierten ASML-Holding-Abschlüsse in EUR.
- 20 Jahresberichte und 81 Quartalsberichte wurden erkannt.
- 2025 Revenue wurde mit 32,6673 Mrd. EUR geliefert und stimmt mit ASML US GAAP überein.
- Ein vollständiger Snapshot-Import wurde lokal erfolgreich durchgeführt: 720 Financial-Fact-Datenpunkte über 20 Geschäftsjahre.

Verwendung:
- historische GuV über `INCOME_STATEMENT`
- Bilanz über `BALANCE_SHEET`
- Cashflow über `CASH_FLOW`
- Analystenschätzungen über `EARNINGS_ESTIMATES`
- Unternehmenssuche über `SYMBOL_SEARCH`

Free-Tier:
- 25 Requests pro Tag
- Requests werden im Adapter konservativ zeitlich gestaffelt
- vollständiger Import benötigt derzeit vier Requests
- geeignet für Entwicklung und Einzelanalysen, nicht für Massen-Screening

**Qualitäts-Gate:** Alpha Vantage wird erst für konkrete Rohdatenfelder freigegeben, wenn diese gegen offizielle ASML-US-GAAP-Kontrollwerte geprüft wurden. Der Gate ist in `stock_valuation.validation.service` implementiert.

Bekannte erste Prüfpunkte:
- `accounts_receivable`: sichtbare semantische Abweichung
- `capital_expenditures`: sichtbare Abweichung zur offiziellen PP&E-Cash-Purchase-Zahl
- `cash_and_short_term_investments`: nur Cross-Check; Komponenten werden später separat aufgebaut

Siehe `docs/ASML_PROVIDER_VALIDATION.md`.

Dokumentation:
- `https://www.alphavantage.co/documentation/`
- `https://documentation.alphavantage.co/FundamentalDataDocs/index.html`

### 3. EODHD — integrierter Fallback, Fundamentals im Free-Tier nicht verfügbar

Referenzsymbol: `ASML.AS`.

Der lokale Test am 22.08.2026 mit einem gültigen kostenlosen EODHD-Key ergab beim Fundamentals-v1.1-Abruf für ASML:

- HTTP `403 Forbidden`
- API-Key wurde erkannt
- der kostenlose Tarif schaltet Fundamentals für diesen Abruf nicht frei

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

Alpha Vantage liefert zusätzlich lange historische Estimate-/Revisionsreihen. Diese bleiben im Snapshot auditierbar, werden in der normalen UI aber standardmäßig ausgeblendet, wenn ihre Periode vor dem Analysestichtag liegt.

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
2. für das konkrete Rohdatenfeld freigegebener automatischer Provider
3. optionaler Cross-Check-Provider
4. manuelle Ergänzung

### Primärquellen-Gate

Für ASML 2025/2024:
- <= 0,5 % relative Abweichung: PASS
- > 0,5 % bis 2 %: WARN
- > 2 %: FAIL
- fehlend: MISSING

Ein Providerwert wird bei FAIL/MISSING nicht still durch den Kontrollwert ersetzt. Stattdessen muss Mapping/Definition geklärt werden.

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

## ASML-Referenzwerte

Die offizielle ASML-US-GAAP-Berichterstattung 2025/2024 dient als Primärquellen-Gate für Umsatz, Ergebnis, Bilanz und Cashflow. Die Kontrollwerte stehen in `src/stock_valuation/validation/asml_reference.py` und werden ausschließlich zur Validierung verwendet, nicht als automatische Ersatzdaten.

---

## Verwandte Dokumente

- `docs/RAW_DATA_SCHEMA.md`
- `docs/ASML_DATA_MAPPING.md`
- `docs/ASML_PROVIDER_VALIDATION.md`
- `docs/NORMALIZATION_POLICY.md`
- `docs/DCF_METHOD.md`
