# Offene Punkte

Stand: 22.08.2026

Diese Datei ist die zentrale Übersicht aller fachlichen, datenbezogenen und technischen Punkte, die vor den jeweiligen späteren Phasen noch offen sind. `CURRENT_TASK.md` bleibt der operative Arbeitsauftrag; diese Datei erklärt den Gesamt-Restumfang.

## 1. Sofort offene Punkte – Phase 3A

### 1.1 Buchdefinitionen für Kapitel 2

Für folgende Kennzahlen ist die Rohdatenbasis grundsätzlich vorhanden, die exakte Schmidlin-Definition aber noch zu verifizieren:

- ROE – Kindle S. 94: Jahresend-Eigenkapital oder durchschnittliches Eigenkapital?
- Umsatzrendite – Kindle S. 101: exakte Gewinn-Zählerdefinition.
- Kapitalumschlag – Kindle S. 107: exakte Kapitalbasis / Durchschnittsbildung.
- Gesamtkapitalrendite – Kindle S. 109: Zähler- und Nennerdefinition.
- ROCE – Kindle S. 111: exakte Capital-Employed-Definition.
- Umsatzverdienstrate – Kindle S. 114: konkrete Formel/Definition.

EBIT-Marge ist bereits aktiv und getestet.

### 1.2 Datenblocker für EBITDA-Marge

`depreciation_amortization` ist im ASML-Primärquellen-Gate blockiert. Zu klären:

- geeignetes Alpha-Vantage-Rohfeld bzw. alternatives Mapping,
- Vergleich gegen ASML D&A 2024/2025,
- erst danach EBITDA-Marge freigeben.

## 2. Noch offene Datenqualität

Alpha Vantage wird feldweise und nicht pauschal freigegeben.

Derzeit problematisch/blockiert:

- `accounts_receivable`
- `inventory`
- `ppe_net`
- `short_term_debt`
- `operating_cash_flow`
- `capital_expenditures`
- `depreciation_amortization`
- `cash_and_short_term_investments` als Cross-Check-Feld
- weitere Felder, die im Feld-Gate FAIL/MISSING zeigen

Noch zu tun:

- problematische Providerfelder fachlich neu mappen oder ausschließen,
- ältere Jahre stichprobenartig gegen ASML-Primärquellen prüfen,
- keine offiziellen Kontrollwerte automatisch als Ersatz in die Providerhistorie schreiben,
- ggf. zweite Quelle nur für fehlende Rohdaten evaluieren.

## 3. Phase 3 – Kennzahlenengine nach Kapitel 2

Nach Phase 3A folgen:

### Finanzielle Stabilität
- Eigenkapitalquote
- Gearing
- Dynamischer Verschuldungsgrad
- Net Debt/EBITDA
- Sachinvestitionsquote
- Anlagenabnutzungsgrad
- Wachstumsquote
- Cash-Burn-Rate, falls anwendbar
- Umlauf-/Anlagenintensität
- Anlagendeckungsgrad I/II
- Goodwill-Anteil

### Working Capital
- DSO / Debitorenlaufzeit
- DPO / Kreditorenlaufzeit
- Liquidität 1./2./3. Grades
- Vorratsintensität
- Inventory Turnover
- DIO
- Cash Conversion Cycle
- Auftragseingang/-bestand bei Anwendbarkeit

### Ausschüttung / Kapitalallokation
- Dividendenquoten
- Aktienrückkäufe
- Netto-Aktienzahlentwicklung
- Kapitalallokationsanalyse

## 4. Offene Methodikfragen

Verbindlich in `docs/METHODOLOGY_OPEN_QUESTIONS.md` dokumentiert:

- Owner-Earnings-Definition im Equity-DCF
- Risiko-KGV vs. vollständiges faires KGV
- Risikostufen / numerische Dropdown-Werte
- Analystenschätzungen im DCF – finale Übergangslogik
- Sonder-/Einmaleffekte und Normalisierung
- ROE-Kapitalbasis
- Working-Capital-Laufzeiten 360 vs. 365 und Nenner
- Enterprise-Value-Brücke inkl. Leasing/Pensionen/Minderheiten
- FCF-/FCFF-/Owner-Earnings-Abgrenzung
- Net Cash je Aktie
- Fair-KGV-Scoring und ungehebelte Rentabilität

## 5. Spätere Projektphasen

### Phase 4 – Geschäftsmodellanalyse
- Kompetenzbereich
- Charakteristika
- Rahmenbedingungen
- Informationsbeschaffung
- Porter Five Forces
- SWOT
- Wettbewerbsstrategie
- Management
- Begründungen und Quellen

### Phase 5 – Bewertungskennzahlen
- KGV, KBV, KCV, KUV
- Enterprise Value
- EV/EBITDA, EV/EBIT, EV/FCF bzw. FCFF, EV/Sales
- 5J-/10J-Historien, Median/Bandbreiten

### Phase 6 – Faires KGV / Multiplikatorenmethode
- Sockel-KGV
- finanzielle Stabilität
- Marktposition
- Rentabilität
- Wachstum
- Individualität
- vollständige Schmidlin-Formel und Punktelogik verifizieren

### Phase 7 – Equity-DCF V1
- bestehende Excel-Owner-Earnings-Logik reproduzieren
- Diskontierung
- Terminal Value
- Fair Value je Aktie
- Margin of Safety separat

### Phase 8 – DCF V2
- Guidance/Konsens Jahre 1–3
- eigene Forecasts Jahre 4–5
- Fade/Mean Reversion Jahre 6–10
- Terminalphase

### Phase 9 – Risikomodell
- risikofreier Zins
- Risikoaufschlag / Risiko-KGV
- Risikostufen
- CAPM als Vergleich optional

### Phase 10 – Szenarioengine
- Worst/Base/Best als konsistente wirtschaftliche Szenarien
- Sensitivitäten
- später probabilistische Simulation optional

### Phase 11 – Entity-DCF / APV
- FCFF/WACC
- Entity-DCF als Cross-Check
- APV für Spezialfälle

### Phase 12 – UX
- vollständiger geführter Analyseworkflow
- Navigation/Status/Blocker
- Charts und Eingabehilfen

### Phase 13 – PDF
- Kurzreport ca. 5–10 Seiten
- Vollreport
- ausschließlich aus eingefrorenem Snapshot

### Phase 14 – Qualität / Release
- Regressionstests
- Datenmigrationen
- Fehlerbehandlung
- Installations-/Updateprozess
- Release-Dokumentation

## 6. Was jetzt konkret als Nächstes passiert

Parallel arbeiten wir an zwei Strängen:

1. **Buchmethodik:** Nutzer liefert die Formel-/Definitionsabschnitte für Kindle S. 94, 101, 107, 109, 111 und 114. Danach werden die restlichen Kapitel-2-Kennzahlen freigeschaltet.
2. **Datenqualität:** D&A und die weiteren gesperrten Alpha-Vantage-Felder werden technisch untersucht und ggf. neu gemappt/ersetzt.

Keine spätere Bewertungslogik wird vorgezogen, solange dafür zentrale Rohdaten oder Buchdefinitionen noch nicht verifiziert sind.
