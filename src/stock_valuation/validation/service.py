from __future__ import annotations

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
    counts["provider_gate_passed"] = bool(critical) and counts["critical_fail"] == 0 and counts["critical_missing"] == 0
    return counts
