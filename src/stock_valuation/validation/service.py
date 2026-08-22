from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_valuation.database.models import Analysis, FinancialFactSnapshot
from stock_valuation.validation.asml_reference import (
    ASML_US_GAAP_REFERENCES,
    PrimarySourceReference,
)


@dataclass(frozen=True)
class ValidationResult:
    metric: str
    period: str
    label: str
    provider: str
    provider_value: Decimal | None
    reference_value: Decimal
    relative_difference: Decimal | None
    status: str
    critical: bool
    provider_field: str | None
    source_url: str
    note: str | None = None


@dataclass(frozen=True)
class MetricValidationGate:
    metric: str
    status: str
    years_checked: int
    pass_count: int
    warn_count: int
    fail_count: int
    missing_count: int
    critical: bool
    reason: str


PHASE_3A_DATA_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "Eigenkapitalrendite (ROE)": ("net_income", "shareholders_equity"),
    "Umsatzrendite": ("net_income", "revenue"),
    "EBIT-Marge": ("operating_income", "revenue"),
    "Kapitalumschlag": ("revenue", "total_assets"),
    "ROCE – Datenbasis": ("operating_income", "total_assets", "current_liabilities"),
    "EBITDA-Marge – Datenbasis": (
        "operating_income",
        "depreciation_amortization",
        "revenue",
    ),
}


def _status(provider_value: Decimal | None, reference_value: Decimal) -> tuple[str, Decimal | None]:
    if provider_value is None:
        return "missing", None
    if reference_value == 0:
        difference = abs(provider_value - reference_value)
        return ("pass" if difference == 0 else "fail"), None

    relative = abs(provider_value - reference_value) / abs(reference_value)
    if relative <= Decimal("0.005"):
        return "pass", relative
    if relative <= Decimal("0.02"):
        return "warn", relative
    return "fail", relative


def validate_asml_primary_source(
    session: Session,
    analysis: Analysis,
    *,
    provider: str = "alphavantage",
    references: tuple[PrimarySourceReference, ...] = ASML_US_GAAP_REFERENCES,
) -> list[ValidationResult]:
    """Compare persisted ASML provider facts with official historical US-GAAP controls.

    The reference values are validation-only. They never fill, overwrite, or normalize
    provider facts. A mismatch therefore remains visible and must be resolved in the
    provider mapping before downstream metrics rely on that field.
    """
    if analysis.company.ticker.upper() != "ASML":
        return []

    facts = session.scalars(
        select(FinancialFactSnapshot).where(
            FinancialFactSnapshot.analysis_id == analysis.id,
            FinancialFactSnapshot.provider == provider,
            FinancialFactSnapshot.period_type == "FY",
        )
    ).all()
    indexed = {(fact.metric, fact.period_end): fact for fact in facts}

    results: list[ValidationResult] = []
    for reference in references:
        fact = indexed.get((reference.metric, reference.period_end))
        provider_value = fact.value if fact is not None else None
        status, relative = _status(provider_value, reference.value)
        results.append(
            ValidationResult(
                metric=reference.metric,
                period=str(reference.period_end.year),
                label=reference.label,
                provider=provider,
                provider_value=provider_value,
                reference_value=reference.value,
                relative_difference=relative,
                status=status,
                critical=reference.critical,
                provider_field=fact.provider_field if fact is not None else None,
                source_url=reference.source_url,
                note=reference.note,
            )
        )
    return results


def validation_summary(results: list[ValidationResult]) -> dict[str, int | bool]:
    critical = [row for row in results if row.critical]
    counts = {
        "pass": sum(row.status == "pass" for row in results),
        "warn": sum(row.status == "warn" for row in results),
        "fail": sum(row.status == "fail" for row in results),
        "missing": sum(row.status == "missing" for row in results),
        "critical_fail": sum(row.critical and row.status == "fail" for row in results),
        "critical_missing": sum(row.critical and row.status == "missing" for row in results),
    }
    counts["provider_gate_passed"] = (
        bool(critical)
        and counts["critical_fail"] == 0
        and counts["critical_missing"] == 0
    )
    return counts


def metric_validation_gates(results: list[ValidationResult]) -> list[MetricValidationGate]:
    """Create a field-level trust decision from the available primary-source checks.

    A metric is only `approved` if every checked reference row is a PASS. WARN keeps the
    field in review. Any FAIL or MISSING blocks the field. This prevents one good year
    from masking an inconsistent provider mapping in another year.
    """
    grouped: dict[str, list[ValidationResult]] = defaultdict(list)
    for row in results:
        grouped[row.metric].append(row)

    gates: list[MetricValidationGate] = []
    for metric, rows in sorted(grouped.items()):
        pass_count = sum(row.status == "pass" for row in rows)
        warn_count = sum(row.status == "warn" for row in rows)
        fail_count = sum(row.status == "fail" for row in rows)
        missing_count = sum(row.status == "missing" for row in rows)
        critical = any(row.critical for row in rows)

        if fail_count or missing_count:
            status = "blocked"
            reason = (
                f"{fail_count} FAIL, {missing_count} MISSING in "
                f"{len(rows)} Primärquellen-Checks"
            )
        elif warn_count:
            status = "review"
            reason = f"{warn_count} WARN in {len(rows)} Primärquellen-Checks"
        elif rows and pass_count == len(rows):
            status = "approved"
            reason = f"{pass_count}/{len(rows)} Primärquellen-Checks PASS"
        else:
            status = "review"
            reason = "Zu wenig Evidenz für eine Freigabe"

        gates.append(
            MetricValidationGate(
                metric=metric,
                status=status,
                years_checked=len(rows),
                pass_count=pass_count,
                warn_count=warn_count,
                fail_count=fail_count,
                missing_count=missing_count,
                critical=critical,
                reason=reason,
            )
        )
    return gates


def phase_3a_data_readiness(
    gates: list[MetricValidationGate],
) -> list[dict[str, str | bool]]:
    """Show whether the validated raw-data basis is ready for Phase 3A metrics.

    This is only a data-quality gate. It does not approve formulas that are still marked
    as methodology questions in the project documentation.
    """
    by_metric = {gate.metric: gate for gate in gates}
    rows: list[dict[str, str | bool]] = []
    for label, required_metrics in PHASE_3A_DATA_REQUIREMENTS.items():
        blocked = [
            metric
            for metric in required_metrics
            if by_metric.get(metric) is None or by_metric[metric].status != "approved"
        ]
        rows.append(
            {
                "metric": label,
                "ready": not blocked,
                "required": ", ".join(required_metrics),
                "blocked_by": ", ".join(blocked),
            }
        )
    return rows
