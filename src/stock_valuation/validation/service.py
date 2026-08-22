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
    """Validate the best available ASML snapshot source against official controls.

    Source priority for each metric/year is deliberately explicit:
    1. `asml_primary` facts imported from ASML's official workbook;
    2. the supplied fallback provider, currently Alpha Vantage.

    The fallback fact is never deleted when a primary-source fact exists. This keeps the
    original provider result auditable while downstream gates use the authoritative source.
    """
    if analysis.company.ticker.upper() != "ASML":
        return []

    facts = session.scalars(
        select(FinancialFactSnapshot).where(
            FinancialFactSnapshot.analysis_id == analysis.id,
            FinancialFactSnapshot.provider.in_(("asml_primary", provider)),
            FinancialFactSnapshot.period_type == "FY",
        )
    ).all()

    fallback_index: dict[tuple[str, object], FinancialFactSnapshot] = {}
    primary_index: dict[tuple[str, object], FinancialFactSnapshot] = {}
    for fact in facts:
        key = (fact.metric, fact.period_end)
        if fact.provider == "asml_primary":
            primary_index[key] = fact
        elif fact.provider == provider:
            fallback_index[key] = fact

    results: list[ValidationResult] = []
    for reference in references:
        key = (reference.metric, reference.period_end)
        fact = primary_index.get(key) or fallback_index.get(key)
        selected_provider = fact.provider if fact is not None else provider
        provider_value = fact.value if fact is not None else None
        status, relative = _status(provider_value, reference.value)
        source_note = reference.note
        if fact is not None and fact.provider == "asml_primary":
            priority_note = "Authoritative ASML primary-source fact selected over fallback provider."
            source_note = f"{source_note} {priority_note}" if source_note else priority_note
        results.append(
            ValidationResult(
                metric=reference.metric,
                period=str(reference.period_end.year),
                label=reference.label,
                provider=selected_provider,
                provider_value=provider_value,
                reference_value=reference.value,
                relative_difference=relative,
                status=status,
                critical=reference.critical,
                provider_field=fact.provider_field if fact is not None else None,
                source_url=reference.source_url,
                note=source_note,
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
            primary_count = sum(row.provider == "asml_primary" for row in rows)
            suffix = f"; davon {primary_count} direkt aus ASML" if primary_count else ""
            reason = f"{pass_count}/{len(rows)} Primärquellen-Checks PASS{suffix}"
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
