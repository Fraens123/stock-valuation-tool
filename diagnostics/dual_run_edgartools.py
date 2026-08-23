from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stock_valuation.data.metric_requirements import required_metrics
from stock_valuation.data.providers.edgartools_provider import EdgarToolsProvider
from stock_valuation.data.providers.sec import SECCompanyFactsProvider
from stock_valuation.data.types import NormalizedFinancialFact


OUT_CSV = ROOT / "diagnostics" / "edgartools_dual_run.csv"
OUT_JSON = ROOT / "diagnostics" / "EDGARTOOLS_DUAL_RUN.json"
COMPANIES = ["ASML", "AAPL", "MSFT", "TSM", "ADBE"]


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
        if existing is None or (fact.filing_date or datetime.min.date()) > (
            existing.filing_date or datetime.min.date()
        ):
            selected[key] = fact
    return selected


def _classification(old: NormalizedFinancialFact | None, new: NormalizedFinancialFact | None) -> str:
    if old is None and new is None:
        return "MISSING_BOTH"
    if old is None:
        return "EDGARTOOLS_ONLY"
    if new is None:
        return "OLD_ONLY"
    if old.currency and new.currency and old.currency.upper() != new.currency.upper():
        return "CURRENCY_MISMATCH"
    if old.value == new.value:
        return "VALUE_MATCH"
    if old.value in (None, Decimal("0")) or new.value is None:
        return "VALUE_MISMATCH"
    rel = abs(new.value - old.value) / abs(old.value)
    return "SEMANTIC_MATCH" if rel <= Decimal("0.005") else "VALUE_MISMATCH"


def main() -> int:
    _load_env()
    sec = SECCompanyFactsProvider()
    edgar = EdgarToolsProvider()
    rows: list[dict[str, object]] = []
    summary: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "companies": {},
        "go_no_go": "NO-GO",
        "reason": "Produktionsumschaltung bleibt blockiert, bis alle REQUIRED-Felder die Gates pro Zieluniversum erfüllen.",
    }
    for ticker in COMPANIES:
        company_summary: dict[str, object] = {}
        try:
            match = sec.resolve_company(ticker)
            old_facts = sec.get_normalized_financials(match.cik) if match is not None else []
            old = _index(old_facts)
        except Exception as exc:
            old = {}
            company_summary["old_error"] = f"{type(exc).__name__}: {exc}"
        try:
            result = edgar.get_normalized_financials_with_versions(ticker)
            new = _index(list(result.facts))
            company_summary["historical_versions"] = len(result.historical_versions)
        except Exception as exc:
            new = {}
            company_summary["edgartools_error"] = f"{type(exc).__name__}: {exc}"

        years = sorted({year for _, year in old} | {year for _, year in new})[-3:]
        required = set(required_metrics())
        classes: dict[str, int] = {}
        required_missing = 0
        for year in years:
            for metric in sorted(required):
                old_fact = old.get((metric, year))
                new_fact = new.get((metric, year))
                klass = _classification(old_fact, new_fact)
                classes[klass] = classes.get(klass, 0) + 1
                if new_fact is None:
                    required_missing += 1
                rows.append(
                    {
                        "ticker": ticker,
                        "fiscal_year": year,
                        "metric": metric,
                        "old_value": str(old_fact.value) if old_fact and old_fact.value is not None else "",
                        "old_field": old_fact.provider_field if old_fact else "",
                        "old_filing_date": old_fact.filing_date.isoformat() if old_fact and old_fact.filing_date else "",
                        "edgartools_value": str(new_fact.value) if new_fact and new_fact.value is not None else "",
                        "edgartools_field": new_fact.provider_field if new_fact else "",
                        "edgartools_filing_date": new_fact.filing_date.isoformat() if new_fact and new_fact.filing_date else "",
                        "classification": klass,
                    }
                )
        company_summary["years"] = years
        company_summary["classes"] = classes
        company_summary["required_missing"] = required_missing
        company_summary["required_gate_pass"] = required_missing == 0 and classes.get("VALUE_MISMATCH", 0) == 0
        summary["companies"][ticker] = company_summary

    if rows:
        with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_CSV}")
    print(f"Wrote {OUT_JSON}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
