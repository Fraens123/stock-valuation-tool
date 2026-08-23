from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.database.models import Base, ValuationAssumption
from stock_valuation.valuation_assumptions.approvals import (
    APPROVAL_STALE,
    approve_recommended_value,
    load_current_approvals,
    override_assumption,
    validate_approvals,
)
from stock_valuation.valuation_assumptions.service import build_assumption_set, build_assumption_set_for_analysis


BASE_DIR = Path(__file__).resolve().parent


def _normalized_fcf() -> dict:
    return {
        "metric_id": "free_cash_flow",
        "method": "three_year_median",
        "value": "100",
        "currency": "USD",
        "status": "AVAILABLE",
        "issues": [],
        "input_refs": ["calculation:fcf:2023", "calculation:fcf:2024", "calculation:fcf:2025"],
        "inputs_hash": "normalized-hash",
        "used_fiscal_years": [2023, 2024, 2025],
        "input_values": ["90", "100", "110"],
    }


def _historical_context() -> dict:
    return {
        "historical_analysis_version": "historical-v1.0",
        "historical_window": ["2023", "2024", "2025"],
        "revenue_growth": [{"fiscal_year": "2025", "value": "0.10"}],
        "earnings_growth": [{"fiscal_year": "2025", "value": "0.30"}],
        "fcf_growth": [{"fiscal_year": "2025", "value": "-0.05"}],
        "cagr": {"revenue": {"3Y_CAGR": "0.10"}},
        "margin_trend": {"free_cash_flow_margin": "0.01"},
        "volatility": {"free_cash_flow_margin": "0.01"},
        "negative_years": {"free_cash_flow": "0"},
        "missing_years": {"free_cash_flow": "0"},
        "input_refs": ["historical:ref"],
        "context_hash": "historical-hash",
    }


def _quality_context() -> dict:
    return {
        "overall_quality_score": "8.2",
        "overall_quality_assessment": "STRONG",
        "quality_version": "quality-v1.0",
        "context_hash": "quality-hash",
    }


def run_audit() -> dict:
    checks = {
        "approve_recommended_value_records_hash": False,
        "override_requires_note": False,
        "override_preserves_recommendation": False,
        "stale_approval_blocked": False,
        "manual_approvals_used_in_service_path": False,
        "scenario_spreads_derived_from_approved_base": False,
        "approval_and_recommendation_separate": False,
    }
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        company = get_or_create_company(session, name="Test Co", ticker="TEST", currency="USD")
        analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
        recommendation_set = build_assumption_set(
            ticker="TEST",
            analysis_as_of_date=analysis.as_of_date.isoformat(),
            normalized_fcf=_normalized_fcf(),
            historical_context=_historical_context(),
            quality_context=_quality_context(),
        )
        approval = approve_recommended_value(
            session,
            analysis,
            recommendation_set.growth_recommendation,
            recommendation_inputs_hash=recommendation_set.inputs_hash,
        )
        checks["approve_recommended_value_records_hash"] = (
            approval.recommendation_inputs_hash == recommendation_set.inputs_hash
        )
        current = load_current_approvals(session, analysis)
        valid, _warnings = validate_approvals(current, recommendation_inputs_hash=recommendation_set.inputs_hash)
        stale_valid, stale_warnings = validate_approvals(current, recommendation_inputs_hash="changed")
        checks["stale_approval_blocked"] = bool(valid) and not stale_valid and any(
            APPROVAL_STALE in warning for warning in stale_warnings
        )
        try:
            override_assumption(
                session,
                analysis,
                recommendation_set.discount_rate_recommendation,
                approved_value=Decimal("0.11"),
                recommendation_inputs_hash=recommendation_set.inputs_hash,
                note="",
            )
            checks["override_requires_note"] = False
        except ValueError:
            checks["override_requires_note"] = True
        override = override_assumption(
            session,
            analysis,
            recommendation_set.discount_rate_recommendation,
            approved_value=Decimal("0.11"),
            recommendation_inputs_hash=recommendation_set.inputs_hash,
            note="Manual required return review",
        )
        checks["override_preserves_recommendation"] = (
            override.recommended_value == recommendation_set.discount_rate_recommendation.recommended_value
            and override.approved_value == Decimal("0.11000000")
        )
        session.add_all(
            [
                ValuationAssumption(analysis_id=analysis.id, method="equity_dcf", scenario="base", key="discount_rate", value=Decimal("0.11"), unit="decimal_ratio", source_type="MANUAL_APPROVED"),
                ValuationAssumption(analysis_id=analysis.id, method="equity_dcf", scenario="base", key="terminal_growth_rate", value=Decimal("0.025"), unit="decimal_ratio", source_type="MANUAL_APPROVED"),
                ValuationAssumption(analysis_id=analysis.id, method="equity_dcf", scenario="base", key="growth_rate", value=Decimal("0.04"), unit="decimal_ratio", source_type="MANUAL_APPROVED"),
            ]
        )
        session.commit()
        approved_set = build_assumption_set_for_analysis(
            session,
            analysis,
            ticker="TEST",
            normalized_fcf=_normalized_fcf(),
            historical_context=_historical_context(),
            quality_context=_quality_context(),
            latest_actuals={},
        )
        scenarios = {item.scenario: item for item in approved_set.scenarios}
        checks["manual_approvals_used_in_service_path"] = (
            approved_set.discount_rate_recommendation.approved_value == Decimal("0.11000000")
            and approved_set.terminal_growth_recommendation.approved_value == Decimal("0.02500000")
            and approved_set.growth_recommendation.approved_value == Decimal("0.04000000")
        )
        checks["scenario_spreads_derived_from_approved_base"] = (
            scenarios["bear"].discount_rate == Decimal("0.12000000")
            and scenarios["base"].discount_rate == Decimal("0.11000000")
            and scenarios["bull"].discount_rate == Decimal("0.10000000")
            and scenarios["base"].sources["growth_source"] == "MANUAL_APPROVED"
        )
        checks["approval_and_recommendation_separate"] = (
            approved_set.growth_recommendation.recommended_value is not None
            and approved_set.growth_recommendation.approved_value == Decimal("0.04000000")
        )
    engine.dispose()
    blockers = [key for key, value in checks.items() if value is not True]
    decision = (
        "GO – ASSUMPTION APPROVAL WORKFLOW READY"
        if not blockers
        else "NO-GO – ASSUMPTION APPROVAL WORKFLOW"
    )
    return {"decision": decision, "checks": checks, "blockers": blockers}


def write_outputs(payload: dict) -> None:
    (BASE_DIR / "ASSUMPTION_APPROVAL_WORKFLOW_AUDIT.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    lines = [
        "# ASSUMPTION APPROVAL WORKFLOW AUDIT",
        "",
        f"Decision: **{payload['decision']}**",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in payload["checks"].items())
    lines.extend(["", "## Blockers", ""])
    lines.extend([f"- {item}" for item in payload["blockers"]] or ["- None."])
    (BASE_DIR / "ASSUMPTION_APPROVAL_WORKFLOW_AUDIT.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    result = run_audit()
    write_outputs(result)
    print(result["decision"])
    for blocker in result["blockers"]:
        print(blocker)
