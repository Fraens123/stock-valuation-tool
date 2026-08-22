from __future__ import annotations

import os
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import requests

from stock_valuation.data.types import NormalizedFinancialFact
from stock_valuation.data.providers.base import ProviderResponseError


SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}

# Ordered candidates: first matching concept wins for a metric. Company-specific extensions
# are deliberately excluded; this provider uses only standardized SEC US-GAAP/IFRS taxonomies.
CONCEPT_MAP: dict[str, tuple[tuple[str, str], ...]] = {
    "revenue": (
        ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        ("us-gaap", "Revenues"),
        ("us-gaap", "SalesRevenueNet"),
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
        ("us-gaap", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"),
        ("us-gaap", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"),
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
    ),
    "short_term_debt": (
        ("us-gaap", "ShortTermBorrowings"),
        ("us-gaap", "LongTermDebtCurrent"),
        ("ifrs-full", "CurrentBorrowings"),
    ),
    "long_term_debt": (
        ("us-gaap", "LongTermDebtNoncurrent"),
        ("ifrs-full", "NoncurrentBorrowings"),
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
        ("ifrs-full", "DepreciationAndAmortisationExpense"),
    ),
    "dividends_paid": (
        ("us-gaap", "PaymentsOfDividends"),
        ("us-gaap", "PaymentsOfDividendsCommonStock"),
        ("ifrs-full", "DividendsPaidClassifiedAsFinancingActivities"),
    ),
}

POSITIVE_OUTFLOW_METRICS = {"capital_expenditures", "intangible_purchases", "dividends_paid"}


class SECProviderError(RuntimeError):
    pass


class SECCompanyFactsProvider:
    """Official SEC EDGAR XBRL adapter for companies that report to the SEC.

    SEC requires automated clients to declare a User-Agent. Set `SEC_USER_AGENT` locally,
    for example `Your Name your.email@example.com`. No API key is required.
    """

    def __init__(self, user_agent: str | None = None, timeout: int = 30) -> None:
        self.user_agent = (user_agent or os.getenv("SEC_USER_AGENT") or "").strip()
        self.timeout = timeout
        if not self.user_agent:
            raise ValueError(
                "SEC_USER_AGENT fehlt. In `.env` z. B. `SEC_USER_AGENT=Name email@example.com` "
                "eintragen. Diese Angabe wird nur lokal als SEC-Request-Header verwendet."
            )

    def _get_json(self, url: str) -> dict[str, Any]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
        }
        try:
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise SECProviderError(f"SEC-Abruf fehlgeschlagen: {exc}") from exc
        except ValueError as exc:
            raise ProviderResponseError("SEC lieferte keine gültige JSON-Antwort.") from exc
        if not isinstance(payload, dict):
            raise ProviderResponseError("SEC lieferte ein unerwartetes Antwortformat.")
        return payload

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
    # Keep the latest filed annual fact for each period end. This naturally prefers later
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


def normalize_sec_companyfacts(payload: dict[str, Any]) -> list[NormalizedFinancialFact]:
    facts_root = payload.get("facts") or {}
    if not isinstance(facts_root, dict):
        return []

    normalized: list[NormalizedFinancialFact] = []
    retrieved = datetime.now(timezone.utc)
    for metric, candidates in CONCEPT_MAP.items():
        chosen_taxonomy: str | None = None
        chosen_concept: str | None = None
        concept_payload: dict[str, Any] | None = None
        for taxonomy, concept_name in candidates:
            taxonomy_payload = facts_root.get(taxonomy) or {}
            candidate_payload = taxonomy_payload.get(concept_name) if isinstance(taxonomy_payload, dict) else None
            if isinstance(candidate_payload, dict) and _annual_entries(candidate_payload):
                chosen_taxonomy = taxonomy
                chosen_concept = concept_name
                concept_payload = candidate_payload
                break
        if concept_payload is None or chosen_taxonomy is None or chosen_concept is None:
            continue

        for unit, entry in _best_entries_for_concept(concept_payload):
            value = _decimal(entry.get("val"))
            period_end = _date(entry.get("end"))
            if value is None or period_end is None:
                continue
            economic_value = abs(value) if metric in POSITIVE_OUTFLOW_METRICS else value
            statement = (
                "cash_flow"
                if metric in {
                    "operating_cash_flow",
                    "capital_expenditures",
                    "intangible_purchases",
                    "depreciation_amortization",
                    "dividends_paid",
                }
                else "balance_sheet"
                if metric in {
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
                    note=f"SEC form={entry.get('form')}; accn={entry.get('accn')}",
                )
            )
    return normalized
