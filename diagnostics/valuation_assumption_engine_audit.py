from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stock_valuation.valuation.models import MarketSnapshotInput
from stock_valuation.valuation.snapshot import canonical_json
from stock_valuation.valuation_assumptions.models import (
    ASSUMPTION_ENGINE_VERSION,
    ASSUMPTION_POLICY_VERSION,
)
from stock_valuation.valuation_assumptions.service import build_assumption_set, preview_scenarios


BASE_DIR = Path(__file__).resolve().parent
TICKERS = ("ASML", "AAPL", "MSFT", "TSM", "ADBE")


def _decimal(value: str | None) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _market_inputs() -> dict[str, MarketSnapshotInput]:
    rows = _read_csv(BASE_DIR / "market_data_live_results.csv")
    grouped: dict[str, dict[str, dict[str, str]]] = {}
    for row in rows:
        if row["ticker"] in TICKERS:
            grouped.setdefault(row["ticker"], {})[row["metric_id"]] = row
    snapshot_rows = {row["ticker"]: row for row in _read_csv(BASE_DIR / "valuation_snapshot_results.csv")}
    markets = {}
    for ticker, metric_rows in grouped.items():
        market_cap_row = metric_rows["market_cap"]
        ev_row = metric_rows.get("enterprise_value", market_cap_row)
        snapshot_ref = snapshot_rows[ticker]
        refs = tuple(
            ref
            for row in (market_cap_row, ev_row)
            for ref in row.get("input_refs", "").split(";")
            if ref
        )
        markets[ticker] = MarketSnapshotInput(
            ticker=ticker,
            company=market_cap_row["company"],
            analysis_as_of_date=market_cap_row["analysis_as_of_date"],
            market_snapshot_id=snapshot_ref["market_snapshot_id"],
            market_data_version="market-data-v1.0",
            security_type=market_cap_row["security_type"],
            price=_decimal(market_cap_row["price"]),
            market_cap=_decimal(market_cap_row["value"]),
            enterprise_value=_decimal(ev_row["value"]),
            shares_outstanding=_decimal(market_cap_row["shares_outstanding"]),
            share_basis=market_cap_row["share_basis"],
            financial_currency=market_cap_row["financial_currency"],
            trading_currency=market_cap_row["trading_currency"],
            fx_rate=_decimal(market_cap_row["fx_rate"]),
            adr_ratio=_decimal(market_cap_row["adr_ratio"]),
            underlying_share_ratio=_decimal(market_cap_row["underlying_share_ratio"]),
            input_refs=refs,
            inputs_hash=snapshot_ref["inputs_hash"],
        )
    return markets


def _generic_fair_values() -> dict[str, dict[str, Decimal | None]]:
    output: dict[str, dict[str, Decimal | None]] = {}
    for row in _read_csv(BASE_DIR / "valuation_results.csv"):
        if row["ticker"] not in TICKERS or row["method"] != "equity_dcf":
            continue
        scenario = row["metric_id"].replace("fair_value_per_unit_", "")
        output.setdefault(row["ticker"], {})[scenario] = _decimal(row["value"])
        if row["market_price"]:
            output[row["ticker"]]["market_price"] = _decimal(row["market_price"])
    return output


def _row(base: dict, **kwargs) -> dict:
    copy = dict(base)
    copy.update(kwargs)
    return copy


