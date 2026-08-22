from decimal import Decimal

from stock_valuation.validation.service import (
    MetricValidationGate,
    ValidationResult,
    metric_validation_gates,
    phase_3a_data_readiness,
)


def _row(metric: str, period: str, status: str, *, critical: bool = True) -> ValidationResult:
    return ValidationResult(
        metric=metric,
        period=period,
        label=metric,
        provider="alphavantage",
        provider_value=Decimal("100"),
        reference_value=Decimal("100"),
        relative_difference=Decimal("0"),
        status=status,
        critical=critical,
        provider_field=metric,
        source_url="https://example.com",
    )


def test_metric_gate_blocks_if_one_year_fails() -> None:
    gates = metric_validation_gates(
        [
            _row("inventory", "2025", "pass"),
            _row("inventory", "2024", "fail"),
        ]
    )

    assert len(gates) == 1
    assert gates[0].status == "blocked"
    assert gates[0].pass_count == 1
    assert gates[0].fail_count == 1


def test_metric_gate_approves_only_all_pass() -> None:
    gates = metric_validation_gates(
        [
            _row("revenue", "2025", "pass"),
            _row("revenue", "2024", "pass"),
        ]
    )

    assert gates[0].status == "approved"
    assert gates[0].years_checked == 2


def test_phase_3a_readiness_requires_approved_inputs() -> None:
    gates = [
        MetricValidationGate("revenue", "approved", 2, 2, 0, 0, 0, True, "ok"),
        MetricValidationGate("net_income", "approved", 2, 2, 0, 0, 0, True, "ok"),
        MetricValidationGate("shareholders_equity", "approved", 2, 2, 0, 0, 0, True, "ok"),
        MetricValidationGate("operating_income", "approved", 2, 2, 0, 0, 0, True, "ok"),
        MetricValidationGate("total_assets", "approved", 2, 2, 0, 0, 0, True, "ok"),
        MetricValidationGate("current_liabilities", "approved", 2, 2, 0, 0, 0, True, "ok"),
        MetricValidationGate(
            "depreciation_amortization", "blocked", 2, 1, 0, 1, 0, True, "fail"
        ),
    ]

    readiness = {row["metric"]: row for row in phase_3a_data_readiness(gates)}

    assert readiness["Eigenkapitalrendite (ROE)"]["ready"] is True
    assert readiness["Umsatzrendite"]["ready"] is True
    assert readiness["EBIT-Marge"]["ready"] is True
    assert readiness["Kapitalumschlag"]["ready"] is True
    assert readiness["ROCE – Datenbasis"]["ready"] is True
    assert readiness["EBITDA-Marge – Datenbasis"]["ready"] is False
