# Phase 1 – Inventarisierung des bestehenden Excel-Modells

## Zweck

Das bestehende Excel wird nicht 1:1 kopiert, sondern zuerst fachlich zerlegt. Diese Datei hält fest, **was aktuell vorhanden ist**, **welche Formel das Excel tatsächlich verwendet** und **was im neuen Tool beibehalten, ergänzt oder fachlich geprüft werden muss**.

Referenzdatei bei der Inventarisierung: lokales `Aktien_Bewertungs_Tool_refactor_v1.xlsm`, Blatt `Krones`. Die fachlichen Inhalte stammen aus dem ursprünglichen Bewertungsblatt; die zusätzlich erzeugten Sheets `00_ControlCenter`, `01_Input_Inventory` und `99_Glossary` sind nicht Teil der ursprünglichen Bewertungsmethodik.

Die maschinenlesbare Fassung liegt in `src/stock_valuation/knowledge/metrics.yaml`.

---

## 1. Aufbau des Excel-Modells

Die vorhandene Reihenfolge ist fachlich sinnvoll und wird grundsätzlich übernommen:

1. GuV / Bilanz / Cashflow als Rohdatenbasis
2. Kennzahlen zu Ertrag und Rentabilität
3. Kennzahlen zur finanziellen Stabilität
4. Working Capital Management
5. Bewertungskennzahlen
6. DCF – Equity-Methode / Owner Earnings
7. Multiplikatorenmethode / Faires KGV
8. Fairer Preis je Aktie
9. Szenarioauswertung über VBA

Die neue Anwendung ergänzt die im Buch vorhandenen, im Excel aber fehlenden Kapitel und trennt Daten, Berechnungen, Einschätzungen und Bewertung sauber.

---

## 2. Rohdatenzeilen im bestehenden Excel

Wichtige Zellbezüge, die in den Formeln wiederholt verwendet werden:

| Excel-Zeile | Inhalt | spätere Normalisierung |
|---|---|---|
| 2 | Umsatz / Ertrag | `revenue` |
| 12 | Betriebsergebnis vor Zinsen und Steuern | `ebit` |
| 17 | Nettogewinn | `net_income` |
| 18 | Nettogewinn für Aktionäre | `net_income_attributable` |
| 20/21 | EPS unverwässert / verwässert | `basic_eps` / `diluted_eps` |
| 30 | Liquidität, Geldmarktanlagen, kurzlaufende Anlagen | `cash_and_short_term_investments` |
| 31 | Forderungen | `accounts_receivable` |
| 32 | Lagerbestand | `inventory` |
| 34 | Umlaufvermögen | `current_assets` |
| 38 | Immaterielle Vermögenswerte | `intangible_assets` |
| 41 | langfristige Vermögenswerte | `non_current_assets` – Provider-Mapping prüfen |
| 42 | Gesamtvermögen | `total_assets` |
| 46 | Accounts Payable | `accounts_payable` |
| 50 | laufende / kurzfristige Verbindlichkeiten | `current_liabilities` |
| 55 | langfristige Verbindlichkeiten | `long_term_liabilities` |
| 56 | Summe Verbindlichkeiten | `total_liabilities` |
| 63 | Eigenkapital | `total_equity` |
| 64 | Gesamtkapital | im neuen Schema mit `total_assets` harmonisieren |
| 70 | Abschreibungen und Abgrenzungen | `depreciation_amortization` |
| 77 / 95 | operativer Cashflow – Bezeichnungen im Altmodell doppelt | in Phase 2 Provider-Mapping eindeutig festlegen |
| 79 | Investitionen in Sachanlagen | `capex_ppe` |
| 83 | Kauf immaterieller Anlagewerte | `capex_intangibles` |
| 85 | Investment-Cashflow | nicht mit CAPEX gleichsetzen |
| 88 | Dividenden | `dividends_paid` |
| 97 | verfügbarer / Free Cashflow | künftig intern selbst berechnen |

Manuelle Alt-Inputs:
- `Krones!I75:M75`: zinstragende Verbindlichkeiten
- `Krones!I173:M173`: Goodwill
- `Krones!I183:M183`: Zinskosten
- `Krones!I225:M225`: Anzahl Aktien
- DCF-Schätzungen und Fair-KGV-Punkte in gelben Eingabezellen

