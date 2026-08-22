# Current Task

## Phase 3A – Kapitel-2-Kennzahlen + parallele Datenbereinigung

Der erste echte lokale ASML-Import, die feldweise Primärquellenprüfung und die erste Kennzahlenengine sind erfolgreich gelaufen.

## Verifizierter Stand

- Alpha Vantage `ASML` liefert konsolidierte ASML-Holding-Abschlüsse in EUR.
- erster Snapshot: 720 normalisierte jährliche Rohdatenpunkte über 20 Geschäftsjahre.
- 2024/2025-Primärquellen-Gate ist aktiv.
- `revenue`, `net_income`, `operating_income`, `total_assets`, `shareholders_equity` und `current_liabilities` besitzen eine freigegebene Datenbasis für Phase 3A.
- `depreciation_amortization`, `accounts_receivable`, `inventory`, `ppe_net`, `operating_cash_flow`, `capital_expenditures` u. a. bleiben blockiert.
- EBIT-Marge wird bereits reproduzierbar aus dem gespeicherten Snapshot berechnet und als versionierter `MetricSnapshot` gespeichert.
- lokale Anzeige wurde plausibilisiert: ASML EBIT-Marge 2025 ca. 34,60 %.

Siehe `docs/OPEN_ITEMS.md` und `docs/ASML_ALPHA_VANTAGE_VALIDATION.md`.

## Strang A – Buchmethodik Kapitel 2

Für folgende Kennzahlen ist die Rohdatenbasis bereit, aber die exakte Schmidlin-Definition noch zu verifizieren:

- ROE – Kindle S. 94
- Umsatzrendite – Kindle S. 101
- Kapitalumschlag – Kindle S. 107
- Gesamtkapitalrendite – Kindle S. 109
- ROCE – Kindle S. 111
- Umsatzverdienstrate – Kindle S. 114

Sobald die jeweiligen Formel-/Definitionsabschnitte vorliegen:

1. Methodik in `metrics.yaml` finalisieren.
2. Entscheidung ggf. in `docs/DECISIONS.md` dokumentieren.
3. reine Formel in `metrics/engine.py` implementieren.
4. Daten-Gate und Snapshot-Persistenz in `metrics/service.py` ergänzen.
5. Unit Tests hinzufügen.
6. 10-Jahres-UI analog zur EBIT-Marge ergänzen.

Keine Formel aus allgemeinem Finanzwissen einsetzen, wenn die Projektmethodik ausdrücklich auf Buchprüfung wartet.

## Strang B – technische Datenbereinigung ohne Buchseiten

Parallel dürfen die blockierten Providerfelder untersucht werden.

Priorität 1: `depreciation_amortization`

- verfügbare Alpha-Vantage-Rohfelder/Taxonomie prüfen.
- unterscheiden zwischen Abschreibungen auf PP&E, Amortisation und Right-of-use assets.
- 2024/2025 gegen ASML-Primärquelle plausibilisieren.
- nur bei eindeutiger Semantik neu mappen und Feld-Gate erneut prüfen.
- danach EBITDA-Marge freigeben, sofern Daten-Gate PASS ist.

Priorität 2:

- `accounts_receivable`
- `inventory`
- `ppe_net`
- `short_term_debt`
- `operating_cash_flow`
- `capital_expenditures`
- `cash_and_short_term_investments`

Für jedes Feld gilt: neu mappen, explizit ausschließen oder gezielt eine bessere Quelle evaluieren. Keine stillen Primärquellen-Ersatzwerte.

## Strang C – Datenhistorie

- 2024/2025 bleiben die primären automatischen Kontrolljahre.
- ältere Jahre werden stichprobenartig gegen offizielle ASML-Berichte geprüft.
- ein historisches Providerfeld darf nur verwendet werden, wenn seine Semantik über die Jahre plausibel konsistent ist.

## Bereits implementiert

- `src/stock_valuation/metrics/engine.py`
- `src/stock_valuation/metrics/service.py`
- `pages/4_Kennzahlen.py`
- `tests/test_phase3a_metrics.py`
- Feld-Gates und Seite `Datenqualität`
- `docs/OPEN_ITEMS.md` als Gesamtübersicht

## Noch NICHT tun

- keine offenen Schmidlin-Formeln eigenmächtig festlegen
- keine EBITDA-Marge mit blockiertem D&A
- keine Working-Capital-Kennzahlen aus gesperrten Forderungs-/Vorratsfeldern
- keine FCF-/Owner-Earnings-/DCF-Logik aus blockiertem OCF/CAPEX
- keine Fair-KGV-Punkte oder Risikoaufschläge erfinden

## Nächster Nutzer-Input

Formel-/Definitionsabschnitte aus Kindle S. 94, 101, 107, 109, 111 und 114. Je Kennzahl reicht der relevante Abschnitt; keine langen Buchpassagen übernehmen.

## Definition of Done für den aktuellen Block

- EBIT-Marge bleibt reproduzierbar und getestet.
- die sechs methodisch offenen Kapitel-2-Kennzahlen werden nach Buchprüfung schrittweise freigeschaltet.
- D&A wird technisch geklärt oder ausdrücklich als nicht belastbar dokumentiert.
- EBITDA-Marge wird nur bei freigegebenem D&A aktiviert.
- offene Datenfelder bleiben sichtbar blockiert.
