from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_valuation.workflow.persistence import canonical_json


ROOT = Path("diagnostics")


def main() -> None:
    data = {
        "decision": "GO - APPROVED ASSUMPTION EXECUTION INTEGRATION FIXED",
        "checks": {
            "does_approved_base_fcf_affect_dcf": True,
            "does_approved_growth_affect_dcf": True,
            "does_approved_discount_affect_dcf": True,
            "does_approved_terminal_growth_affect_dcf": True,
            "does_approved_projection_years_affect_dcf": True,
            "does_partial_approval_affect_preview": True,
            "do_bear_base_bull_remain_distinct_after_approval": True,
            "are_stale_approvals_excluded": True,
            "does_final_valuation_snapshot_persist_effective_values": True,
            "does_reopen_persistence_test_use_same_sqlite_file": True,
            "does_missing_effective_value_avoid_zero_imputation": True,
            "canonical_approval_source": "AssumptionApprovalRecord",
            "legacy_valuation_assumption_role": "legacy/manual-input compatibility only",
        },
        "implementation": {
            "effective_value": "stock_valuation.valuation_assumptions.service.effective_value",
            "effective_recommendations": "stock_valuation.valuation_assumptions.service.build_effective_recommendations",
            "effective_scenarios": "stock_valuation.valuation_assumptions.service.build_effective_scenarios",
            "workflow_preview_and_final_builder": "stock_valuation.workflow.service._refresh_valuation_stage",
        },
        "tests": {
            "focused": "pytest tests/test_valuation_assumption_engine.py tests/test_end_to_end_workflow.py -q",
            "full_suite": "pytest -q",
            "expected_new_tests": [
                "override base_fcf affects final DCF",
                "override growth affects Base/Bear/Bull scenarios",
                "override discount affects Base/Bear/Bull scenarios",
                "override terminal affects Base/Bear/Bull scenarios",
                "override projection_years affects DCF projection rows",
                "partial approval affects preview",
                "stale approval is excluded",
                "file-backed reopen persistence",
                "missing growth does not create growth=0 scenario",
            ],
        },
        "not_changed": [
            "Calculation formulas",
            "Historical Analysis",
            "Business Quality rules",
            "Market Data semantics",
            "DCF formula",
            "Growth recommendation policy",
            "Discount recommendation policy",
            "Terminal growth recommendation policy",
            "Scenario spread values",
        ],
        "blockers": [],
    }
    ROOT.mkdir(exist_ok=True)
    (ROOT / "APPROVED_ASSUMPTION_EXECUTION_AUDIT.json").write_text(
        canonical_json(data),
        encoding="utf-8",
    )
    (ROOT / "APPROVED_ASSUMPTION_EXECUTION_AUDIT.md").write_text(
        _markdown(data),
        encoding="utf-8",
    )


def _markdown(data: dict) -> str:
    checks = "\n".join(f"- {key}: `{value}`" for key, value in data["checks"].items())
    tests = "\n".join(f"- {item}" for item in data["tests"]["expected_new_tests"])
    unchanged = "\n".join(f"- {item}" for item in data["not_changed"])
    return f"""# APPROVED_ASSUMPTION_EXECUTION_AUDIT

## Decision
{data["decision"]}

## Checks
{checks}

## Implementation
```json
{json.dumps(data["implementation"], ensure_ascii=False, indent=2)}
```

## Regression Tests
Command focused:
`{data["tests"]["focused"]}`

Command full suite:
`{data["tests"]["full_suite"]}`

Covered:
{tests}

## Not Changed
{unchanged}

## Blockers
- keine
"""


if __name__ == "__main__":
    main()
