from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import requests

from stock_valuation.data.providers.base import ProviderResponseError
from stock_valuation.data.providers.response_cache import ProviderResponseCache
from stock_valuation.data.types import NormalizedFinancialFact


SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}

# Ordered candidates are resolved per period end, not once for the entire company history.
# This preserves legitimate standard-tag transitions across years while keeping the preferred
# semantic concept when two candidate concepts exist for the same period. Company-specific
# extensions are deliberately excluded.
CONCEPT_MAP: dict[str, tuple[tuple[str, str], ...]] = {
    "revenue": (
        ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        ("us-gaap", "Revenues"),
        ("us-gaap", "SalesRevenueNet"),
        ("ifrs-full", "RevenueFromContractsWithCustomers"),
        ("ifrs-full", "Revenue"),
    ),
    "cost_of_revenue": (
        ("us-gaap", "CostOfRevenue"),
        ("us-gaap", "CostOfGoodsAndServicesSold"),
        ("ifrs-full", "CostOfSales"),
    ),
    "gross_profit": (
        ("us-gaap", "GrossProfit"),
        ("ifrs-full", "GrossProfit"),
    ),
    "operating_income": (
        ("us-gaap", "OperatingIncomeLoss"),
        ("ifrs-full", "ProfitLossFromOperatingActivities"),
    ),
    "pretax_income": (
        (
            "us-gaap",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        ),
        (
            "us-gaap",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        ),
        ("ifrs-full", "ProfitLossBeforeTax"),
    ),
    "net_income": (
        ("us-gaap", "NetIncomeLoss"),
        ("ifrs-full", "ProfitLoss"),
    ),
    "total_assets": (
        ("us-gaap", "Assets"),
        ("ifrs-full", "Assets"),
    ),
    "current_assets": (
        ("us-gaap", "AssetsCurrent"),
        ("ifrs-full", "CurrentAssets"),
    ),
    "cash_and_equivalents": (
        ("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),
        ("ifrs-full", "CashAndCashEquivalents"),
    ),
    "short_term_investments": (
        ("us-gaap", "ShortTermInvestments"),
        ("us-gaap", "MarketableSecuritiesCurrent"),
    ),
    "accounts_receivable": (
        ("us-gaap", "AccountsReceivableNetCurrent"),
        ("ifrs-full", "TradeAndOtherCurrentReceivables"),
        ("ifrs-full", "TradeReceivables"),
        ("ifrs-full", "CurrentTradeReceivables"),
    ),
    "inventory": (
        ("us-gaap", "InventoryNet"),
        ("ifrs-full", "Inventories"),
    ),
    "ppe_net": (
        ("us-gaap", "PropertyPlantAndEquipmentNet"),
        ("ifrs-full", "PropertyPlantAndEquipment"),
    ),
    "goodwill": (
        ("us-gaap", "Goodwill"),
        ("ifrs-full", "Goodwill"),
    ),
    "total_liabilities": (
        ("us-gaap", "Liabilities"),
        ("ifrs-full", "Liabilities"),
    ),
    "current_liabilities": (
        ("us-gaap", "LiabilitiesCurrent"),
        ("ifrs-full", "CurrentLiabilities"),
    ),
    "accounts_payable": (
        ("us-gaap", "AccountsPayableCurrent"),
        ("ifrs-full", "TradeAndOtherCurrentPayables"),
        ("ifrs-full", "TradePayables"),
        ("ifrs-full", "TradeAndOtherCurrentPayablesToTradeSuppliers"),
        ("ifrs-full", "TradeAndOtherCurrentPayablesToRelatedParties"),
    ),
    "short_term_debt": (
        ("us-gaap", "DebtCurrent"),
        ("us-gaap", "ShortTermBorrowings"),
        ("us-gaap", "LongTermDebtCurrent"),
        ("ifrs-full", "CurrentBorrowings"),
        ("ifrs-full", "CurrentPortionOfLongtermBorrowings"),
    ),
    "long_term_debt": (
        ("us-gaap", "LongTermDebtNoncurrent"),
        ("us-gaap", "LongTermDebt"),
        ("ifrs-full", "NoncurrentBorrowings"),
        ("ifrs-full", "LongtermBorrowings"),
    ),
    "shareholders_equity": (
        ("us-gaap", "StockholdersEquity"),
        ("us-gaap", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
        ("ifrs-full", "Equity"),
    ),
    "operating_cash_flow": (
        ("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
        ("ifrs-full", "CashFlowsFromUsedInOperatingActivities"),
    ),
    "capital_expenditures": (
        ("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment"),
        ("ifrs-full", "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"),
    ),
    "intangible_purchases": (
        ("us-gaap", "PaymentsToAcquireProductiveAssets"),
        ("ifrs-full", "PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities"),
    ),
    "depreciation_amortization": (
        ("us-gaap", "DepreciationDepletionAndAmortization"),
        ("us-gaap", "DepreciationAndAmortization"),
        ("ifrs-full", "DepreciationAndAmortisationExpense"),
        ("us-gaap", "Depreciation"),
        ("us-gaap", "AmortizationOfIntangibleAssets"),
        ("ifrs-full", "DepreciationExpense"),
        ("ifrs-full", "AmortisationExpense"),
    ),
    "interest_expense": (
        ("us-gaap", "InterestExpenseNonOperating"),
        ("us-gaap", "InterestExpense"),
        ("ifrs-full", "FinanceCosts"),
    ),
    "dividends_paid": (
        ("us-gaap", "PaymentsOfDividends"),
        ("us-gaap", "PaymentsOfDividendsCommonStock"),
        ("ifrs-full", "DividendsPaidClassifiedAsFinancingActivities"),
    ),
}

AGGREGATE_TOTAL_CONCEPTS: dict[str, tuple[tuple[str, str], ...]] = {
    "accounts_payable": (
        ("us-gaap", "AccountsPayableCurrent"),
        ("ifrs-full", "TradeAndOtherCurrentPayables"),
        ("ifrs-full", "TradePayables"),
    ),
    "short_term_debt": (
        ("us-gaap", "DebtCurrent"),
        ("ifrs-full", "CurrentBorrowings"),
    ),
    "depreciation_amortization": (
        ("us-gaap", "DepreciationDepletionAndAmortization"),
        ("us-gaap", "DepreciationAndAmortization"),
        ("ifrs-full", "DepreciationAndAmortisationExpense"),
    ),
}

AGGREGATE_COMPONENT_CONCEPTS: dict[str, tuple[tuple[str, str], ...]] = {
    "accounts_payable": (
        ("ifrs-full", "TradeAndOtherCurrentPayablesToTradeSuppliers"),
        ("ifrs-full", "TradeAndOtherCurrentPayablesToRelatedParties"),
    ),
    "short_term_debt": (
        ("us-gaap", "ShortTermBorrowings"),
        ("us-gaap", "LongTermDebtCurrent"),
        ("ifrs-full", "CurrentPortionOfLongtermBorrowings"),
    ),
    "depreciation_amortization": (
        ("us-gaap", "Depreciation"),
        ("us-gaap", "AmortizationOfIntangibleAssets"),
        ("ifrs-full", "DepreciationExpense"),
        ("ifrs-full", "AmortisationExpense"),
    ),
}

POSITIVE_OUTFLOW_METRICS = {"capital_expenditures", "intangible_purchases", "dividends_paid"}


class SECProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class SECCompanyCandidate:
    cik: str
    ticker: str
    name: str


def _normalized_name(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


class SECCompanyFactsProvider:
    """Official SEC EDGAR XBRL adapter for companies that report to the SEC.

    SEC requires automated clients to declare a User-Agent. Set `SEC_USER_AGENT` locally,
    for example `Your Name your.email@example.com`. No API key is required.
    """

    def __init__(
        self,
        user_agent: str | None = None,
        timeout: int = 30,
        *,
        use_cache: bool = True,
    ) -> None:
        self.user_agent = (user_agent or os.getenv("SEC_USER_AGENT") or "").strip()
        self.timeout = timeout
        self.use_cache = use_cache
        self.cache = ProviderResponseCache("sec")
        self.cache_hits = 0
        self.network_requests = 0
        if not self.user_agent:
            raise ValueError(
                "SEC_USER_AGENT fehlt. In `.env` z. B. `SEC_USER_AGENT=Name email@example.com` "
                "eintragen. Diese Angabe wird nur lokal als SEC-Request-Header verwendet."
            )

    def _get_json(self, url: str) -> dict[str, Any]:
        cache_params = {"url": url}
        if self.use_cache:
            cached = self.cache.get("GET", cache_params)
            if cached is not None:
                self.cache_hits += 1
                return cached

        headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
        }
        try:
            response = requests.get(url, headers=headers, timeout=self.timeout)
            self.network_requests += 1
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise SECProviderError(f"SEC-Abruf fehlgeschlagen: {exc}") from exc
        except ValueError as exc:
            raise ProviderResponseError("SEC lieferte keine gültige JSON-Antwort.") from exc
        if not isinstance(payload, dict):
            raise ProviderResponseError("SEC lieferte ein unerwartetes Antwortformat.")
        if self.use_cache:
            self.cache.put("GET", cache_params, payload)
        return payload

    def search_companies(self, query: str, *, limit: int = 10) -> list[SECCompanyCandidate]:
        """Search the SEC's public ticker/CIK directory locally after one cached download."""
        term = query.strip()
        if not term:
            return []
        payload = self._get_json(SEC_TICKERS_URL)
        normalized_term = _normalized_name(term)
        ticker_term = term.upper()
        scored: list[tuple[tuple[int, int, str], SECCompanyCandidate]] = []
        for row in payload.values():
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").strip().upper()
            name = str(row.get("title") or "").strip()
            cik = str(row.get("cik_str") or "").zfill(10)
            if not ticker or not name or not cik:
                continue
            normalized_name = _normalized_name(name)
            if ticker == ticker_term:
                rank = 0
            elif normalized_name == normalized_term:
                rank = 1
            elif ticker.startswith(ticker_term) and ticker_term:
                rank = 2
            elif normalized_term and normalized_term in normalized_name:
                rank = 3
            else:
                continue
            candidate = SECCompanyCandidate(cik=cik, ticker=ticker, name=name)
            scored.append(((rank, len(name), ticker), candidate))
        scored.sort(key=lambda item: item[0])
        return [candidate for _, candidate in scored[: max(1, int(limit))]]

    def resolve_cik(self, ticker: str) -> tuple[str, str] | None:
        payload = self._get_json(SEC_TICKERS_URL)
        normalized = ticker.strip().upper()
        for row in payload.values():
            if not isinstance(row, dict):
                continue
            if str(row.get("ticker") or "").strip().upper() != normalized:
                continue
            cik = str(row.get("cik_str") or "").zfill(10)
            title = str(row.get("title") or normalized)
            return cik, title
        return None

    def resolve_company(self, ticker: str, name: str | None = None) -> SECCompanyCandidate | None:
        direct = self.resolve_cik(ticker)
        if direct is not None:
            return SECCompanyCandidate(cik=direct[0], ticker=ticker.strip().upper(), name=direct[1])
        if not name:
            return None
        target = _normalized_name(name)
        exact = [
            row
            for row in self.search_companies(name, limit=20)
            if _normalized_name(row.name) == target
        ]
        return exact[0] if len(exact) == 1 else None

    def get_company_facts(self, cik: str) -> dict[str, Any]:
        normalized = str(cik).strip().replace("CIK", "").zfill(10)
        return self._get_json(SEC_COMPANYFACTS_URL.format(cik=normalized))

    def get_normalized_financials(self, cik: str) -> list[NormalizedFinancialFact]:
        payload = self.get_company_facts(cik)
        return normalize_sec_companyfacts(payload)


def _decimal(value: Any) -> Decimal | None:
    if value in (None, "", "None"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _is_monetary_unit(unit: str) -> bool:
    normalized = unit.upper()
    return normalized not in {"SHARES", "PURE"} and "PER" not in normalized


def _annual_entries(concept: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    units = concept.get("units") or {}
    output: list[tuple[str, dict[str, Any]]] = []
    if not isinstance(units, dict):
        return output
    for unit, entries in units.items():
        if not _is_monetary_unit(str(unit)) or not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("form") or "") not in ANNUAL_FORMS:
                continue
            if str(entry.get("fp") or "").upper() not in {"FY", ""}:
                continue
            if _date(entry.get("end")) is None or _decimal(entry.get("val")) is None:
                continue
            output.append((str(unit), entry))
    return output


def _best_entries_for_concept(concept: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    # Keep the latest filed annual fact for each exact period end. This naturally prefers later
    # restatements/comparatives while preserving filing metadata in the snapshot.
    selected: dict[date, tuple[str, dict[str, Any]]] = {}
    for unit, entry in _annual_entries(concept):
        period_end = _date(entry.get("end"))
        if period_end is None:
            continue
        existing = selected.get(period_end)
        if existing is None:
            selected[period_end] = (unit, entry)
            continue
        existing_filed = _date(existing[1].get("filed")) or date.min
        candidate_filed = _date(entry.get("filed")) or date.min
        if candidate_filed > existing_filed:
            selected[period_end] = (unit, entry)
    return [selected[key] for key in sorted(selected)]


def _best_entries_for_metric(
    facts_root: dict[str, Any],
    candidates: tuple[tuple[str, str], ...],
) -> list[tuple[str, str, str, dict[str, Any]]]:
    """Resolve ordered standard concepts per period end instead of per whole history.

    Candidate order remains the semantic priority for collisions on the same date. Lower-priority
    standard concepts are used only for period ends not covered by a higher-priority concept. This
    exposes legitimate taxonomy/tag changes instead of turning them into artificial history gaps.
    """
    selected: dict[date, tuple[str, str, str, dict[str, Any]]] = {}
    for taxonomy, concept_name in candidates:
        taxonomy_payload = facts_root.get(taxonomy) or {}
        if not isinstance(taxonomy_payload, dict):
            continue
        concept_payload = taxonomy_payload.get(concept_name)
        if not isinstance(concept_payload, dict):
            continue
        for unit, entry in _best_entries_for_concept(concept_payload):
            period_end = _date(entry.get("end"))
            if period_end is None or period_end in selected:
                continue
            selected[period_end] = (taxonomy, concept_name, unit, entry)
    return [selected[key] for key in sorted(selected)]


def _best_entries_for_aggregate_metric(
    facts_root: dict[str, Any],
    metric: str,
) -> list[tuple[str, str, str, dict[str, Any]]]:
    totals = _best_entries_for_metric(facts_root, AGGREGATE_TOTAL_CONCEPTS[metric])
    total_by_end = {_date(entry.get("end")): (taxonomy, concept_name, unit, entry) for taxonomy, concept_name, unit, entry in totals}
    component_rows: list[tuple[str, str, str, dict[str, Any]]] = []
    for taxonomy, concept_name in AGGREGATE_COMPONENT_CONCEPTS[metric]:
        taxonomy_payload = facts_root.get(taxonomy) or {}
        if not isinstance(taxonomy_payload, dict):
            continue
        concept_payload = taxonomy_payload.get(concept_name)
        if not isinstance(concept_payload, dict):
            continue
        component_rows.extend(
            (taxonomy, concept_name, unit, entry)
            for unit, entry in _best_entries_for_concept(concept_payload)
        )
    by_period_filing: dict[tuple[date, date, str], list[tuple[str, str, str, dict[str, Any]]]] = {}
    for taxonomy, concept_name, unit, entry in component_rows:
        period_end = _date(entry.get("end"))
        filed = _date(entry.get("filed"))
        if period_end is None or filed is None:
            continue
        by_period_filing.setdefault((period_end, filed, str(entry.get("accn") or "")), []).append(
            (taxonomy, concept_name, unit, entry)
        )

    aggregated: dict[date, tuple[str, str, str, dict[str, Any]]] = {}
    for (period_end, filed, accn), rows in by_period_filing.items():
        existing = aggregated.get(period_end)
        if existing is not None and (_date(existing[3].get("filed")) or date.min) > filed:
            continue
        if period_end in total_by_end:
            continue
        if metric == "depreciation_amortization" and not _has_complete_d_and_a_components(rows):
            continue
        total = sum((_decimal(row[3].get("val")) or Decimal("0")) for row in rows)
        unit = rows[0][2]
        field = "+".join(f"{taxonomy}:{concept}" for taxonomy, concept, _, _ in rows)
        aggregated[period_end] = (
            "aggregation",
            field,
            unit,
            {
                "val": total,
                "end": period_end.isoformat(),
                "filed": filed.isoformat(),
                "form": rows[0][3].get("form"),
                "accn": accn,
                "components": field,
            },
        )

    output = dict(total_by_end)
    output.update(aggregated)
    return [output[key] for key in sorted(output)]


def _has_complete_d_and_a_components(rows: list[tuple[str, str, str, dict[str, Any]]]) -> bool:
    fields = {f"{taxonomy}:{concept_name}" for taxonomy, concept_name, _, _ in rows}
    return (
        {"us-gaap:Depreciation", "us-gaap:AmortizationOfIntangibleAssets"}.issubset(fields)
        or {"ifrs-full:DepreciationExpense", "ifrs-full:AmortisationExpense"}.issubset(fields)
    )


def normalize_sec_companyfacts(payload: dict[str, Any]) -> list[NormalizedFinancialFact]:
    facts_root = payload.get("facts") or {}
    if not isinstance(facts_root, dict):
        return []

    normalized: list[NormalizedFinancialFact] = []
    retrieved = datetime.now(timezone.utc)
    for metric, candidates in CONCEPT_MAP.items():
        entries = (
            _best_entries_for_aggregate_metric(facts_root, metric)
            if metric in AGGREGATE_TOTAL_CONCEPTS
            else _best_entries_for_metric(facts_root, candidates)
        )
        for chosen_taxonomy, chosen_concept, unit, entry in entries:
            value = _decimal(entry.get("val"))
            period_end = _date(entry.get("end"))
            if value is None or period_end is None:
                continue
            economic_value = abs(value) if metric in POSITIVE_OUTFLOW_METRICS else value
            statement = (
                "cash_flow"
                if metric
                in {
                    "operating_cash_flow",
                    "capital_expenditures",
                    "intangible_purchases",
                    "depreciation_amortization",
                    "dividends_paid",
                }
                else "balance_sheet"
                if metric
                in {
                    "total_assets",
                    "current_assets",
                    "cash_and_equivalents",
                    "short_term_investments",
                    "accounts_receivable",
                    "inventory",
                    "ppe_net",
                    "goodwill",
                    "total_liabilities",
                    "current_liabilities",
                    "accounts_payable",
                    "short_term_debt",
                    "long_term_debt",
                    "shareholders_equity",
                }
                else "income_statement"
            )
            normalized.append(
                NormalizedFinancialFact(
                    statement=statement,
                    metric=metric,
                    period_end=period_end,
                    period_type="FY",
                    value=economic_value,
                    provider_value=value,
                    currency=unit,
                    unit="currency",
                    provider="sec_companyfacts",
                    provider_field=f"{chosen_taxonomy}:{chosen_concept}",
                    filing_date=_date(entry.get("filed")),
                    retrieved_at=retrieved,
                    note=f"SEC form={entry.get('form')}; accn={entry.get('accn')}"
                    + (f"; components={entry.get('components')}" if entry.get("components") else ""),
                )
            )
    return normalized
