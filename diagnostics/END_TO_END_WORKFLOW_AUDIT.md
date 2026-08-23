# END_TO_END_WORKFLOW_AUDIT

## 1. Executive Summary
GO - END-TO-END ANALYSIS WORKFLOW V1 PRODUCTION READY / FROZEN

## 2. Production vs Diagnostics Paths
production_uses_diagnostics_csv: `false`
phase8a_decision: `GO - REAL COMPANY END-TO-END VALIDATION PASSED`
validation_db: `diagnostics\runtime\phase8a_validation.sqlite`

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

## 16. Real-Company Validation Status
{
  "ASML": {
    "overall_validation_status": "PASS",
    "financial_status": "REVIEW_REQUIRED",
    "calculation_status": "REVIEW_REQUIRED",
    "historical_status": "READY",
    "business_quality_status": "READY",
    "market_status": "REVIEW_REQUIRED",
    "enterprise_value_status": "EV_REVIEW_REQUIRED",
    "enterprise_value_reason": "MISSING_NET_DEBT",
    "assumption_status": "REVIEW_REQUIRED",
    "valuation_status": "READY_FOR_PREVIEW"
  },
  "AAPL": {
    "overall_validation_status": "PASS",
    "financial_status": "REVIEW_REQUIRED",
    "calculation_status": "REVIEW_REQUIRED",
    "historical_status": "READY",
    "business_quality_status": "READY",
    "market_status": "REVIEW_REQUIRED",
    "enterprise_value_status": "EV_REVIEW_REQUIRED",
    "enterprise_value_reason": "MISSING_NET_DEBT",
    "assumption_status": "REVIEW_REQUIRED",
    "valuation_status": "READY_FOR_PREVIEW"
  },
  "MSFT": {
    "overall_validation_status": "PASS",
    "financial_status": "REVIEW_REQUIRED",
    "calculation_status": "REVIEW_REQUIRED",
    "historical_status": "READY",
    "business_quality_status": "READY",
    "market_status": "READY",
    "enterprise_value_status": "EV_READY",
    "enterprise_value_reason": "CURRENCY_MATCH",
    "assumption_status": "REVIEW_REQUIRED",
    "valuation_status": "READY_FOR_PREVIEW"
  },
  "TSM": {
    "overall_validation_status": "PASS",
    "financial_status": "REVIEW_REQUIRED",
    "calculation_status": "REVIEW_REQUIRED",
    "historical_status": "READY",
    "business_quality_status": "READY",
    "market_status": "REVIEW_REQUIRED",
    "enterprise_value_status": "EV_REVIEW_REQUIRED",
    "enterprise_value_reason": "MISSING_NET_DEBT",
    "assumption_status": "REVIEW_REQUIRED",
    "valuation_status": "READY_FOR_PREVIEW"
  },
  "ADBE": {
    "overall_validation_status": "PASS",
    "financial_status": "REVIEW_REQUIRED",
    "calculation_status": "REVIEW_REQUIRED",
    "historical_status": "READY",
    "business_quality_status": "READY",
    "market_status": "READY",
    "enterprise_value_status": "EV_READY",
    "enterprise_value_reason": "CURRENCY_MATCH",
    "assumption_status": "REVIEW_REQUIRED",
    "valuation_status": "READY_FOR_PREVIEW"
  }
}