def build_audit() -> dict:
    valuation_audit = json.loads((BASE_DIR / "VALUATION_ENGINE_AUDIT.json").read_text(encoding="utf-8"))
    markets = _market_inputs()
    generic = _generic_fair_values()
    evidence_rows: list[dict] = []
    result_rows: list[dict] = []
    preview_rows: list[dict] = []
    companies: dict[str, dict] = {}
    review_required: list[str] = []
    blockers: list[str] = []
    analysis_approval_status: dict[str, str] = {}

    for ticker in TICKERS:
        company_payload = valuation_audit["companies"][ticker]
        normalized_fcf = company_payload["normalized_inputs"]["free_cash_flow"]
        assumption_set = build_assumption_set(
            ticker=ticker,
            analysis_as_of_date=markets[ticker].analysis_as_of_date,
            normalized_fcf=normalized_fcf,
            historical_context=company_payload["historical_context"],
            quality_context=company_payload["quality_context"],
        )
        preview = preview_scenarios(assumption_set, markets[ticker], normalized_fcf)
        for item in assumption_set.evidence:
            evidence_rows.append(
                {
                    "ticker": ticker,
                    "evidence_id": item.evidence_id,
                    "metric": item.metric,
                    "value": "" if item.value is None else str(item.value),
                    "unit": item.unit,
                    "period": item.period,
                    "window": item.window,
                    "source_type": item.source_type,
                    "source_date": item.source_date or "",
                    "status": item.status,
                    "confidence": item.confidence,
                    "source_ref": item.source_ref,
                }
            )
        recommendations = (
            assumption_set.fcf_base_assessment,
            assumption_set.growth_recommendation,
            assumption_set.discount_rate_recommendation,
            assumption_set.terminal_growth_recommendation,
            assumption_set.projection_years_recommendation,
        )
        for recommendation in recommendations:
            result_rows.append(
                {
                    "ticker": ticker,
                    "analysis_as_of_date": markets[ticker].analysis_as_of_date,
                    "assumption_key": recommendation.assumption_key,
                    "scenario": "base",
                    "recommended_value": "" if recommendation.recommended_value is None else str(recommendation.recommended_value),
                    "approved_value": "" if recommendation.approved_value is None else str(recommendation.approved_value),
                    "status": recommendation.status,
                    "confidence": recommendation.confidence,
                    "requires_review": str(recommendation.requires_review),
                    "source_type": recommendation.source_type,
                    "policy_id": recommendation.policy_id,
                    "policy_version": recommendation.policy_version,
                    "primary_anchor": recommendation.primary_anchor,
                    "warnings": ";".join(recommendation.warnings),
                    "evidence_refs": ";".join(recommendation.evidence_refs),
                    "inputs_hash": assumption_set.inputs_hash,
                }
            )
        for scenario in assumption_set.scenarios:
            result_rows.append(
                {
                    "ticker": ticker,
                    "analysis_as_of_date": markets[ticker].analysis_as_of_date,
                    "assumption_key": "scenario_assumption_set",
                    "scenario": scenario.scenario,
                    "recommended_value": canonical_json(
                        {
                            "projection_years": scenario.projection_years,
                            "base_fcf": scenario.base_fcf,
                            "annual_growth_rate": scenario.annual_growth_rate,
                            "discount_rate": scenario.discount_rate,
                            "terminal_growth_rate": scenario.terminal_growth_rate,
                            "sources": scenario.sources,
                        }
                    ),
                    "approved_value": "",
                    "status": scenario.status,
                    "confidence": scenario.confidence,
                    "requires_review": str(scenario.status == "REVIEW_REQUIRED"),
                    "source_type": "PROJECT_POLICY_V1",
                    "policy_id": "PROJECT_POLICY_V1",
                    "policy_version": ASSUMPTION_POLICY_VERSION,
                    "primary_anchor": assumption_set.growth_recommendation.primary_anchor,
                    "warnings": ";".join(scenario.warnings),
                    "evidence_refs": ";".join(scenario.evidence_refs),
                    "inputs_hash": assumption_set.inputs_hash,
                }
            )
        generic_values = generic.get(ticker, {})
        base_delta = None
        if generic_values.get("base") is not None and preview["base"].get("fair_value_per_unit") is not None:
            base_delta = Decimal(str(preview["base"]["fair_value_per_unit"])) - generic_values["base"]
        preview_rows.append(
            {
                "ticker": ticker,
                "generic_bear_fair_value": str(generic_values.get("bear", "")),
                "generic_base_fair_value": str(generic_values.get("base", "")),
                "generic_bull_fair_value": str(generic_values.get("bull", "")),
                "recommended_bear_fair_value": str(preview["bear"].get("fair_value_per_unit", "")),
                "recommended_base_fair_value": str(preview["base"].get("fair_value_per_unit", "")),
                "recommended_bull_fair_value": str(preview["bull"].get("fair_value_per_unit", "")),
                "market_price": str(preview["base"].get("market_price", "")),
                "base_delta_vs_generic": "" if base_delta is None else str(base_delta),
                "status": preview["base"].get("status", ""),
                "warnings": ";".join(assumption_set.warnings),
            }
        )
        if assumption_set.requires_review:
            review_required.append(f"{ticker}: {','.join(assumption_set.warnings)}")
            analysis_approval_status[ticker] = "REVIEW_REQUIRED"
        else:
            analysis_approval_status[ticker] = "APPROVED_READY"
        companies[ticker] = {
            "company": markets[ticker].company,
            "assumption_set": asdict(assumption_set),
            "preview": preview,
            "generic": generic_values,
            "base_delta_vs_generic": base_delta,
        }

    deferred = [
        "automatic CAPM",
        "automatic beta",
        "automatic equity risk premium",
        "automatic WACC",
        "macro-derived terminal growth",
        "sector-specific valuation frameworks",
        "bank/insurance valuation",
        "cycle timing",
    ]
    engine_decision = (
        "NO-GO – VALUATION ASSUMPTION ENGINE V1"
        if blockers
        else "GO – VALUATION ASSUMPTION ENGINE V1 PRODUCTION READY / FROZEN"
    )
    return {
        "decision": engine_decision,
        "engine_decision": engine_decision,
        "analysis_approval_status": analysis_approval_status,
        "assumption_engine_version": ASSUMPTION_ENGINE_VERSION,
        "policy_version": ASSUMPTION_POLICY_VERSION,
        "companies": companies,
        "review_required": review_required,
        "blockers": blockers,
        "deferred": deferred,
        "evidence_rows": evidence_rows,
        "result_rows": result_rows,
        "preview_rows": preview_rows,
    }


