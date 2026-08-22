# PDF-Report-Spezifikation

## Grundsatz

Reports werden immer aus einem gespeicherten Analyse-Snapshot erzeugt. Beim Rendern einer alten Analyse dürfen keine aktuellen API-Daten zugemischt werden.

## Reporttypen

### Kurzreport
Ziel: ca. 5–10 Seiten.

Inhalt:
1. Titelblatt / Stammdaten / Datenstand
2. Executive Summary
3. wichtigste Finanzkennzahlen und Trends
4. Geschäftsmodell / Marktposition kurz
5. Bewertungsübersicht
6. DCF Worst/Base/Best
7. faires KGV / Multiples
8. Investmentthese
9. Top-Risiken
10. Margin of Safety

### Vollreport
Ziel: vollständige dokumentierte Investmentakte.

Kapitel:
1. Unternehmen und Datenquellen
2. Historische Finanzentwicklung
3. Ertrag und Rentabilität
4. Finanzielle Stabilität
5. Working Capital
6. Geschäftsmodell
7. Marktposition / Wettbewerb
8. Management
9. Ausschüttungspolitik / Kapitalallokation
10. Bewertungskennzahlen
11. Multiplikatorenmethode / faires KGV
12. Equity-DCF
13. Szenarien und Sensitivitäten
14. Investmentthese
15. Risiken / Invalidation Conditions
16. Fair Value / Margin of Safety
17. Quellen und methodische Hinweise

## Was nicht in voller Länge in den PDF-Report gehört

Die ausführlichen `ⓘ`-Lerntexte bleiben primär in der Anwendung. Im Report werden kurze Interpretationen und methodische Hinweise verwendet.

## Dateiname

Beispiel:

`ASML_Analysis_2026-08-22_R01_full.pdf`

## Vergleichsreport später

Optional eigener Reporttyp:

`ASML_2026-08-22_vs_2027-02-15.pdf`

mit geänderten Fundamentaldaten, Estimates, Bewertungsannahmen, eigener Einschätzung und Fair Value.

## PDF-Technik V1

ReportLab als robuste lokale Windows-Lösung. Die Report-Engine bleibt hinter einem Interface, damit später ein HTML/CSS-basierter Renderer ergänzt werden kann.
