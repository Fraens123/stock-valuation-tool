from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_valuation.data.resolution import DEFAULT_PROVIDER_PRIORITY, load_preferred_financial_facts
from stock_valuation.database.ai_review_models import AIReviewFinding, AIReviewRun
from stock_valuation.database.models import Analysis, FinancialFactSnapshot


DEFAULT_HISTORY_YEARS = 10
BASE_SOURCE_PRIORITY = tuple(
    provider for provider in DEFAULT_PROVIDER_PRIORITY if provider != "manual_override"
)
SEC_REVIEW_CANDIDATE_PROVIDERS = {
    "sec_filing_extension",
    "sec_filing_text_candidate",
}


@dataclass(frozen=True)
class HistoryMappingRow:
    metric: str
    status: str
    covered_years: int
    expected_years: int
    missing_years: tuple[int, ...]
    duplicate_years: tuple[int, ...]
    provider_fields: tuple[str, ...]
    providers: tuple[str, ...]
    currencies: tuple[str, ...]
    taxonomies: tuple[str, ...]
    change_years: tuple[int, ...]
    mapping_sequence: str
    reason: str

    @property
    def coverage_label(self) -> str:
        return f"{self.covered_years}/{self.expected_years}"


@dataclass(frozen=True)
class HistoryMappingAudit:
    requested_years: int
    first_year: int | None
    last_year: int | None
    rows: tuple[HistoryMappingRow, ...]

    @property
    def stable_count(self) -> int:
        return sum(row.status == "PASS" for row in self.rows)

    @property
    def review_count(self) -> int:
        return sum(row.status == "REVIEW" for row in self.rows)

    @property
    def gap_count(self) -> int:
        return sum(row.status == "GAP" for row in self.rows)


def _clean(value: str | None, fallback: str = "—") -> str:
    text = (value or "").strip()
    return text or fallback


def _taxonomy(fact: FinancialFactSnapshot) -> str:
    field = _clean(fact.provider_field, "")
    if ":" in field:
        return field.split(":", 1)[0].strip().lower() or _clean(fact.provider)
    return _clean(fact.provider).lower()


def _provider_family(provider: str | None) -> str:
    normalized = _clean(provider).lower()
    if normalized in {
        "sec_companyfacts",
        "sec_filing_xbrl",
        "sec_filing_extension",
        "sec_filing_text_candidate",
    }:
        return "sec"
    return normalized


def _normal_fiscal_year_end(facts: list[FinancialFactSnapshot]) -> tuple[int, int] | None:
    if not facts:
        return None
    counts = Counter((fact.period_end.month, fact.period_end.day) for fact in facts)
    return counts.most_common(1)[0][0]


def _effective_year_facts(
    year_facts: list[FinancialFactSnapshot],
    fiscal_year_end: tuple[int, int] | None,
) -> list[FinancialFactSnapshot]:
    """Prefer the company's normal fiscal-year end over opening/restatement instants."""
    if fiscal_year_end is None:
        return year_facts
    matching = [
        fact
        for fact in year_facts
        if (fact.period_end.month, fact.period_end.day) == fiscal_year_end
    ]
    return matching or year_facts


def _compress_sequence(year_to_field: dict[int, str]) -> str:
    if not year_to_field:
        return "—"
    items = sorted(year_to_field.items())
    segments: list[tuple[int, int, str]] = []
    start_year, previous_year = items[0][0], items[0][0]
    current_field = items[0][1]

    for year, field in items[1:]:
        if field == current_field and year == previous_year + 1:
            previous_year = year
            continue
        segments.append((start_year, previous_year, current_field))
        start_year = previous_year = year
        current_field = field
    segments.append((start_year, previous_year, current_field))

    rendered: list[str] = []
    for start, end, field in segments:
        period = str(start) if start == end else f"{start}–{end}"
        rendered.append(f"{period}: {field}")
    return " → ".join(rendered)


def _change_years(year_to_field: dict[int, str]) -> tuple[int, ...]:
    changes: list[int] = []
    previous_field: str | None = None
    previous_year: int | None = None
    for year, field in sorted(year_to_field.items()):
        if previous_field is not None and previous_year is not None:
            if year == previous_year + 1 and field != previous_field:
                changes.append(year)
        previous_year = year
        previous_field = field
    return tuple(changes)


