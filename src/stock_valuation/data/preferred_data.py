from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_valuation.data.resolution import load_preferred_financial_facts
from stock_valuation.database.ai_review_models import AIReviewFinding, AIReviewRun
from stock_valuation.database.models import Analysis, FinancialFactSnapshot
from stock_valuation.validation.service import metric_validation_gates, validate_asml_primary_source


PRIMARY_SOURCE_PROVIDERS = {
    "asml_primary",
    "esef_xbrl_json",
    "esef_ixbrl",
    "sec_companyfacts",
    "sec_filing_xbrl",
    "sec_filing_extension",
    "sec_filing_text_candidate",
}

# A primary source proves provenance, but not automatically that one XBRL concept or extracted
# filing-table row has exactly the same economic scope as our internal field. These combinations
# therefore require an explicit semantic PASS (or a confirmed manual override) before calculations.
PRIMARY_SEMANTIC_REVIEW_REQUIRED = {
    ("sec_companyfacts", "short_term_debt"),
    ("sec_filing_xbrl", "short_term_debt"),
    ("sec_companyfacts", "depreciation_amortization"),
    ("sec_filing_xbrl", "depreciation_amortization"),
    ("esef_xbrl_json", "depreciation_amortization"),
    ("esef_ixbrl", "depreciation_amortization"),
}
PRIMARY_SEMANTIC_PROVIDER_REVIEW_REQUIRED = {
    "sec_filing_extension",
    "sec_filing_text_candidate",
}

# These definitions describe what the internal raw-data keys mean. They are intentionally narrower
# than arbitrary provider labels so unusual provider/extension/text concepts can be rejected when
# their economic meaning is broader or different.
FIELD_DEFINITIONS: dict[str, str] = {
    "ppe_net": (
        "Netto-Sachanlagen (Property, Plant & Equipment) für den operativen Betrieb. Separat "
        "ausgewiesene Operating-Lease-Right-of-Use-Assets gehören nicht in ppe_net."
    ),
    "short_term_debt": (
        "Kurzfristige zinstragende Finanzschulden mit Fälligkeit innerhalb von zwölf Monaten, "
        "einschließlich des innerhalb von zwölf Monaten fälligen Anteils langfristiger Schulden. "
        "Lieferantenverbindlichkeiten und Leasingverbindlichkeiten bleiben getrennt."
    ),
    "depreciation_amortization": (
        "Abschreibungen auf Sachanlagen plus Amortisation immaterieller Vermögenswerte. "
        "Unspezifische zusätzliche Non-Cash-Positionen wie 'and other' gehören nicht automatisch dazu."
    ),
    "operating_cash_flow": (
        "Netto-Cashflow aus der laufenden Geschäftstätigkeit des konsolidierten Geschäftsjahres. "
        "Investitions- und Finanzierungscashflows gehören nicht dazu."
    ),
    "dividends_paid": (
        "Im Geschäftsjahr tatsächlich zahlungswirksam an Anteilseigner ausgeschüttete Dividenden. "
        "Nur angekündigte, vorgeschlagene oder noch zahlbare Dividenden gehören nicht dazu."
    ),
    "ebitda": (
        "EBITDA ist eine abgeleitete Kennzahl. Provider-EBITDA dient nur als Cross-Check; für "
        "Berechnungen wird EBITDA selbst aus freigegebenem EBIT und freigegebenem D&A abgeleitet."
    ),
}


@dataclass(frozen=True)
class PreferredDataState:
    fact: FinancialFactSnapshot
    quality_status: str
    calculation_ready: bool
    reason: str
    review_verdict: str | None = None
    review_decision: str | None = None

    @property
    def definition(self) -> str | None:
        return FIELD_DEFINITIONS.get(self.fact.metric)


def internal_field_definition(metric: str) -> str | None:
    return FIELD_DEFINITIONS.get(metric)


def _latest_review_index(
    session: Session,
    analysis_id: int,
) -> dict[tuple[str, object], AIReviewFinding]:
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


def _legacy_approved_metrics(session: Session, analysis_id: int) -> set[str]:
    """Bridge the original ASML field gate into the generic preferred-data layer."""
    analysis = session.get(Analysis, analysis_id)
    if analysis is None or analysis.company.ticker.upper() != "ASML":
        return set()
    validation = validate_asml_primary_source(session, analysis)
    return {
        gate.metric
        for gate in metric_validation_gates(validation)
        if gate.status == "approved"
    }


def _is_primary_source(fact: FinancialFactSnapshot) -> bool:
    return fact.source_type == "primary_source" or (fact.provider or "") in PRIMARY_SOURCE_PROVIDERS


def _finding_matches_fact(finding: AIReviewFinding, fact: FinancialFactSnapshot) -> bool:
    if finding.imported_value is None or fact.value is None:
        return False
    if finding.imported_value != fact.value:
        return False
    if finding.provider and fact.provider and finding.provider != fact.provider:
        return False
    if finding.provider_field and fact.provider_field and finding.provider_field != fact.provider_field:
        return False
    return True


def _unreviewed_primary_reason(fact: FinancialFactSnapshot, *, is_review_candidate: bool) -> str:
    if is_review_candidate:
        return (
            "Offizieller SEC-Filing-Kandidat. Der Importer hat nur einen möglichen Mapping-/Tabellenwert "
            "erkannt; vor Berechnungen müssen wirtschaftliche Bedeutung, Periode und Einheit gegen das "
            "interne Feld semantisch bestätigt werden."
        )
    if fact.metric == "short_term_debt":
        return (
            "Offizielle Primärquelle, aber dieses Feld kann aus mehreren kurzfristigen "
            "Finanzierungskomponenten bestehen. Vor Berechnungen ist eine semantische Prüfung erforderlich."
        )
    if fact.metric == "depreciation_amortization":
        return (
            "Offizielle Primärquelle, aber eine berichtete Sammelzeile für Depreciation/Amortization "
            "kann zusätzliche Amortisations- oder andere Non-Cash-Komponenten enthalten. Vor der "
            "Verwendung für EBITDA muss die Zeile exakt zur internen D&A-Definition passen."
        )
    return (
        "Offizielle Primärquelle, aber die Feldsemantik muss vor Berechnungen zusätzlich bestätigt werden."
    )