Ziel: Diese manuellen Daten werden künftig entweder API-Rohdaten oder zentrale `ManualInputSnapshot`-Felder mit Quelle `Aktienfinder`.

---

## 3. Kennzahlen – Ertrag und Rentabilität

### Vorhanden und grundsätzlich behalten

| Buch | Kennzahl | Excel-Formel | Entscheidung |
|---|---|---|---|
| 2.1 / Kindle 94 | Eigenkapitalrendite | `Net Income / Jahresend-EK` | **prüfen/anpassen**: durchschnittliches EK fachlich bevorzugt; Buchdefinition verifizieren |
| 2.2 / 101 | Umsatzrendite | `Gewinn Aktionäre / Umsatz` | behalten, Zählerdefinition prüfen |
| 2.3 / 105 | EBIT-Marge | `EBIT / Umsatz` | behalten |
| 2.3 / 105 | EBITDA-Marge | `(EBIT + D&A) / Umsatz` | behalten |
| 2.5 / 109 | Gesamtkapitalrendite | `(Net Income + Zinsaufwand) / Gesamtkapital` | Buchdefinition verifizieren |
| 2.6 / 111 | ROCE | `EBIT / (Gesamtkapital - kurzfristige Verbindlichkeiten)` | behalten, Capital-Employed-Definition verifizieren |

### Im Buch, aber im Excel nicht separat umgesetzt

- 2.4 Kapitalumschlag – Kindle 107
- 2.7 Umsatzverdienstrate – Kindle 114

Diese beiden Kennzahlen werden ergänzt, aber erst nach Prüfung der konkreten Buchdefinition.

---

## 4. Finanzielle Stabilität

### Schmidlin-Kennzahlen im Excel

| Buch | Kennzahl | Excel | Entscheidung |
|---|---|---|---|
| 3.1 / 118 | Eigenkapitalquote | `EK / Gesamtkapital` | behalten |
| 3.2 / 124 | Gearing | `(zinstragende Verb. - Cash) / EK` | behalten; Debt-Definition zentralisieren |
| 3.3 / 129 | Dynamischer Verschuldungsgrad | `Net Debt / FCF` | behalten; nachhaltigen FCF verwenden |
| 3.4 / 135 | Net Debt/EBITDA | `Net Debt / (EBIT + D&A)` | behalten |
| 3.5 / 136 | Sachinvestitionsquote | `Sach-CAPEX / operativer CF` | behalten; OCF-Zeile prüfen |
| 3.7 / 144 | Wachstumsquote | `CAPEX / D&A` | behalten; CAPEX-Definition prüfen |
| 3.9 / 148 | Umlaufintensität | `Umlaufvermögen / Gesamtvermögen` | behalten |
| 3.9 / 148 | Anlagenintensität | `langfristige Vermögenswerte / Gesamtkapital` | behalten; API-Mapping prüfen |
| 3.10 / 151 | Anlagendeckung I | `EK / Anlagevermögen` | behalten |
| 3.10 / 151 | Anlagendeckung II | `(EK + langfristiges FK) / Anlagevermögen` | behalten |
| 3.11 / 153 | Goodwill-Anteil | `Goodwill / EK` | behalten; künftig API statt zwingend manuell |

### Im Buch, im Excel fehlend

- 3.6 Anlagenabnutzungsgrad – Kindle 141
- 3.8 Cash-Burn-Rate – Kindle 145

Cash-Burn wird als **Spezialkennzahl** implementiert und bei profitablen Unternehmen als `nicht anwendbar` dargestellt.

### Sinnvolle Excel-Erweiterungen, die wir behalten

- Zinsdeckungsgrad
- Debt-to-Equity
- Long-Term Debt-to-Equity
- Short-Term Debt-to-Equity
- Relative Verschuldung
- Schulden je Aktie
- Netto-Cash je Aktie
- Buchwert je Aktie
- materieller Buchwert je Aktie
- Intangibles-to-Assets
- Free Cashflow

Wichtig: **Netto-Cash je Aktie wird fachlich geändert.** Das Excel zieht derzeit sämtliche Verbindlichkeiten vom Cash ab. Das neue Tool soll dieselbe Nettofinanzschulden-Definition verwenden wie Gearing und Enterprise Value.

