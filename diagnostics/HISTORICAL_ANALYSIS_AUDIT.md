# HISTORICAL_ANALYSIS_AUDIT

Decision: GO – HISTORICAL ANALYSIS ENGINE V1 FROZEN

## Scope

- Baut historische Zeitreihen aus Calculation Engine V1 und freigegebenen Basiswerten.
- Keine Marktpreise, keine Aktienzahl-Daten, keine DCF-Schaetzungen.
- Ausreisser, negative Jahre und fehlende Jahre werden als Status/Issue sichtbar gemacht.
- CAGR wird fuer 3/5/10 Jahre berechnet; bei nur drei Jahren sind 5Y/10Y explizit INSUFFICIENT_HISTORY.

## Coverage

- YoY-Wachstum: Revenue, Operating Income, Net Income, EBITDA, Operating Cash Flow, Free Cash Flow.
- CAGR: 3 / 5 / 10 Jahre fuer dieselben Wachstumsgroessen.
- Margenentwicklung: Gross, Operating, Net, EBITDA, FCF Margin.
- Kapitalstruktur: Equity Ratio, Debt, Net Debt, Debt/Equity.
- Working Capital: Working Capital, WC/Revenue, Receivables Days, Payables Days, Inventory Intensity, Inventory Days.
- Stabilitaets-/Qualitaetskennzahlen: negative_years, missing_years, volatility je relevanter Zeitreihe.

## Company Runs

| Company | Years | Available historical outputs | Unavailable historical outputs |
| --- | --- | ---: | ---: |
| AAPL | 2023, 2024, 2025 | 86 | 18 |
| ADBE | 2023, 2024, 2025 | 86 | 18 |
| ASML | 2023, 2024, 2025 | 86 | 18 |
| MSFT | 2024, 2025, 2026 | 86 | 18 |
| TSM | 2023, 2024, 2025 | 86 | 18 |

## Explicit Unavailable Cases

