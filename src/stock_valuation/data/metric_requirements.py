from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MetricRequirement(str, Enum):
    REQUIRED = "REQUIRED"
    CONDITIONAL = "CONDITIONAL"
    DERIVED = "DERIVED"
    OPTIONAL = "OPTIONAL"


class MetricAvailabilityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
    NOT_SEPARATELY_REPORTED = "NOT_SEPARATELY_REPORTED"


@dataclass(frozen=True)
class MetricPolicy:
    requirement: MetricRequirement
    statement: str
    definition: str
    needs_semantic_gate: bool = False
    derived_from: tuple[str, ...] = ()


METRIC_POLICIES: dict[str, MetricPolicy] = {
    "revenue": MetricPolicy(MetricRequirement.REQUIRED, "income_statement", "Total annual revenue."),
    "cost_of_revenue": MetricPolicy(MetricRequirement.OPTIONAL, "income_statement", "Cost directly attributable to revenue."),
    "gross_profit": MetricPolicy(MetricRequirement.REQUIRED, "income_statement", "Gross profit."),
    "operating_income": MetricPolicy(MetricRequirement.REQUIRED, "income_statement", "Operating profit/EBIT before financing and taxes."),
    "pretax_income": MetricPolicy(MetricRequirement.OPTIONAL, "income_statement", "Income before income taxes."),
    "net_income": MetricPolicy(MetricRequirement.REQUIRED, "income_statement", "Consolidated net income."),
    "total_assets": MetricPolicy(MetricRequirement.REQUIRED, "balance_sheet", "Total assets at fiscal year end."),
    "current_assets": MetricPolicy(MetricRequirement.REQUIRED, "balance_sheet", "Current assets at fiscal year end."),
    "cash_and_equivalents": MetricPolicy(MetricRequirement.REQUIRED, "balance_sheet", "Cash and cash equivalents."),
    "short_term_investments": MetricPolicy(MetricRequirement.OPTIONAL, "balance_sheet", "Short-term marketable/current investments."),
    "accounts_receivable": MetricPolicy(MetricRequirement.REQUIRED, "balance_sheet", "Trade/accounts receivable, net."),
    "inventory": MetricPolicy(
        MetricRequirement.CONDITIONAL,
        "balance_sheet",
        "Inventory, net. Conditional: required only when the official primary filing reports inventory as a separate fact; never impute zero from absence.",
    ),
    "ppe_net": MetricPolicy(
        MetricRequirement.REQUIRED,
        "balance_sheet",
        "Net operating property, plant and equipment, excluding separately reported right-of-use assets.",
        needs_semantic_gate=True,
    ),
    "goodwill": MetricPolicy(MetricRequirement.OPTIONAL, "balance_sheet", "Goodwill."),
    "total_liabilities": MetricPolicy(MetricRequirement.REQUIRED, "balance_sheet", "Total liabilities."),
    "current_liabilities": MetricPolicy(MetricRequirement.REQUIRED, "balance_sheet", "Current liabilities."),
    "accounts_payable": MetricPolicy(MetricRequirement.REQUIRED, "balance_sheet", "Trade/accounts payable."),
    "short_term_debt": MetricPolicy(
        MetricRequirement.REQUIRED,
        "balance_sheet",
        "Short-term interest-bearing debt due within twelve months, excluding trade payables and lease liabilities.",
        needs_semantic_gate=True,
    ),
    "long_term_debt": MetricPolicy(MetricRequirement.REQUIRED, "balance_sheet", "Non-current interest-bearing debt."),
    "shareholders_equity": MetricPolicy(MetricRequirement.REQUIRED, "balance_sheet", "Shareholders' equity."),
    "operating_cash_flow": MetricPolicy(MetricRequirement.REQUIRED, "cash_flow", "Net cash from operating activities."),
    "capital_expenditures": MetricPolicy(MetricRequirement.REQUIRED, "cash_flow", "Cash paid to acquire property, plant and equipment."),
    "intangible_purchases": MetricPolicy(MetricRequirement.OPTIONAL, "cash_flow", "Cash paid to acquire intangible assets."),
    "depreciation_amortization": MetricPolicy(
        MetricRequirement.REQUIRED,
        "cash_flow",
        "Depreciation of tangible assets plus amortization of intangible assets; excludes broad non-cash catch-all rows.",
        needs_semantic_gate=True,
    ),
    "dividends_paid": MetricPolicy(MetricRequirement.OPTIONAL, "cash_flow", "Cash dividends paid to shareholders."),
    "ebitda": MetricPolicy(
        MetricRequirement.DERIVED,
        "derived",
        "EBITDA is derived internally as operating_income + depreciation_amortization.",
        derived_from=("operating_income", "depreciation_amortization"),
    ),
    "free_cash_flow": MetricPolicy(
        MetricRequirement.DERIVED,
        "derived",
        "Free cash flow is derived internally from operating cash flow and capital expenditures.",
        derived_from=("operating_cash_flow", "capital_expenditures"),
    ),
}


def metric_policy(metric: str) -> MetricPolicy:
    return METRIC_POLICIES[metric]


def required_metrics() -> tuple[str, ...]:
    return core_required_metrics()


def core_required_metrics() -> tuple[str, ...]:
    return tuple(
        metric
        for metric, policy in METRIC_POLICIES.items()
        if policy.requirement == MetricRequirement.REQUIRED
    )


def conditional_metrics() -> tuple[str, ...]:
    return tuple(
        metric
        for metric, policy in METRIC_POLICIES.items()
        if policy.requirement == MetricRequirement.CONDITIONAL
    )


def gate_metrics() -> tuple[str, ...]:
    return tuple(
        metric
        for metric, policy in METRIC_POLICIES.items()
        if policy.requirement in {MetricRequirement.REQUIRED, MetricRequirement.CONDITIONAL}
    )
