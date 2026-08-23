from __future__ import annotations

import csv
import json
import re
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stock_valuation.data.metric_requirements import (
    MetricRequirement,
    conditional_metrics,
    core_required_metrics,
    gate_metrics,
    metric_policy,
)
from stock_valuation.data.providers.edgartools_provider import CONCEPT_RULES, EdgarToolsProvider
from stock_valuation.data.providers.sec import SECCompanyFactsProvider
from stock_valuation.data.providers.sec_filing import SECFilingFallbackProvider
from stock_valuation.data.types import NormalizedFinancialFact


COMPANIES = ["ASML", "AAPL", "MSFT", "TSM", "ADBE"]
OUT_MD = ROOT / "diagnostics" / "FINAL_DATA_GATE_REPORT.md"
OUT_JSON = ROOT / "diagnostics" / "FINAL_DATA_GATE_REPORT.json"
OUT_CSV = ROOT / "diagnostics" / "final_data_gate_report.csv"
BLOCKING_STATUSES = {"MISSING", "VALUE_MISMATCH", "CURRENCY_MISMATCH", "PERIOD_MISMATCH"}
INVENTORY_DEPENDENT_ANALYTICS = (
    "inventory_intensity",
    "inventory_turnover",
    "inventory_days",
    "cash_conversion_cycle",
    "owner_earnings",
)


def _load_env() -> None:
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT.parent / ".env")


def _index(facts: list[NormalizedFinancialFact]) -> dict[tuple[str, int], NormalizedFinancialFact]:
    selected: dict[tuple[str, int], NormalizedFinancialFact] = {}
    for fact in facts:
        if fact.value is None or fact.period_type != "FY":
            continue
        key = (fact.metric, fact.period_end.year)
        existing = selected.get(key)
        if existing is None or (fact.filing_date or date.min) > (existing.filing_date or date.min):
            selected[key] = fact
    return selected


def _classification(old: NormalizedFinancialFact | None, new: NormalizedFinancialFact | None) -> str:
    if old is None and new is None:
        return "MISSING"
    if old is None:
        return "EDGARTOOLS_ONLY"
    if new is None:
        return "SEC_FALLBACK_ONLY"
    if old.period_end != new.period_end:
        return "PERIOD_MISMATCH"
    if old.currency and new.currency and old.currency.upper() != new.currency.upper():
        return "CURRENCY_MISMATCH"
    if old.value == new.value:
        return "VALUE_MATCH"
    if old.value in (None, Decimal("0")) or new.value is None:
        return "VALUE_MISMATCH"
    rel = abs(new.value - old.value) / abs(old.value)
    return "SEMANTIC_MATCH" if rel <= Decimal("0.005") else "VALUE_MISMATCH"


def _accession(fact: NormalizedFinancialFact | None) -> str:
    if fact is None:
        return ""
    match = re.search(r"accn=([^;]+)", fact.note or "")
    return match.group(1).strip() if match else ""


def _official_missing_reason(
    ticker: str,
    metric: str,
    year: int,
    annual_fact: NormalizedFinancialFact | None,
) -> str:
    rule = CONCEPT_RULES.get(metric)
    tags = ", ".join(rule.tags) if rule else metric
    filing = ""
    if annual_fact is not None:
        filing = f" Filing-Kontext: accession={_accession(annual_fact)}, filed={annual_fact.filing_date}."
    return (
        f"{ticker} FY{year}: kein offizieller SEC-XBRL-Fact fuer CORE_REQUIRED-Metrik "
        f"{metric} ueber die erlaubten Standard-Tags ({tags}).{filing} "
        "Es wurde kein Nullwert imputiert."
    )


def _not_separately_reported_reason(
    ticker: str,
    metric: str,
    year: int,
    annual_fact: NormalizedFinancialFact,
) -> str:
    rule = CONCEPT_RULES.get(metric)
    tags = ", ".join(rule.tags) if rule else metric
    unavailable = ", ".join(INVENTORY_DEPENDENT_ANALYTICS) if metric == "inventory" else "metrikspezifische Folgekennzahlen"
    return (
        f"{ticker} FY{year}: CONDITIONAL-Metrik {metric} wurde in der offiziellen Primaerquelle "
        f"geprueft (accession={_accession(annual_fact)}, filed={annual_fact.filing_date}); "
        f"kein separater Fact ueber die erlaubten Standard-Tags ({tags}) vorhanden. "
        "Status NOT_SEPARATELY_REPORTED; es wurde kein Nullwert erzeugt. "
        f"Nicht verfuegbare Folgekennzahlen fuer dieses Jahr: {unavailable}."
    )