def _semantic_primary_state(
    fact: FinancialFactSnapshot,
    finding: AIReviewFinding | None,
) -> PreferredDataState:
    """Require a semantic review for a known ambiguous primary-source mapping/candidate."""
    is_review_candidate = fact.provider in {
        "sec_filing_extension",
        "sec_filing_text_candidate",
    }
    if finding is not None and _finding_matches_fact(finding, fact):
        verdict = finding.verdict.upper()
        if verdict == "PASS":
            return PreferredDataState(
                fact=fact,
                quality_status="primary_reviewed_pass",
                calculation_ready=True,
                reason=(
                    "Offizielle Primärquelle; die Zuordnung zum internen Feld wurde zusätzlich "
                    "semantisch bestätigt."
                ),
                review_verdict=verdict,
                review_decision=finding.decision,
            )
        return PreferredDataState(
            fact=fact,
            quality_status="primary_semantic_review_required",
            calculation_ready=False,
            reason=(
                finding.reason
                or "Offizielle Zahl vorhanden, aber die Feldsemantik ist für unser internes Feld noch nicht freigegeben."
            ),
            review_verdict=verdict,
            review_decision=finding.decision,
        )
    if finding is not None:
        return PreferredDataState(
            fact=fact,
            quality_status="review_stale",
            calculation_ready=False,
            reason="Der letzte semantische Prüffund gehört nicht mehr exakt zum aktuellen Primärquellenwert.",
            review_verdict=finding.verdict,
            review_decision=finding.decision,
        )
    return PreferredDataState(
        fact=fact,
        quality_status="primary_semantic_review_required",
        calculation_ready=False,
        reason=_unreviewed_primary_reason(fact, is_review_candidate=is_review_candidate),
    )


def _state_for_fact(
    fact: FinancialFactSnapshot,
    finding: AIReviewFinding | None,
    *,
    legacy_approved_metrics: set[str],
) -> PreferredDataState:
    if fact.provider == "manual_override":
        return PreferredDataState(
            fact=fact,
            quality_status="confirmed_override",
            calculation_ready=True,
            reason="Vom Nutzer bestätigter Override mit erhaltener Provider-Provenienz.",
        )

    if (
        ((fact.provider or ""), fact.metric) in PRIMARY_SEMANTIC_REVIEW_REQUIRED
        or (fact.provider or "") in PRIMARY_SEMANTIC_PROVIDER_REVIEW_REQUIRED
    ):
        return _semantic_primary_state(fact, finding)

    if _is_primary_source(fact):
        return PreferredDataState(
            fact=fact,
            quality_status="primary_source",
            calculation_ready=True,
            reason="Eindeutig zugeordnete offizielle Primärquelle.",
        )

    if fact.metric == "ebitda":
        return PreferredDataState(
            fact=fact,
            quality_status="derive_required",
            calculation_ready=False,
            reason="EBITDA wird für Berechnungen selbst aus EBIT + D&A abgeleitet.",
        )

    if fact.metric in legacy_approved_metrics:
        return PreferredDataState(
            fact=fact,
            quality_status="legacy_primary_validated",
            calculation_ready=True,
            reason="Über die vorhandene Primärquellenvalidierung freigegeben.",
        )

    if finding is None:
        return PreferredDataState(
            fact=fact,
            quality_status="provider_unverified",
            calculation_ready=False,
            reason="Providerwert vorhanden, aber noch nicht gegen Primärquelle freigegeben.",
        )

    if not _finding_matches_fact(finding, fact):
        return PreferredDataState(
            fact=fact,
            quality_status="review_stale",
            calculation_ready=False,
            reason="Der letzte Prüffund gehört nicht mehr exakt zum aktuellen Providerwert.",
            review_verdict=finding.verdict,
            review_decision=finding.decision,
        )

    verdict = finding.verdict.upper()
    if verdict == "PASS":
        return PreferredDataState(
            fact=fact,
            quality_status="reviewed_pass",
            calculation_ready=True,
            reason="Providerwert wurde gegen Primärquelle mit PASS bestätigt.",
            review_verdict=verdict,
            review_decision=finding.decision,
        )
    if verdict == "UNKLAR":
        quality = "unclear"
    else:
        quality = "review_conflict"
    return PreferredDataState(
        fact=fact,
        quality_status=quality,
        calculation_ready=False,
        reason=finding.reason or f"ChatGPT-Prüfung: {verdict}.",
        review_verdict=verdict,
        review_decision=finding.decision,
    )


def load_preferred_data_states(
    session: Session,
    analysis_id: int,
    *,
    metrics: Iterable[str] | None = None,
    period_type: str = "FY",
) -> list[PreferredDataState]:
    facts = load_preferred_financial_facts(
        session,
        analysis_id,
        metrics=metrics,
        period_type=period_type,
    )
    review_index = _latest_review_index(session, analysis_id)
    legacy_approved = _legacy_approved_metrics(session, analysis_id)
    return [
        _state_for_fact(
            fact,
            review_index.get((fact.metric, fact.period_end)),
            legacy_approved_metrics=legacy_approved,
        )
        for fact in facts
    ]