## 17. ASML Long-History Proof
{
  "core_historical_series": {
    "capital_expenditures": {
      "calculation_ready_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "calculation_ready_year_count": 19,
      "coverage_status": "CALCULATION_READY_10Y",
      "earliest_source_year": 2007,
      "latest_source_year": 2025,
      "metric": "capital_expenditures",
      "missing_source_years": "",
      "review_pending_fiscal_years": "",
      "review_pending_year_count": 0,
      "source_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "source_year_count": 19,
      "ticker": "ASML"
    },
    "free_cash_flow": {
      "calculation_ready_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "calculation_ready_year_count": 16,
      "coverage_status": "DERIVED_CALCULATION_READY_10Y",
      "earliest_source_year": "",
      "latest_source_year": "",
      "metric": "free_cash_flow",
      "missing_source_years": "",
      "review_pending_fiscal_years": "",
      "review_pending_year_count": 0,
      "source_fiscal_years": "",
      "source_year_count": 0,
      "ticker": "ASML"
    },
    "net_income": {
      "calculation_ready_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "calculation_ready_year_count": 19,
      "coverage_status": "CALCULATION_READY_10Y",
      "earliest_source_year": 2007,
      "latest_source_year": 2025,
      "metric": "net_income",
      "missing_source_years": "",
      "review_pending_fiscal_years": "",
      "review_pending_year_count": 0,
      "source_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "source_year_count": 19,
      "ticker": "ASML"
    },
    "operating_cash_flow": {
      "calculation_ready_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "calculation_ready_year_count": 16,
      "coverage_status": "CALCULATION_READY_10Y",
      "earliest_source_year": 2007,
      "latest_source_year": 2025,
      "metric": "operating_cash_flow",
      "missing_source_years": "2014 2015 2016",
      "review_pending_fiscal_years": "",
      "review_pending_year_count": 0,
      "source_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "source_year_count": 16,
      "ticker": "ASML"
    },
    "operating_income": {
      "calculation_ready_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "calculation_ready_year_count": 19,
      "coverage_status": "CALCULATION_READY_10Y",
      "earliest_source_year": 2007,
      "latest_source_year": 2025,
      "metric": "operating_income",
      "missing_source_years": "",
      "review_pending_fiscal_years": "",
      "review_pending_year_count": 0,
      "source_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "source_year_count": 19,
      "ticker": "ASML"
    },
    "revenue": {
      "calculation_ready_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "calculation_ready_year_count": 19,
      "coverage_status": "CALCULATION_READY_10Y",
      "earliest_source_year": 2007,
      "latest_source_year": 2025,
      "metric": "revenue",
      "missing_source_years": "",
      "review_pending_fiscal_years": "",
      "review_pending_year_count": 0,
      "source_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "source_year_count": 19,
      "ticker": "ASML"
    }
  },
  "minimum_core_year_count": 16,
  "missing_required_metrics": [],
  "status": "LONG_HISTORY_PASS_WITH_REVIEW_GAPS",
  "supporting_derived_history": {
    "depreciation_amortization": {
      "calculation_ready_fiscal_years": "2007 2008 2009 2010 2011",
      "calculation_ready_year_count": 5,
      "coverage_status": "CALCULATION_READY_5Y",
      "earliest_source_year": 2007,
      "latest_source_year": 2025,
      "metric": "depreciation_amortization",
      "missing_source_years": "",
      "review_pending_fiscal_years": "2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "review_pending_year_count": 14,
      "source_fiscal_years": "2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "source_year_count": 19,
      "ticker": "ASML"
    },
    "ebitda": {
      "calculation_ready_fiscal_years": "2007 2008 2009 2010 2011",
      "calculation_ready_year_count": 5,
      "coverage_status": "DERIVED_CALCULATION_READY_5Y",
      "earliest_source_year": "",
      "latest_source_year": "",
      "metric": "ebitda",
      "missing_source_years": "",
      "review_pending_fiscal_years": "2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025",
      "review_pending_year_count": 14,
      "source_fiscal_years": "",
      "source_year_count": 0,
      "ticker": "ASML"
    },
    "net_debt": {
      "calculation_ready_fiscal_years": "",
      "calculation_ready_year_count": 0,
      "coverage_status": "DERIVED_SEMANTIC_REVIEW_REQUIRED",
      "earliest_source_year": "",
      "latest_source_year": "",
      "metric": "net_debt",
      "missing_source_years": "",
      "review_pending_fiscal_years": "2010 2011 2012 2013 2014 2018 2019 2020 2021 2022 2023 2024 2025",
      "review_pending_year_count": 13,
      "source_fiscal_years": "",
      "source_year_count": 0,
      "ticker": "ASML"
    },
    "short_term_debt": {
      "calculation_ready_fiscal_years": "",
      "calculation_ready_year_count": 0,
      "coverage_status": "SEMANTIC_REVIEW_REQUIRED",
      "earliest_source_year": 2010,
      "latest_source_year": 2025,
      "metric": "short_term_debt",
      "missing_source_years": "2015 2016 2017",
      "review_pending_fiscal_years": "2010 2011 2012 2013 2014 2018 2019 2020 2021 2022 2023 2024 2025",
      "review_pending_year_count": 13,
      "source_fiscal_years": "2010 2011 2012 2013 2014 2018 2019 2020 2021 2022 2023 2024 2025",
      "source_year_count": 13,
      "ticker": "ASML"
    }
  }
}

## 18. Review States
FINANCIAL_DATA, CALCULATION, MARKET_DATA und ASSUMPTIONS duerfen fuer reale Unternehmen REVIEW_REQUIRED sein, wenn die Ursache transparent ist. Das ist kein technischer Pipelinefehler.

## 19. Market / Enterprise Value
{
  "ASML": {
    "market_status": "REVIEW_REQUIRED",
    "enterprise_value_status": "EV_REVIEW_REQUIRED",
    "enterprise_value_reason": "MISSING_NET_DEBT"
  },
  "AAPL": {
    "market_status": "REVIEW_REQUIRED",
    "enterprise_value_status": "EV_REVIEW_REQUIRED",
    "enterprise_value_reason": "MISSING_NET_DEBT"
  },
  "MSFT": {
    "market_status": "READY",
    "enterprise_value_status": "EV_READY",
    "enterprise_value_reason": "CURRENCY_MATCH"
  },
  "TSM": {
    "market_status": "REVIEW_REQUIRED",
    "enterprise_value_status": "EV_REVIEW_REQUIRED",
    "enterprise_value_reason": "MISSING_NET_DEBT"
  },
  "ADBE": {
    "market_status": "READY",
    "enterprise_value_status": "EV_READY",
    "enterprise_value_reason": "CURRENCY_MATCH"
  }
}

## 20. Review-Required E2E Test
Abgedeckt durch `tests/test_end_to_end_workflow.py`.

## 21. Approved E2E Test
Abgedeckt durch `tests/test_end_to_end_workflow.py`.

## 22. Stale Approval Test
Abgedeckt durch `tests/test_end_to_end_workflow.py`.

## 23. Tests
Siehe aktuelle Pytest-Ausgabe.

## 24. GO / NO-GO
GO - END-TO-END ANALYSIS WORKFLOW V1 PRODUCTION READY / FROZEN

### Blocker
- keine