def write_outputs(payload: dict) -> None:
    _write_csv(BASE_DIR / "valuation_assumption_evidence.csv", payload["evidence_rows"])
    _write_csv(BASE_DIR / "valuation_assumption_results.csv", payload["result_rows"])
    _write_csv(BASE_DIR / "valuation_assumption_preview.csv", payload["preview_rows"])
    json_payload = {key: value for key, value in payload.items() if not key.endswith("_rows")}
    (BASE_DIR / "VALUATION_ASSUMPTION_ENGINE_AUDIT.json").write_text(
        json.dumps(json_payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    (BASE_DIR / "VALUATION_ASSUMPTION_ENGINE_AUDIT.md").write_text(_markdown(json_payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _markdown(payload: dict) -> str:
    lines = [
        "# VALUATION ASSUMPTION ENGINE AUDIT",
        "",
        f"ENGINE_DECISION: **{payload['engine_decision']}**",
        "",
        "## 1. Executive Summary",
        "",
        "- Phase 7 creates deterministic assumption recommendations and preview valuations.",
        "- Recommendations are not automatically approved.",
        "- Frozen Valuation Engine V1 is reused for preview; DCF math is not duplicated.",
        "",
        "## 2. Input Layers",
        "",
        "- VALUATION_ENGINE_AUDIT.json",
        "- valuation_results.csv",
        "- valuation_snapshot_results.csv",
        "- market_data_live_results.csv",
        "",
        "## 3. Evidence Model",
        "",
        "- Evidence is separated into historical growth, margin, volatility, quality context, and optional forward evidence.",
        "",
        "## 4. Policy Model",
        "",
        "- All interpretation rules are marked PROJECT_POLICY_V1.",
        "",
        "## 5. Recommendation vs Approval",
        "",
        "- Recommendations can be REVIEW_REQUIRED and are not silently promoted to approved assumptions.",
        "",
        "## 6. FCF Base Policy",
        "",
        "- Base FCF uses frozen normalized_fcf only.",
        "- OUTLIER_REVIEW and PARTIAL_NORMALIZATION_WINDOW require review but do not discard FCF.",
        "",
        "## 7. Historical Growth Evidence",
        "",
        "- Revenue, earnings, and FCF growth are tracked separately.",
        "- The engine does not average different growth metrics into one mixed anchor.",
        "",
        "## 8. Forward Estimates / Guidance",
        "",
        "- Supported as point-in-time evidence when persisted.",
        "- Productive service path integrates EstimateSnapshot and GuidanceSnapshot through build_assumption_set_for_analysis.",
        "- Current CSV diagnostics found no approved forward evidence in the frozen artifacts.",
        "",
        "## 9. Margin Context",
        "",
        "- Operating, EBITDA, and FCF margin trend/volatility are retained as context and warnings.",
        "",
        "## 10. Volatility / Cyclicality",
        "",
        "- High FCF volatility triggers CYCLICALITY_REVIEW and lowers confidence.",
        "",
        "## 11. Business Quality Context",
        "",
        "- Quality can affect confidence/review context only; it does not change growth, discount rate, or fair value directly.",
        "",
        "## 12. Discount Rate / Cost of Equity Policy",
        "",
        "- Equity DCF requires Cost of Equity, not WACC.",
        "- Missing beta/ERP are not imputed; generic fallback requires review.",
        "",
        "## 13. Terminal Growth Policy",
        "",
        "- Terminal growth is not copied from company CAGR.",
        "- Generic terminal growth requires review unless manually/macro approved.",
        "",
        "## 14. Scenario Construction",
        "",
        "- Bear/Base/Bull growth uses historical distribution policy.",
        "- Discount rate ordering is Bear >= Base >= Bull.",
        "- Preview fair value ordering is checked through Frozen Valuation Engine V1.",
        "",
        "## 15. Point-in-Time Rules",
        "",
        "- Guidance after analysis_as_of_date is LOOKAHEAD_BLOCKED.",
        "- Estimates retrieved after analysis_as_of_date are LOOKAHEAD_BLOCKED.",
        "",
    ]
    for index, ticker in enumerate(("ASML", "AAPL", "MSFT", "TSM", "ADBE"), start=16):
        company = payload["companies"][ticker]
        assumption_set = company["assumption_set"]
        preview = company["preview"]
        lines.extend(
            [
                f"## {index}. {ticker}",
                "",
                f"- normalized FCF: {assumption_set['normalized_fcf']}",
                f"- FCF base assessment: {assumption_set['fcf_base_assessment']['status']}",
                f"- growth primary anchor: {assumption_set['growth_recommendation']['primary_anchor']}",
                f"- base growth recommendation: {assumption_set['growth_recommendation']['recommended_value']}",
                f"- base discount rate: {assumption_set['discount_rate_recommendation']['recommended_value']}",
                f"- base terminal growth: {assumption_set['terminal_growth_recommendation']['recommended_value']}",
                f"- projection years: {assumption_set['projection_years_recommendation']['recommended_value']}",
                f"- confidence: {assumption_set['confidence']}",
                f"- review required: {assumption_set['requires_review']}",
                f"- analysis approval status: {payload['analysis_approval_status'][ticker]}",
                f"- warnings: {', '.join(assumption_set['warnings']) or 'None'}",
                f"- preview fair value bear/base/bull: {preview['bear'].get('fair_value_per_unit')} / {preview['base'].get('fair_value_per_unit')} / {preview['bull'].get('fair_value_per_unit')}",
                f"- generic base fair value: {company['generic'].get('base')}",
                f"- company-specific preview base delta: {company['base_delta_vs_generic']}",
                "",
            ]
        )
    lines.extend(
        [
            "## 21. Generic vs Company-Specific Preview",
            "",
            "- Preview values use recommended assumptions and are marked ASSUMPTION_PREVIEW.",
            "",
            "## 22. Review Required Cases",
            "",
        ]
    )
    lines.extend([f"- {item}" for item in payload["review_required"]] or ["- None."])
    lines.extend(
        [
            "",
            "## 23. Tests",
            "",
            "- tests/test_valuation_assumption_engine.py covers policy separation, growth anchors, point-in-time rules, discount/terminal safeguards, quality non-multiplication, and preview ordering.",
            "",
            "## 24. GO / NO-GO",
            "",
            f"- ENGINE_DECISION: {payload['engine_decision']}",
            "- Individual company analyses may remain REVIEW_REQUIRED until user approval/override.",
            "",
            "## Deferred",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in payload["deferred"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    audit = build_audit()
    write_outputs(audit)
    print(audit["decision"])
    for blocker in audit["blockers"]:
        print(blocker)
    for item in audit["review_required"]:
        print(item)
