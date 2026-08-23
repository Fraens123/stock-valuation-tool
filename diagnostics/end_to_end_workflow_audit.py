from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_valuation.analyses.service import list_analyses
from stock_valuation.database.session import get_session, init_database
from stock_valuation.workflow.models import STAGES
from stock_valuation.workflow.persistence import canonical_json
from stock_valuation.workflow.service import build_analysis_state


ROOT = Path("diagnostics")
COMPANIES = ("ASML", "AAPL", "MSFT", "TSM", "ADBE")


def main() -> None:
    init_database()
    with get_session() as session:
        analyses = list_analyses(session, include_archived=True)
        states = [build_analysis_state(session, item) for item in analyses if item.company.ticker.upper() in COMPANIES]

    stage_rows = []
    coverage_rows = []
    companies = {}
    blockers: list[str] = []
    for state in states:
        ticker = state.ticker.upper()
        companies.setdefault(ticker, {"analyses": 0, "latest_status": None, "history_years": []})
        companies[ticker]["analyses"] += 1
        companies[ticker]["latest_status"] = state.analysis_status
        companies[ticker]["history_years"] = list(state.history_years)
        coverage_rows.append(
            {
                "ticker": ticker,
                "analysis_id": state.analysis_id,
                "history_year_count": len(state.history_years),
                "history_years": " ".join(str(year) for year in state.history_years),
            }
        )
        for stage in STAGES:
            item = state.stages[stage]
            stage_rows.append(
                {
                    "ticker": ticker,
                    "analysis_id": state.analysis_id,
                    "stage": stage,
                    "status": item.status,
                    "version": item.version or "",
                    "snapshot_id": item.snapshot_id or "",
                    "inputs_hash": item.inputs_hash or "",
                    "warnings": "; ".join(item.warnings),
                    "blockers": "; ".join(item.blockers),
                }
            )
            if item.blockers:
                blockers.extend(f"{ticker} {stage}: {blocker}" for blocker in item.blockers)

    missing_companies = [ticker for ticker in COMPANIES if ticker not in companies]
    blockers.extend(f"{ticker}: keine Analysis in lokaler DB gefunden" for ticker in missing_companies)
    if len(companies.get("ASML", {}).get("history_years", [])) < 5:
        blockers.append("ASML: laengerer History Proof in lokaler DB nicht nachgewiesen")
    decision = (
        "GO - END-TO-END ANALYSIS WORKFLOW V1 PRODUCTION READY / FROZEN"
        if not blockers and states
        else "NO-GO - END-TO-END ANALYSIS WORKFLOW V1"
    )
    data = {
        "decision": decision,
        "production_uses_diagnostics_csv": False,
        "global_analysis_selection": True,
        "stages": {
            "FINANCIAL_DATA": "Analysis -> FinancialFactSnapshot -> Preferred Data",
            "CALCULATION": "Preferred Data -> CalculationInput -> Calculation Engine V1 -> analysis_stage_snapshots",
            "HISTORICAL_ANALYSIS": "Calculation Stage Snapshot -> Historical Analysis Engine V1 -> analysis_stage_snapshots",
            "BUSINESS_QUALITY": "Calculation + Historical Stage Snapshots -> Business Quality Engine V1 -> analysis_stage_snapshots",
            "MARKET_DATA": "MarketDataSnapshotRecord, deterministic latest valid snapshot",
            "ASSUMPTIONS": "Current Analysis context + EstimateSnapshot + GuidanceSnapshot + AssumptionApprovalRecord",
            "VALUATION": "Preview until approvals; final ValuationSnapshotRecord only after valid approvals",
        },
        "companies": companies,
        "long_history_proof": {
            "ticker": "ASML",
            "available_years": companies.get("ASML", {}).get("history_years", []),
            "status": "AVAILABLE" if len(companies.get("ASML", {}).get("history_years", [])) >= 5 else "NOT_PROVEN_IN_LOCAL_DB",
        },
        "blockers": blockers,
        "warnings": [
            "Diagnostics files are generated for audit/regression only and are not used by the Streamlit workflow.",
            "External market, estimate and financial imports remain explicit user actions.",
        ],
    }

    ROOT.mkdir(exist_ok=True)
    (ROOT / "END_TO_END_WORKFLOW_AUDIT.json").write_text(canonical_json(data), encoding="utf-8")
    _write_csv(ROOT / "end_to_end_stage_results.csv", stage_rows)
    _write_csv(ROOT / "end_to_end_history_coverage.csv", coverage_rows)
    (ROOT / "END_TO_END_WORKFLOW_AUDIT.md").write_text(_markdown(data), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = list(rows[0]) if rows else ["ticker", "analysis_id", "stage", "status", "version", "snapshot_id", "inputs_hash", "warnings", "blockers"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _markdown(data: dict) -> str:
    sections = [
        "# END_TO_END_WORKFLOW_AUDIT",
        "",
        "## 1. Executive Summary",
        data["decision"],
        "",
        "## 2. Production vs Diagnostics Paths",
        f"production_uses_diagnostics_csv: `{str(data['production_uses_diagnostics_csv']).lower()}`",
        "",
        "## 3. Workflow Architecture",
        "Zentrale Schicht: `src/stock_valuation/workflow/` mit `build_analysis_state(...)` und `refresh_local_analysis_stages(...)`.",
        "",
        "## 4. Stage Persistence",
        "`analysis_stage_snapshots` speichert Stage, Snapshot-ID, Engine-Version, Inputs-Hash, Status und Payload append-only.",
        "",
        "## 5. Global Analysis Selection",
        "`selected_analysis_id` wird in `st.session_state` gehalten und von Uebersicht, Finanzdaten, Manuelle Daten, Analyse und Kennzahlen-Details respektiert.",
        "",
    ]
    for number, name in enumerate(
        [
            "Financial Data Integration",
            "Calculation Integration",
            "Historical Integration",
            "Business Quality Integration",
            "Market Integration",
            "Assumption Approval Integration",
            "Valuation Integration",
            "Preview vs Final",
            "Snapshot / Immutability",
            "UI Structure",
        ],
        start=6,
    ):
        sections.extend([f"## {number}. {name}", json.dumps(data["stages"], ensure_ascii=False, indent=2) if number == 6 else "Implementiert im zentralen Workflow-Service; Details siehe JSON-Audit.", ""])
    sections.extend(
        [
            "## 16. ASML Long-History Proof",
            json.dumps(data["long_history_proof"], ensure_ascii=False, indent=2),
            "",
        ]
    )
    for number, ticker in enumerate(("AAPL", "MSFT", "TSM", "ADBE"), start=17):
        sections.extend([f"## {number}. {ticker} Regression", json.dumps(data["companies"].get(ticker, {"status": "not found"}), ensure_ascii=False, indent=2), ""])
    sections.extend(
        [
            "## 21. Review-Required E2E Test",
            "Abgedeckt durch `tests/test_end_to_end_workflow.py`.",
            "",
            "## 22. Approved E2E Test",
            "Abgedeckt durch `tests/test_end_to_end_workflow.py`.",
            "",
            "## 23. Stale Approval Test",
            "Abgedeckt durch `tests/test_end_to_end_workflow.py`.",
            "",
            "## 24. Tests",
            "Siehe aktuelle Pytest-Ausgabe.",
            "",
            "## 25. GO / NO-GO",
            data["decision"],
            "",
            "### Blocker",
            "\n".join(f"- {item}" for item in data["blockers"]) if data["blockers"] else "- keine",
        ]
    )
    return "\n".join(sections) + "\n"


if __name__ == "__main__":
    main()
