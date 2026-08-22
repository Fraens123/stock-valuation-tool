from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from stock_valuation.data.types import NormalizedEstimate, NormalizedFinancialFact


STATEMENT_MAPPINGS: dict[str, dict[str, tuple[str, str, bool]]] = {
    "income_statement": {
        "revenue": ("totalRevenue", "currency", False),
        "gross_profit": ("grossProfit", "currency", False),
        "cost_of_revenue": ("costOfRevenue", "currency", False),
        "operating_income": ("operatingIncome", "currency", False),
        "ebit": ("ebit", "currency", False),
        "ebitda": ("ebitda", "currency", False),
        "depreciation_amortization": ("depreciationAndAmortization", "currency", False),
        "pretax_income": ("incomeBeforeTax", "currency", False),
        "income_tax_expense": ("incomeTaxExpense", "currency", False),
        "net_income": ("netIncome", "currency", False),
        "interest_expense": ("interestExpense", "currency", False),
        "research_and_development": ("researchAndDevelopment", "currency", False),
    },
    "balance_sheet": {
        "total_assets": ("totalAssets", "currency", False),
        "current_assets": ("totalCurrentAssets", "currency", False),
        "cash_and_equivalents": ("cashAndCashEquivalentsAtCarryingValue", "currency", False),
        "cash_and_short_term_investments": ("cashAndShortTermInvestments", "currency", True),
        "short_term_investments": ("shortTermInvestments", "currency", False),
        "accounts_receivable": ("currentNetReceivables", "currency", False),
        "inventory": ("inventory", "currency", False),
        "ppe_net": ("propertyPlantEquipment", "currency", False),
        "intangible_assets": ("intangibleAssets", "currency", False),
        "goodwill": ("goodwill", "currency", False),
        "total_liabilities": ("totalLiabilities", "currency", False),
        "current_liabilities": ("totalCurrentLiabilities", "currency", False),
        "accounts_payable": ("currentAccountsPayable", "currency", False),
        "short_term_debt": ("shortTermDebt", "currency", False),
        "current_debt": ("currentDebt", "currency", True),
        "long_term_debt": ("longTermDebt", "currency", False),
        "shareholders_equity": ("totalShareholderEquity", "currency", False),
        "retained_earnings": ("retainedEarnings", "currency", False),
    },
    "cash_flow": {
        "operating_cash_flow": ("operatingCashflow", "currency", False),
        "capital_expenditures": ("capitalExpenditures", "currency", False),
        "dividends_paid": ("dividendPayout", "currency", False),
        "share_repurchases": ("paymentsForRepurchaseOfCommonStock", "currency", False),
        "depreciation_amortization_cashflow_crosscheck": (
            "depreciationDepletionAndAmortization",
            "currency",
            True,
        ),
        "change_in_operating_assets": ("changeInOperatingAssets", "currency", True),
        "change_in_operating_liabilities": ("changeInOperatingLiabilities", "currency", True),
    },
}


def _decimal(value: Any) -> Decimal | None:
    if value in (None, "", "None", "null"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _economic_value(metric: str, raw: Decimal | None) -> Decimal | None:
    if raw is None:
        return None
    if metric in {"capital_expenditures", "dividends_paid", "share_repurchases"}:
        return abs(raw)
    return raw


def normalize_alphavantage_financials(
    payloads: dict[str, dict[str, Any]],
    *,
    period_type: str = "FY",
    retrieved_at: datetime | None = None,
) -> list[NormalizedFinancialFact]:
    """Normalize Alpha Vantage statement payloads to the tool's internal keys.

    The function intentionally maps raw statement lines only. It does not calculate ratios,
    debt bridges or working-capital deltas. Those belong to the later metrics engine.
    """
    retrieved_at = retrieved_at or datetime.now(timezone.utc)
    reports_key = "annualReports" if period_type == "FY" else "quarterlyReports"
    output: list[NormalizedFinancialFact] = []

    for statement, mapping in STATEMENT_MAPPINGS.items():
        payload = payloads.get(statement) or {}
        rows = payload.get(reports_key) or []
        if not isinstance(rows, list):
            continue

        for row in rows:
            if not isinstance(row, dict):
                continue
            period_end = _date(row.get("fiscalDateEnding"))
            if period_end is None:
                continue
            currency = row.get("reportedCurrency")

            for metric, (provider_field, unit, optional) in mapping.items():
                provider_value = _decimal(row.get(provider_field))
                output.append(
                    NormalizedFinancialFact(
                        statement=statement,
                        metric=metric,
                        period_end=period_end,
                        period_type=period_type,
                        value=_economic_value(metric, provider_value),
                        provider_value=provider_value,
                        currency=currency,
                        unit=unit,
                        provider="alphavantage",
                        provider_field=provider_field,
                        filing_date=None,
                        retrieved_at=retrieved_at,
                        is_cross_check_only=optional,
                        note="optional/cross-check provider field" if optional else None,
                    )
                )

    return output


def normalize_alphavantage_estimates(
    payload: dict[str, Any], *, retrieved_at: datetime | None = None
) -> list[NormalizedEstimate]:
    """Normalize Alpha Vantage EARNINGS_ESTIMATES rows.

    Alpha Vantage documents annual and quarterly EPS/revenue estimates in the same endpoint.
    We keep only rows that contain at least one estimate and preserve the provider's horizon/date
    as the period label.
    """
    retrieved_at = retrieved_at or datetime.now(timezone.utc)
    rows = payload.get("estimates") or []
    if not isinstance(rows, list):
        return []

    output: list[NormalizedEstimate] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        period = str(row.get("date") or row.get("horizon") or "").strip()
        if not period:
            continue

        eps_low = _decimal(row.get("eps_estimate_low"))
        eps_avg = _decimal(row.get("eps_estimate_average"))
        eps_high = _decimal(row.get("eps_estimate_high"))
        eps_count = _decimal(row.get("eps_estimate_analyst_count"))
        if any(v is not None for v in (eps_low, eps_avg, eps_high)):
            output.append(
                NormalizedEstimate(
                    metric="eps",
                    period=period,
                    low=eps_low,
                    average=eps_avg,
                    high=eps_high,
                    analyst_count=int(eps_count) if eps_count is not None else None,
                    provider="alphavantage",
                    unit="currency_per_share",
                    retrieved_at=retrieved_at,
                )
            )

        revenue_low = _decimal(row.get("revenue_estimate_low"))
        revenue_avg = _decimal(row.get("revenue_estimate_average"))
        revenue_high = _decimal(row.get("revenue_estimate_high"))
        revenue_count = _decimal(row.get("revenue_estimate_analyst_count"))
        if any(v is not None for v in (revenue_low, revenue_avg, revenue_high)):
            output.append(
                NormalizedEstimate(
                    metric="revenue",
                    period=period,
                    low=revenue_low,
                    average=revenue_avg,
                    high=revenue_high,
                    analyst_count=int(revenue_count) if revenue_count is not None else None,
                    provider="alphavantage",
                    unit="currency",
                    retrieved_at=retrieved_at,
                )
            )

    return output
