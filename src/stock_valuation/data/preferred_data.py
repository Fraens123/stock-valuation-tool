from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_valuation.data.resolution import load_preferred_financial_facts
from stock_valuation.database.ai_review_models import AIReviewFinding, AIReviewRun
from stock_valuation.database.models import FinancialFactSnapshot


PRIMARY_SOURCE_PROVIDERS = {
    "asml_primary",
    "esef_ixbrl",
    "sec_companyfacts",
}

# These definitions describe what the internal raw-data keys mean. They are intentionally
# narrower than arbitrary provider labels so that provider fields can be rejected when their
# economic meaning is broader or different.
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
    "ebitda": (
        "EBITDA ist eine abgeleitete Kennzahl. Provider-EBITDA dient nur als Cross-Check; für "
        "Berechnungen soll EBITDA aus freigegebenem EBIT und freigegebenem D&A entstehen."
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


def _state_for_fact(
    fact: FinancialFactSnapshot,
    finding: AIReviewFinding | None,
) -> PreferredDataState:
    if fact.provider == "manual_override":
        return PreferredDataState(
            fact=fact,
            quality_status="confirmed_override",
            calculation_ready=True,
            reason="Vom Nutzer bestätigter Override mit erhaltener Provider-Provenienz.",
        )

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
            reason=(
                "Provider-EBITDA wird nicht als Berechnungsinput freigegeben. EBITDA wird später "
                "aus verifiziertem EBIT und verifiziertem D&A selbst abgeleitet."
            ),
            review_verdict=finding.verdict if finding else None,
            review_decision=finding.decision if finding else None,
        )

    if finding is None:
        return PreferredDataState(
            fact=fact,
            quality_status="provider_unverified",
            calculation_ready=False,
            reason="Providerwert ist gespeichert, aber noch nicht gegen eine Primärquelle verifiziert.",
        )

    if not _finding_matches_fact(finding, fact):
        return PreferredDataState(
            fact=fact,
            quality_status="review_stale",
            calculation_ready=False,
            reason="Der letzte Prüffund gehört nicht mehr exakt zum aktuell bevorzugten Providerwert.",
            review_verdict=finding.verdict,
            review_decision=finding.decision,
        )

    verdict = finding.verdict.upper()
    if verdict == "PASS":
        return PreferredDataState(
            fact=fact,
            quality_status="reviewed_pass",
            calculation_ready=True,
            reason="Providerwert wurde im ChatGPT-Prüflauf gegen eine offizielle Primärquelle bestätigt.",
            review_verdict=verdict,
            review_decision=finding.decision,
        )

    if verdict == "UNKLAR":
        return PreferredDataState(
            fact=fact,
            quality_status="unclear",
            calculation_ready=False,
            reason=finding.reason or "Semantik oder Primärquellen-Zuordnung ist nicht eindeutig.",
            review_verdict=verdict,
            review_decision=finding.decision,
        )

    if verdict in {"WARN", "FAIL"}:
        if finding.decision == "accepted":
            # Normally source resolution already returns the resulting manual_override. If not,
            # blocking here is safer than silently using the old provider value.
            reason = "Prüfkorrektur wurde akzeptiert, aber der bestätigte Override ist nicht bevorzugt auflösbar."
        elif finding.decision == "rejected":
            reason = (
                "Der Korrekturvorschlag wurde verworfen. Das bestätigt den ursprünglichen Providerwert "
                "nicht automatisch; für Berechnungen bleibt er gesperrt."
            )
        else:
            reason = "Es liegt eine ungeklärte Abweichung zur Primärquelle vor."
        return PreferredDataState(
            fact=fact,
            quality_status="review_conflict",
            calculation_ready=False,
            reason=reason,
            review_verdict=verdict,
            review_decision=finding.decision,
        )

    return PreferredDataState(
        fact=fact,
        quality_status="provider_unverified",
        calculation_ready=False,
        reason="Kein verwertbarer Freigabestatus für diesen Providerwert.",
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
    """Return the preferred stored fact plus its calculation-readiness state.

    Source resolution and calculation approval are deliberately separate: Alpha Vantage may be
    the preferred fallback source while still being blocked for calculations until verified.
    """
    facts = load_preferred_financial_facts(
        session,
        analysis_id,
        metrics=metrics,
        period_type=period_type,
    )
    review_index = _latest_review_index(session, analysis_id)
    return [
        _state_for_fact(fact, review_index.get((fact.metric, fact.period_end)))
        for fact in facts
    ]


def calculation_ready_fact_index(
    session: Session,
    analysis_id: int,
    *,
    metrics: Iterable[str] | None = None,
    period_type: str = "FY",
) -> dict[tuple[str, object], FinancialFactSnapshot]:
    """Return only preferred facts that are explicitly safe for downstream calculations."""
    return {
        (state.fact.metric, state.fact.period_end): state.fact
        for state in load_preferred_data_states(
            session,
            analysis_id,
            metrics=metrics,
            period_type=period_type,
        )
        if state.calculation_ready
    }
