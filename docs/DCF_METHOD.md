# DCF-Methodik

## Ziel

Die bestehende Excel-Logik wird zuerst reproduziert und erst danach erweitert. Hauptverfahren ist zunächst das **Equity-DCF über Owner Earnings**.

Buchreferenz in der Kindle-Ausgabe des Nutzers:
- 8. Unternehmensbewertung — S. 287
- 8.1 Discounted-Cashflow-Modell — S. 291
- 8.1.1 Equity-Verfahren — S. 295
- 8.1.2 Entity-Verfahren — S. 310
- 8.1.3 APV — S. 319
- 8.1.5 Alternative Verwendung des DCF-Modells — S. 334
- 8.1.6 Fallbeispiele — S. 335

## V1-Reihenfolge wie im Excel

1. Owner Earnings bestimmen
2. Diskontierungsfaktor bestimmen
3. Ewige Rente bestimmen
4. Fairen Aktienkurs bestimmen

## Owner Earnings

Arbeitsform für V1:

`Owner Earnings = Jahresüberschuss + nicht zahlungswirksame Aufwendungen - CAPEX - Δ Working Capital`

Die exakte Behandlung einzelner Positionen wird gegen Excel und Buch validiert, bevor die Formel als stabil markiert wird.

## Prognose V2

### Jahr 1
Management Guidance und Analystenkonsens als kurzfristige Anker.

### Jahre 2–3
Analystenschätzungen Low / Average / High, jeweils mit Analystenzahl sofern verfügbar.

### Jahre 4–5
Übergang zu eigenen fundamentalen Annahmen.

### Jahre 6–10
Fade / Mean Reversion zu nachhaltigen Wachstums-, Margen- und Kapitalbedarfsniveaus.

### ab Jahr 11
Terminalphase / ewige Rente.

## Kausale Prognoselogik

Das Modell soll nicht Gewinn und Umsatz unabhängig beliebig kombinieren. Zielkette:

`Umsatz -> Marge -> operatives Ergebnis/Gewinn -> Reinvestitionsbedarf -> Working Capital -> Owner Earnings`

Wachstum muss Kapitalbedarf berücksichtigen.

## Analystenschätzungen

Ja, für die ersten Jahre sinnvoll. Sie sind aber Ausgangspunkte und keine Wahrheit. Management Guidance, Analystenkonsens und eigene Annahmen bleiben getrennte Datenklassen.

## Eigenkapitalkosten und Risiko

Bestehendes Excel-Grundprinzip:

`Eigenkapitalkosten = risikofreier Zins + Risikoaufschlag`

und sinngemäß ein Risikoaufschlag über den Kehrwert eines fairen/riskobezogenen KGV.

### Ziel-UI

Dropdown:
- Sehr gering
- Gering
- Mittel
- Hoch
- Sehr hoch
- Benutzerdefiniert

Daneben sichtbar:
- Risiko-KGV
- impliziter Risikoaufschlag in %
- risikofreier Zins
- resultierende Eigenkapitalkosten

Die konkreten numerischen Stufen werden **nicht** erfunden. Sie werden erst nach fachlicher Prüfung der relevanten Buch-/Excel-Logik fixiert.

## Risiko-KGV vs vollständiges faires KGV

Das vollständige faire KGV enthält auch Wachstum und weitere Bewertungsfaktoren. Für den DCF-Diskontsatz soll eine separate risikoorientierte Größe geprüft werden, damit Wachstum nicht doppelt positiv wirkt:

1. höhere prognostizierte Cashflows
2. gleichzeitig niedrigerer Diskontsatz über ein wachstumsgetriebenes KGV

Diese Trennung ist eine methodische Hypothese und muss in Phase 6/9 gegen Buch und Excel validiert werden.

## Risikofreier Zins

Für ASML/EUR wird ein aktueller 10-jähriger EUR-AAA-Zins über die ECB als Näherung vorgesehen. Wert und Stichtag werden gespeichert. Manuelles Override bleibt möglich.

## Terminal Value

Grundform:

`TV = OE_10 × (1 + g) / (ke - g)`

Regeln:
- `g < ke`
- konservatives langfristiges Wachstum
- nachhaltiger Reinvestitionsbedarf beachten
- Terminal-Value-Anteil am gesamten Fair Value immer anzeigen
- Warnhinweis bei extremer Terminal-Abhängigkeit

## Fair Value / Margin of Safety

Nicht vermischen:
- innerer Wert / Fair Value
- aktueller Marktpreis
- Unter-/Überbewertung
- Kaufgrenze nach gewünschter Margin of Safety

## Szenarien

### Worst
untere Guidance/Low Estimates, schwächere Margen, höherer Kapitalbedarf, höheres Risiko, konservatives Terminalwachstum.

### Base
Konsens/mittlere Guidance und fundamental plausible nachhaltige Annahmen.

### Best
obere Guidance/High Estimates, bessere Entwicklung nur dort, wo wirtschaftlich begründbar.

Später zusätzlich probabilistische Simulationen mit Korrelationen und Plausibilitätsregeln.

## Entity-DCF

Wird später als eigenständiger Cross-Check über FCFF/WACC implementiert und ist klar vom `Enterprise-Value-Ansatz` der Bewertungsmultiplikatoren zu unterscheiden.
