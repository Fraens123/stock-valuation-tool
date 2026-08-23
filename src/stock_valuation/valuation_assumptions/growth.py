from __future__ import annotations

from decimal import Decimal
from statistics import median

from stock_valuation.valuation_assumptions.models import (
    INSUFFICIENT_EVIDENCE,
    LOW,
    PROJECT_POLICY_ID,
    RECOMMENDED,
    REVIEW_REQUIRED,
    ASSUMPTION_POLICY_VERSION,
    AssumptionEvidence,
    AssumptionRecommendation,
)
from stock_valuation.valuation_assumptions.policy import (
    HIGH_VOLATILITY_THRESHOLD,
    MAX_SCENARIO_SPREAD,
    MIN_SCENARIO_SPREAD,
    STABLE_MARGIN_VOLATILITY_THRESHOLD,
    clamp_growth,
    confidence_from_history,
)


def growth_recommendation(evidence: tuple[AssumptionEvidence, ...]) -> AssumptionRecommendation:
    anchors = _anchors_by_metric(evidence)
    warnings: list[str] = []
    primary_anchor = ""
    selected: Decimal | None = None
    evidence_refs: list[str] = []
    if anchors.get("free_cash_flow", {}).get("cagr"):
        selected, ref = _latest_window(anchors["free_cash_flow"]["cagr"])
        primary_anchor = "historical FCF CAGR"
        evidence_refs.append(ref)
    elif anchors.get("revenue", {}).get("cagr"):
        selected, ref = _latest_window(anchors["revenue"]["cagr"])
        primary_anchor = "historical revenue CAGR"
        evidence_refs.append(ref)
        if not _fcf_margin_stable(evidence):
            warnings.append("REVENUE_PROXY_WITH_UNSTABLE_FCF_MARGIN")
    elif anchors.get("revenue", {}).get("yoy"):
        values = anchors["revenue"]["yoy"]
        selected = Decimal(str(median([item[0] for item in values])))
        primary_anchor = "historical median revenue YoY"
        evidence_refs.extend(item[1] for item in values)
    if selected is None:
        return AssumptionRecommendation(
            "growth_rate",
            None,
            "decimal_ratio",
            INSUFFICIENT_EVIDENCE,
            PROJECT_POLICY_ID,
            ASSUMPTION_POLICY_VERSION,
            (),
            "No usable growth evidence was available.",
            LOW,
            ("MISSING_GROWTH_HISTORY",),
            True,
            "HISTORICAL_ANALYSIS",
        )
    selected, cap_warnings = clamp_growth(selected)
    warnings.extend(cap_warnings)
    fcf_vol = _volatility(evidence, "free_cash_flow")
    if fcf_vol is not None and fcf_vol > HIGH_VOLATILITY_THRESHOLD:
        warnings.append("CYCLICALITY_REVIEW")
    negative_fcf = _negative_years(evidence, "free_cash_flow")
    if negative_fcf and negative_fcf > 0:
        warnings.append("NEGATIVE_FCF_YEARS_REVIEW")
    history_years = len({item.period for item in evidence if item.metric in {"revenue", "free_cash_flow"} and item.value is not None})
    confidence = confidence_from_history(history_years, tuple(warnings))
    status = REVIEW_REQUIRED if warnings or confidence == LOW else RECOMMENDED
    return AssumptionRecommendation(
        "growth_rate",
        selected,
        "decimal_ratio",
        status,
        PROJECT_POLICY_ID,
        ASSUMPTION_POLICY_VERSION,
        tuple(evidence_refs),
        "Growth recommendation selects one documented primary anchor; it does not average revenue, earnings, and FCF growth together.",
        confidence,
        tuple(dict.fromkeys(warnings)),
        status == REVIEW_REQUIRED,
        "HISTORICAL_ANALYSIS",
        primary_anchor=primary_anchor,
    )


def scenario_growths(base: Decimal, evidence: tuple[AssumptionEvidence, ...]) -> tuple[Decimal, Decimal, Decimal]:
    volatility = _volatility(evidence, "free_cash_flow") or _volatility(evidence, "revenue") or MIN_SCENARIO_SPREAD
    spread = max(MIN_SCENARIO_SPREAD, min(abs(volatility), MAX_SCENARIO_SPREAD))
    return base - spread, base, base + spread


def _anchors_by_metric(evidence: tuple[AssumptionEvidence, ...]) -> dict[str, dict[str, list[tuple[Decimal, str, str]]]]:
    output: dict[str, dict[str, list[tuple[Decimal, str, str]]]] = {}
    for item in evidence:
        if item.value is None or item.status != "AVAILABLE":
            continue
        metric_bucket = output.setdefault(item.metric, {"cagr": [], "yoy": []})
        if item.window == "CAGR":
            metric_bucket["cagr"].append((item.value, item.evidence_id, item.period))
        elif item.window == "YoY":
            metric_bucket["yoy"].append((item.value, item.evidence_id, item.period))
    return output


def _latest_window(values: list[tuple[Decimal, str, str]]) -> tuple[Decimal, str]:
    priority = {"10Y_CAGR": 3, "5Y_CAGR": 2, "3Y_CAGR": 1}
    value, ref, _window = sorted(values, key=lambda item: priority.get(item[2], 0))[-1]
    return value, ref


def _volatility(evidence: tuple[AssumptionEvidence, ...], metric: str) -> Decimal | None:
    matches = [item.value for item in evidence if item.metric == metric and item.window == "volatility" and item.value is not None]
    if not matches:
        return None
    value = matches[-1]
    # Treat only ratio-like volatility as growth volatility. Absolute currency volatility remains
    # evidence, but it is not comparable to decimal growth thresholds.
    return value if abs(value) <= 1 else None


def _negative_years(evidence: tuple[AssumptionEvidence, ...], metric: str) -> Decimal | None:
    matches = [item.value for item in evidence if item.metric == metric and item.window == "negative_years" and item.value is not None]
    return matches[-1] if matches else None


def _fcf_margin_stable(evidence: tuple[AssumptionEvidence, ...]) -> bool:
    vol = _volatility(evidence, "free_cash_flow_margin")
    return vol is not None and vol <= STABLE_MARGIN_VOLATILITY_THRESHOLD