def main() -> int:
    _load_env()
    core_required = tuple(sorted(core_required_metrics()))
    conditional = set(conditional_metrics())
    gate = tuple(sorted(gate_metrics()))
    sec = SECCompanyFactsProvider()
    edgar = EdgarToolsProvider()
    filing = SECFilingFallbackProvider(user_agent=sec.user_agent, timeout=sec.timeout)
    rows: list[dict[str, object]] = []
    unresolved: list[str] = []
    mixed_version_issues: list[str] = []
    company_summaries: dict[str, object] = {}

    for ticker in COMPANIES:
        match = sec.resolve_company(ticker)
        old_facts = sec.get_normalized_financials(match.cik) if match is not None else []
        new_result = edgar.get_normalized_financials_with_versions(ticker)
        fallback_facts = []
        fallback_unresolved = []
        if match is not None:
            fallback = filing.gap_facts(match.cik, [*old_facts, *new_result.facts], years=10)
            fallback_facts = list(fallback.facts)
            fallback_unresolved = list(fallback.unresolved)
        old = _index([*old_facts, *fallback_facts])
        new = _index(list(new_result.facts))
        years = sorted({year for _, year in old} | {year for _, year in new})[-3:]
        unresolved.extend(
            f"{ticker} FY{gap.year} {gap.metric}: SEC Original-Filing-Fallback {gap.status}; "
            f"{gap.reason} Filing={gap.filing_url or ''}"
            for gap in fallback_unresolved
            if gap.metric in core_required and gap.year in years
        )
        selected_by_year: dict[int, list[NormalizedFinancialFact]] = {year: [] for year in years}
        classes: dict[str, int] = {}

        for year in years:
            annual_context = new.get(("total_assets", year)) or old.get(("total_assets", year))
            for metric in gate:
                old_fact = old.get((metric, year))
                new_fact = new.get((metric, year))
                final_fact = new_fact or old_fact
                klass = _classification(old_fact, new_fact)
                requirement = metric_policy(metric).requirement
                final_status = "PASS" if final_fact is not None and klass not in BLOCKING_STATUSES else "FAIL"
                reason = ""

                if final_fact is None:
                    if metric in conditional and annual_context is not None:
                        klass = "NOT_SEPARATELY_REPORTED"
                        final_status = "NOT_SEPARATELY_REPORTED"
                        reason = _not_separately_reported_reason(ticker, metric, year, annual_context)
                    else:
                        reason = _official_missing_reason(ticker, metric, year, annual_context)
                        unresolved.append(reason)
                elif klass in BLOCKING_STATUSES:
                    reason = (
                        f"{ticker} FY{year} {metric}: ungeklaerter Dual-Run-{klass}; "
                        f"SEC={old_fact.value if old_fact else ''} ({old_fact.provider_field if old_fact else ''}), "
                        f"EdgarTools={new_fact.value if new_fact else ''} ({new_fact.provider_field if new_fact else ''})."
                    )
                    unresolved.append(reason)
                else:
                    selected_by_year[year].append(final_fact)

                classes[klass] = classes.get(klass, 0) + 1
                rows.append(
                    {
                        "ticker": ticker,
                        "fiscal_year": year,
                        "metric": metric,
                        "requirement": requirement.value,
                        "final_status": final_status,
                        "final_provider": final_fact.provider if final_fact else "",
                        "final_value": str(final_fact.value) if final_fact and final_fact.value is not None else "",
                        "final_currency": final_fact.currency if final_fact else "",
                        "final_field": final_fact.provider_field if final_fact else "",
                        "final_filing_date": final_fact.filing_date.isoformat() if final_fact and final_fact.filing_date else "",
                        "final_accession": _accession(final_fact),
                        "dual_run_classification": klass,
                        "sec_value": str(old_fact.value) if old_fact and old_fact.value is not None else "",
                        "sec_field": old_fact.provider_field if old_fact else "",
                        "edgartools_value": str(new_fact.value) if new_fact and new_fact.value is not None else "",
                        "edgartools_field": new_fact.provider_field if new_fact else "",
                        "reason": reason,
                        "dependent_metrics_unavailable": ";".join(INVENTORY_DEPENDENT_ANALYTICS)
                        if klass == "NOT_SEPARATELY_REPORTED" and metric == "inventory"
                        else "",
                    }
                )

        for year, facts in selected_by_year.items():
            providers = {fact.provider for fact in facts}
            if "edgartools" not in providers or "sec_companyfacts" not in providers:
                continue
            versions = {
                (fact.provider, fact.filing_date.isoformat() if fact.filing_date else "", _accession(fact))
                for fact in facts
            }
            if len(versions) > 1:
                issue = (
                    f"{ticker} FY{year}: EdgarTools und SEC-Fallback wurden innerhalb eines "
                    f"Geschaeftsjahres mit unterschiedlichen Filing-/Restatement-Versionen gemischt: "
                    + ", ".join("/".join(item) for item in sorted(versions))
                )
                mixed_version_issues.append(issue)
                unresolved.append(issue)

        company_rows = [row for row in rows if row["ticker"] == ticker]
        company_summaries[ticker] = {
            "years": years,
            "classes": classes,
            "core_required_fields": len(years) * len(core_required),
            "conditional_fields": len(years) * len(conditional),
            "failed_core_fields": sum(
                1
                for row in company_rows
                if row["requirement"] == MetricRequirement.REQUIRED.value
                and row["dual_run_classification"] in BLOCKING_STATUSES
            ),
            "conditional_not_separately_reported": sum(
                1 for row in company_rows if row["final_status"] == "NOT_SEPARATELY_REPORTED"
            ),
        }

    decision = "GO – FINANCIAL DATA PIPELINE V1 FROZEN" if not unresolved else "NO-GO"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "companies": company_summaries,
        "mixed_filing_version_issues": mixed_version_issues,
        "unresolved": unresolved,
        "requirement_review": {
            "changed_to_conditional": ["inventory"],
            "kept_core_required": list(core_required),
            "rationale": (
                "Inventory is business-model dependent and can be absent as a separate official fact. "
                "The remaining CORE_REQUIRED metrics are retained for Financial Data Pipeline V1 because "
                "they are needed as baseline income statement, balance sheet, debt, equity, cash-flow, "
                "capex and D&A anchors for the target non-financial SEC universe."
            ),
        },
    }

    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# FINAL_DATA_GATE_REPORT",
        "",
        f"Generated: {payload['generated_at']}",
        f"Decision: {decision}",
        "",
        "## Summary",
        "",
        "| Company | Years | Core required fields | Failed core fields | Conditional not separately reported | Gate classes |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for ticker, summary in company_summaries.items():
        lines.append(
            f"| {ticker} | {', '.join(str(year) for year in summary['years'])} | "
            f"{summary['core_required_fields']} | {summary['failed_core_fields']} | "
            f"{summary['conditional_not_separately_reported']} | {summary['classes']} |"
        )
    lines.extend(["", "## Requirement Review", ""])
    lines.append("- inventory wurde von REQUIRED auf CONDITIONAL geaendert.")
    lines.append(
        "- Andere bisher globale REQUIRED-Metriken bleiben in V1 CORE_REQUIRED, weil sie die Basisanker fuer "
        "GuV, Bilanz, Schulden, Eigenkapital, Cashflow, Capex und D&A bilden."
    )
    lines.extend(["", "## Remaining Core Causes", ""])
    if unresolved:
        lines.extend(f"- {item}" for item in unresolved)
    else:
        lines.append("- Keine echten MISSING-, VALUE_MISMATCH-, CURRENCY_MISMATCH- oder PERIOD_MISMATCH-Faelle in CORE_REQUIRED-Feldern.")
    lines.extend(["", "## Conditional Fields", ""])
    conditional_rows = [row for row in rows if row["final_status"] == "NOT_SEPARATELY_REPORTED"]
    if conditional_rows:
        lines.extend(
            f"- {row['ticker']} FY{row['fiscal_year']} {row['metric']}: NOT_SEPARATELY_REPORTED; "
            f"nicht verfuegbare Folgekennzahlen: {row['dependent_metrics_unavailable']}."
            for row in conditional_rows
        )
    else:
        lines.append("- Keine CONDITIONAL-Metrik musste als NOT_SEPARATELY_REPORTED markiert werden.")
    lines.extend(["", "## Mixed Filing/Restatement Check", ""])
    if mixed_version_issues:
        lines.extend(f"- {item}" for item in mixed_version_issues)
    else:
        lines.append("- Keine Mischung unterschiedlicher EdgarTools/SEC-Fallback-Versionen innerhalb eines Geschaeftsjahres festgestellt.")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {OUT_MD}")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_CSV}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
