# APPROVED_ASSUMPTION_EXECUTION_AUDIT

## Decision
GO - APPROVED ASSUMPTION EXECUTION INTEGRATION FIXED

## Checks
- does_approved_base_fcf_affect_dcf: `True`
- does_approved_growth_affect_dcf: `True`
- does_approved_discount_affect_dcf: `True`
- does_approved_terminal_growth_affect_dcf: `True`
- does_approved_projection_years_affect_dcf: `True`
- does_partial_approval_affect_preview: `True`
- do_bear_base_bull_remain_distinct_after_approval: `True`
- are_stale_approvals_excluded: `True`
- does_final_valuation_snapshot_persist_effective_values: `True`
- does_reopen_persistence_test_use_same_sqlite_file: `True`
- does_missing_effective_value_avoid_zero_imputation: `True`
- canonical_approval_source: `AssumptionApprovalRecord`
- legacy_valuation_assumption_role: `legacy/manual-input compatibility only`

## Implementation
```json
{
  "effective_value": "stock_valuation.valuation_assumptions.service.effective_value",
  "effective_recommendations": "stock_valuation.valuation_assumptions.service.build_effective_recommendations",
  "effective_scenarios": "stock_valuation.valuation_assumptions.service.build_effective_scenarios",
  "workflow_preview_and_final_builder": "stock_valuation.workflow.service._refresh_valuation_stage"
}
```

## Regression Tests
Command focused:
`pytest tests/test_valuation_assumption_engine.py tests/test_end_to_end_workflow.py -q`

Command full suite:
`pytest -q`

Covered:
- override base_fcf affects final DCF
- override growth affects Base/Bear/Bull scenarios
- override discount affects Base/Bear/Bull scenarios
- override terminal affects Base/Bear/Bull scenarios
- override projection_years affects DCF projection rows
- partial approval affects preview
- stale approval is excluded
- file-backed reopen persistence
- missing growth does not create growth=0 scenario

## Not Changed
- Calculation formulas
- Historical Analysis
- Business Quality rules
- Market Data semantics
- DCF formula
- Growth recommendation policy
- Discount recommendation policy
- Terminal growth recommendation policy
- Scenario spread values

## Blockers
- keine