def _base_facts(session: Session, analysis_id: int) -> list[FinancialFactSnapshot]:
    """Use underlying imported sources for mapping continuity; do not hide them with overrides."""
    facts = load_preferred_financial_facts(
        session,
        analysis_id,
        period_type="FY",
        provider_priority=BASE_SOURCE_PRIORITY,
    )
    usable = [fact for fact in facts if not fact.is_cross_check_only]
    if usable:
        return usable
    return [
        fact
        for fact in load_preferred_financial_facts(session, analysis_id, period_type="FY")
        if not fact.is_cross_check_only
    ]


def _latest_review_index(session: Session, analysis_id: int) -> dict[tuple[str, object], AIReviewFinding]:
    findings = session.scalars(
        select(AIReviewFinding)
        .join(AIReviewRun, AIReviewFinding.run_id == AIReviewRun.id)
        .where(AIReviewFinding.analysis_id == analysis_id)
        .order_by(AIReviewRun.created_at.desc(), AIReviewFinding.id.desc())
    ).all()
    result: dict[tuple[str, object], AIReviewFinding] = {}
    for finding in findings:
        result.setdefault((finding.metric, finding.period_end), finding)
    return result


def _override_keys(session: Session, analysis_id: int) -> set[tuple[str, object]]:
    rows = session.scalars(
        select(FinancialFactSnapshot).where(
            FinancialFactSnapshot.analysis_id == analysis_id,
            FinancialFactSnapshot.provider == "manual_override",
            FinancialFactSnapshot.period_type == "FY",
        )
    ).all()
    return {(row.metric, row.period_end) for row in rows if row.value is not None}


def _review_candidate_mapping_resolved(
    fact: FinancialFactSnapshot,
    review_index: dict[tuple[str, object], AIReviewFinding],
    override_keys: set[tuple[str, object]],
) -> bool:
    if fact.provider not in SEC_REVIEW_CANDIDATE_PROVIDERS:
        return False
    key = (fact.metric, fact.period_end)
    if key in override_keys:
        return True
    finding = review_index.get(key)
    if finding is None or finding.verdict.upper() != "PASS":
        return False
    if finding.provider != fact.provider or finding.provider_field != fact.provider_field:
        return False
    if finding.imported_value is None or fact.value is None:
        return False
    return finding.imported_value == fact.value


