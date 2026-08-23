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
    OUTLIER_DEVIATION_THRESHOLD,
)
from stock_valuation.valuation.dcf import equity_dcf
from stock_valuation.valuation.models import (
    AVAILABLE,
    VALUATION_ENGINE_VERSION,
    DCFScenario,
    FinancialPoint,
    MarketSnapshotInput,
    stable_hash,
)
from stock_valuation.valuation.multiples import current_market_multiples
from stock_valuation.valuation.normalization import normalize_three_year_metric
from stock_valuation.valuation.snapshot import assumptions_payload, create_valuation_snapshot
from stock_valuation.valuation.snapshot import canonical_hash
from stock_valuation.valuation.summary import dcf_summary


BASE_DIR = Path(__file__).resolve().parent
TICKERS = ("ASML", "AAPL", "MSFT", "TSM", "ADBE")
FINANCIAL_DATA_REFERENCE = "diagnostics/final_data_gate_report.csv"
CALCULATION_VERSION = "calc-v1.0"
HISTORICAL_ANALYSIS_VERSION = "historical-v1.0"
QUALITY_VERSION = "quality-v1.0"
MARKET_DATA_VERSION = "market-data-v1.0"


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
        market_inputs_hash = stable_hash(
            tuple(row["inputs_hash"] for row in (market_cap_row, ev_row) if row and row.get("inputs_hash"))
        )
        market_snapshot_id = stable_hash(
            (ticker, market_cap_row["analysis_as_of_date"], market_inputs_hash, MARKET_DATA_VERSION)
        )
        markets[ticker] = MarketSnapshotInput(
            ticker=ticker,
            company=market_cap_row["company"],
            analysis_as_of_date=market_cap_row["analysis_as_of_date"],
            market_snapshot_id=market_snapshot_id,
            market_data_version=MARKET_DATA_VERSION,
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
            inputs_hash=market_inputs_hash,
        )
    return markets


def _quality_context() -> dict[str, dict[str, str]]:
    path = BASE_DIR / "business_quality_results.csv"
    if not path.exists():
        return {}
    output: dict[str, dict[str, str]] = {}
    component_ids = {
        "profitability",
        "margin_quality",
        "cashflow_quality",
        "growth",
        "balance_sheet",
        "capital_efficiency",
        "stability",
    }
    for row in _read_csv(path):
        if row["ticker"] not in TICKERS:
            continue
        ticker = row["ticker"]
        context = output.setdefault(ticker, {"components": {}})
        if row["metric_id"] == "overall_quality_score":
            context.update(
                {
                    "overall_quality_score": row["score"],
                    "overall_quality_assessment": row["assessment"],
                    "quality_version": row["quality_version"],
                    "years": row["years"],
                    "quality_inputs_hash": row["inputs_hash"],
                }
            )
        elif row["category"] == "component_score" and row["metric_id"] in component_ids:
            context["components"][row["metric_id"]] = {
                "score": row["score"],
                "status": row["status"],
                "input_metrics": row["input_metrics"],
            }
            if row["quality_version"]:
                context.setdefault("quality_version", row["quality_version"])
    for context in output.values():
        context["context_hash"] = canonical_hash(context)
    return output


