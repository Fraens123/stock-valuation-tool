# UX Excel Alignment Audit

Ergebnis: GO - EXCEL-/BUCHGEFUEHRTE DEUTSCHE ANALYSE-UX V1

Datum: 2026-08-23

## Scope

Die fachlichen Engines wurden nicht umgebaut. Diese Phase hat nur die deutschsprachige Analyse-UX, deren View-Model, Beschriftungen, Info-Texte, Mapping-Dokumentation und Smoke-/Regressionstests ergänzt.

## Excel-Vorlage

Geprüfte Vorlage: `Bewertung Kone Aufzüge.xlsm`

Blatt: `Krones`

Verwendet für:

- Reihenfolge der Analyse
- deutsche Abschnitts- und Kennzahlenlogik
- didaktische Erklärstruktur
- Trennung von Finanzdaten, Kennzahlen, Bewertung und Zusammenfassung

Nicht verwendet für:

- Übernahme von Excel-Formeln in Frozen Engines
- neue Bewertungsmethodik
- neue Datenimport- oder Calculation-Engine-Regeln

## Umsetzung

| Anforderung | Status | Nachweis |
|---|---|---|
| Lineare Analyse-Seite statt Tab-Dashboard | PASS | `pages/3_Analyse.py` rendert die Analyse vertikal von Überblick bis Zusammenfassung |
| Excel-/Buch-Reihenfolge abgebildet | PASS | `PRIMARY_ANALYSIS_ORDER` enthält 13 Abschnitte |
| Deutsche Labels statt interner Statuscodes | PASS | `src/stock_valuation/ui/labels_de.py` |
| Zentrales Info-System | PASS | `src/stock_valuation/ui/info_catalog.py` |
| Zentrale Layout-Konfiguration | PASS | `src/stock_valuation/ui/analysis_layout.py` |
| Zentrales View-Model | PASS | `src/stock_valuation/ui/analysis_view_model.py` |
| Jeder sichtbare Analysepunkt mit InfoEntry | PASS | `tests/test_analysis_ux.py` |
| Fehlende Werte nicht als 0 darstellen | PASS | `tests/test_analysis_ux.py` |
| Review-Zustände deutsch und nicht als App-Fehler | PASS | `REVIEW_REQUIRED`, `EV_REVIEW_REQUIRED`, `READY_FOR_PREVIEW` sind deutsch gemappt |
| Excel-Mapping dokumentiert | PASS | `docs/EXCEL_TO_APP_ANALYSIS_MAPPING.md` |
| App-Smoke | PASS | Streamlit HTTP 200 auf `http://localhost:8510` |
| Komplette Testsuite | PASS | `221 passed in 2.48s` |

## Bewusst nicht umgesetzt

Folgende Excel-Kennzahlen wurden nicht nachgebaut, weil sie nicht als freigegebene Outputs der eingefrorenen Engines existieren:

- Anlagendeckung
- Long-Term Debt to Equity
- Short-Term Debt to Equity
- Zinsdeckungsgrad
- Schulden je Aktie
- Netto-Cash je Aktie
- Kurs-Buchwert-Verhältnis
- Kurs-Cashflow-Verhältnis
- EV/Umsatz
- EV/FCF

Diese Kennzahlen werden in der UX transparent als `Noch nicht in der aktuellen Engine verfügbar` geführt und nicht still berechnet.

## Tests

Ausgeführt:

```text
.venv\Scripts\python.exe -m pytest -q
```

Ergebnis:

```text
221 passed in 2.48s
```

Zusätzliche Smoke-Checks:

```text
.venv\Scripts\python.exe -m py_compile app.py pages\0_Unternehmen.py pages\1_Datenimport.py pages\2_Manuelle_Daten.py pages\3_Analyse.py pages\4_Kennzahlen.py
```

```text
import ok: app.py
import ok: pages/0_Unternehmen.py
import ok: pages/1_Datenimport.py
import ok: pages/2_Manuelle_Daten.py
import ok: pages/3_Analyse.py
import ok: pages/4_Kennzahlen.py
```

```text
streamlit run app.py -> HTTP 200
```

## Entscheidung

GO - EXCEL-/BUCHGEFUEHRTE DEUTSCHE ANALYSE-UX V1
