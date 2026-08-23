from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stock_valuation.valuation.assumptions import (
    DEFAULT_DCF_SCENARIOS,
    DEFAULT_SENSITIVITY_DISCOUNT_RATES,
    DEFAULT_SENSITIVITY_TERMINAL_GROWTH_RATES,
    NORMALIZATION_METHOD,
)
from stock_valuation.valuation.dcf import equity_dcf
from stock_valuation.valuation.models import AVAILABLE, DCFScenario, FinancialPoint, MarketSnapshotInput, stable_hash
from stock_valuation.valuation.multiples import current_market_multiples
from stock_valuation.valuation.normalization import normalize_three_year_metric
from stock_valuation.valuation.summary import dcf_summary


BASE_DIR = Path(__file__).resolve().parent
TICKERS = ("ASML", "AAPL", "MSFT", "TSM", "ADBE")


def _decimal(value: str | None) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _financial_points() -> dict[str, dict[str, list[FinancialPoint]]]:
    rows = _read_csv(BASE_DIR / "final_data_gate_report.csv")
    output: dict[str, dict[str, list[FinancialPoint]]] = {}
    for row in rows:
        if row["ticker"] not in TICKERS:
            continue
        if row["final_status"] != "PASS":
            continue
        value = _decimal(row["final_value"])
        if value is None:
            continue
        ticker = row["ticker"]
        metric = row["metric"]
        fiscal_year = int(row["fiscal_year"])
        input_ref = (
            f"final_data_gate:{ticker}:{metric}:{fiscal_year}:"
            f"{row['final_accession']}:{row['final_field']}"
        )
        point = FinancialPoint(
            metric,
            fiscal_year,
            value,
            row["final_currency"],
            AVAILABLE,
            input_ref,
            stable_hash((input_ref, str(value), row["final_currency"])),
        )
        output.setdefault(ticker, {}).setdefault(metric, []).append(point)
    return output


def _calculation_points() -> dict[str, dict[str, list[FinancialPoint]]]:
    rows = _read_csv(BASE_DIR / "calculation_engine_results.csv")
    output: dict[str, dict[str, list[FinancialPoint]]] = {}
    for row in rows:
        if row["ticker"] not in TICKERS or row["status"] != AVAILABLE:
            continue
        value = _decimal(row["value"])
        if value is None:
            continue
        ticker = row["ticker"]
        metric = row["metric_id"]
        fiscal_year = int(row["fiscal_year"])
        currency = "RATIO" if row["unit"] != "currency" else _currency_for_ticker(ticker)
        input_ref = f"calculation_engine:{ticker}:{metric}:{fiscal_year}:{row['inputs_hash']}"
        point = FinancialPoint(
            metric,
            fiscal_year,
            value,
            currency,
            AVAILABLE,
            input_ref,
            row["inputs_hash"] or stable_hash((input_ref, str(value))),
        )
        output.setdefault(ticker, {}).setdefault(metric, []).append(point)
    return output


def _currency_for_ticker(ticker: str) -> str:
    return {"ASML": "EUR", "TSM": "TWD"}.get(ticker, "USD")


