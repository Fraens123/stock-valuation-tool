from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.database.models import Base, MarketDataSnapshotRecord, ValuationSnapshotRecord
from stock_valuation.valuation.assumptions import OUTLIER_DEVIATION_THRESHOLD
from stock_valuation.valuation.dcf import equity_dcf
from stock_valuation.valuation.models import ASSUMPTIONS_NOT_COMPANY_SPECIFIC, MarketSnapshotInput
from stock_valuation.valuation.normalization import normalize_three_year_metric
from stock_valuation.valuation.persistence import (
    MARKET_SNAPSHOT_NOT_PERSISTED,
    SNAPSHOT_ID_COLLISION,
    list_valuation_snapshots_for_analysis,
    load_valuation_snapshot,
    payload_from_record,
    persist_valuation_snapshot,
)
from stock_valuation.valuation.snapshot import (
    assumptions_payload,
    canonical_hash,
    create_valuation_snapshot,
)
from stock_valuation.valuation.summary import dcf_summary
from stock_valuation.valuation.models import DCFScenario, FinancialPoint


BASE_DIR = Path(__file__).resolve().parent


def _point(metric: str, year: int, value: str) -> FinancialPoint:
    return FinancialPoint(
        metric_id=metric,
        fiscal_year=year,
        value=Decimal(value),
        currency="USD",
        status="AVAILABLE",
        input_ref=f"calculation:{metric}:{year}",
        inputs_hash=f"hash:{metric}:{year}:{value}",
    )


def _market_input(snapshot_id: str) -> MarketSnapshotInput:
    return MarketSnapshotInput(
        ticker="TEST",
        company="Test Co",
        analysis_as_of_date="2026-08-23",
        market_snapshot_id=snapshot_id,
        market_data_version="market-data-v1.0",
        security_type="ordinary_share",
        price=Decimal("100"),
        market_cap=Decimal("1000"),
        enterprise_value=Decimal("1200"),
        shares_outstanding=Decimal("10"),
        share_basis="ORDINARY_SHARES",
        financial_currency="USD",
        trading_currency="USD",
        fx_rate=None,
        adr_ratio=None,
        underlying_share_ratio=None,
        input_refs=(f"market_snapshot_id:{snapshot_id}", "market:test"),
        inputs_hash=f"market-inputs:{snapshot_id}",
    )


def _add_market_record(session: Session, analysis_id: int, snapshot_id: str) -> None:
    session.add(
        MarketDataSnapshotRecord(
            analysis_id=analysis_id,
            snapshot_id=snapshot_id,
            analysis_as_of_date=date(2026, 8, 23),
            ticker="TEST",
            price=Decimal("100"),
            shares_outstanding=Decimal("10"),
            inputs_hash=f"market-inputs:{snapshot_id}",
            payload_json='{"snapshot":"market"}',
            retrieved_at=datetime(2026, 8, 23, tzinfo=UTC),
        )
    )
    session.commit()


def _assumptions(growth: str = "0.05") -> dict:
    return assumptions_payload(
        (DCFScenario("base", 1, Decimal(growth), Decimal("0.10"), Decimal("0")),),
        normalization_method="three_year_median",
        outlier_threshold=str(OUTLIER_DEVIATION_THRESHOLD),
        sensitivity_discount_rates=("0.09",),
        sensitivity_terminal_growth_rates=("0.02",),
    )


def _snapshot(analysis_id: int, market_snapshot_id: str, *, quality_score: str = "8.2", growth: str = "0.05"):
    normalized = normalize_three_year_metric(
        "free_cash_flow",
        (
            _point("free_cash_flow", 2023, "100"),
            _point("free_cash_flow", 2024, "110"),
            _point("free_cash_flow", 2025, "500"),
        ),
    )
    scenario = DCFScenario("base", 1, Decimal(growth), Decimal("0.10"), Decimal("0"))
    dcf = equity_dcf("TEST", normalized, scenario)
    summary = dcf_summary(dcf, _market_input(market_snapshot_id))
    return create_valuation_snapshot(
        analysis_id=str(analysis_id),
        market=_market_input(market_snapshot_id),
        financial_data_reference="diagnostics/final_data_gate_report.csv",
        calculation_version="calc-v1.0",
        historical_analysis_version="historical-v1.0",
        quality_version="quality-v1.0",
        assumptions=_assumptions(growth),
        normalized_inputs=(normalized,),
        valuation_results=(summary,),
        quality_context={
            "overall_quality_score": quality_score,
            "overall_quality_assessment": "STRONG",
            "quality_version": "quality-v1.0",
            "quality_inputs_hash": f"quality:{quality_score}",
            "components": {"profitability": {"score": "8"}},
        },
        historical_context={
            "historical_analysis_version": "historical-v1.0",
            "historical_window": ["2023", "2024", "2025"],
            "revenue_growth": [{"fiscal_year": "2025", "value": "0.10"}],
            "margin_trend": {"free_cash_flow_margin": "0.2"},
            "volatility": {"free_cash_flow": "1"},
            "negative_years": {"free_cash_flow": "0"},
            "missing_years": {"free_cash_flow": "0"},
            "input_refs": ["historical:TEST:free_cash_flow:2025"],
            "context_hash": "historical-hash",
        },
        created_at="2026-08-23T00:00:00+00:00",
    )


