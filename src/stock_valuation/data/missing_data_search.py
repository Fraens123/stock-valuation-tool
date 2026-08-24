from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_valuation.data.semantic_policy import SemanticMappingDecision, semantic_mapping_policy
from stock_valuation.database.models import Analysis, FinancialFactSnapshot


class MissingDataSearchStatus(str, Enum):
    FOUND_SAFE = "FOUND_SAFE"
    FOUND_REVIEW_REQUIRED = "FOUND_REVIEW_REQUIRED"
    MULTIPLE_CANDIDATES = "MULTIPLE_CANDIDATES"
    NOT_FOUND = "NOT_FOUND"
    NOT_SEPARATELY_REPORTED = "NOT_SEPARATELY_REPORTED"


class CandidateType(str, Enum):
    STRUCTURED_PRIMARY = "STRUCTURED_PRIMARY"
    COMPANY_EXTENSION_XBRL = "COMPANY_EXTENSION_XBRL"
    FILING_TABLE_TEXT = "FILING_TABLE_TEXT"
    DERIVED = "DERIVED"
    EXTERNAL_FALLBACK = "EXTERNAL_FALLBACK"


@dataclass(frozen=True)
class MissingDataCandidate:
    metric: str
    fiscal_year: int
    value: Decimal | None
    currency: str | None
    provider: str | None
    provider_field: str | None
    source_url: str | None
    filing_date: date | None
    retrieved_at: object | None
    candidate_type: str
    semantic_status: str
    semantic_reason: str
    confidence: Decimal
    input_refs: tuple[str, ...]
    fact_id: int | None = None
    formula: str | None = None
    method_version: str = "missing-data-assistant-v1"


@dataclass(frozen=True)
class MissingDataSearchResult:
    metric: str
    fiscal_year: int
    status: MissingDataSearchStatus
    candidates: tuple[MissingDataCandidate, ...]
    search_steps: tuple[str, ...]
    message: str
    searched_at: datetime


SEARCH_STEPS: tuple[str, ...] = (
    "bereits importierte strukturierte Primaerdaten",
    "alternative zulaessige Standard-XBRL-Concepts",
    "Company Extension XBRL",
    "Original Filing / XBRL",
    "offizielle Filing-Tabellen",
    "offizielle Filing-Notes / Text",
    "ESEF / offizieller Jahresbericht",
    "freigegebener externer Fallback",
    "manuelle Eingabe",
)

VALUATION_RELEVANT_METRICS = {
    "short_term_debt",
    "long_term_debt",
    "cash_and_equivalents",
    "depreciation_amortization",
    "operating_income",
    "revenue",
    "net_income",
    "operating_cash_flow",
    "capital_expenditures",
    "interest_expense",
}

METRIC_IMPACTS: dict[str, tuple[str, ...]] = {
    "short_term_debt": (
        "Nettoverschuldung",
        "Enterprise Value",
        "EV/EBIT",
        "EV/EBITDA",
        "EV/Sales",
        "Verschuldungskennzahlen",
    ),
    "depreciation_amortization": ("EBITDA", "EBITDA Margin", "EV/EBITDA", "Entity-FCF"),
    "interest_expense": ("Entity-FCF", "Zinsdeckungsgrad", "EV/FCF-Kontext"),
    "intangible_purchases": ("Owner Earnings", "Buch-DCF", "Reinvestitionsanalyse"),
}

D_AND_A_COMPONENTS = {
    "us-gaap:Depreciation",
    "us-gaap:AmortizationOfIntangibleAssets",
    "ifrs-full:DepreciationExpense",
    "ifrs-full:AmortisationExpense",
}


def metric_impacts(metric: str) -> tuple[str, ...]:
    return METRIC_IMPACTS.get(metric, ())


def is_valuation_relevant(metric: str) -> bool:
    return metric in VALUATION_RELEVANT_METRICS