def _market_inputs() -> dict[str, MarketSnapshotInput]:
    rows = _read_csv(BASE_DIR / "market_data_live_results.csv")
    grouped: dict[str, dict[str, dict[str, str]]] = {}
    for row in rows:
        if row["ticker"] in TICKERS:
            grouped.setdefault(row["ticker"], {})[row["metric_id"]] = row
    markets: dict[str, MarketSnapshotInput] = {}
    for ticker, metric_rows in grouped.items():
        market_cap_row = metric_rows.get("market_cap")
        ev_row = metric_rows.get("enterprise_value")
        if market_cap_row is None:
            continue
        refs = tuple(
            ref
            for row in (market_cap_row, ev_row)
            if row
            for ref in row.get("input_refs", "").split(";")
            if ref
        )
        markets[ticker] = MarketSnapshotInput(
            ticker=ticker,
            company=market_cap_row["company"],
            analysis_as_of_date=market_cap_row["analysis_as_of_date"],
            security_type=market_cap_row["security_type"],
            price=_decimal(market_cap_row["price"]),
            market_cap=_decimal(market_cap_row["value"]),
            enterprise_value=_decimal(ev_row["value"]) if ev_row else None,
            shares_outstanding=_decimal(market_cap_row["shares_outstanding"]),
            share_basis=market_cap_row["share_basis"],
            financial_currency=market_cap_row["financial_currency"],
            trading_currency=market_cap_row["trading_currency"],
            fx_rate=_decimal(market_cap_row["fx_rate"]),
            adr_ratio=_decimal(market_cap_row["adr_ratio"]),
            underlying_share_ratio=_decimal(market_cap_row["underlying_share_ratio"]),
            input_refs=refs,
            inputs_hash=stable_hash(
                tuple(row["inputs_hash"] for row in (market_cap_row, ev_row) if row and row.get("inputs_hash"))
            ),
        )
    return markets


def _quality_context() -> dict[str, dict[str, str]]:
    path = BASE_DIR / "business_quality_results.csv"
    if not path.exists():
        return {}
    output: dict[str, dict[str, str]] = {}
    for row in _read_csv(path):
        if row["ticker"] not in TICKERS:
            continue
        if row["metric_id"] == "overall_business_quality_score":
            output[row["ticker"]] = row
    return output


def _latest_points(
    ticker: str,
    financials: dict[str, dict[str, list[FinancialPoint]]],
    calculations: dict[str, dict[str, list[FinancialPoint]]],
) -> dict[str, FinancialPoint]:
    combined: dict[str, list[FinancialPoint]] = {}
    for source in (financials.get(ticker, {}), calculations.get(ticker, {})):
        for metric, points in source.items():
            combined.setdefault(metric, []).extend(points)
    latest_year = max(point.fiscal_year for points in combined.values() for point in points)
    latest: dict[str, FinancialPoint] = {}
    for metric, points in combined.items():
        same_year = [point for point in points if point.fiscal_year == latest_year]
        if same_year:
            latest[metric] = sorted(same_year, key=lambda item: item.input_ref)[-1]
    return latest


def _points_for_metric(
    ticker: str,
    metric: str,
    financials: dict[str, dict[str, list[FinancialPoint]]],
    calculations: dict[str, dict[str, list[FinancialPoint]]],
) -> tuple[FinancialPoint, ...]:
    points = calculations.get(ticker, {}).get(metric) or financials.get(ticker, {}).get(metric) or []
    return tuple(sorted(points, key=lambda item: item.fiscal_year))


def _result_row(ticker: str, company: str, method: str, metric_id: str, status: str, value, unit, currency, issues, refs, inputs_hash, fiscal_year=None):
    return {
        "ticker": ticker,
        "company": company,
        "fiscal_year": fiscal_year or "",
        "method": method,
        "metric_id": metric_id,
        "status": status,
        "value": "" if value is None else str(value),
        "unit": unit,
        "currency": currency or "",
        "issues": ";".join(issues),
        "input_refs": ";".join(refs),
        "inputs_hash": inputs_hash,
    }


