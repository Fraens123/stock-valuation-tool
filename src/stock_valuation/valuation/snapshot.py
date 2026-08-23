from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from datetime import datetime, timezone
from decimal import Decimal

from stock_valuation.valuation.models import (
    VALUATION_ENGINE_VERSION,
    DCFScenario,
    MarketSnapshotInput,
    NormalizedValue,
    ValuationMetricResult,
    ValuationSnapshot,
    ValuationSummary,
    stable_hash,
)


def _canonical_default(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (tuple, set)):
        return list(value)
    return str(value)


def canonical_json(payload: object) -> str:
    return json.dumps(payload, default=_canonical_default, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_hash(payload: object) -> str:
    return stable_hash((canonical_json(payload),))


def assumptions_payload(
    scenarios: tuple[DCFScenario, ...],
    *,
    normalization_method: str,
    outlier_threshold: str,
    sensitivity_discount_rates: tuple[str, ...],
    sensitivity_terminal_growth_rates: tuple[str, ...],
) -> dict:
    generic = all(item.assumption_source == "GENERIC_V1_DEFAULT" for item in scenarios)
    return {
        "assumption_set": "GENERIC_V1_DEFAULT" if generic else "CUSTOM",
        "assumption_source": "GENERIC_V1_DEFAULT" if generic else "CUSTOM_EXPLICIT",
        "scenarios": [asdict(item) for item in scenarios],
        "normalization_method": normalization_method,
        "outlier_threshold": outlier_threshold,
        "sensitivity": {
            "discount_rates": list(sensitivity_discount_rates),
            "terminal_growth_rates": list(sensitivity_terminal_growth_rates),
        },
    }


def create_valuation_snapshot(
    *,
    analysis_id: str,
    market: MarketSnapshotInput,
    financial_data_reference: str,
    calculation_version: str,
    historical_analysis_version: str,
    quality_version: str,
    assumptions: dict,
    normalized_inputs: tuple[NormalizedValue, ...],
    valuation_results: tuple[ValuationMetricResult | ValuationSummary, ...],
    quality_context: dict,
    historical_context: dict,
    created_at: str | None = None,
) -> ValuationSnapshot:
    assumptions_hash = canonical_hash(assumptions)
    result_hashes = tuple(item.inputs_hash for item in valuation_results)
    quality_context_hash = canonical_hash(quality_context)
    historical_context_hash = canonical_hash(historical_context)
    inputs_hash = stable_hash(
        tuple(item.inputs_hash for item in normalized_inputs)
        + result_hashes
        + (
            quality_context_hash,
            historical_context_hash,
            market.market_snapshot_id,
            f"market_snapshot_id:{market.market_snapshot_id}",
            market.inputs_hash,
            assumptions_hash,
            f"assumptions_hash:{assumptions_hash}",
            VALUATION_ENGINE_VERSION,
        )
    )
    snapshot_id = stable_hash(
        (
            analysis_id,
            market.analysis_as_of_date,
            market.market_snapshot_id,
            assumptions_hash,
            inputs_hash,
            VALUATION_ENGINE_VERSION,
        )
    )
    input_refs = (
        tuple(ref for item in normalized_inputs for ref in item.input_refs)
        + tuple(ref for item in valuation_results for ref in item.input_refs)
        + tuple(historical_context.get("input_refs", ()))
        + market.input_refs
        + (
            f"quality_context_hash:{quality_context_hash}",
            f"historical_context_hash:{historical_context_hash}",
            f"market_snapshot_id:{market.market_snapshot_id}",
            f"assumptions_hash:{assumptions_hash}",
        )
    )
    return ValuationSnapshot(
        analysis_id=analysis_id,
        analysis_as_of_date=market.analysis_as_of_date,
        market_snapshot_id=market.market_snapshot_id,
        market_data_version=market.market_data_version,
        financial_data_reference=financial_data_reference,
        calculation_version=calculation_version,
        historical_analysis_version=historical_analysis_version,
        quality_version=quality_version,
        valuation_version=VALUATION_ENGINE_VERSION,
        assumptions=assumptions,
        assumptions_hash=assumptions_hash,
        normalized_inputs={item.metric_id: asdict(item) for item in normalized_inputs},
        valuation_results={
            f"{item.__class__.__name__}:{index}": asdict(item)
            for index, item in enumerate(valuation_results)
        },
        quality_context=quality_context,
        historical_context=historical_context,
        input_refs=input_refs,
        inputs_hash=inputs_hash,
        created_at=created_at or datetime.now(timezone.utc).isoformat(),
        snapshot_id=snapshot_id,
    )
