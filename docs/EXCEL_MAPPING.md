# Mapping des bestehenden Excel-Modells

Das Excel wird nicht verworfen. Es ist die fachliche Referenz für Reihenfolge, bisherige Kennzahlen und Bewertungslogik. Die Python-Anwendung trennt diese Inhalte nur sauberer in Daten, Berechnung, qualitative Analyse und UI.

## Historische Daten

Basisbereiche:
- Gewinn- und Verlustrechnung
- Bilanz
- Cashflow
- Free Cashflow
- historische Jahresdaten

Ziel: 10 Jahre Historie laden und Kennzahlen selbst berechnen.

## Ertrag und Rentabilität

Im neuen Tool mindestens:
- Eigenkapitalrendite (ROE)
- Umsatzrendite
- EBIT-/EBITDA-Marge
- Kapitalumschlag
- Gesamtkapitalrendite
- ROCE
- Umsatzverdienstrate

## Finanzielle Stabilität

Mindestens:
- Eigenkapitalquote
- Gearing
- dynamischer Verschuldungsgrad
- Net Debt/EBITDA
- Sachinvestitionsquote
- Anlagenabnutzungsgrad
- Wachstumsquote
- Cash-Burn-Rate
- Umlauf-/Anlagenintensität
- Anlagendeckungsgrad I/II
- Goodwill-Anteil

Zusätzliche Excel-Kennzahlen werden in Phase 1 vollständig inventarisiert.

## Working Capital

- Debitorenlaufzeit
- Kreditorenlaufzeit
- Liquidität I/II/III
- Vorratsintensität
- Lagerumschlag / DIO
- Geldumschlag / Cash Conversion
- Auftragseingang/-bestand, wenn für das Unternehmen sinnvoll

## Geschäftsmodell

Der qualitative Teil bleibt bewusst erhalten:
- Kompetenzbereich
- Charakteristika
- Rahmenbedingungen
- Informationsbeschaffung
- Branchenstruktur / Porter
- SWOT
- BCG optional
- Wettbewerbsstrategie
- Management

Jede Bewertung erhält Kommentar und Quelle.

## Bewertungskennzahlen

### Equitymultiplikatoren
- KGV
- KBV
- KCV
- KUV

### Enterprise-Value-Ansatz
- Enterprise Value
- EV/EBITDA
- EV/EBIT
- EV/FCF
- EV/Sales

Der Enterprise-Value-Ansatz der Multiplikatoren ist nicht mit dem Entity-DCF zu verwechseln.

## DCF

Bestehende Reihenfolge:
1. Owner Earnings
2. Diskontierungsfaktor
3. Ewige Rente
4. fairer Aktienkurs

Diese Reihenfolge bleibt erhalten. V1 reproduziert, V2 verbessert die Prognose- und Szenariologik.

## Multiplikatorenmethode / Faires KGV

Bestehende Reihenfolge:
1. Sockel-KGV
2. Finanzielle Stabilität
3. Marktposition
4. Rentabilität
5. Wachstum
6. Individualität
7. Bewertung
8. fairer Preis je Aktie

Diese Methodik bleibt eine zentrale Säule des Tools.

## Verbesserungen gegenüber Excel

- zentrale Datenquellen und manuelle Eingabezentrale
- keine verteilten gelben Eingabefelder
- Snapshot-/Revisionsmodell
- ausführliche `ⓘ`-Erklärungen
- nachvollziehbare Quellen
- echte Scenario Objects statt Zellkombinatorik
- getrennte Guidance / Analyst Estimates / eigene Annahmen
- Fair Value getrennt von Margin of Safety
- PDF-Report und Analysevergleich