def is_short_term_debt_candidate_field(provider_field: str | None) -> tuple[bool, str | None]:
    text = (provider_field or "").casefold()
    rejected = (
        "accountspayable",
        "accounts payable",
        "liabilitiescurrent",
        "currentliabilities",
        "current liabilities",
        "leaseliability",
        "lease liability",
        "lease",
        "tradepayable",
        "trade payable",
        "tax",
    )
    if any(token in text for token in rejected):
        return False, (
            "Nicht uebernehmen: Lieferantenverbindlichkeiten, Gesamtverbindlichkeiten, "
            "Steuer- oder Leasingverbindlichkeiten sind keine kurzfristigen Finanzschulden."
        )
    return True, None


def search_missing_metric_candidates(
    session: Session,
    analysis: Analysis,
    *,
    metric: str,
    fiscal_year: int,
) -> MissingDataSearchResult:
    rows = _facts_for_cell(session, analysis.id, metric, fiscal_year)
    nsr = [row for row in rows if row.value is None]
    value_rows = [row for row in rows if row.value is not None]
    if not value_rows and nsr:
        return MissingDataSearchResult(
            metric,
            fiscal_year,
            MissingDataSearchStatus.NOT_SEPARATELY_REPORTED,
            (),
            SEARCH_STEPS,
            "Offizielle Quelle wurde geprueft; die Kennzahl ist nicht separat berichtet.",
            datetime.now(UTC),
        )

    candidate_rows = value_rows
    if metric == "depreciation_amortization":
        candidate_rows = [
            row
            for row in value_rows
            if row.provider_field not in D_AND_A_COMPONENTS
        ]
    candidates = tuple(_candidate_from_fact(row, metric, fiscal_year) for row in candidate_rows)
    candidates = tuple(candidate for candidate in candidates if candidate.semantic_status != "REJECTED")
    derived = _derived_candidates(value_rows, metric, fiscal_year)
    candidates = (*candidates, *derived)

    if not candidates:
        return MissingDataSearchResult(
            metric,
            fiscal_year,
            MissingDataSearchStatus.NOT_FOUND,
            (),
            SEARCH_STEPS,
            "Kein gespeicherter offizieller Kandidat gefunden; manuelle Eingabe bleibt moeglich.",
            datetime.now(UTC),
        )
    if len(candidates) > 1:
        status = MissingDataSearchStatus.MULTIPLE_CANDIDATES
        message = "Mehrere Kandidaten gefunden; keine automatische Auswahl."
    elif candidates[0].semantic_status == SemanticMappingDecision.SAFE_STANDARD_MAPPING.value:
        status = MissingDataSearchStatus.FOUND_SAFE
        message = "Eindeutiger freigegebener Standard-Kandidat gefunden."
    else:
        status = MissingDataSearchStatus.FOUND_REVIEW_REQUIRED
        message = "Kandidat gefunden, aber semantische Nutzerpruefung ist erforderlich."

    return MissingDataSearchResult(
        metric,
        fiscal_year,
        status,
        tuple(sorted(candidates, key=lambda item: (item.semantic_status, item.provider or "", item.provider_field or ""))),
        SEARCH_STEPS,
        message,
        datetime.now(UTC),
    )


def _facts_for_cell(
    session: Session,
    analysis_id: int,
    metric: str,
    fiscal_year: int,
) -> list[FinancialFactSnapshot]:
    rows = session.scalars(
        select(FinancialFactSnapshot).where(
            FinancialFactSnapshot.analysis_id == analysis_id,
            FinancialFactSnapshot.metric == metric,
            FinancialFactSnapshot.period_type == "FY",
        )
    ).all()
    return [
        row
        for row in rows
        if row.period_end.year == fiscal_year and row.provider != "manual_override"
    ]


def _candidate_type(fact: FinancialFactSnapshot) -> CandidateType:
    provider = fact.provider or ""
    if provider in {"sec_filing_extension"}:
        return CandidateType.COMPANY_EXTENSION_XBRL
    if provider in {"sec_filing_text_candidate"}:
        return CandidateType.FILING_TABLE_TEXT
    if provider in {"alphavantage", "eodhd"}:
        return CandidateType.EXTERNAL_FALLBACK
    return CandidateType.STRUCTURED_PRIMARY