def build_audit() -> dict:
    financials = _financial_points()
    calculations = _calculation_points()
    markets = _market_inputs()
    quality = _quality_context()
    valuation_rows: list[dict[str, str]] = []
    sensitivity_rows: list[dict[str, str]] = []
    company_payload: dict[str, dict] = {}
    blockers: list[str] = []

    for ticker in TICKERS:
        market = markets.get(ticker)
        if market is None:
            blockers.append(f"{ticker}: market snapshot missing")
            continue
        latest = _latest_points(ticker, financials, calculations)
        company_rows: list[dict[str, str]] = []

        for result in current_market_multiples(latest, market):
            row = _result_row(
                ticker,
                market.company,
                result.method,
                result.metric_id,
                result.status,
                result.value,
                result.unit,
                result.currency,
                result.issues,
                result.input_refs,
                result.inputs_hash,
                result.fiscal_year,
            )
            valuation_rows.append(row)
            company_rows.append(row)

        normalized_fcf = normalize_three_year_metric(
            "free_cash_flow",
            _points_for_metric(ticker, "free_cash_flow", financials, calculations),
            method=NORMALIZATION_METHOD,
        )
        normalized_income = normalize_three_year_metric(
            "net_income",
            _points_for_metric(ticker, "net_income", financials, calculations),
            method=NORMALIZATION_METHOD,
        )
        normalized_rows = (normalized_fcf, normalized_income)
        for result in normalized_rows:
            row = _result_row(
                ticker,
                market.company,
                result.method,
                result.metric_id,
                result.status,
                result.value,
                "currency",
                result.currency,
                result.issues,
                result.input_refs,
                result.inputs_hash,
            )
            valuation_rows.append(row)
            company_rows.append(row)

        scenario_payload: dict[str, dict] = {}
        summaries = []
        for scenario in DEFAULT_DCF_SCENARIOS:
            dcf = equity_dcf(ticker, normalized_fcf, scenario)
            summary = dcf_summary(dcf, market)
            summaries.append(summary)
            row = _result_row(
                ticker,
                market.company,
                "equity_dcf",
                f"fair_value_per_unit_{scenario.scenario}",
                summary.status,
                summary.fair_value_per_unit,
                "currency_per_listed_unit",
                summary.trading_currency,
                summary.issues,
                summary.input_refs,
                summary.inputs_hash,
            )
            row["market_price"] = "" if summary.market_price is None else str(summary.market_price)
            row["upside_downside"] = "" if summary.upside_downside is None else str(summary.upside_downside)
            row["margin_of_safety"] = "" if summary.margin_of_safety is None else str(summary.margin_of_safety)
            valuation_rows.append(row)
            company_rows.append(row)
            scenario_payload[scenario.scenario] = {
                "dcf": asdict(dcf),
                "summary": asdict(summary),
            }

        for discount_rate in DEFAULT_SENSITIVITY_DISCOUNT_RATES:
            for terminal_growth in DEFAULT_SENSITIVITY_TERMINAL_GROWTH_RATES:
                scenario = DCFScenario("sensitivity", 5, Decimal("0.05"), discount_rate, terminal_growth)
                dcf = equity_dcf(ticker, normalized_fcf, scenario)
                summary = dcf_summary(dcf, market)
                sensitivity_rows.append(
                    {
                        "ticker": ticker,
                        "discount_rate": str(discount_rate),
                        "terminal_growth_rate": str(terminal_growth),
                        "status": summary.status,
                        "fair_value_per_unit": "" if summary.fair_value_per_unit is None else str(summary.fair_value_per_unit),
                        "currency": summary.trading_currency,
                        "issues": ";".join(summary.issues),
                        "inputs_hash": summary.inputs_hash,
                    }
                )

        fair_values = [item.fair_value_per_unit for item in summaries if item.status == AVAILABLE and item.fair_value_per_unit is not None]
        if len(fair_values) != 3:
            blockers.append(f"{ticker}: not all DCF scenarios available")
        elif not (fair_values[0] <= fair_values[1] <= fair_values[2]):
            blockers.append(f"{ticker}: DCF scenario ordering is not bear <= base <= bull")
        for row in company_rows:
            if row["status"] not in {AVAILABLE, "NOT_MEANINGFUL"}:
                blockers.append(f"{ticker}: {row['metric_id']} {row['status']} {row['issues']}")

        company_payload[ticker] = {
            "company": market.company,
            "quality_context": quality.get(ticker, {}),
            "latest_fiscal_year": max(point.fiscal_year for point in latest.values()),
            "rows": company_rows,
            "scenarios": scenario_payload,
        }

    decision = "GO – VALUATION ENGINE V1 FROZEN" if not blockers else "NO-GO – VALUATION ENGINE V1"
    return {
        "decision": decision,
        "blockers": blockers,
        "companies": company_payload,
        "valuation_rows": valuation_rows,
        "sensitivity_rows": sensitivity_rows,
        "methodology": {
            "inputs": [
                "diagnostics/final_data_gate_report.csv",
                "diagnostics/calculation_engine_results.csv",
                "diagnostics/historical_analysis_results.csv",
                "diagnostics/business_quality_results.csv",
                "diagnostics/market_data_live_results.csv",
            ],
            "normalization_method": NORMALIZATION_METHOD,
            "dcf_type": "Equity DCF; net debt is not subtracted.",
            "ev_multiple_policy": "EV-based current multiples use enterprise_value; market-cap multiples use market_cap.",
            "recommendation_policy": "No BUY/SELL/HOLD output.",
        },
    }


