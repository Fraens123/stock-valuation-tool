from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable

from stock_valuation.data.metric_requirements import METRIC_POLICIES
from stock_valuation.data.providers.sec import POSITIVE_OUTFLOW_METRICS
from stock_valuation.data.types import NormalizedFinancialFact


class EdgarToolsProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class HistoricalFinancialFactVersion:
    metric: str
    fiscal_year: int
    period_end: date
    value: Decimal
    currency: str | None
    provider_field: str
    filing_date: date | None
    filing_form: str | None
    accession_number: str | None
    selected: bool
    reason: str


@dataclass(frozen=True)
class EdgarToolsFinancialResult:
    facts: tuple[NormalizedFinancialFact, ...]
    historical_versions: tuple[HistoricalFinancialFactVersion, ...]


@dataclass(frozen=True)
class _ConceptRule:
    tags: tuple[str, ...]
    aggregate: bool = False
    total_tags: tuple[str, ...] = ()
    component_tags: tuple[str, ...] = ()
    allow_dimensioned: bool = False
    reject_tokens: tuple[str, ...] = ()
    note: str | None = None


CONCEPT_RULES: dict[str, _ConceptRule] = {
    "revenue": _ConceptRule(
        ("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", "us-gaap:Revenues", "us-gaap:SalesRevenueNet", "ifrs-full:RevenueFromContractsWithCustomers", "ifrs-full:Revenue")
    ),
    "cost_of_revenue": _ConceptRule(("us-gaap:CostOfRevenue", "us-gaap:CostOfGoodsAndServicesSold", "ifrs-full:CostOfSales")),
    "gross_profit": _ConceptRule(("us-gaap:GrossProfit", "ifrs-full:GrossProfit")),
    "operating_income": _ConceptRule(("us-gaap:OperatingIncomeLoss", "ifrs-full:ProfitLossFromOperatingActivities")),
    "pretax_income": _ConceptRule((
        "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        "ifrs-full:ProfitLossBeforeTax",
    )),
    "net_income": _ConceptRule(("us-gaap:NetIncomeLoss", "ifrs-full:ProfitLoss")),
    "total_assets": _ConceptRule(("us-gaap:Assets", "ifrs-full:Assets")),
    "current_assets": _ConceptRule(("us-gaap:AssetsCurrent", "ifrs-full:CurrentAssets")),
    "cash_and_equivalents": _ConceptRule(("us-gaap:CashAndCashEquivalentsAtCarryingValue", "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "ifrs-full:CashAndCashEquivalents")),
    "short_term_investments": _ConceptRule(("us-gaap:ShortTermInvestments", "us-gaap:MarketableSecuritiesCurrent", "us-gaap:AvailableForSaleSecuritiesDebtSecuritiesCurrent")),
    "accounts_receivable": _ConceptRule(("us-gaap:AccountsReceivableNetCurrent", "ifrs-full:TradeAndOtherCurrentReceivables", "ifrs-full:TradeReceivables", "ifrs-full:CurrentTradeReceivables")),
    "inventory": _ConceptRule(("us-gaap:InventoryNet", "ifrs-full:Inventories")),
    "ppe_net": _ConceptRule(
        ("us-gaap:PropertyPlantAndEquipmentNet", "ifrs-full:PropertyPlantAndEquipment"),
        reject_tokens=("right of use", "right-of-use", "lease"),
        note="Explicit rule: PPE excludes separately reported right-of-use/lease assets.",
    ),
    "goodwill": _ConceptRule(("us-gaap:Goodwill", "ifrs-full:Goodwill")),
    "total_liabilities": _ConceptRule(("us-gaap:Liabilities", "ifrs-full:Liabilities")),
    "current_liabilities": _ConceptRule(("us-gaap:LiabilitiesCurrent", "ifrs-full:CurrentLiabilities")),
    "accounts_payable": _ConceptRule(
        (
            "us-gaap:AccountsPayableCurrent",
            "ifrs-full:TradeAndOtherCurrentPayables",
            "ifrs-full:TradePayables",
            "ifrs-full:TradeAndOtherCurrentPayablesToTradeSuppliers",
            "ifrs-full:TradeAndOtherCurrentPayablesToRelatedParties",
        ),
        aggregate=True,
        total_tags=(
            "us-gaap:AccountsPayableCurrent",
            "ifrs-full:TradeAndOtherCurrentPayables",
            "ifrs-full:TradePayables",
        ),
        component_tags=(
            "ifrs-full:TradeAndOtherCurrentPayablesToTradeSuppliers",
            "ifrs-full:TradeAndOtherCurrentPayablesToRelatedParties",
        ),
    ),
    "short_term_debt": _ConceptRule(
        (
            "us-gaap:DebtCurrent",
            "us-gaap:ShortTermBorrowings",
            "us-gaap:LongTermDebtCurrent",
            "ifrs-full:CurrentBorrowings",
            "ifrs-full:CurrentPortionOfLongtermBorrowings",
        ),
        aggregate=True,
        total_tags=("us-gaap:DebtCurrent", "ifrs-full:CurrentBorrowings"),
        component_tags=(
            "us-gaap:ShortTermBorrowings",
            "us-gaap:LongTermDebtCurrent",
            "ifrs-full:CurrentPortionOfLongtermBorrowings",
        ),
        reject_tokens=("lease", "payable", "trade"),
        note="Explicit rule: use official short-term debt total when present; otherwise aggregate only short-term interest-bearing debt components; exclude trade payables and lease liabilities.",
    ),
    "long_term_debt": _ConceptRule(("us-gaap:LongTermDebtNoncurrent", "us-gaap:LongTermDebt", "ifrs-full:NoncurrentBorrowings", "ifrs-full:LongtermBorrowings")),
    "shareholders_equity": _ConceptRule(("us-gaap:StockholdersEquity", "us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", "ifrs-full:Equity")),
    "operating_cash_flow": _ConceptRule(("us-gaap:NetCashProvidedByUsedInOperatingActivities", "us-gaap:NetCashProvidedByUsedInOperatingActivitiesContinuingOperations", "ifrs-full:CashFlowsFromUsedInOperatingActivities")),
    "capital_expenditures": _ConceptRule(("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment", "ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities")),
    "intangible_purchases": _ConceptRule(("us-gaap:PaymentsToAcquireIntangibleAssets", "us-gaap:PaymentsToAcquireProductiveAssets", "ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities")),
    "depreciation_amortization": _ConceptRule(
        (
            "us-gaap:DepreciationDepletionAndAmortization",
            "us-gaap:DepreciationAndAmortization",
            "ifrs-full:DepreciationAndAmortisationExpense",
            "us-gaap:Depreciation",
            "us-gaap:AmortizationOfIntangibleAssets",
            "ifrs-full:DepreciationExpense",
            "ifrs-full:AmortisationExpense",
        ),
        aggregate=True,
        total_tags=(
            "us-gaap:DepreciationDepletionAndAmortization",
            "us-gaap:DepreciationAndAmortization",
            "ifrs-full:DepreciationAndAmortisationExpense",
        ),
        component_tags=(
            "us-gaap:Depreciation",
            "us-gaap:AmortizationOfIntangibleAssets",
            "ifrs-full:DepreciationExpense",
            "ifrs-full:AmortisationExpense",
        ),
        reject_tokens=("and other", "other noncash", "other non-cash", "lease", "right-of-use", "rightofuse"),
        note="Explicit rule: use official combined D&A when present; otherwise aggregate depreciation plus intangible amortization only; reject broad non-cash catch-all and lease/ROU rows.",
    ),
    "dividends_paid": _ConceptRule(("us-gaap:PaymentsOfDividends", "us-gaap:PaymentsOfDividendsCommonStock", "us-gaap:DividendsCommonStockCash", "ifrs-full:DividendsPaidClassifiedAsFinancingActivities")),
}

BALANCE_METRICS = {
    metric for metric, policy in METRIC_POLICIES.items() if policy.statement == "balance_sheet"
}
CASH_FLOW_METRICS = {
    metric for metric, policy in METRIC_POLICIES.items() if policy.statement == "cash_flow"
}


def _decimal(value: Any) -> Decimal | None:
    if value in (None, "", "None"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _tag(fact: Any) -> str:
    concept = str(getattr(fact, "concept", "") or "").strip()
    taxonomy = str(getattr(fact, "taxonomy", "") or "").strip()
    if ":" in concept:
        return concept
    return f"{taxonomy}:{concept}".strip(":")


def _statement(metric: str) -> str:
    return METRIC_POLICIES[metric].statement


def _is_currency_unit(unit: str | None) -> bool:
    normalized = str(unit or "").upper()
    return bool(normalized) and normalized not in {"SHARES", "PURE"} and "PER" not in normalized


def _duration_days(fact: Any) -> int | None:
    start = getattr(fact, "period_start", None)
    end = getattr(fact, "period_end", None)
    if start is None or end is None:
        return None
    try:
        return (end - start).days
    except TypeError:
        return None


def _is_annual_for_metric(fact: Any, metric: str) -> bool:
    if str(getattr(fact, "fiscal_period", "") or "").upper() != "FY":
        return False
    if metric in BALANCE_METRICS:
        return getattr(fact, "period_end", None) is not None
    days = _duration_days(fact)
    return days is not None and 300 <= days <= 380


def _passes_semantic_rule(fact: Any, rule: _ConceptRule) -> bool:
    if not rule.allow_dimensioned and bool(getattr(fact, "is_dimensioned", False)):
        return False
    if not _is_currency_unit(getattr(fact, "unit", None)):
        return False
    text = f"{getattr(fact, 'concept', '')} {getattr(fact, 'label', '')}".casefold()
    return not any(token.casefold() in text for token in rule.reject_tokens)


def _priority(rule: _ConceptRule, tag: str) -> int:
    try:
        return rule.tags.index(tag)
    except ValueError:
        local = tag.split(":", 1)[-1]
        for index, candidate in enumerate(rule.tags):
            if candidate.split(":", 1)[-1] == local:
                return index
    return len(rule.tags)


def _tag_matches(tag: str, candidates: tuple[str, ...]) -> bool:
    if tag in candidates:
        return True
    local = tag.split(":", 1)[-1]
    return any(candidate.split(":", 1)[-1] == local for candidate in candidates)


def _note(metric: str, fact: Any, *, components: Iterable[Any] = ()) -> str:
    rule = CONCEPT_RULES[metric]
    parts = [
        "EdgarTools isolated SEC/XBRL adapter.",
        "Restatement policy: latest official filed comparative/restated value wins; older versions are retained in historical_versions.",
        f"form={getattr(fact, 'form_type', None)}",
        f"accn={getattr(fact, 'accession', None)}",
    ]
    if rule.note:
        parts.append(rule.note)
    component_list = list(components)
    if component_list:
        parts.append(
            "components="
            + ", ".join(
                f"{_tag(item)}={getattr(item, 'numeric_value', getattr(item, 'value', None))}"
                for item in component_list
            )
        )
    return "; ".join(str(part) for part in parts if part)


def _version(metric: str, fact: Any, *, selected: bool, reason: str) -> HistoricalFinancialFactVersion:
    value = _decimal(getattr(fact, "numeric_value", None) or getattr(fact, "value", None))
    if value is None:
        value = Decimal("0")
    return HistoricalFinancialFactVersion(
        metric=metric,
        fiscal_year=int(getattr(fact, "period_end").year),
        period_end=getattr(fact, "period_end"),
        value=abs(value) if metric in POSITIVE_OUTFLOW_METRICS else value,
        currency=getattr(fact, "unit", None),
        provider_field=_tag(fact),
        filing_date=getattr(fact, "filing_date", None),
        filing_form=getattr(fact, "form_type", None),
        accession_number=getattr(fact, "accession", None),
        selected=selected,
        reason=reason,
    )


def _fact(metric: str, source: Any, value: Decimal, field: str, *, components: Iterable[Any] = ()) -> NormalizedFinancialFact:
    economic = abs(value) if metric in POSITIVE_OUTFLOW_METRICS else value
    return NormalizedFinancialFact(
        statement=_statement(metric),
        metric=metric,
        period_end=getattr(source, "period_end"),
        period_type="FY",
        value=economic,
        provider_value=value,
        currency=getattr(source, "unit", None),
        unit="currency",
        provider="edgartools",
        provider_field=field,
        filing_date=getattr(source, "filing_date", None),
        retrieved_at=datetime.now(timezone.utc),
        note=_note(metric, source, components=components),
        source_url="https://www.sec.gov/Archives/edgar/data/",
    )


def _choose_latest(metric: str, facts: list[Any], rule: _ConceptRule) -> tuple[NormalizedFinancialFact | None, list[HistoricalFinancialFactVersion]]:
    if not facts:
        return None, []
    if rule.aggregate:
        total_candidates = [
            fact for fact in facts if rule.total_tags and _tag_matches(_tag(fact), rule.total_tags)
        ]
        if total_candidates:
            selected_fact, versions = _choose_latest(metric, total_candidates, _ConceptRule(rule.total_tags))
            return selected_fact, [
                _version(
                    metric,
                    fact,
                    selected=selected_fact is not None and fact is next((item for item in total_candidates if _tag(item) == selected_fact.provider_field and getattr(item, "filing_date", None) == selected_fact.filing_date), None),
                    reason="selected_official_total" if selected_fact is not None and _tag(fact) == selected_fact.provider_field and getattr(fact, "filing_date", None) == selected_fact.filing_date else "not_selected_component_or_older_version",
                )
                for fact in facts
            ]
        component_candidates = [
            fact for fact in facts if not rule.component_tags or _tag_matches(_tag(fact), rule.component_tags)
        ]
        if not component_candidates:
            return None, []
        latest_filed = max(getattr(fact, "filing_date", None) or date.min for fact in component_candidates)
        latest = [fact for fact in component_candidates if (getattr(fact, "filing_date", None) or date.min) == latest_filed]
        by_tag: dict[str, Any] = {}
        for fact in sorted(latest, key=lambda item: _priority(rule, _tag(item))):
            by_tag.setdefault(_tag(fact), fact)
        components = list(by_tag.values())
        total = sum((_decimal(getattr(item, "numeric_value", None) or getattr(item, "value", None)) or Decimal("0")) for item in components)
        selected = components[0]
        field = "aggregation:" + "+".join(_tag(item) for item in components)
        versions = [
            _version(metric, fact, selected=fact in components, reason="selected_latest_filing_component" if fact in components else "older_filing_version")
            for fact in facts
        ]
        return _fact(metric, selected, total, field, components=components), versions

    best_priority = min(_priority(rule, _tag(fact)) for fact in facts)
    selected_pool = [fact for fact in facts if _priority(rule, _tag(fact)) == best_priority]
    ranked = sorted(selected_pool, key=lambda fact: getattr(fact, "filing_date", None) or date.min, reverse=True)
    selected = ranked[0]
    value = _decimal(getattr(selected, "numeric_value", None) or getattr(selected, "value", None))
    if value is None:
        return None, []
    versions = [
        _version(
            metric,
            fact,
            selected=fact is selected,
            reason="selected_latest_official_filed_version"
            if fact is selected
            else "older_filing_version"
            if _priority(rule, _tag(fact)) == best_priority
            else "lower_semantic_priority",
        )
        for fact in sorted(facts, key=lambda item: (_priority(rule, _tag(item)), getattr(item, "filing_date", None) or date.min))
    ]
    return _fact(metric, selected, value, _tag(selected)), versions


def normalize_edgartools_facts(raw_facts: Iterable[Any]) -> EdgarToolsFinancialResult:
    all_facts = list(raw_facts)
    normalized: list[NormalizedFinancialFact] = []
    versions: list[HistoricalFinancialFactVersion] = []
    for metric, rule in CONCEPT_RULES.items():
        candidate_tags = set(rule.tags)
        candidate_locals = {tag.split(":", 1)[-1] for tag in rule.tags}
        metric_candidates = [
            fact
            for fact in all_facts
            if _tag(fact) in candidate_tags or _tag(fact).split(":", 1)[-1] in candidate_locals
            if _decimal(getattr(fact, "numeric_value", None) or getattr(fact, "value", None)) is not None
            if _is_annual_for_metric(fact, metric)
            if _passes_semantic_rule(fact, rule)
        ]
        by_year: dict[int, list[Any]] = {}
        for fact in metric_candidates:
            period_end = getattr(fact, "period_end", None)
            if period_end is not None:
                by_year.setdefault(int(period_end.year), []).append(fact)
        for year in sorted(by_year):
            fact, fact_versions = _choose_latest(metric, by_year[year], rule)
            if fact is not None:
                normalized.append(fact)
            versions.extend(fact_versions)
    return EdgarToolsFinancialResult(
        facts=tuple(sorted(normalized, key=lambda item: (item.period_end, item.metric))),
        historical_versions=tuple(sorted(versions, key=lambda item: (item.fiscal_year, item.metric, item.filing_date or date.min))),
    )


class EdgarToolsProvider:
    """Isolated EdgarTools SEC/XBRL adapter.

    This provider is intentionally not wired into the production source router yet.
    """

    def __init__(
        self,
        identity: str | None = None,
        *,
        company_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self.identity = (identity or os.getenv("SEC_USER_AGENT") or os.getenv("EDGAR_IDENTITY") or "").strip()
        self._company_factory = company_factory
        if not self.identity:
            raise ValueError("SEC_USER_AGENT oder EDGAR_IDENTITY fehlt fuer EdgarTools.")

    def _company(self, ticker_or_cik: str) -> Any:
        if self._company_factory is not None:
            return self._company_factory(ticker_or_cik)
        try:
            from edgar import Company, set_identity
        except ImportError as exc:
            raise EdgarToolsProviderError("edgartools ist nicht installiert.") from exc
        set_identity(self.identity)
        return Company(ticker_or_cik)

    def get_normalized_financials_with_versions(self, ticker_or_cik: str) -> EdgarToolsFinancialResult:
        company = self._company(ticker_or_cik)
        try:
            facts = company.get_facts().get_all_facts()
        except Exception as exc:
            raise EdgarToolsProviderError(f"EdgarTools-Facts konnten nicht geladen werden: {exc}") from exc
        return normalize_edgartools_facts(facts)

    def get_normalized_financials(self, ticker_or_cik: str) -> list[NormalizedFinancialFact]:
        return list(self.get_normalized_financials_with_versions(ticker_or_cik).facts)