def _historical_context() -> dict[str, dict[str, object]]:
    path = BASE_DIR / "historical_analysis_results.csv"
    if not path.exists():
        return {}
    context: dict[str, dict[str, object]] = {}
    wanted_growth = {"revenue", "net_income", "free_cash_flow"}
    wanted_margins = {
        "gross_margin",
        "operating_margin",
        "net_margin",
        "ebitda_margin",
        "free_cash_flow_margin",
    }
    for row in _read_csv(path):
        ticker = row["ticker"]
        if ticker not in TICKERS:
            continue
        target = context.setdefault(
            ticker,
            {
                "historical_analysis_version": row["calculation_version"],
                "historical_window": set(),
                "revenue_growth": [],
                "earnings_growth": [],
                "fcf_growth": [],
                "margin_trend": {},
                "volatility": {},
                "negative_years": {},
                "missing_years": {},
                "data_confidence": "AVAILABLE",
                "input_refs": [],
            },
        )
        if row["fiscal_year"]:
            target["historical_window"].add(row["fiscal_year"])
        ref = f"historical_analysis:{ticker}:{row['category']}:{row['metric_id']}:{row['fiscal_year']}:{row['window']}"
        target["input_refs"].append(ref)
        if row["category"] == "yoy_growth" and row["status"] == AVAILABLE and row["metric_id"] in wanted_growth:
            key = {
                "revenue": "revenue_growth",
                "net_income": "earnings_growth",
                "free_cash_flow": "fcf_growth",
            }[row["metric_id"]]
            target[key].append({"fiscal_year": row["fiscal_year"], "value": row["value"]})
        elif row["category"] == "cagr" and row["status"] == AVAILABLE and row["metric_id"] in wanted_growth:
            target.setdefault("cagr", {}).setdefault(row["metric_id"], {})[row["window"]] = row["value"]
        elif row["category"] == "margin_trends" and row["metric_id"] in wanted_margins:
            target["margin_trend"][row["metric_id"]] = row["value"]
        elif row["window"] == "volatility" and row["metric_id"] in wanted_growth | wanted_margins:
            target["volatility"][row["metric_id"]] = row["value"]
        elif row["window"] == "negative_years" and row["metric_id"] in wanted_growth | wanted_margins:
            target["negative_years"][row["metric_id"]] = row["value"]
        elif row["window"] == "missing_years" and row["metric_id"] in wanted_growth | wanted_margins:
            target["missing_years"][row["metric_id"]] = row["value"]
    for target in context.values():
        target["historical_window"] = sorted(target["historical_window"])
        target["context_hash"] = canonical_hash(target)
    return context


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
    historical = _historical_context()
    assumptions = assumptions_payload(
        DEFAULT_DCF_SCENARIOS,
        normalization_method=NORMALIZATION_METHOD,
        outlier_threshold=str(OUTLIER_DEVIATION_THRESHOLD),
        sensitivity_discount_rates=tuple(str(item) for item in DEFAULT_SENSITIVITY_DISCOUNT_RATES),
        sensitivity_terminal_growth_rates=tuple(str(item) for item in DEFAULT_SENSITIVITY_TERMINAL_GROWTH_RATES),
    )
    valuation_rows: list[dict[str, str]] = []
    sensitivity_rows: list[dict[str, str]] = []
    snapshot_rows: list[dict[str, str]] = []
    company_payload: dict[str, dict] = {}
    blockers: list[str] = []

    for ticker in TICKERS:
        market = markets.get(ticker)
        if market is None:
            blockers.append(f"{ticker}: market snapshot missing")
            continue
        latest = _latest_points(ticker, financials, calculations)
        company_rows: list[dict[str, str]] = []
        valuation_results = []

        for result in current_market_multiples(latest, market):
            valuation_results.append(result)
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
            valuation_results.append(summary)
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
                "assumptions": asdict(scenario),
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

        quality_context = quality.get(ticker, {})
        historical_context = historical.get(ticker, {})
        if not quality_context.get("overall_quality_score"):
            blockers.append(f"{ticker}: quality context missing overall_quality_score")
        if not historical_context:
            blockers.append(f"{ticker}: historical context missing")
        snapshot = create_valuation_snapshot(
            analysis_id=f"valuation-v1:{ticker}:{market.analysis_as_of_date}",
            market=market,
            financial_data_reference=FINANCIAL_DATA_REFERENCE,
            calculation_version=CALCULATION_VERSION,
            historical_analysis_version=historical_context.get(
                "historical_analysis_version",
                HISTORICAL_ANALYSIS_VERSION,
            ),
            quality_version=quality_context.get("quality_version", QUALITY_VERSION),
            assumptions=assumptions,
            normalized_inputs=normalized_rows,
            valuation_results=tuple(valuation_results),
            quality_context=quality_context,
            historical_context=historical_context,
            created_at=f"{market.analysis_as_of_date}T00:00:00+00:00",
        )
        snapshot_rows.append(
            {
                "ticker": ticker,
                "company": market.company,
                "analysis_id": snapshot.analysis_id,
                "analysis_as_of_date": snapshot.analysis_as_of_date,
                "market_snapshot_id": snapshot.market_snapshot_id,
                "valuation_snapshot_id": snapshot.snapshot_id,
                "assumptions_hash": snapshot.assumptions_hash,
                "inputs_hash": snapshot.inputs_hash,
                "quality_score": str(quality_context.get("overall_quality_score", "")),
                "quality_assessment": str(quality_context.get("overall_quality_assessment", "")),
                "historical_context_available": str(bool(historical_context)),
                "warnings": ";".join(sorted({issue for row in company_rows for issue in row["issues"].split(";") if issue})),
                "status": "AVAILABLE" if not any(row["status"] not in {AVAILABLE, "NOT_MEANINGFUL"} for row in company_rows) else "UNAVAILABLE",
            }
        )

        company_payload[ticker] = {
            "company": market.company,
            "market_snapshot_id": market.market_snapshot_id,
            "valuation_snapshot_id": snapshot.snapshot_id,
            "quality_context": quality_context,
            "historical_context": historical_context,
            "latest_fiscal_year": max(point.fiscal_year for point in latest.values()),
            "normalized_inputs": {result.metric_id: asdict(result) for result in normalized_rows},
            "assumptions": assumptions,
            "rows": company_rows,
            "scenarios": scenario_payload,
            "snapshot": asdict(snapshot),
        }

    decision = "GO – VALUATION ENGINE V1 FROZEN" if not blockers else "NO-GO – VALUATION ENGINE V1"
    return {
        "decision": decision,
        "blockers": blockers,
        "companies": company_payload,
        "valuation_rows": valuation_rows,
        "sensitivity_rows": sensitivity_rows,
        "snapshot_rows": snapshot_rows,
        "methodology": {
            "inputs": [
                "diagnostics/final_data_gate_report.csv",
                "diagnostics/calculation_engine_results.csv",
                "diagnostics/historical_analysis_results.csv",
                "diagnostics/business_quality_results.csv",
                "diagnostics/market_data_live_results.csv",
            ],
            "normalization_method": NORMALIZATION_METHOD,
            "assumption_source": "GENERIC_V1_DEFAULT",
            "dcf_type": "Equity DCF; net debt is not subtracted.",
            "ev_multiple_policy": "EV-based current multiples use enterprise_value; market-cap multiples use market_cap.",
            "recommendation_policy": "No BUY/SELL/HOLD output.",
        },
    }