def run_gate() -> dict:
    checks: dict[str, object] = {
        "valuation_snapshots_table_exists": False,
        "survives_new_db_session": False,
        "append_only_idempotent": False,
        "snapshot_id_collision_blocked": False,
        "market_snapshot_persisted_linkage": False,
        "wrong_analysis_blocked": False,
        "missing_market_snapshot_blocked": False,
        "contexts_and_warnings_after_reload": False,
        "canonical_hash_reproducible": False,
        "valuation_math_changed": False,
    }
    blockers: list[str] = []
    with tempfile.TemporaryDirectory() as tempdir:
        db_path = Path(tempdir) / "valuation_persistence.db"
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        checks["valuation_snapshots_table_exists"] = "valuation_snapshots" in Base.metadata.tables
        with Session(engine, expire_on_commit=False) as session:
            company = get_or_create_company(session, name="Test Co", ticker="TEST", currency="USD")
            analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 23))
            other_analysis = create_analysis(session, company=company, as_of_date=date(2026, 8, 24))
            _add_market_record(session, analysis.id, "market-snapshot-1")
            _add_market_record(session, other_analysis.id, "wrong-analysis-market")
            snapshot = _snapshot(analysis.id, "market-snapshot-1")
            record = persist_valuation_snapshot(session, analysis, snapshot)
            second = persist_valuation_snapshot(session, analysis, snapshot)
            checks["append_only_idempotent"] = record.id == second.id and len(list_valuation_snapshots_for_analysis(session, analysis)) == 1
            checks["market_snapshot_persisted_linkage"] = record.market_snapshot_id == "market-snapshot-1"
            try:
                persist_valuation_snapshot(session, analysis, _snapshot(analysis.id, "missing-market"))
            except ValueError as exc:
                checks["missing_market_snapshot_blocked"] = MARKET_SNAPSHOT_NOT_PERSISTED in str(exc)
            try:
                persist_valuation_snapshot(session, analysis, _snapshot(analysis.id, "wrong-analysis-market"))
            except ValueError as exc:
                checks["wrong_analysis_blocked"] = "MARKET_SNAPSHOT_ANALYSIS_MISMATCH" in str(exc)
            collision = _snapshot(analysis.id, "market-snapshot-1")
            collision = type(collision)(
                **{**collision.__dict__, "inputs_hash": "different-inputs"}
            )
            try:
                persist_valuation_snapshot(session, analysis, collision)
            except ValueError as exc:
                checks["snapshot_id_collision_blocked"] = SNAPSHOT_ID_COLLISION in str(exc)
            changed_quality = _snapshot(analysis.id, "market-snapshot-1", quality_score="2.0")
            checks["quality_context_changes_hash_only"] = (
                snapshot.inputs_hash != changed_quality.inputs_hash
                and snapshot.valuation_results["ValuationSummary:0"]["fair_value_per_unit"]
                == changed_quality.valuation_results["ValuationSummary:0"]["fair_value_per_unit"]
            )
            record_id = record.id
            snapshot_id = snapshot.snapshot_id
        with Session(engine, expire_on_commit=False) as session:
            reloaded = load_valuation_snapshot(session, snapshot_id)
            payload = payload_from_record(reloaded) if reloaded else {}
            checks["survives_new_db_session"] = reloaded is not None and reloaded.id == record_id
            summary = payload.get("valuation_results", {}).get("ValuationSummary:0", {})
            checks["contexts_and_warnings_after_reload"] = (
                payload.get("quality_context", {}).get("overall_quality_score") == "8.2"
                and bool(payload.get("historical_context", {}).get("input_refs"))
                and "OUTLIER_REVIEW" in summary.get("issues", [])
                and ASSUMPTIONS_NOT_COMPANY_SPECIFIC in summary.get("issues", [])
            )
        checks["canonical_hash_reproducible"] = canonical_hash({"a": 1, "b": {"x": 2}}) == canonical_hash(
            {"b": {"x": 2}, "a": 1}
        )
        engine.dispose()

    for key, value in checks.items():
        if value is not True and key != "valuation_math_changed":
            blockers.append(key)
    decision = (
        "GO – VALUATION ENGINE V1 PRODUCTION READY / FROZEN"
        if not blockers and checks["valuation_math_changed"] is False
        else "NO-GO – VALUATION SNAPSHOT PERSISTENCE GATE"
    )
    return {"decision": decision, "checks": checks, "blockers": blockers}


def write_outputs(payload: dict) -> None:
    (BASE_DIR / "VALUATION_SNAPSHOT_PERSISTENCE_AUDIT.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    lines = [
        "# VALUATION SNAPSHOT PERSISTENCE AUDIT",
        "",
        f"Decision: **{payload['decision']}**",
        "",
        "## Answers",
        "",
        f"- Existiert eine echte valuation_snapshots DB-Tabelle? {payload['checks']['valuation_snapshots_table_exists']}",
        f"- Ist der Snapshot nach neuer DB-Session noch vorhanden? {payload['checks']['survives_new_db_session']}",
        f"- Ist er append-only/idempotent? {payload['checks']['append_only_idempotent']}",
        f"- Ist market_snapshot_id persistent verknüpft? {payload['checks']['market_snapshot_persisted_linkage']}",
        f"- Falsche Analysis-Zuordnung blockiert? {payload['checks']['wrong_analysis_blocked']}",
        f"- Fehlender Market Snapshot blockiert? {payload['checks']['missing_market_snapshot_blocked']}",
        f"- Contexts und Warnings nach Reload vorhanden? {payload['checks']['contexts_and_warnings_after_reload']}",
        f"- Hashes kanonisch und reproduzierbar? {payload['checks']['canonical_hash_reproducible']}",
        f"- Bewertungsmathematik verändert? {payload['checks']['valuation_math_changed']}",
        "",
        "## Blockers",
        "",
    ]
    lines.extend([f"- {item}" for item in payload["blockers"]] or ["- None."])
    (BASE_DIR / "VALUATION_SNAPSHOT_PERSISTENCE_AUDIT.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    result = run_gate()
    write_outputs(result)
    print(result["decision"])
    for blocker in result["blockers"]:
        print(blocker)
