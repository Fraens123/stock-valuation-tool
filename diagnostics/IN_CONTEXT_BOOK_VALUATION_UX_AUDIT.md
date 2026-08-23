# PHASE 9C - IN-CONTEXT BOOK VALUATION UX AUDIT

Datum: 2026-08-23

Entscheidung:

GO - EXCEL-/BUCH-WORKFLOW PRAKTISCH NUTZBAR V1

## Ziel

Die Excel-/Buch-Bewertung wurde nicht neu erfunden. Phase 9C macht die vorhandene Book-Valuation praktisch bedienbar:

- fehlende Werte direkt am Verwendungsort eingeben
- keine internen Schluessel als Voraussetzung fuer den Benutzer
- keine stillen Book-Defaults
- ECB-Risk-Free-Rate korrekt aus gespeicherten Market-Facts lesen
- Multiplikatorenmethode als gefuehrten Rechenweg zeigen
- Book-DCF-Szenarien bearbeitbar und persistent machen
- normale Zusammenfassung von technischen Rohcodes trennen
- Infofelder mit explizitem Buch-/Excel-Referenzstatus anzeigen

## Realer ASML-Status

Aktuell manuell zu ergaenzen oder zu bestaetigen:

- Kaeufe immaterieller Anlagewerte fuer Owner Earnings
- risikofreier Zins, falls noch kein ECB-Wert gespeichert ist
- Forecast Net Income fuer Multiplikatorenmethode
- Sockel-KGV und KGV-Aufschlaege als bestaetigte Annahmen
- Book-DCF-Szenarien fuer bear/base/bull
- Nettoverschuldung bzw. kurzfristige Finanzschulden fuer EV, falls Net Debt nicht calculation-ready ist

Der Service verwendet diese fehlenden Werte nicht stillschweigend als 0 oder als Default.

## Direkte Eingaben am Verwendungsort

Status: PASS

Direkt in der Analyse-Seite ergaenzbar:

- Owner Earnings:
  - intangible_purchases je Geschaeftsjahr
  - explizite 0-Bestaetigung je Geschaeftsjahr
  - depreciation_amortization je Geschaeftsjahr
- Enterprise Value:
  - short_term_debt im EV-Pruefblock
- Diskontierungszins:
  - ECB 10Y AAA Zins direkt in Schritt 2 laden
  - manueller Risk-Free-Override direkt in Schritt 2
- Multiplikatorenmethode:
  - Sockel-KGV sichtbar und editierbar
  - Forecast Net Income sichtbar und editierbar
  - KGV-Aufschlaege sichtbar und speicherbar
  - Porter-Punkte und Begruendungen persistent speicherbar
- Book-DCF:
  - bear/base/bull-Szenarien direkt im DCF-Bereich bearbeitbar

## ECB Risk-Free Rate

Status: PASS

Bug behoben:

- gespeicherter ECB-Wert wird als `FinancialFactSnapshot` mit
  `statement = market`
  `metric = risk_free_rate_eur_aaa_10y`
  gelesen
- Book-Service sucht nicht mehr nur in Calculation `base_facts.risk_free_rate`
- EUR-Zins wird nur bei EUR-Bewertungswaehrung verwendet
- manueller Override bleibt moeglich

Regressionstest:

- gespeicherter `risk_free_rate_eur_aaa_10y` wird gefunden
- Discount Rate wird daraus berechenbar

## Keine stillen Defaults

Status: PASS

Entfernt:

- stilles `base_pe -> 7.5`
- stille 0-Aufschlaege
- stille `profitability_multiplier -> 1`
- stille DCF-Werte fuer Growth, Terminal Growth, Projection Years und Margin of Safety
- stiller Forecast-Fallback auf letzten Ist-Jahresueberschuss
- technische Discount-Rate 0 beim Terminal Value

Neue Policy:

- fehlende Werte bleiben `FEHLT`
- Vorschlaege erscheinen als `EMPFOHLENER_STARTWERT`
- erst gespeicherte Werte werden als echte Annahme verwendet

## Multiplikatorenmethode

Status: PASS

Sichtbarer Rechenweg:

- A. Sockel-KGV
- B. Finanzielle Stabilitaet
- C. Marktposition
- D. Rentabilitaet
- E. Wachstum
- F. Individualitaet
- G. Faires KGV
- H. Fairer Aktienkurs

Forecast Net Income wird nicht mehr aus dem letzten Ist-Gewinn gefaelscht. Prioritaet:

1. gespeicherter Annual Estimate
2. passende Management Guidance
3. explizite manuelle Prognose
4. sonst fehlt

## Book-DCF-Szenarien

Status: PASS

Implementiert:

- `bear` = Pessimistisch
- `base` = Basis
- `bull` = Optimistisch

Persistenz:

- Nutzung der bestehenden `ValuationAssumption.scenario`
- Reopen-Test mit temp SQLite bestaetigt Persistenz

Szenario-Tabelle zeigt:

- Owner Earnings Basis
- Wachstum
- Diskontierungszins
- ewiges Wachstum
- PV Owner Earnings
- PV ewige Rente
- fairer Aktienkurs
- Wert nach Sicherheitsmarge
- aktueller Kurs

## Zusammenfassung

Status: PASS

Geaendert:

- Marktinformationen werden getrennt von Review-Hinweisen dargestellt
- Abschlusswaehrung und Handelswaehrung erscheinen nicht mehr als Pruefproblem
- Speicherverhalten wird in der Zusammenfassung erklaert
- technische Details bleiben im technischen Expander

## Buch- und Excel-Bezug

Status: PASS MIT REVIEW-LUECKEN

InfoEntry wurde erweitert um:

- `book_chapter`
- `book_page`
- `excel_location`
- `reference_status`

Anzeige:

- KNOWN: Buch-/Excel-Bezug wird angezeigt
- UNKNOWN: `Buchseite: noch nicht zugeordnet`

Es wurden keine Seitenzahlen erfunden. Noch fehlende Seitenreferenzen sind explizit als nicht zugeordnet markiert.

## Tests

Status: PASS

Ausgefuehrt:

```text
pytest -q
```

Ergebnis:

```text
236 passed in 2.64s
```

Zusatztests:

- ECB-Risk-Free wird aus gespeicherten Market-Facts gelesen
- kein stiller Forecast-Fallback auf Ist-Gewinn
- bear/base/bull Book-DCF-Szenarien bleiben nach DB-Reopen erhalten
- InfoEntries haben expliziten reference_status

## App Smoke

Status: PASS

Ausgefuehrt:

```text
streamlit run app.py --server.headless true --server.port 8516 --browser.gatherUsageStats false
```

Ergebnis:

- HTTP 200
- kein Startup-Crash

## Abschluss

GO - EXCEL-/BUCH-WORKFLOW PRAKTISCH NUTZBAR V1

Naechster Schritt:

Manueller App-Test mit ASML:

1. fehlende Owner-Earnings-Werte direkt im DCF-Schritt ergaenzen
2. ECB-Zins direkt im Diskontierungsblock laden
3. Sockel-KGV und Forecast Net Income speichern
4. Porter-Punkte und KGV-Aufschlaege speichern
5. bear/base/bull-Szenarien speichern
6. App neu starten und Persistenz pruefen
