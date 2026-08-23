from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_valuation.companies.provider_symbols import get_provider_symbol
from stock_valuation.data.history_mapping_audit import audit_history_mapping
from stock_valuation.data.providers.sec_filing import SECFilingFallbackProvider, SECFilingGap
from stock_valuation.data.providers.sec_text import SECFilingTextFallbackProvider, SECFilingTextResult
from stock_valuation.data.snapshot_service import replace_financial_facts
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


def sync_sec_history_text_candidates(
    session: Session,
    analysis: Analysis,
    *,
    text_provider: SECFilingTextFallbackProvider | None = None,
) -> SECHistoryCompletionResult:
    """Fill remaining 10-year SEC gaps with review-only official filing table candidates.

    This is the final automated SEC discovery stage. It never marks a table extraction as
    calculation-ready. Candidates are stored separately and stay blocked until the normal semantic
    review returns PASS or a reviewed correction is explicitly accepted.
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
        replace_financial_facts(
            session,
            analysis,
            [],
            provider="sec_filing_text_candidate",
            source_url="https://www.sec.gov/Archives/edgar/data/",
            source_type="primary_source",
        )
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
    count = replace_financial_facts(
        session,
        analysis,
        result.facts,
        provider="sec_filing_text_candidate",
        source_url="https://www.sec.gov/Archives/edgar/data/",
        source_type="primary_source",
    )
    unresolved = len(result.unresolved)
    if count:
        message = (
            f"{count} offizielle Tabellen-/Textkandidat(en) gefunden; sie bleiben bis zur "
            "semantischen Prüfung blockiert."
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