def write_outputs(payload: dict) -> None:
    valuation_path = BASE_DIR / "valuation_results.csv"
    sensitivity_path = BASE_DIR / "dcf_sensitivity.csv"
    snapshot_path = BASE_DIR / "valuation_snapshot_results.csv"
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

    with snapshot_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "ticker",
                "company",
                "analysis_id",
                "analysis_as_of_date",
                "market_snapshot_id",
                "valuation_snapshot_id",
                "assumptions_hash",
                "inputs_hash",
                "quality_score",
                "quality_assessment",
                "historical_context_available",
                "warnings",
                "status",
            ],
        )
        writer.writeheader()
        writer.writerows(payload["snapshot_rows"])

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
        "## Quality Context Integration",
        "",
        "- Business Quality is loaded from overall_quality_score plus component scores.",
        "- Quality context is persisted for review and provenance only.",
        "- Quality does not change DCF cash flows, discount rates, fair values, or multiples.",
        "",
        "## Historical Context Integration",
        "",
        "- Historical Analysis is loaded as read-only context for Phase 7.",
        "- Included context covers growth, CAGR, margin trends, volatility, negative years, and missing years where available.",
        "- Historical context does not derive or modify DCF assumptions in V1.",
        "",
        "## Warning Propagation",
        "",
        "- Non-blocking upstream warnings are propagated through DCF and final Valuation Summary.",
        "- OUTLIER_REVIEW remains visible when normalized inputs are still usable.",
        "- Generic V1 DCF assumptions are marked with ASSUMPTIONS_NOT_COMPANY_SPECIFIC.",
        "",
        "## Valuation Snapshot Architecture",
        "",
        "- Each company receives an immutable ValuationSnapshot payload in the JSON audit.",
        "- Snapshot identity is deterministic from analysis_id, analysis date, market_snapshot_id, assumptions_hash, inputs_hash, and valuation version.",
        "- Same inputs and assumptions produce the same reproducibility hash; changed inputs produce a new snapshot.",
        "",
        "## Market Snapshot Linkage",
        "",
        "- Diagnostics derive a deterministic market_snapshot_id from ticker, analysis date, market input hashes, and market data version.",
        "- Production callers can provide a persistent market_snapshot_id through MarketSnapshotInput.",
        "- Diagnostic rows are marked as DIAGNOSTIC_SNAPSHOT_REFERENCE unless persisted through valuation_snapshots.",
        "- Production persistence requires PERSISTED_MARKET_SNAPSHOT_REFERENCE via market_data_snapshots.",
        "",
        "## Diagnostics Mode",
        "",
        "- diagnostics/valuation_engine_audit.py reads frozen CSV artifacts and produces reproducible diagnostic snapshots.",
        "- This mode does not claim that the CSV-derived market_snapshot_id is already stored in market_data_snapshots.",
        "",
        "## Production Persistence Mode",
        "",
        "- stock_valuation.valuation.persistence persists append-only ValuationSnapshotRecord rows in valuation_snapshots.",
        "- Production persistence verifies that market_snapshot_id exists in market_data_snapshots and belongs to the same analysis_id.",
        "- Missing or cross-analysis market snapshots block persistence with VALUATION_NOT_READY.",
        "",
        "## Assumption Snapshot",
        "",
        "- Bear/Base/Bull assumptions are stored inside every valuation snapshot.",
        "- The default V1 assumptions are marked as GENERIC_V1_DEFAULT, not company-specific forecasts.",
        "",
        "## Generic vs Company-Specific Assumptions",
        "",
        "- Current V1 DCF values are available but carry ASSUMPTIONS_NOT_COMPANY_SPECIFIC.",
        "- Company-specific assumption derivation is reserved for Phase 7.",
        "",
        "## Persistence / Immutability",
        "",
        "- valuation_snapshot_results.csv records market_snapshot_id, valuation_snapshot_id, assumptions_hash, and inputs_hash.",
        "- No old valuation result is overwritten in the snapshot model; new inputs create new deterministic snapshot identities.",
        "",
        "## Companies",
        "",
    ]
    for ticker, company in payload["companies"].items():
        statuses = sorted({row["status"] for row in company["rows"]})
        latest_year = company["latest_fiscal_year"]
        normalized_fcf = company["normalized_inputs"]["free_cash_flow"]
        quality_context = company["quality_context"]
        summaries = {
            scenario: company["scenarios"][scenario]["summary"]
            for scenario in ("bear", "base", "bull")
        }
        lines.extend(
            [
                f"### {ticker}",
                "",
                f"- Latest fiscal year used: FY{latest_year}",
                f"- Market snapshot ID: {company['market_snapshot_id']}",
                f"- Valuation snapshot ID: {company['valuation_snapshot_id']}",
                f"- Normalized FCF: {normalized_fcf['value']} {normalized_fcf['currency']}",
                f"- Normalization issues: {', '.join(normalized_fcf['issues']) or 'None'}",
                f"- Quality score: {quality_context.get('overall_quality_score', '')}",
                f"- Quality assessment: {quality_context.get('overall_quality_assessment', '')}",
                f"- Historical context availability: {bool(company['historical_context'])}",
                f"- DCF assumption source: {company['assumptions']['assumption_set']}",
                f"- Bear assumptions: {company['scenarios']['bear']['assumptions']}",
                f"- Base assumptions: {company['scenarios']['base']['assumptions']}",
                f"- Bull assumptions: {company['scenarios']['bull']['assumptions']}",
                f"- Bear fair value: {summaries['bear']['fair_value_per_unit']} {summaries['bear']['trading_currency']}",
                f"- Base fair value: {summaries['base']['fair_value_per_unit']} {summaries['base']['trading_currency']}",
                f"- Bull fair value: {summaries['bull']['fair_value_per_unit']} {summaries['bull']['trading_currency']}",
                f"- Market price: {summaries['base']['market_price']} {summaries['base']['trading_currency']}",
                f"- Base upside/downside: {summaries['base']['upside_downside']}",
                f"- Base margin of safety: {summaries['base']['margin_of_safety']}",
                f"- Warnings: {', '.join(sorted({issue for row in company['rows'] for issue in row['issues'].split(';') if issue})) or 'None'}",
                f"- Inputs hash: {company['snapshot']['inputs_hash']}",
                f"- Statuses: {', '.join(statuses)}",
                "",
            ]
        )
    lines.extend(["## Regression Results", ""])
    lines.append("- Valuation snapshot, context, warning propagation, and deterministic hash tests are covered by tests/test_valuation_engine.py.")
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
            "- diagnostics/valuation_snapshot_results.csv",
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