def audit_history_mapping(
    session: Session,
    analysis: Analysis,
    *,
    years: int = DEFAULT_HISTORY_YEARS,
    metrics: Iterable[str] | None = None,
) -> HistoryMappingAudit:
    """Audit longitudinal mapping consistency without network access or semantic guessing.

    PASS means the requested history is complete and its technical changes are either absent or an
    SEC review-candidate change was explicitly resolved by semantic PASS/accepted override.
    REVIEW means a complete series still has an unresolved mapping/source/currency/taxonomy change.
    GAP means at least one requested fiscal year has no candidate/value at all.
    """
    requested_years = max(1, int(years))
    facts = [
        fact
        for fact in _base_facts(session, analysis.id)
        if fact.value is not None and fact.period_end <= analysis.as_of_date
    ]
    metric_filter = set(metrics) if metrics is not None else None
    if metric_filter is not None:
        facts = [fact for fact in facts if fact.metric in metric_filter]

    if not facts:
        return HistoryMappingAudit(
            requested_years=requested_years,
            first_year=None,
            last_year=None,
            rows=(),
        )

    review_index = _latest_review_index(session, analysis.id)
    override_keys = _override_keys(session, analysis.id)
    fiscal_year_end = _normal_fiscal_year_end(facts)
    last_year = max(fact.period_end.year for fact in facts)
    first_year = last_year - requested_years + 1
    target_years = tuple(range(first_year, last_year + 1))
    facts = [fact for fact in facts if first_year <= fact.period_end.year <= last_year]

    by_metric: dict[str, list[FinancialFactSnapshot]] = {}
    for fact in facts:
        by_metric.setdefault(fact.metric, []).append(fact)

    rows: list[HistoryMappingRow] = []
    for metric, metric_facts in sorted(by_metric.items()):
        by_year: dict[int, list[FinancialFactSnapshot]] = {}
        for fact in metric_facts:
            by_year.setdefault(fact.period_end.year, []).append(fact)

        effective_by_year = {
            year: _effective_year_facts(year_facts, fiscal_year_end)
            for year, year_facts in by_year.items()
        }
        present_years = {year for year, year_facts in effective_by_year.items() if year_facts}
        missing_years = tuple(year for year in target_years if year not in present_years)
        duplicate_years = tuple(
            year
            for year, year_facts in sorted(effective_by_year.items())
            if len({fact.period_end for fact in year_facts}) > 1
        )

        representative_by_year = {
            year: sorted(year_facts, key=lambda fact: (fact.period_end, fact.id))[-1]
            for year, year_facts in effective_by_year.items()
            if year_facts
        }
        effective_metric_facts = [
            fact for year_facts in effective_by_year.values() for fact in year_facts
        ]
        year_to_field = {
            year: _clean(fact.provider_field, _clean(fact.provider))
            for year, fact in representative_by_year.items()
        }

        provider_fields = tuple(
            sorted(
                {
                    _clean(fact.provider_field, _clean(fact.provider))
                    for fact in effective_metric_facts
                }
            )
        )
        providers = tuple(sorted({_clean(fact.provider) for fact in effective_metric_facts}))
        provider_families = {_provider_family(fact.provider) for fact in effective_metric_facts}
        currencies = tuple(sorted({_clean(fact.currency) for fact in effective_metric_facts}))
        taxonomies = tuple(sorted({_taxonomy(fact) for fact in effective_metric_facts}))
        change_years = _change_years(year_to_field)

        review_candidate_facts = [
            fact
            for fact in effective_metric_facts
            if fact.provider in SEC_REVIEW_CANDIDATE_PROVIDERS
        ]
        review_candidates_resolved = bool(review_candidate_facts) and all(
            _review_candidate_mapping_resolved(fact, review_index, override_keys)
            for fact in review_candidate_facts
        )
        non_candidate_fields = {
            _clean(fact.provider_field, _clean(fact.provider))
            for fact in effective_metric_facts
            if fact.provider not in SEC_REVIEW_CANDIDATE_PROVIDERS
        }
        non_candidate_taxonomies = {
            _taxonomy(fact)
            for fact in effective_metric_facts
            if fact.provider not in SEC_REVIEW_CANDIDATE_PROVIDERS
        }
        field_change_requires_review = len(provider_fields) > 1
        taxonomy_change_requires_review = len(taxonomies) > 1
        if review_candidates_resolved:
            if len(non_candidate_fields) <= 1:
                field_change_requires_review = False
            if len(non_candidate_taxonomies) <= 1:
                taxonomy_change_requires_review = False

        reasons: list[str] = []
        if missing_years:
            reasons.append("fehlende Jahre: " + ", ".join(str(year) for year in missing_years))
        if duplicate_years:
            reasons.append(
                "mehrere echte Geschäftsjahres-Enden im selben Jahr: "
                + ", ".join(str(year) for year in duplicate_years)
            )
        if field_change_requires_review:
            reasons.append(f"Originalfeld wechselte ({len(provider_fields)} Varianten)")
        if len(provider_families) > 1:
            reasons.append("Quellenfamilie wechselte: " + ", ".join(sorted(provider_families)))
        if len(currencies) > 1:
            reasons.append("Währung wechselte: " + ", ".join(currencies))
        if taxonomy_change_requires_review:
            reasons.append("Taxonomie wechselte: " + ", ".join(taxonomies))
        if review_candidates_resolved:
            reasons.append("SEC-Filing-Kandidaten semantisch bestätigt")

        if missing_years:
            status = "GAP"
        elif (
            duplicate_years
            or field_change_requires_review
            or len(provider_families) > 1
            or len(currencies) > 1
            or taxonomy_change_requires_review
        ):
            status = "REVIEW"
        else:
            status = "PASS"
            if not reasons:
                reasons.append(
                    f"{requested_years}-Jahres-Serie vollständig und Mapping technisch unverändert."
                )

        rows.append(
            HistoryMappingRow(
                metric=metric,
                status=status,
                covered_years=len(present_years.intersection(target_years)),
                expected_years=requested_years,
                missing_years=missing_years,
                duplicate_years=duplicate_years,
                provider_fields=provider_fields,
                providers=providers,
                currencies=currencies,
                taxonomies=taxonomies,
                change_years=change_years,
                mapping_sequence=_compress_sequence(year_to_field),
                reason="; ".join(reasons),
            )
        )

    return HistoryMappingAudit(
        requested_years=requested_years,
        first_year=first_year,
        last_year=last_year,
        rows=tuple(rows),
    )
