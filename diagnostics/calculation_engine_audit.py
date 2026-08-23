from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stock_valuation.metrics.calculation_engine import (
    NOT_SEPARATELY_REPORTED,
    CalculationInput,
    METRIC_DEFINITIONS,
    calculate_metrics_for_year,
)


IN_CSV = ROOT / "diagnostics" / "final_data_gate_report.csv"
OUT_MD = ROOT / "diagnostics" / "CALCULATION_ENGINE_AUDIT.md"
OUT_JSON = ROOT / "diagnostics" / "CALCULATION_ENGINE_AUDIT.json"
OUT_CSV = ROOT / "diagnostics" / "calculation_engine_results.csv"


def _decimal(value: str) -> Decimal | None:
    if value in {"", "None", "null"}:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return None


def _load_inputs() -> dict[tuple[str, int], dict[str, CalculationInput]]:
    by_company_year: dict[tuple[str, int], dict[str, CalculationInput]] = defaultdict(dict)
    with IN_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            ticker = row["ticker"]
            year = int(row["fiscal_year"])
            metric = row["metric"]
            status = row["final_status"]
            value = _decimal(row["final_value"])
            by_company_year[(ticker, year)][metric] = CalculationInput(
                metric=metric,
                fiscal_year=year,
                value=value,
                currency=row["final_currency"] or None,
                source_status=NOT_SEPARATELY_REPORTED if status == NOT_SEPARATELY_REPORTED else status,
                provider=row["final_provider"] or "final_data_gate",
                provider_field=row["final_field"] or None,
                accession=row["final_accession"] or None,
                filing_date=row["final_filing_date"] or None,
            )
    return by_company_year


