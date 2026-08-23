from __future__ import annotations

from decimal import Decimal

from stock_valuation.valuation.models import (
    ASSUMPTIONS_NOT_COMPANY_SPECIFIC,
    AVAILABLE,
    GENERIC_ASSUMPTION_SOURCE,
    INVALID_ASSUMPTION,
    UNAVAILABLE,
    DCFProjectionRow,
    DCFResult,
    DCFScenario,
    NormalizedValue,
    stable_hash,
)


def equity_dcf(ticker: str, normalized_fcf: NormalizedValue, scenario: DCFScenario) -> DCFResult:
    issues: list[str] = []
    if scenario.discount_rate <= 0:
        issues.append("DISCOUNT_RATE_NOT_POSITIVE")
    if scenario.terminal_growth_rate >= scenario.discount_rate:
        issues.append("TERMINAL_GROWTH_NOT_BELOW_DISCOUNT_RATE")
    if normalized_fcf.value is None or normalized_fcf.status != AVAILABLE:
        issues.append("NORMALIZED_FCF_UNAVAILABLE")
    if normalized_fcf.value is not None and normalized_fcf.value <= 0:
        issues.append("NORMALIZED_FCF_NOT_POSITIVE")
    non_blocking_issues = list(normalized_fcf.issues)
    if scenario.assumption_source == GENERIC_ASSUMPTION_SOURCE:
        non_blocking_issues.append(ASSUMPTIONS_NOT_COMPANY_SPECIFIC)
    if issues:
        return DCFResult(
            ticker,
            scenario.scenario,
            INVALID_ASSUMPTION if any("RATE" in issue or "GROWTH" in issue for issue in issues) else UNAVAILABLE,
            None,
            normalized_fcf.currency,
            None,
            (),
            tuple(issues + non_blocking_issues),
            normalized_fcf.input_refs,
            normalized_fcf.inputs_hash,
        )
    assert normalized_fcf.value is not None
    projections: list[DCFProjectionRow] = []
    equity_value = Decimal("0")
    projected = normalized_fcf.value
    for year_index in range(1, scenario.projection_years + 1):
        projected *= Decimal("1") + scenario.annual_growth_rate
        discount_factor = (Decimal("1") + scenario.discount_rate) ** year_index
        present_value = projected / discount_factor
        equity_value += present_value
        projections.append(DCFProjectionRow(ticker, scenario.scenario, year_index, projected, present_value))
    terminal_value = projected * (Decimal("1") + scenario.terminal_growth_rate) / (
        scenario.discount_rate - scenario.terminal_growth_rate
    )
    equity_value += terminal_value / ((Decimal("1") + scenario.discount_rate) ** scenario.projection_years)
    return DCFResult(
        ticker,
        scenario.scenario,
        AVAILABLE,
        equity_value,
        normalized_fcf.currency,
        terminal_value,
        tuple(projections),
        tuple(non_blocking_issues),
        normalized_fcf.input_refs,
        stable_hash((normalized_fcf.inputs_hash, str(scenario))),
    )