def _candidate_from_fact(
    fact: FinancialFactSnapshot,
    metric: str,
    fiscal_year: int,
) -> MissingDataCandidate:
    policy = semantic_mapping_policy(fact.provider, fact.provider_field, metric)
    semantic_status = policy.decision.value
    semantic_reason = policy.reason
    confidence = Decimal("0.95") if policy.decision == SemanticMappingDecision.SAFE_STANDARD_MAPPING else Decimal("0.60")
    if metric == "short_term_debt":
        allowed, rejected_reason = is_short_term_debt_candidate_field(fact.provider_field)
        if not allowed:
            semantic_status = "REJECTED"
            semantic_reason = rejected_reason or semantic_reason
            confidence = Decimal("0")
        elif fact.provider_field and "LongTermDebtCurrent" in fact.provider_field:
            semantic_status = SemanticMappingDecision.REVIEW_REQUIRED.value
            semantic_reason = (
                "Current Portion of Long-Term Debt ist ein plausibler Kandidat, aber allein "
                "nicht automatisch die komplette kurzfristige Finanzschuld, falls weitere "
                "Short-Term Borrowings separat bestehen."
            )
            confidence = Decimal("0.60")
    return MissingDataCandidate(
        metric=metric,
        fiscal_year=fiscal_year,
        value=fact.value,
        currency=fact.currency,
        provider=fact.provider,
        provider_field=fact.provider_field,
        source_url=fact.source_url,
        filing_date=fact.filing_date,
        retrieved_at=fact.retrieved_at,
        candidate_type=_candidate_type(fact).value,
        semantic_status=semantic_status,
        semantic_reason=semantic_reason,
        confidence=confidence,
        input_refs=(f"financial_fact_snapshot:{fact.id}",),
        fact_id=fact.id,
    )


def _derived_candidates(
    facts: list[FinancialFactSnapshot],
    metric: str,
    fiscal_year: int,
) -> tuple[MissingDataCandidate, ...]:
    if metric != "depreciation_amortization":
        return ()
    by_field = {fact.provider_field: fact for fact in facts if fact.provider_field in D_AND_A_COMPONENTS}
    us_components = ("us-gaap:Depreciation", "us-gaap:AmortizationOfIntangibleAssets")
    ifrs_components = ("ifrs-full:DepreciationExpense", "ifrs-full:AmortisationExpense")
    for components in (us_components, ifrs_components):
        if all(component in by_field for component in components):
            selected = tuple(by_field[component] for component in components)
            if any(item.value is None for item in selected):
                continue
            value = sum((item.value or Decimal("0")) for item in selected)
            currency = selected[0].currency
            if any(item.currency != currency for item in selected):
                continue
            return (
                MissingDataCandidate(
                    metric=metric,
                    fiscal_year=fiscal_year,
                    value=value,
                    currency=currency,
                    provider="derived",
                    provider_field="aggregation:" + "+".join(components),
                    source_url=selected[0].source_url,
                    filing_date=max((item.filing_date for item in selected if item.filing_date), default=None),
                    retrieved_at=max((item.retrieved_at for item in selected if item.retrieved_at), default=None),
                    candidate_type=CandidateType.DERIVED.value,
                    semantic_status=SemanticMappingDecision.SAFE_STANDARD_MAPPING.value,
                    semantic_reason="Depreciation und Amortization sind beide separat vorhanden und werden vollstaendig addiert.",
                    confidence=Decimal("0.95"),
                    input_refs=tuple(f"financial_fact_snapshot:{item.id}" for item in selected),
                    formula="depreciation + amortization",
                ),
            )
    if any(fact.provider_field in D_AND_A_COMPONENTS for fact in facts):
        return (
            MissingDataCandidate(
                metric=metric,
                fiscal_year=fiscal_year,
                value=None,
                currency=None,
                provider="derived",
                provider_field="incomplete_d_and_a_components",
                source_url=None,
                filing_date=None,
                retrieved_at=None,
                candidate_type=CandidateType.DERIVED.value,
                semantic_status=SemanticMappingDecision.REVIEW_REQUIRED.value,
                semantic_reason="Nur eine D&A-Komponente ist vorhanden; Gesamt-D&A wird nicht konstruiert.",
                confidence=Decimal("0.40"),
                input_refs=tuple(f"financial_fact_snapshot:{fact.id}" for fact in facts if fact.provider_field in D_AND_A_COMPONENTS),
                formula="depreciation + amortization",
            ),
        )
    return ()
