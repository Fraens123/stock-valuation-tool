# Analysis Lifecycle

## Grundidee

Eine Analyse ist ein reproduzierbarer Snapshot. Sie wird nach Abschluss nicht mit neuen Daten überschrieben.

Beispiel:

```text
ASML
├── Analyse 2026-08-22 · Revision 1 · completed
├── Analyse 2027-02-15 · Revision 2 · completed
└── Analyse 2027-08-10 · Revision 3 · in_progress
```

## Neue Analyse

1. Unternehmen suchen/auswählen.
2. Analyse-Stichtag festlegen.
3. aktuellen Marktpreis und Datenstand erfassen.
4. historische Daten und Estimates laden.
5. Management Guidance erfassen/importieren.
6. manuelle Aktienfinder-Daten ergänzen.
7. Kennzahlen berechnen.
8. qualitative Analyse durchführen.
9. Multiples, faires KGV und DCF rechnen.
10. Investmentthese/Risiken dokumentieren.
11. Analyse abschließen und einfrieren.

## Neue Revision

Eine neue Revision kopiert bewusst die Teile der alten Analyse, die die eigene These repräsentieren, z. B.:
- qualitative Einschätzungen
- Kommentare
- Investmentthese
- Watch Items
- eigene langfristige Annahmen als Ausgangspunkt

Neu geladen werden:
- historische/aktuelle veröffentlichte Daten
- Marktpreis
- Analystenschätzungen
- Management Guidance
- risikofreier Zins

Der Nutzer prüft anschließend die übernommenen Einschätzungen.

## Vergleich

Der Vergleich zweier Revisionen wird in vier Hauptgruppen dargestellt:

### Fundamentaldaten
Umsatz, Margen, Cashflow, Bilanz, Kennzahlen.

### Prognosen
Analystenschätzungen, Management Guidance, eigene Prognosen.

### Bewertung
Multiples, Risikoannahmen, DCF-Treiber, Fair Value.

### Eigene Einschätzung
Marktposition, Management, Risiken, Investmentthese.

Jede Änderung soll Altwert, Neuwert, absolute/relative Änderung und optional Begründung zeigen.

## Status

- `draft`: gerade angelegt
- `in_progress`: Analyse wird aktiv bearbeitet
- `completed`: fachlich abgeschlossen und eingefroren
- `archived`: bleibt lesbar, wird aber im Standardworkflow nicht mehr angeboten

## Reproduzierbarkeit

Ein Report einer alten Analyse verwendet ausschließlich Daten dieses Snapshots. Ein PDF von Revision 1 muss auch Jahre später denselben Bewertungsstand wiedergeben können.