---

## 5. Working Capital

### Vorhanden

- Debitorenlaufzeit
- Kreditorenlaufzeit
- Differenz Debitoren/Kreditoren
- Liquidität 1. Grades / Cash Ratio
- Liquidität 2. Grades / Quick Ratio
- Liquidität 3. Grades / Current Ratio
- Vorratsintensität
- Dauer der Lagerhaltung / DIO

### Zwei wichtige methodische Korrekturen

**Kreditorenlaufzeit:** Das Excel verwendet Betriebskosten als Ersatznenner, weil Morningstar den Materialaufwand damals nicht separat lieferte. Im neuen Tool nutzen wir nach Möglichkeit COGS/Materialaufwand.

**DIO:** Das Excel teilt durchschnittlichen Lagerbestand durch **Umsatz**. Methodisch soll im neuen Tool COGS/Wareneinsatz verwendet werden.

### Im Buch ergänzen

- Umschlagshäufigkeit der Vorräte – Kindle 171
- Geldumschlag / Cash Conversion Cycle – Kindle 172
- Auftragseingang und Auftragsbestand – Kindle 175, nur wenn für das Unternehmen sinnvoll

Für ASML ist Auftragseingang/Backlog fachlich besonders relevant und wird als unternehmensspezifische Kennzahl unterstützt.

---

## 6. Ausschüttungspolitik

Das Excel enthält bereits:
- Dividende / Gewinn
- Dividende / Free Cashflow

Zu ergänzen:
- Aktienrückkäufe – Kindle 213
- Nettoveränderung der verwässerten Aktienzahl
- Kapitalallokationskommentar

Bei Rückkäufen zählt nicht nur der ausgegebene Betrag, sondern ob die Aktienzahl tatsächlich sinkt und ob der Rückkaufpreis wirtschaftlich sinnvoll war.

---

## 7. Bewertungskennzahlen

### Equitymultiplikatoren

Vorhanden:
- KGV
- KBV
- KCV

Fehlt trotz Buchkapitel:
- **KUV / P/S** – Kindle 252

### Enterprise Value

Vorhanden:
- Enterprise Value
- EV/EBITDA
- EV/EBIT
- EV/FCF
- EV/Sales

### Wichtige Korrektur des Enterprise Value

Das Alt-Excel verwendet:

`EV = Marktkapitalisierung + Summe aller Verbindlichkeiten - liquide Mittel`

Das ist für ein sauberes Enterprise-Value-Modell zu breit. Im neuen Tool definieren wir eine nachvollziehbare EV-Brücke auf Basis der **Nettofinanzverschuldung** und gegebenenfalls weiterer relevanter Positionen. Nicht jede Lieferantenverbindlichkeit ist 'Marktwert des Fremdkapitals'.

EV/FCF wird ebenfalls neu validiert, weil der Zähler EV und der Cashflow-Nenner kapitalgeberkonsistent sein müssen.

---

## 8. DCF – vorhandene Logik

Das bestehende Excel folgt einer klaren Equity-DCF-Struktur:

1. Owner Earnings bestimmen
2. Diskontierungsfaktor bestimmen
3. Ewige Rente bestimmen
4. Fairen Aktienkurs bestimmen

### Owner Earnings im Excel

`Net Income + Abschreibungen - CAPEX - Δ Working Capital`

Working Capital:

`Inventory + Receivables - Accounts Payable`

CAPEX:

`PPE Capex + immaterielle Investitionen`

Das ist eine gute Ausgangsbasis und wird in DCF V1 reproduziert. DCF V2 koppelt Umsatz, Margen, CAPEX und Working Capital ökonomisch stärker.

### Alte Prognoselogik

- Gewinn- und Umsatzschätzungen werden teilweise unabhängig vorgegeben.
- Danach werden konstante Wachstumsraten fortgeschrieben.
- CAPEX wird über historischen CAPEX/Umsatz-Durchschnitt geschätzt.
- Abschreibungen werden so hochgerechnet, dass sie langfristig zu Investitionen konvergieren.
- Working Capital wird über historischen WC/Umsatz-Durchschnitt hochgerechnet.

### Was V2 verbessert