def write_outputs(payload: dict) -> None:
    valuation_path = BASE_DIR / "valuation_results.csv"
    sensitivity_path = BASE_DIR / "dcf_sensitivity.csv"
    json_path = BASE_DIR / "VALUATION_ENGINE_AUDIT.json"
    markdown_path = BASE_DIR / "VALUATION_ENGINE_AUDIT.md"

    fieldnames = [
        "ticker",
        "company",
        "fiscal_year",
        "method",
        "metric_id",
        "status",
        "value",
        "unit",
        "currency",
        "issues",
        "input_refs",
        "inputs_hash",
        "market_price",
        "upside_downside",
        "margin_of_safety",
    ]
    with valuation_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in payload["valuation_rows"]:
            writer.writerow({field: row.get(field, "") for field in fieldnames})

    with sensitivity_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "ticker",
                "discount_rate",
                "terminal_growth_rate",
                "status",
                "fair_value_per_unit",
                "currency",
                "issues",
                "inputs_hash",
            ],
        )
        writer.writeheader()
        writer.writerows(payload["sensitivity_rows"])

    def default(value):
        if isinstance(value, Decimal):
            return str(value)
        return str(value)

    json_path.write_text(json.dumps(payload, indent=2, default=default), encoding="utf-8")
    markdown_path.write_text(_markdown(payload), encoding="utf-8")


def _markdown(payload: dict) -> str:
    lines = [
        "# VALUATION ENGINE AUDIT",
        "",
        f"Decision: **{payload['decision']}**",
        "",
        "## Scope",
        "",
        "- New Valuation Engine V1 reads frozen CSV artifacts only.",
        "- No direct provider, HTTP, raw SEC, EdgarTools, or market API access is used.",
        "- Equity DCF does not subtract net debt; EV-based current multiples use enterprise value.",
        "- No BUY/SELL/HOLD recommendation is generated.",
        "",
        "## Methods",
        "",
        "- Current market multiples: P/E, EV/EBIT, EV/EBITDA, P/FCF, earnings yield, FCF yield.",
        "- Normalized earnings/cash flow: three-year median selected; average and weighted average are implemented alternatives.",
        "- Equity DCF scenarios: Bear/Base/Bull with explicit centralized assumptions.",
        "- Summary: fair value per listed ordinary/ADR/ADS unit, upside/downside, margin of safety.",
        "",
        "## Companies",
        "",
    ]
    for ticker, company in payload["companies"].items():
        statuses = sorted({row["status"] for row in company["rows"]})
        latest_year = company["latest_fiscal_year"]
        lines.extend(
            [
                f"### {ticker}",
                "",
                f"- Latest fiscal year used: FY{latest_year}",
                f"- Statuses: {', '.join(statuses)}",
                "",
            ]
        )
    lines.extend(["## Blockers", ""])
    if payload["blockers"]:
        lines.extend(f"- {blocker}" for blocker in payload["blockers"])
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            "- diagnostics/valuation_results.csv",
            "- diagnostics/dcf_sensitivity.csv",
            "- diagnostics/VALUATION_ENGINE_AUDIT.json",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    audit = build_audit()
    write_outputs(audit)
    print(audit["decision"])
    for blocker in audit["blockers"]:
        print(blocker)
