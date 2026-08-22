# Datenquellen

## Ziel

Möglichst wenige, konsistente Rohdatenquellen. Kennzahlen werden intern berechnet. Jede Zahl wird mit Quelle und Datenstand gespeichert.

## V1-Quellen

### EODHD — primärer API-Kandidat

Verwendung:
- historische GuV
- Bilanz
- Cashflow
- Shares/Dividenden
- Unternehmensstammdaten
- ggf. Analystenschätzungen

Referenzsymbol für ASML: `ASML.AS`.

Vor produktiver Nutzung werden Feldabdeckung, Historientiefe, Kosten/Tarif und Datenqualität an ASML geprüft.

### ASML Investor Relations — Primärquelle zur Validierung

Verwendung:
- Geschäftsberichte
- Quartalsberichte
- Management Guidance
- Investor-Day-Ziele
- Sondereffekte / Restatements

Offizielle Unternehmensangaben haben bei veröffentlichten historischen Zahlen Vorrang vor normalisierten Sekundärprovidern.

### ECB Data API — risikofreier EUR-Zins

Für EUR-Unternehmen soll die Euro-Area-AAA-Zinskurve verwendet werden, z. B. ein 10-jähriger Punkt als Näherung. Verwendeter Wert und Datum werden im Analyse-Snapshot gespeichert.

### Aktienfinder.de — manuelle Ergänzung

Keine Abhängigkeit von einer undokumentierten API.

Manuell erfassbar:
- Prognosen/Schätzungen, falls dort sinnvoll aufbereitet
- spezielle Kennzahlen/Informationen
- eigene Notizen

Pflichtfelder: Wert, Zeitraum, Quelle, Eingabedatum, optional Kommentar.

## Zukunftsschätzungen: Priorität

1. Management Guidance — separater Korridor
2. Analystenkonsens Low/Average/High + Analystenzahl
3. eigene Schätzung/Override
4. historische Modellableitung

Analystenschätzungen werden primär in Jahren 1–3 verwendet. Die langfristige DCF wird nicht einfach aus Analystenwerten fortgeschrieben.

## Cross-Checks / spätere Provider

- Alpha Vantage
- Financial Modeling Prep
- weitere Provider nur hinter dem gemeinsamen Provider-Interface

## Datenregel

Keine gemischten fertigen Kennzahlen ohne Kennzeichnung. Beispiel: ROE soll aus unseren Rohdaten berechnet werden, nicht aus einem Provider-Fertigwert, wenn die nötigen Rohdaten verfügbar sind.
