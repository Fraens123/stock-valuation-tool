# MISSING DATA ASSISTANT AUDIT

Status: GO - FEHLENDE-DATEN-ASSISTENT V1

## Scope

Phase 9E wurde als UI-/Workflow-Erweiterung fuer das Finanzdaten-Arbeitsblatt umgesetzt.
Es wurden keine neuen Engines gebaut und keine eingefrorene Bewertungs-, Market-, Historical-,
Calculation- oder Financial-Data-Pipeline-Methodik fachlich umgebaut.

## Implementierte Komponenten

- Zentraler Service: `src/stock_valuation/data/missing_data_search.py`
- UI-Anbindung: `src/stock_valuation/ui/financial_worksheet.py`
- Streamlit-Integration: `pages/1_Datenimport.py`
- Regressionstests: `tests/test_missing_data_search.py`, `tests/test_financial_worksheet.py`

## Zellstatus

Der Assistent unterscheidet jetzt explizit:

- `VORHANDEN_UND_FREIGEGEBEN`
- `VORHANDEN_ABER_PRUEFUNG_ERFORDERLICH`
- `OFFIZIELLER_KANDIDAT_GEFUNDEN`
- `ABLEITBAR`
- `NICHT_SEPARAT_BERICHTET`
- `NICHT_GEFUNDEN`
- `MANUELL_BESTAETIGT`
- `MANUELL_UEBERSCHRIEBEN`

Ein fehlender Fact wird nicht automatisch als 0 behandelt. Manuelle Overrides erzeugen
separate `manual_override`-Facts und lassen importierte Originalfacts unveraendert erhalten.

## Kandidatenmodell

`MissingDataCandidate` enthaelt:

- Metrik und Geschaeftsjahr
- Wert, Waehrung und Quelle
- Provider Field / Filing Link / Filing Date / Retrieved At
- Kandidatentyp
- Semantic Status und Begruendung
- Confidence
- `input_refs` fuer alle tatsaechlich verwendeten Facts
- optionale Formel fuer abgeleitete Kandidaten

`MissingDataSearchResult` klassifiziert:

- `FOUND_SAFE`
- `FOUND_REVIEW_REQUIRED`
- `MULTIPLE_CANDIDATES`
- `NOT_FOUND`
- `NOT_SEPARATELY_REPORTED`

## Suchreihenfolge

Die Suche nutzt nur vorhandene Infrastruktur und gespeicherte offizielle Kandidaten:

1. bereits importierte strukturierte Primaerdaten
2. alternative zulaessige Standard-XBRL-Concepts
3. Company Extension XBRL
4. Original Filing / XBRL
5. offizielle Filing-Tabellen
6. offizielle Filing-Notes / Text
7. ESEF / offizieller Jahresbericht
8. freigegebener externer Fallback
9. manuelle Eingabe

Diagnostics-CSV wird nicht als Produktquelle verwendet.

## Short-Term-Debt-Policy

Kurzfristige Finanzschulden werden nicht aus `CurrentLiabilities - AccountsPayable`
oder aehnlichen unsicheren Heuristiken gebaut.

Explizit abgelehnt werden unter anderem:

- `AccountsPayable`
- `CurrentLiabilities` / `LiabilitiesCurrent`
- Trade-Payables-Felder
- Leasingverbindlichkeiten
- Steuerverbindlichkeiten

`Current Portion of Long-Term Debt` bleibt ein plausibler offizieller Kandidat, wird aber
als `FOUND_REVIEW_REQUIRED` behandelt, wenn daraus nicht sicher die vollstaendige
kurzfristige Finanzschuld hervorgeht.

## D&A-Policy

Depreciation/Amortization wird unterstuetzt als:

- sicherer strukturierter Kandidat, wenn das Feld semantisch freigegeben ist
- abgeleitete Summe aus Depreciation plus Amortization, wenn beide Komponenten fuer
  dasselbe Jahr separat vorhanden sind

Bei nur einer vorhandenen Komponente wird kein Wert konstruiert. Der Status bleibt
pruefpflichtig; es findet kein Null-Imputing statt.

## UI-Verhalten

- Das Finanzdaten-Arbeitsblatt zeigt offene und pruefpflichtige Zellen direkt.
- Bewertungskritische offene Werte koennen separat gefiltert werden.
- Pro Zelle sind Kandidatensuche, Kandidatenanzeige, manuelle Bestaetigung,
  manuelles Ueberschreiben und Override-Entfernung moeglich.
- Die UI zeigt Auswirkungen auf Folgekennzahlen, zum Beispiel Net Debt, EV,
  EV/EBITDA oder EBITDA.
- Kandidaten mit Review-Pflicht werden nicht automatisch freigegeben.

## ASML-Check

Lokaler Stand: ASML Analyse `id=1`, Stichtag `2026-08-23`, Revision `1`.

Short-Term Debt:

| Jahr | Status | Wert | Waehrung | Quelle | Provider Field | Grund |
|---:|---|---:|---|---|---|---|
| 2023 | FOUND_REVIEW_REQUIRED | 100000.00000000 | EUR | sec_companyfacts | aggregation:us-gaap:LongTermDebtCurrent | Current Portion ist plausibel, aber nicht automatisch vollstaendige kurzfristige Finanzschuld. |
| 2024 | FOUND_REVIEW_REQUIRED | 1010300000.00000000 | EUR | sec_companyfacts | aggregation:us-gaap:LongTermDebtCurrent | Current Portion ist plausibel, aber nicht automatisch vollstaendige kurzfristige Finanzschuld. |
| 2025 | FOUND_REVIEW_REQUIRED | 1681900000.00000000 | EUR | sec_companyfacts | aggregation:us-gaap:LongTermDebtCurrent | Current Portion ist plausibel, aber nicht automatisch vollstaendige kurzfristige Finanzschuld. |

D&A:

| Jahr | Preferred-Status | Calculation Ready | Wert | Waehrung | Quelle |
|---:|---|---|---:|---|---|
| 2023 | primary_reviewed_pass | true | 739800000.00000000 | EUR | sec_companyfacts |
| 2024 | primary_reviewed_pass | true | 918600000.00000000 | EUR | sec_companyfacts |
| 2025 | primary_reviewed_pass | true | 1025900000.00000000 | EUR | sec_companyfacts |

## Regressionstests

Abgedeckt:

- Safe Candidate wird als `FOUND_SAFE` klassifiziert.
- Semantisch unsicherer Kandidat wird als `FOUND_REVIEW_REQUIRED` klassifiziert.
- Mehrere Kandidaten werden nicht automatisch ausgewaehlt.
- Nicht separat berichtete Werte bleiben `NOT_SEPARATELY_REPORTED`.
- D&A kann aus vollstaendigen Komponenten abgeleitet werden.
- Unvollstaendige D&A-Komponenten erzeugen keinen stillen Wert.
- Short-Term Debt wird nicht aus Current Liabilities / Payables abgeleitet.
- Manual Override persistiert, erhaelt Originalfacts und kann entfernt werden.
- Manual Override fuer Short-Term Debt macht Net Debt nach Recalculation verfuegbar.

## Testlauf

`pytest -q`

Ergebnis: 259 passed, 1 warning.

## Entscheidung

GO - FEHLENDE-DATEN-ASSISTENT V1