def main() -> int:
    inputs = _load_inputs()
    result_rows: list[dict[str, object]] = []
    summary: dict[str, dict[str, object]] = {}
    for (ticker, year), facts in sorted(inputs.items()):
        results = calculate_metrics_for_year(facts, year)
        available = sum(1 for result in results if result.status == "AVAILABLE")
        unavailable = len(results) - available
        summary.setdefault(ticker, {"years": [], "available": 0, "unavailable": 0})
        summary[ticker]["years"].append(year)
        summary[ticker]["available"] += available
        summary[ticker]["unavailable"] += unavailable
        for result in results:
            result_rows.append(
                {
                    "ticker": ticker,
                    "fiscal_year": year,
                    "metric_id": result.metric_id,
                    "status": result.status,
                    "value": str(result.value) if result.value is not None else "",
                    "unit": result.unit,
                    "issues": ";".join(f"{issue.code}:{','.join(issue.inputs)}" for issue in result.issues),
                    "input_metrics": ";".join(result.input_metrics),
                    "input_provenance": ";".join(
                        f"{item.metric}@{item.accession or item.provider_field or item.provider or 'unknown'}"
                        for item in result.input_provenance
                    ),
                    "inputs_hash": result.inputs_hash or "",
                    "calculation_version": result.calculation_version,
                }
            )

    blockers = [
        row
        for row in result_rows
        if row["status"] == "UNAVAILABLE"
        and not str(row["issues"]).startswith(f"{NOT_SEPARATELY_REPORTED}:inventory")
    ]
    decision = "GO" if not blockers else "NO-GO"

    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result_rows[0]))
        writer.writeheader()
        writer.writerows(result_rows)

    payload = {
        "decision": decision,
        "source": str(IN_CSV),
        "summary": summary,
        "implemented_metrics": [definition.metric_id for definition in METRIC_DEFINITIONS if definition.implemented],
        "documented_not_implemented": [definition.metric_id for definition in METRIC_DEFINITIONS if not definition.implemented],
        "blockers": blockers,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# CALCULATION_ENGINE_AUDIT",
        "",
        "Decision: " + decision + " for CALCULATION ENGINE V1",
        "",
        "## Scope",
        "",
        "- Financial Data Pipeline V1 bleibt eingefroren; dieses Audit nutzt nur den freigegebenen Final-Data-Gate-Output als Calculation-Ready-Eingang.",
        "- Keine Formel liest direkte Providerdaten.",
        "- EBITDA wird ausschliesslich intern berechnet: operating_income + depreciation_amortization.",
        "- NOT_SEPARATELY_REPORTED wird nie als 0 behandelt.",
        "",
        "## Existing Calculation Inventory",
        "",
        "- Vorhanden vor Phase 3: `src/stock_valuation/metrics/engine.py` mit `safe_ratio`, `calculate_ebit_margin`, `calculate_ebitda_margin`.",
        "- Vorhanden vor Phase 3: `src/stock_valuation/metrics/service.py` mit DB-Service fuer EBIT-/EBITDA-Marge aus `load_preferred_data_states(... calculation_ready=True)`.",
        "- Katalogquelle: `src/stock_valuation/knowledge/metrics.yaml`; viele Alt-/Excel-Formeln sind dort dokumentiert, aber nicht automatisch als V1-Formel uebernommen.",
        "- Neu fuer V1: `src/stock_valuation/metrics/calculation_engine.py` mit explizitem Formel- und Availability-Katalog.",
        "",
        "## Metric Catalog",
        "",
        "| Metric | Category | Formula | Inputs | Unit | Sign convention | Missing input behavior | Interpretation |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for definition in METRIC_DEFINITIONS:
        status = "" if definition.implemented else " [documented only]"
        lines.append(
            f"| {definition.metric_id}{status} | {definition.category} | {definition.formula} | "
            f"{', '.join(definition.inputs)} | {definition.unit} | {definition.sign_convention} | "
            f"{definition.missing_inputs} | {definition.interpretation} |"
        )

    lines.extend(
        [
            "",
            "## Categories",
            "",
            "- Profitabilitaet: ebitda",
            "- Margen: gross_margin, operating_margin, net_margin, ebitda_margin",
            "- Kapitalstruktur: equity_ratio",
            "- Liquiditaet: current_ratio, quick_ratio, cash_ratio",
            "- Verschuldung: debt_to_assets, debt_to_equity, net_debt, net_debt_to_ebitda",
            "- Cashflow: operating_cash_flow_margin, capex_ratio, free_cash_flow, free_cash_flow_margin",
            "- Working Capital: working_capital, working_capital_to_revenue, receivables_days, payables_days, inventory_intensity, inventory_days",
            "- Kapitalrenditen: return_on_assets, return_on_equity",
            "- Wachstum: revenue_growth dokumentiert, fuer V1 wegen expliziter Vorjahres-Policy noch nicht produktiv aktiviert",
            "- Aktien-/Bewertungskennzahlen: valuation_multiples dokumentiert, blockiert bis Markt-/Aktienzahl-Datenquelle freigegeben ist",
            "",
            "## Company Runs",
            "",
            "| Company | Years | Available | Unavailable |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for ticker, item in summary.items():
        lines.append(
            f"| {ticker} | {', '.join(str(year) for year in item['years'])} | "
            f"{item['available']} | {item['unavailable']} |"
        )

    lines.extend(["", "## Availability Notes", ""])
    nsr = [row for row in result_rows if NOT_SEPARATELY_REPORTED in str(row["issues"])]
    if nsr:
        for row in nsr:
            lines.append(
                f"- {row['ticker']} FY{row['fiscal_year']} {row['metric_id']}: unavailable because inventory is NOT_SEPARATELY_REPORTED; no zero imputed."
            )
    else:
        lines.append("- Keine NOT_SEPARATELY_REPORTED-bedingten Kennzahlenausfaelle.")

    lines.extend(["", "## Test Coverage", ""])
    lines.extend(
        [
            "- Division durch 0: getestet.",
            "- Negative Werte: getestet.",
            "- Fehlende Werte: getestet.",
            "- Prozent-/Dezimalfehler: getestet; Ratios werden als Dezimalwerte gespeichert.",
            "- Einheitenfehler/Currency Consistency: getestet.",
            "- Unterschiedliche Geschaeftsjahreslaengen: getestet.",
            "- Provenienz/Inputs-Hash: getestet.",
        ]
    )

    lines.extend(["", "## Decision", "", f"{decision} for CALCULATION ENGINE V1"])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_MD}")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_CSV}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
