# Normalisierung und Jahresabschlussbereinigung

## Ziel

Das Tool muss zwischen **veröffentlichten Zahlen** und **für die Analyse normalisierten Zahlen** unterscheiden. Historische Rohdaten werden niemals überschrieben. Jede Bereinigung ist eine zusätzliche, nachvollziehbare Analystenentscheidung.

Buchreferenzen der Kindle-Ausgabe:
- 8.3 Jahresabschlussbereinigung – Kindle **422**
- 8.3.1 Pro-forma-Abschlüsse und Sondereffekte – Kindle **427**

Die konkrete Buchmethodik wird bei offenen Detailfragen weiter validiert; diese Policy definiert zunächst die Softwarearchitektur und konservative Grundregeln.

---

## 1. Drei Datenebenen

### A. `reported`

Originalwert aus Geschäftsbericht oder normalisiertem Datenprovider.

Beispiele:
- gemeldeter Umsatz
- gemeldetes EBIT
- gemeldeter Jahresüberschuss
- gemeldeter Operating Cash Flow

`reported` wird nach Import nicht manuell verändert.

### B. `adjustment`

Explizite Anpassung mit:
- Metrik
- Periode
- Betrag
- Vorzeichen
- Kategorie
- Begründung
- Quelle
- Nutzer/Ersteller
- Datum

Beispiele:
- einmalige Restrukturierungskosten herausrechnen
- nicht wiederkehrenden Veräußerungsgewinn entfernen
- außergewöhnliche Rechtskosten normalisieren, sofern fachlich begründet

### C. `normalized`

`normalized = reported + Summe der akzeptierten adjustments`

Der normalisierte Wert wird nicht als zweite Wahrheit gespeichert, ohne die Brücke zu zeigen.

---

## 2. Grundregel

**Nicht jede ungewöhnliche Position ist ein Sondereffekt.**

Wenn bestimmte Restrukturierungen, Integrationskosten oder Sonderabschreibungen regelmäßig auftreten, gehören sie möglicherweise wirtschaftlich zum Geschäftsmodell. Die Software darf deshalb keine Position automatisch aus dem Ergebnis entfernen.

Automatisierung darf nur:
- potenzielle Sondereffekte markieren,
- Quellen zeigen,
- Auswirkungen berechnen.

Die Entscheidung `normalisieren / nicht normalisieren` bleibt bewusst nachvollziehbar.

---

## 3. Adjustment-Kategorien

Geplante Kategorien:

- `restructuring`
- `impairment`
- `asset_disposal_gain_loss`
- `litigation`
- `acquisition_integration`
- `one_time_tax`
- `discontinued_operations`
- `accounting_change`
- `exceptional_compensation`
- `other_non_recurring`

Zusätzlich:
- `reclassification_only` für reine Darstellungs-/Mappingkorrekturen ohne wirtschaftliche Ergebnisänderung.

---

## 4. Welche Größen normalisiert werden können

Typische Kandidaten:

- EBIT / Operating Income
- Net Income
- EPS
- Operating Cash Flow, wenn klare nicht nachhaltige Effekte vorliegen
- Free Cash Flow
- Steuerquote

Bilanzwerte werden grundsätzlich nicht 'schöngerechnet'. Falls ein Analyst beispielsweise überschüssige Liquidität oder nicht betriebsnotwendiges Vermögen separat bewertet, geschieht dies als **Bewertungsanpassung**, nicht als manipulierte Bilanzhistorie.

---

## 5. DCF-Verwendung

DCF-Prognosen sollen grundsätzlich von einer **nachhaltigen Ausgangsbasis** starten.

Deshalb zeigt die DCF-Eingangsseite später nebeneinander:

- Reported letzte Periode
- Adjustments
- Normalized letzte Periode
- Analystenschätzung nächstes Jahr
- Management Guidance
- eigene Annahme

Der Nutzer sieht damit sofort, ob die DCF beispielsweise auf einem durch Sondereffekte ungewöhnlich hohen Gewinn startet.

---

## 6. Fair-KGV-Verwendung

Das Fair-KGV wird nicht mit einem zufällig verzerrten EPS multipliziert.

Für den fairen Preis können getrennt angezeigt werden:

- reported EPS
- normalized EPS
- Forward Consensus EPS
- eigene Forward-EPS-Annahme

Die tatsächlich für die Bewertung verwendete Gewinnbasis muss explizit ausgewählt und im Snapshot gespeichert werden.

---

## 7. Historische Kennzahlen

Kennzahlen sollen standardmäßig zwei Modi unterstützen:

- **Reported** – reine veröffentlichte Historie
- **Normalized** – nur wenn für die betreffenden Jahre konkrete Adjustments vorliegen

Charts dürfen eine Normalisierung nicht unsichtbar machen. Wenn ein Wert angepasst wurde, wird dies im UI und Report gekennzeichnet.

---

## 8. Restatements

Ein Restatement ist etwas anderes als eine Analystenbereinigung.

Wenn ein Unternehmen Vorjahreszahlen offiziell neu ausweist:

- ursprüngliche Providerfassung optional als Importversion behalten,
- aktuell veröffentlichte Restated-Zahl als `reported` für die neue Analyse verwenden,
- `restated = true` markieren,
- Quelle und Filing-Date dokumentieren.

Alte abgeschlossene Analyse-Snapshots werden nicht rückwirkend geändert.

So kann der Vergleich später sogar zeigen, dass sich historische veröffentlichte Zahlen zwischen zwei Analysezeitpunkten geändert haben.

---

## 9. Datenmodell-Erweiterung für Phase 2

Vor Implementierung des Importers sollen Rohdaten mindestens folgende Metadaten unterstützen:

- `reported_value`
- `normalized_value` nur abgeleitet oder gecacht
- `normalization_status`
- `source_type`
- `source_url`
- `filing_date`
- `retrieved_at`
- `restated`

Adjustments gehören in eine eigene Tabelle, z. B. `FinancialAdjustmentSnapshot`:

- `analysis_id`
- `metric`
- `period_end`
- `amount`
- `category`
- `reason`
- `source_url`
- `included_in_normalized`

---

## 10. ASML-Referenzfall

Für ASML wird nicht unterstellt, dass bestimmte Kosten automatisch 'bereinigt' werden müssen. Die erste 10-Jahres-Historie wird reported aufgebaut. Erst danach werden relevante Sondereffekte aus den offiziellen Berichten geprüft.

Bei ASML sind insbesondere größere strategische, regulatorische, akquisitionsbezogene oder einmalige Steuer-/Impairment-Effekte Kandidaten zur Prüfung – nicht zur automatischen Eliminierung.

---

## 11. Qualitätsregeln

1. Reported bleibt unverändert.
2. Kein Adjustment ohne Begründung.
3. Kein Adjustment ohne Periode und Quelle.
4. Wiederkehrende 'Einmaleffekte' werden kritisch behandelt.
5. DCF und Fair-KGV zeigen die verwendete Gewinn-/Cashflow-Basis ausdrücklich.
6. Alte Analyse-Snapshots bleiben reproduzierbar.
7. Im PDF ist sichtbar, wenn die Bewertung normalisierte statt reported Zahlen verwendet.
