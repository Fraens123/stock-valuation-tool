# FINAL_DATA_GATE_REPORT

Generated: 2026-08-23T12:04:46.903781+00:00
Decision: GO – FINANCIAL DATA PIPELINE V1 FROZEN

## Summary

| Company | Years | Core required fields | Failed core fields | Conditional not separately reported | Gate classes |
| --- | --- | ---: | ---: | ---: | --- |
| ASML | 2023, 2024, 2025 | 54 | 0 | 0 | {'VALUE_MATCH': 57} |
| AAPL | 2023, 2024, 2025 | 54 | 0 | 0 | {'VALUE_MATCH': 57} |
| MSFT | 2024, 2025, 2026 | 54 | 0 | 0 | {'VALUE_MATCH': 57} |
| TSM | 2023, 2024, 2025 | 54 | 0 | 0 | {'VALUE_MATCH': 38, 'SEC_FALLBACK_ONLY': 19} |
| ADBE | 2023, 2024, 2025 | 54 | 0 | 3 | {'VALUE_MATCH': 54, 'NOT_SEPARATELY_REPORTED': 3} |

## Requirement Review

- inventory wurde von REQUIRED auf CONDITIONAL geaendert.
- Andere bisher globale REQUIRED-Metriken bleiben in V1 CORE_REQUIRED, weil sie die Basisanker fuer GuV, Bilanz, Schulden, Eigenkapital, Cashflow, Capex und D&A bilden.

## Remaining Core Causes

- Keine echten MISSING-, VALUE_MISMATCH-, CURRENCY_MISMATCH- oder PERIOD_MISMATCH-Faelle in CORE_REQUIRED-Feldern.

## Conditional Fields

- ADBE FY2023 inventory: NOT_SEPARATELY_REPORTED; nicht verfuegbare Folgekennzahlen: inventory_intensity;inventory_turnover;inventory_days;cash_conversion_cycle;owner_earnings.
- ADBE FY2024 inventory: NOT_SEPARATELY_REPORTED; nicht verfuegbare Folgekennzahlen: inventory_intensity;inventory_turnover;inventory_days;cash_conversion_cycle;owner_earnings.
- ADBE FY2025 inventory: NOT_SEPARATELY_REPORTED; nicht verfuegbare Folgekennzahlen: inventory_intensity;inventory_turnover;inventory_days;cash_conversion_cycle;owner_earnings.

## Mixed Filing/Restatement Check

- Keine Mischung unterschiedlicher EdgarTools/SEC-Fallback-Versionen innerhalb eines Geschaeftsjahres festgestellt.
