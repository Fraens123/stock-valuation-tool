# PHASE 9B.1 - BOOK VALUATION PRODUCTION INTEGRATION AUDIT

Datum: 2026-08-23

Entscheidung:

GO - BOOK VALUATION PRODUCTION INTEGRATION READY

## Umfang

Phase 9B.1 integriert die Excel-/Buch-Bewertung produktiv in den bestehenden Analysepfad. Es wurden keine neuen Engines und keine neue Bewertungsmethodik eingeführt.

## Produktive Integration

Status: PASS

- Zentraler Service erstellt: `src/stock_valuation/book_valuation/service.py`
- Einstiegspunkt: `build_book_valuation_for_analysis(session, analysis, workflow_state)`
- Streamlit ruft den Service in `pages/3_Analyse.py` auf.
- Streamlit enthält keine eigene Book-Valuation-Berechnungslogik.
- Ergebnis wird an `build_analysis_view_model(..., book_valuation_result=...)` übergeben.
- `source == "book"` ist nicht mehr hart auf leere Werte verdrahtet, sondern rendert echte Service-Werte über `_book_value(...)`.

## Verwendete Bewertungsfunktionen im Produktivpfad

Status: PASS

- Owner Earnings werden aus Calculation-Ready-Daten aufgebaut.
- `excel_book_discount_rate(...)` wird im Service verwendet.
- `terminal_value(...)` wird im Service verwendet.
- `fair_value(...)` wird im Service verwendet.
- `fair_pe_from_components(...)` wird im Service verwendet.

## Owner-Earnings-Regel

Status: PASS

Implementierte Formel:

```text
operating_working_capital = inventory + accounts_receivable - accounts_payable
change_in_operating_working_capital = current_owc - previous_owc
owner_earnings_capex = capital_expenditures + intangible_purchases
owner_earnings = net_income + depreciation_amortization - owner_earnings_capex - change_in_operating_working_capital
```

Wichtig:

- Fehlende `intangible_purchases` werden nicht automatisch als 0 behandelt.
- 0 wird nur verwendet, wenn der Nutzer diesen Wert explizit als Book-Assumption bestätigt und speichert.
- Fehlende Vorjahreswerte für Working Capital erzeugen Review-/Unavailable-Status statt stillem Imputing.

## Market Refresh

Status: PASS

Implementiert:

- Shares-Priorität: manuelle Eingabe, vorhandener Share-Snapshot, SEC-Share-Provider, sonst Review.
- Net Debt wird aus dem Calculation-Stage-Snapshot übernommen, wenn `net_debt` dort `AVAILABLE` ist.
- EV bleibt `EV_REVIEW_REQUIRED`, wenn Net Debt nicht calculation-ready ist.

Real-ASML-Beobachtung lokal:

- Market Cap: `334050000000 EUR`
- Enterprise Value: nicht verfügbar wegen `MISSING_NET_DEBT`
- Equity-Multiples verfügbar: PE, PB, P/OCF, P/FCF
- EV-Multiples nicht verfügbar, weil EV wegen Net Debt Review offen ist

## Book-Valuation-Snapshot

Status: PASS

Persistiert werden:

- Methode/Version: `excel-book-valuation-v1.0`
- Ergebnis-Payload
- manuelle Inputs
- Marktinputs
- Input-Referenzen
- Input-Hash
- Warnungen und Review-Status

Zusätzlich wurde die Snapshot-Idempotenz robust gemacht:

- Valuation-Snapshots mit identischem fachlichem Payload, aber neuem `created_at`, werden als identisch behandelt.
- Bereits vorhandene Stage-Snapshots mit identischer stabiler Snapshot-ID werden wiederverwendet.
- Immutable Snapshots werden nicht überschrieben.

## Real-App-/ASML-Status

Status: PASS MIT FACHLICHEN REVIEW-LÜCKEN

Produktiv sichtbar:

- `market_cap`: `334,0 Mrd. EUR`
- `latest_fy_pe`: `34,76x`
- `latest_fy_pb`: `17,03x`
- `latest_fy_p_ocf`: `26,39x`
- `latest_fy_p_fcf`: `30,14x`
- `fair_pe`: `7,50x`
- `multiplicator_fair_price_per_share`: `183,4 EUR`

Noch nicht verfügbar, fachlich korrekt als Review/Unavailable:

- `owner_earnings`: `MISSING_OWNER_EARNINGS_CAPEX`
- `cost_of_equity`: `MISSING_DISCOUNT_INPUT`
- `terminal_value`: `MISSING_LAST_OWNER_EARNINGS`
- `fair_value`: `MISSING_EQUITY_VALUE_OR_SHARES`
- `enterprise_value`: `MISSING_NET_DEBT`

Diese offenen Punkte sind keine Integrationsfehler. Sie entstehen aus fehlenden oder nicht bestätigten Eingaben/Daten:

- fehlende oder nicht bestätigte `intangible_purchases`
- fehlender Risk-Free-Rate-Input
- fehlendes calculation-ready Net Debt
- fehlende Porter-/KGV-Detailannahmen für einzelne Add-ons

## Tests

Status: PASS

Ausgeführt:

```text
pytest -q
```

Ergebnis:

```text
232 passed in 2.57s
```

Zusätzliche Regressionen:

- Book-Valuation-Service berechnet echte Werte und persistiert Snapshot.
- Book-Werte werden im ViewModel gerendert.
- Market Refresh übernimmt vorhandene Shares.
- Market Refresh übernimmt `net_debt` aus Calculation.
- Valuation-Snapshot-Idempotenz ignoriert nur `created_at`.

## App Smoke

Status: PASS

Ausgeführt:

```text
streamlit run app.py --server.headless true --server.port 8514 --browser.gatherUsageStats false
```

Ergebnis:

- HTTP `200`
- kein Startup-Crash
- `app.py` importierbar
- `pages/0_Unternehmen.py` importierbar
- `pages/1_Datenimport.py` importierbar
- `pages/2_Manuelle_Daten.py` importierbar
- `pages/3_Analyse.py` importierbar
- `pages/4_Kennzahlen.py` importierbar

## Abschluss

GO - BOOK VALUATION PRODUCTION INTEGRATION READY

Keine neue Engine-Phase starten. Nächster Schritt ist der manuelle App-Test der produktiven Bewertungsoberfläche.
