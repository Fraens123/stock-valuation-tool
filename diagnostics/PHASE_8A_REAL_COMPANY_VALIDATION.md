# PHASE_8A_REAL_COMPANY_VALIDATION

## 1. Executive Summary
VALIDATION INCONCLUSIVE - ENVIRONMENT / PROVIDER BLOCKED

## 2. Environment Preflight
```json
{
  "configured": {
    "SEC_USER_AGENT": false,
    "ALPHA_VANTAGE_API_KEY": false,
    "STOOQ_QUOTE": true,
    "FRANKFURTER_FX": true,
    "OPEN_ER_FX": true
  },
  "environment_blockers": [
    "ENVIRONMENT_BLOCKED: SEC_USER_AGENT missing"
  ]
}
```

## 3. Validation DB
`diagnostics\runtime\phase8a_validation.sqlite`

## 4. Production Code Path
Diagnostics CSV input: `False`



## 6. ASML Long-History Proof
```json
{
  "status": "NOT_RUN_ENVIRONMENT_BLOCKED",
  "metrics": {},
  "minimum_core_year_count": 0,
  "reason": "ENVIRONMENT_BLOCKED: SEC_USER_AGENT missing"
}
```

## 11. Financial Data Results
Siehe `diagnostics/phase8a_company_results.csv`.

## 12. Calculation Results
Siehe `diagnostics/phase8a_stage_results.csv`.

## 13. Historical Analysis Results
Siehe `diagnostics/phase8a_history_coverage.csv`.

## 14. Business Quality Results
Siehe Company- und Stage-CSV.

## 15. Market Data Results
Siehe Company- und Stage-CSV.

## 16. Assumption Results
Review Required ist fuer echte Unternehmen erlaubt und kein Engine-Fehler.

## 17. Valuation Preview Results
Siehe `bear_fair_value`, `base_fair_value`, `bull_fair_value` in Company-CSV.

## 18. Snapshot / Reopen / Immutability
```json
{
  "reopen_checks": {},
  "idempotency_checks": {}
}
```

## 19. Test Suite
Normaler Testlauf bleibt separat: `pytest -q`.

## Provider Failures
- keine

## Engine Blockers
- keine

## 20. GO / NO-GO
VALIDATION INCONCLUSIVE - ENVIRONMENT / PROVIDER BLOCKED
