from __future__ import annotations

import os
from dataclasses import dataclass, replace

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_valuation.companies.provider_symbols import get_provider_symbol
from stock_valuation.data.history_mapping_audit import audit_history_mapping
from stock_valuation.data.providers.sec_filing import SECFilingFallbackProvider, SECFilingGap
from stock_valuation.data.providers.sec_text import SECFilingTextFallbackProvider, SECFilingTextResult
from stock_valuation.data.snapshot_service import replace_financial_facts
from stock_valuation.data.types import NormalizedFinancialFact
from stock_valuation.database.models import Analysis, FinancialFactSnapshot


@dataclass(frozen=True)
class SECHistoryCompletionResult:
    applicable: bool
    candidate_count: int
    unresolved_count: int
    filings_checked: int
    message: str


def _base_sec_facts(session: Session, analysis_id: int) -> list[FinancialFactSnapshot]:
    return list(
        session.scalars(
            select(FinancialFactSnapshot).where(
                FinancialFactSnapshot.analysis_id == analysis_id,
                FinancialFactSnapshot.period_type == "FY",
                FinancialFactSnapshot.provider.in_(
                    (
                        "sec_companyfacts",
                        "sec_filing_xbrl",
                        "sec_filing_extension",
                    )
                ),
            )
        ).all()
    )


def _normalized_from_snapshot(fact: FinancialFactSnapshot) -> NormalizedFinancialFact:
    return NormalizedFinancialFact(
        statement=fact.statement,
        metric=fact.metric,
        period_end=fact.period_end,
        period_type=fact.period_type,
        value=fact.value,
        provider_value=fact.provider_value,
        currency=fact.currency,
        unit=fact.unit or "currency",
        provider=fact.provider or "sec_filing_extension",
        provider_field=fact.provider_field or "",
        filing_date=fact.filing_date,
        retrieved_at=fact.retrieved_at,
        is_cross_check_only=fact.is_cross_check_only,
        note=fact.note,
        source_url=fact.source_url,
    )


def sync_sec_history_text_candidates(
    session: Session,
    analysis: Analysis,
    *,
    text_provider: SECFilingTextFallbackProvider | None = None,
) -> SECHistoryCompletionResult:
    """Fill remaining 10-year SEC gaps with review-only official filing table candidates.

    The final table/text discovery stage feeds candidates into the existing `sec_filing_extension`
    semantic-review path. That keeps one user workflow: recent years plus older open candidates are
    reviewed in the same ChatGPT package. A table candidate is never calculation-ready before PASS.
    """
    cik_row = get_provider_symbol(session, analysis.company, provider="sec", purpose="cik")
    if cik_row is None:
        return SECHistoryCompletionResult(False, 0, 0, 0, "Kein SEC-CIK vorhanden.")

    audit = audit_history_mapping(session, analysis, years=10)
    gaps = [
        SECFilingGap(
            metric=row.metric,
            year=year,
            status="text_review_required",
            reason="10-Jahres-Abdeckung nach strukturierten SEC-Stufen noch unvollständig.",
        )
        for row in audit.rows
        for year in row.missing_years
    ]

    if not gaps:
        return SECHistoryCompletionResult(
            True,
            0,
            0,
            0,
            "Keine verbleibenden 10-Jahres-Lücken nach den strukturierten SEC-Stufen.",
        )

    provider = text_provider
    if provider is None:
        user_agent = (os.getenv("SEC_USER_AGENT") or "").strip()
        if not user_agent:
            return SECHistoryCompletionResult(
                True,
                0,
                len(gaps),
                0,
                "SEC_USER_AGENT fehlt; Tabellen-/Text-Fallback konnte nicht ausgeführt werden.",
            )
        filing_provider = SECFilingFallbackProvider(user_agent=user_agent)
        provider = SECFilingTextFallbackProvider(filing_provider)

    base_facts = _base_sec_facts(session, analysis.id)
    result: SECFilingTextResult = provider.candidate_facts(
        cik_row.symbol,
        gaps,
        base_facts,
    )

    # The router has just refreshed the current XBRL-extension candidates. Preserve those and append
    # table candidates under the same review-only provider so the existing review package includes
    # older candidates automatically. A `text-table:` provider field keeps provenance explicit.
    existing_extension = [
        _normalized_from_snapshot(fact)
        for fact in base_facts
        if fact.provider == "sec_filing_extension"
    ]
    text_candidates = [
        replace(fact, provider="sec_filing_extension")
        for fact in result.facts
    ]
    merged: dict[tuple[str, object], NormalizedFinancialFact] = {
        (fact.metric, fact.period_end): fact for fact in existing_extension
    }
    for fact in text_candidates:
        merged.setdefault((fact.metric, fact.period_end), fact)

    replace_financial_facts(
        session,
        analysis,
        merged.values(),
        provider="sec_filing_extension",
        source_url="https://www.sec.gov/Archives/edgar/data/",
        source_type="primary_source",
    )
    # Clean up any experimental rows from the dedicated provider name if a development snapshot
    # already contains them. New table candidates use the unified review provider above.
    replace_financial_facts(
        session,
        analysis,
        [],
        provider="sec_filing_text_candidate",
        source_url="https://www.sec.gov/Archives/edgar/data/",
        source_type="primary_source",
    )

    count = len(text_candidates)
    unresolved = len(result.unresolved)
    if count:
        message = (
            f"{count} offizielle Tabellen-/Textkandidat(en) gefunden; sie werden automatisch in das "
            "normale ChatGPT-Prüfpaket aufgenommen und bleiben bis zum PASS blockiert."
        )
    else:
        message = "Keine ausreichend eindeutigen Tabellen-/Textkandidaten gefunden."
    if unresolved:
        message += f" {unresolved} Feld/Jahr-Kombination(en) bleiben offen."

    return SECHistoryCompletionResult(
        True,
        count,
        unresolved,
        result.filings_checked,
        message,
    )