- AAPL revenue YoY 2023: MISSING_PRIOR_YEAR
- AAPL operating_income YoY 2023: MISSING_PRIOR_YEAR
- AAPL net_income YoY 2023: MISSING_PRIOR_YEAR
- AAPL ebitda YoY 2023: MISSING_PRIOR_YEAR
- AAPL operating_cash_flow YoY 2023: MISSING_PRIOR_YEAR
- AAPL free_cash_flow YoY 2023: MISSING_PRIOR_YEAR
- AAPL revenue 5Y_CAGR : INSUFFICIENT_HISTORY
- AAPL revenue 10Y_CAGR : INSUFFICIENT_HISTORY
- AAPL operating_income 5Y_CAGR : INSUFFICIENT_HISTORY
- AAPL operating_income 10Y_CAGR : INSUFFICIENT_HISTORY
- AAPL net_income 5Y_CAGR : INSUFFICIENT_HISTORY
- AAPL net_income 10Y_CAGR : INSUFFICIENT_HISTORY
- AAPL ebitda 5Y_CAGR : INSUFFICIENT_HISTORY
- AAPL ebitda 10Y_CAGR : INSUFFICIENT_HISTORY
- AAPL operating_cash_flow 5Y_CAGR : INSUFFICIENT_HISTORY
- AAPL operating_cash_flow 10Y_CAGR : INSUFFICIENT_HISTORY
- AAPL free_cash_flow 5Y_CAGR : INSUFFICIENT_HISTORY
- AAPL free_cash_flow 10Y_CAGR : INSUFFICIENT_HISTORY
- ADBE revenue YoY 2023: MISSING_PRIOR_YEAR
- ADBE operating_income YoY 2023: MISSING_PRIOR_YEAR
- ADBE net_income YoY 2023: MISSING_PRIOR_YEAR
- ADBE ebitda YoY 2023: MISSING_PRIOR_YEAR
- ADBE operating_cash_flow YoY 2023: MISSING_PRIOR_YEAR
- ADBE free_cash_flow YoY 2023: MISSING_PRIOR_YEAR
- ADBE revenue 5Y_CAGR : INSUFFICIENT_HISTORY
- ADBE revenue 10Y_CAGR : INSUFFICIENT_HISTORY
- ADBE operating_income 5Y_CAGR : INSUFFICIENT_HISTORY
- ADBE operating_income 10Y_CAGR : INSUFFICIENT_HISTORY
- ADBE net_income 5Y_CAGR : INSUFFICIENT_HISTORY
- ADBE net_income 10Y_CAGR : INSUFFICIENT_HISTORY
- ADBE ebitda 5Y_CAGR : INSUFFICIENT_HISTORY
- ADBE ebitda 10Y_CAGR : INSUFFICIENT_HISTORY
- ADBE operating_cash_flow 5Y_CAGR : INSUFFICIENT_HISTORY
- ADBE operating_cash_flow 10Y_CAGR : INSUFFICIENT_HISTORY
- ADBE free_cash_flow 5Y_CAGR : INSUFFICIENT_HISTORY
- ADBE free_cash_flow 10Y_CAGR : INSUFFICIENT_HISTORY
- ASML revenue YoY 2023: MISSING_PRIOR_YEAR
- ASML operating_income YoY 2023: MISSING_PRIOR_YEAR
- ASML net_income YoY 2023: MISSING_PRIOR_YEAR
- ASML ebitda YoY 2023: MISSING_PRIOR_YEAR
- ASML operating_cash_flow YoY 2023: MISSING_PRIOR_YEAR
- ASML free_cash_flow YoY 2023: MISSING_PRIOR_YEAR
- ASML revenue 5Y_CAGR : INSUFFICIENT_HISTORY
- ASML revenue 10Y_CAGR : INSUFFICIENT_HISTORY
- ASML operating_income 5Y_CAGR : INSUFFICIENT_HISTORY
- ASML operating_income 10Y_CAGR : INSUFFICIENT_HISTORY
- ASML net_income 5Y_CAGR : INSUFFICIENT_HISTORY
- ASML net_income 10Y_CAGR : INSUFFICIENT_HISTORY
- ASML ebitda 5Y_CAGR : INSUFFICIENT_HISTORY
- ASML ebitda 10Y_CAGR : INSUFFICIENT_HISTORY
- ASML operating_cash_flow 5Y_CAGR : INSUFFICIENT_HISTORY
- ASML operating_cash_flow 10Y_CAGR : INSUFFICIENT_HISTORY
- ASML free_cash_flow 5Y_CAGR : INSUFFICIENT_HISTORY
- ASML free_cash_flow 10Y_CAGR : INSUFFICIENT_HISTORY
- MSFT revenue YoY 2024: MISSING_PRIOR_YEAR
- MSFT operating_income YoY 2024: MISSING_PRIOR_YEAR
- MSFT net_income YoY 2024: MISSING_PRIOR_YEAR
- MSFT ebitda YoY 2024: MISSING_PRIOR_YEAR
- MSFT operating_cash_flow YoY 2024: MISSING_PRIOR_YEAR
- MSFT free_cash_flow YoY 2024: MISSING_PRIOR_YEAR
- MSFT revenue 5Y_CAGR : INSUFFICIENT_HISTORY
- MSFT revenue 10Y_CAGR : INSUFFICIENT_HISTORY
- MSFT operating_income 5Y_CAGR : INSUFFICIENT_HISTORY
- MSFT operating_income 10Y_CAGR : INSUFFICIENT_HISTORY
- MSFT net_income 5Y_CAGR : INSUFFICIENT_HISTORY
- MSFT net_income 10Y_CAGR : INSUFFICIENT_HISTORY
- MSFT ebitda 5Y_CAGR : INSUFFICIENT_HISTORY
- MSFT ebitda 10Y_CAGR : INSUFFICIENT_HISTORY
- MSFT operating_cash_flow 5Y_CAGR : INSUFFICIENT_HISTORY
- MSFT operating_cash_flow 10Y_CAGR : INSUFFICIENT_HISTORY
- MSFT free_cash_flow 5Y_CAGR : INSUFFICIENT_HISTORY
- MSFT free_cash_flow 10Y_CAGR : INSUFFICIENT_HISTORY
- TSM revenue YoY 2023: MISSING_PRIOR_YEAR
- TSM operating_income YoY 2023: MISSING_PRIOR_YEAR
- TSM net_income YoY 2023: MISSING_PRIOR_YEAR
- TSM ebitda YoY 2023: MISSING_PRIOR_YEAR
- TSM operating_cash_flow YoY 2023: MISSING_PRIOR_YEAR
- TSM free_cash_flow YoY 2023: MISSING_PRIOR_YEAR
- TSM revenue 5Y_CAGR : INSUFFICIENT_HISTORY
- TSM revenue 10Y_CAGR : INSUFFICIENT_HISTORY
- ... 10 weitere explizite unavailable rows im CSV.

## Decision

GO – HISTORICAL ANALYSIS ENGINE V1 FROZEN