- Jahre 1–3: Management Guidance + Analyst Low/Consensus/High
- Jahre 4–5: eigene fundamentale Annahmen
- Jahre 6–10: Fade / Mean Reversion
- Umsatz → Marge → Gewinn → Kapitalbedarf → Owner Earnings
- keine wirtschaftlich widersprüchlichen Vollkombinationen

### Diskontierungsfaktor im Excel

`Eigenkapitalkosten = AAA-10Y-Zins + 1/Faires-KGV + Zusatzwert bis Mindest-EK-Kosten`

Das ist ein **offener methodischer Punkt**. Wir wollen die Schmidlin-Logik bewahren, müssen aber verhindern, dass Wachstum doppelt positiv wirkt: einmal im Cashflow und noch einmal über ein höheres Fair-KGV bzw. niedrigeren Risikoaufschlag. Dafür wird ein separates `Risiko-KGV` geprüft.

### Margin of Safety

Das Excel reduziert den Fair Value direkt um die Sicherheitsmarge. Im neuen Tool wird getrennt:

- Innerer Wert / Fair Value
- aktueller Kurs
- Unter-/Überbewertung
- Kaufgrenze bei gewählter Margin of Safety

---

## 9. Multiplikatorenmethode / Faires KGV

Die vorhandene Struktur bleibt erhalten:

1. Sockel-KGV
2. Finanzielle Stabilität
3. Marktposition
4. Rentabilität
5. Wachstum
6. Individualität
7. Bewertung
8. Fairer Preis je Aktie

Aktuelle Excel-Endformel:

`Fair KGV = Sockel + Finanzielle Stabilität + (Marktposition × Rentabilitätsmultiplikator) + Wachstum + Individualität`

Diese Methode ist ein Kernbestandteil des Tools und wird **nicht automatisiert wegrationalisiert**. Die qualitativen Punkte müssen mit Kommentar und Quelle begründet werden.

Offen für Phase 1.2/6:
- exakte Scoring-Bandbreiten gegen Kindle S. 351 ff. validieren
- Definition des Rentabilitätsmultiplikators prüfen
- Risiko-KGV für DCF sauber vom vollständigen Fair-KGV trennen

---

## 10. VBA-Szenariosimulation

Das aktuelle VBA erzeugt ein vollständiges Kombinationsraster aus Annahmen für Gewinn- und Umsatzwachstum und schreibt resultierende Fair Values in den Bereich ab Zeile 546.

Diese Idee – **viele Szenarien statt eines einzelnen Punktwertes** – bleibt erhalten.

Die Python-Version ersetzt jedoch die Zellkombinatorik später durch:
- Worst / Base / Best als explizite wirtschaftliche Szenarien
- Sensitivitäten
- später probabilistische Simulation mit Plausibilitätsregeln/Korrelationen

---

## 11. Ergebnis der Inventarisierung

### Behalten

Die Grundmethodik, Reihenfolge, Owner-Earnings-DCF, Enterprise-/Equity-Multiples und das faire KGV bleiben Kern des neuen Tools.

### Ergänzen

Buchkennzahlen, die im Excel fehlen: Kapitalumschlag, Umsatzverdienstrate, Anlagenabnutzungsgrad, Cash-Burn-Rate, Inventory Turnover, Cash Conversion Cycle, Auftragseingang/-bestand, KUV, Buybacks und später weitere faire Multiples.

### Fachlich korrigieren/prüfen

- ROE-Nenner / durchschnittliches Eigenkapital
- Kreditorenlaufzeit-Nenner
- DIO-Nenner
- Net Cash per Share
- Enterprise-Value-Brücke
- EV/FCF-Konsistenz
- FCF-Definition
- Risikoaufschlag / Fair-KGV im DCF
- Margin of Safety getrennt vom Fair Value

---

## 12. Nächster Schritt

Phase 1.2:

1. normalisiertes Rohdatenwörterbuch finalisieren
2. jede `adjust/verify`-Kennzahl gegen die konkrete Buchdefinition prüfen
3. festlegen, welche Kennzahlen universell und welche nur bei passenden Geschäftsmodellen angezeigt werden
4. ASML-Rohdatenbedarf daraus ableiten
5. danach Phase 2 Datenprovider implementieren
