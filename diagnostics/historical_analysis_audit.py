from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stock_valuation.metrics.historical_analysis import (
    CAPITAL_STRUCTURE_METRICS,
    GROWTH_METRICS,
    MARGIN_METRICS,
    WORKING_CAPITAL_METRICS,
    HistoricalPoint,
    HistoricalResult,
    analyze_historical_series,
    series_from_points,
)


FINAL_GATE_CSV = ROOT / "diagnostics" / "final_data_gate_report.csv"
CALC_CSV = ROOT / "diagnostics" / "calculation_engine_results.csv"
OUT_MD = ROOT / "diagnostics" / "HISTORICAL_ANALYSIS_AUDIT.md"
OUT_JSON = ROOT / "diagnostics" / "HISTORICAL_ANALYSIS_AUDIT.json"
OUT_CSV = ROOT / "diagnostics" / "historical_analysis_results.csv"


def _decimal(value: str) -> Decimal | None:
    if value in {"", "None", "null"}:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return None


def _load_points() -> dict[str, dict[str, list[HistoricalPoint]]]:
    points: dict[str, dict[str, list[HistoricalPoint]]] = defaultdict(lambda: defaultdict(list))
    with FINAL_GATE_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            metric = row["metric"]
            if metric not in GROWTH_METRICS and metric not in {"short_term_debt", "long_term_debt"}:
                continue
            status = "AVAILABLE" if row["final_status"] == "PASS" else "UNAVAILABLE"
            points[row["ticker"]][metric].append(
                HistoricalPoint(
                    metric,
                    int(row["fiscal_year"]),
                    _decimal(row["final_value"]),
                    row["final_currency"] or "currency",
                    status,
                    None if status == "AVAILABLE" else row["final_status"],
                )
            )
    with CALC_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            metric = row["metric_id"]
            if metric not in set(GROWTH_METRICS) | set(MARGIN_METRICS) | set(CAPITAL_STRUCTURE_METRICS) | set(WORKING_CAPITAL_METRICS):
                continue
            points[row["ticker"]][metric].append(
                HistoricalPoint(
                    metric,
                    int(row["fiscal_year"]),
                    _decimal(row["value"]),
                    row["unit"],
                    row["status"],
                    row["issues"] or None,
                )
            )
    for ticker, by_metric in list(points.items()):
        short = {point.fiscal_year: point for point in by_metric.get("short_term_debt", [])}
        long = {point.fiscal_year: point for point in by_metric.get("long_term_debt", [])}
        for year in sorted(set(short) | set(long)):
            st = short.get(year)
            lt = long.get(year)
            if st is None or lt is None or st.value is None or lt.value is None:
                by_metric["debt"].append(HistoricalPoint("debt", year, None, "currency", "UNAVAILABLE", "MISSING_DEBT_COMPONENT"))
            else:
                by_metric["debt"].append(HistoricalPoint("debt", year, st.value + lt.value, st.unit))
    return points


def _serialize(result: HistoricalResult, ticker: str, category: str) -> dict[str, object]:
    return {
        "ticker": ticker,
        "category": category,
        "metric_id": result.metric_id,
        "fiscal_year": result.fiscal_year or "",
        "window": result.window,
        "status": result.status,
        "value": str(result.value) if result.value is not None else "",
        "unit": result.unit,
        "issue": result.issue or "",
        "calculation_version": result.calculation_version,
    }


def main() -> int:
    company_points = _load_points()
    rows: list[dict[str, object]] = []
    summary: dict[str, object] = {}
    accepted_unavailable = {
        "MISSING_PRIOR_YEAR",
        "INSUFFICIENT_HISTORY",
        "MISSING_START_YEAR",
        "NOT_SEPARATELY_REPORTED",
        "UNAVAILABLE_POINT",
    }
    blockers: list[dict[str, object]] = []
    for ticker, by_metric in sorted(company_points.items()):
        series_by_metric = {
            metric: series_from_points(metric_points)
            for metric, metric_points in by_metric.items()
            if metric_points
        }
        analysis = analyze_historical_series(series_by_metric)
        available = 0
        unavailable = 0
        for category, results in analysis.items():
            for result in results:
                row = _serialize(result, ticker, category)
                rows.append(row)
                if result.status == "AVAILABLE":
                    available += 1
                else:
                    unavailable += 1
                    if result.issue not in accepted_unavailable:
                        blockers.append(row)
        years = sorted({point.fiscal_year for points in by_metric.values() for point in points})
        summary[ticker] = {
            "years": years,
            "available": available,
            "unavailable": unavailable,
            "missing_year_checks": [
                row for row in rows if row["ticker"] == ticker and row["window"] == "missing_years" and row["value"] not in {"", "0"}
            ],
        }

    decision = "GO – HISTORICAL ANALYSIS ENGINE V1 FROZEN" if not blockers else "NO-GO"
    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    payload = {
        "decision": decision,
        "summary": summary,
        "blockers": blockers,
        "inputs": [str(FINAL_GATE_CSV), str(CALC_CSV)],
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# HISTORICAL_ANALYSIS_AUDIT",
        "",
        f"Decision: {decision}",
        "",
        "## Scope",
        "",
        "- Baut historische Zeitreihen aus Calculation Engine V1 und freigegebenen Basiswerten.",
        "- Keine Marktpreise, keine Aktienzahl-Daten, keine DCF-Schaetzungen.",
        "- Ausreisser, negative Jahre und fehlende Jahre werden als Status/Issue sichtbar gemacht.",
        "- CAGR wird fuer 3/5/10 Jahre berechnet; bei nur drei Jahren sind 5Y/10Y explizit INSUFFICIENT_HISTORY.",
        "",
        "## Coverage",
        "",
        "- YoY-Wachstum: Revenue, Operating Income, Net Income, EBITDA, Operating Cash Flow, Free Cash Flow.",
        "- CAGR: 3 / 5 / 10 Jahre fuer dieselben Wachstumsgroessen.",
        "- Margenentwicklung: Gross, Operating, Net, EBITDA, FCF Margin.",
        "- Kapitalstruktur: Equity Ratio, Debt, Net Debt, Debt/Equity.",
        "- Working Capital: Working Capital, WC/Revenue, Receivables Days, Payables Days, Inventory Intensity, Inventory Days.",
        "- Stabilitaets-/Qualitaetskennzahlen: negative_years, missing_years, volatility je relevanter Zeitreihe.",
        "",
        "## Company Runs",
        "",
        "| Company | Years | Available historical outputs | Unavailable historical outputs |",
        "| --- | --- | ---: | ---: |",
    ]
    for ticker, item in summary.items():
        lines.append(
            f"| {ticker} | {', '.join(str(year) for year in item['years'])} | "
            f"{item['available']} | {item['unavailable']} |"
        )
    lines.extend(["", "## Explicit Unavailable Cases", ""])
    unavailable_rows = [row for row in rows if row["status"] == "UNAVAILABLE"]
    for row in unavailable_rows[:80]:
        lines.append(
            f"- {row['ticker']} {row['metric_id']} {row['window']} {row['fiscal_year']}: {row['issue']}"
        )
    if len(unavailable_rows) > 80:
        lines.append(f"- ... {len(unavailable_rows) - 80} weitere explizite unavailable rows im CSV.")
    lines.extend(["", "## Decision", "", decision])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_MD}")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_CSV}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
