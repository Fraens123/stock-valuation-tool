# END_TO_END_WORKFLOW_AUDIT

## 1. Executive Summary
NO-GO - END-TO-END ANALYSIS WORKFLOW V1

## 2. Production vs Diagnostics Paths
production_uses_diagnostics_csv: `false`

## 3. Workflow Architecture
Zentrale Schicht: `src/stock_valuation/workflow/` mit `build_analysis_state(...)` und `refresh_local_analysis_stages(...)`.

## 4. Stage Persistence
`analysis_stage_snapshots` speichert Stage, Snapshot-ID, Engine-Version, Inputs-Hash, Status und Payload append-only.

## 5. Global Analysis Selection
`selected_analysis_id` wird in `st.session_state` gehalten und von Uebersicht, Finanzdaten, Manuelle Daten, Analyse und Kennzahlen-Details respektiert.

## 6. Financial Data Integration
{
  "FINANCIAL_DATA": "Analysis -> FinancialFactSnapshot -> Preferred Data",
  "CALCULATION": "Preferred Data -> CalculationInput -> Calculation Engine V1 -> analysis_stage_snapshots",
  "HISTORICAL_ANALYSIS": "Calculation Stage Snapshot -> Historical Analysis Engine V1 -> analysis_stage_snapshots",
  "BUSINESS_QUALITY": "Calculation + Historical Stage Snapshots -> Business Quality Engine V1 -> analysis_stage_snapshots",
  "MARKET_DATA": "MarketDataSnapshotRecord, deterministic latest valid snapshot",
  "ASSUMPTIONS": "Current Analysis context + EstimateSnapshot + GuidanceSnapshot + AssumptionApprovalRecord",
  "VALUATION": "Preview until approvals; final ValuationSnapshotRecord only after valid approvals"
}

## 7. Calculation Integration
Implementiert im zentralen Workflow-Service; Details siehe JSON-Audit.

## 8. Historical Integration
Implementiert im zentralen Workflow-Service; Details siehe JSON-Audit.

## 9. Business Quality Integration
Implementiert im zentralen Workflow-Service; Details siehe JSON-Audit.

## 10. Market Integration
Implementiert im zentralen Workflow-Service; Details siehe JSON-Audit.

## 11. Assumption Approval Integration
Implementiert im zentralen Workflow-Service; Details siehe JSON-Audit.

## 12. Valuation Integration
Implementiert im zentralen Workflow-Service; Details siehe JSON-Audit.

## 13. Preview vs Final
Implementiert im zentralen Workflow-Service; Details siehe JSON-Audit.

## 14. Snapshot / Immutability
Implementiert im zentralen Workflow-Service; Details siehe JSON-Audit.

## 15. UI Structure
Implementiert im zentralen Workflow-Service; Details siehe JSON-Audit.

## 16. ASML Long-History Proof
{
  "ticker": "ASML",
  "available_years": [],
  "status": "NOT_PROVEN_IN_LOCAL_DB"
}

## 17. AAPL Regression
{
  "status": "not found"
}

## 18. MSFT Regression
{
  "status": "not found"
}

## 19. TSM Regression
{
  "status": "not found"
}

## 20. ADBE Regression
{
  "status": "not found"
}

## 21. Review-Required E2E Test
Abgedeckt durch `tests/test_end_to_end_workflow.py`.

## 22. Approved E2E Test
Abgedeckt durch `tests/test_end_to_end_workflow.py`.

## 23. Stale Approval Test
Abgedeckt durch `tests/test_end_to_end_workflow.py`.

## 24. Tests
Siehe aktuelle Pytest-Ausgabe.

## 25. GO / NO-GO
NO-GO - END-TO-END ANALYSIS WORKFLOW V1

### Blocker
- AAPL: keine Analysis in lokaler DB gefunden
- MSFT: keine Analysis in lokaler DB gefunden
- TSM: keine Analysis in lokaler DB gefunden
- ADBE: keine Analysis in lokaler DB gefunden
- ASML: laengerer History Proof in lokaler DB nicht nachgewiesen
