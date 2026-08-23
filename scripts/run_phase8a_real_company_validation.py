from __future__ import annotations

import csv
import json
import os
import sys
from dataclasses import dataclass, asdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from dotenv import dotenv_values, find_dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_valuation.analyses.service import create_analysis, get_analysis
from stock_valuation.companies.provider_symbols import get_provider_symbol, upsert_provider_symbol
from stock_valuation.companies.service import get_or_create_company
from stock_valuation.data.preferred_data import load_preferred_data_states
from stock_valuation.data.providers.alphavantage import AlphaVantageProvider
from stock_valuation.data.providers.sec import SECCompanyFactsProvider
from stock_valuation.data.snapshot_service import sync_alphavantage_estimates
from stock_valuation.data.source_router import FinancialSourceResult, sync_best_available_financials
from stock_valuation.database.models import Base
from stock_valuation.market.engine import derive_market_metrics
from stock_valuation.market.models import (
    FXRate,
    ListingData,
    MarketDataSnapshot,
    NetDebtInput,
    NormalizedShareData,
)
from stock_valuation.market.providers import (
    AlphaVantageQuoteProvider,
    FrankfurterFXProvider,
    MarketProviderError,
    OpenExchangeRateFXProvider,
    SECShareDataProvider,
    StooqQuoteProvider,
)
from stock_valuation.market.snapshot_service import persist_market_snapshot
from stock_valuation.workflow.persistence import canonical_json
from stock_valuation.workflow.service import build_analysis_state, refresh_local_analysis_stages


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "diagnostics" / "runtime"
DB_PATH = RUNTIME_DIR / "phase8a_validation.sqlite"
DIAGNOSTICS = ROOT / "diagnostics"
ANALYSIS_AS_OF_DATE = date.today()


@dataclass(frozen=True)
class ValidationTarget:
    ticker: str
    name: str
    currency: str
    country: str
    quote_symbol: str
    exchange: str
    trading_currency: str
    security_type: str = "ordinary_share"
    adr_ratio: str | None = None
    underlying_share_ratio: str | None = None
    alpha_symbol: str | None = None


TARGETS = (
    ValidationTarget("ASML", "ASML Holding N.V.", "EUR", "NL", "asml.nl", "Euronext Amsterdam", "EUR", alpha_symbol="ASML"),
    ValidationTarget("AAPL", "Apple Inc.", "USD", "US", "aapl.us", "NASDAQ", "USD", alpha_symbol="AAPL"),
    ValidationTarget("MSFT", "Microsoft Corporation", "USD", "US", "msft.us", "NASDAQ", "USD", alpha_symbol="MSFT"),
    ValidationTarget("TSM", "Taiwan Semiconductor Manufacturing Company Limited", "TWD", "TW", "tsm.us", "NYSE", "USD", "ADR", "1", "5", "TSM"),
    ValidationTarget("ADBE", "Adobe Inc.", "USD", "US", "adbe.us", "NASDAQ", "USD", alpha_symbol="ADBE"),
)


def main() -> int:
    runtime_env = _load_runtime_environment()
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    DIAGNOSTICS.mkdir(exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    preflight = _environment_preflight(runtime_env)
    provider_failures: list[dict[str, Any]] = []
    engine_blockers: list[str] = []
    environment_blockers = list(preflight["environment_blockers"])
    company_results: list[dict[str, Any]] = []
    stage_results: list[dict[str, Any]] = []
    history_rows: list[dict[str, Any]] = []
    companies: dict[str, Any] = {}
    reopen_checks: dict[str, Any] = {}
    idempotency_checks: dict[str, Any] = {}

    engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

    if environment_blockers:
        decision = "VALIDATION INCONCLUSIVE - ENVIRONMENT / PROVIDER BLOCKED"
    else:
        with SessionLocal() as session:
            for target in TARGETS:
                result = _run_company(session, target, provider_failures, engine_blockers)
                company_results.append(result["company_row"])
                stage_results.extend(result["stage_rows"])
                history_rows.extend(result["history_rows"])
                companies[target.ticker] = result["company"]
                idempotency_checks[target.ticker] = result["idempotency"]

        with SessionLocal() as session:
            for target in TARGETS:
                analysis_id = companies.get(target.ticker, {}).get("analysis_id")
                if analysis_id is None:
                    reopen_checks[target.ticker] = {"status": "NOT_RUN"}
                    continue
                analysis = get_analysis(session, int(analysis_id))
                state = build_analysis_state(session, analysis) if analysis is not None else None
                reopen_checks[target.ticker] = {
                    "status": "PASS" if state is not None and state.stages else "FAIL",
                    "valuation_status": state.stages["VALUATION"].status if state is not None else None,
                    "market_snapshot_id": state.market_snapshot_id if state is not None else None,
                }

    asml_long_history = (
        {
            "status": "NOT_RUN_ENVIRONMENT_BLOCKED",
            "metrics": {},
            "minimum_core_year_count": 0,
            "reason": "; ".join(environment_blockers),
        }
        if environment_blockers
        else _asml_long_history(history_rows)
    )
    if not environment_blockers:
        if asml_long_history.get("status") == "FAIL_LONG_HISTORY_PIPELINE":
            missing = ", ".join(asml_long_history.get("missing_required_metrics", ()))
            engine_blockers.append(
                "ASML LONG_HISTORY: required core metric history below 5Y"
                + (f" ({missing})" if missing else "")
            )
        decision = _decision(companies, provider_failures, engine_blockers, asml_long_history)
    audit = {
        "decision": decision,
        "validation_mode": "REAL_COMPANY_ISOLATED_DB",
        "analysis_as_of_date": ANALYSIS_AS_OF_DATE.isoformat(),
        "validation_db": str(DB_PATH.relative_to(ROOT)),
        "production_uses_diagnostics_csv": False,
        "dotenv_path_found": preflight["dotenv_path_found"],
        "SEC_USER_AGENT_configured": preflight["configured"]["SEC_USER_AGENT"],
        "SEC_USER_AGENT_source": preflight["SEC_USER_AGENT_SOURCE"],
        "ALPHA_VANTAGE_API_KEY_configured": preflight["configured"]["ALPHA_VANTAGE_API_KEY"],
        "ALPHA_VANTAGE_API_KEY_source": preflight["ALPHA_VANTAGE_API_KEY_SOURCE"],
        "environment": preflight,
        "companies": companies,
        "asml_long_history": asml_long_history,
        "provider_failures": provider_failures,
        "engine_blockers": engine_blockers,
        "environment_blockers": environment_blockers,
        "reopen_checks": reopen_checks,
        "idempotency_checks": idempotency_checks,
        "warnings": [
            "Real validation runner is separate from pytest and uses live providers only when configured.",
            "No artificial approvals are created for real companies; REVIEW_REQUIRED is expected.",
        ],
    }
    _write_outputs(audit, company_results, stage_results, history_rows)
    if decision == "GO - REAL COMPANY END-TO-END VALIDATION PASSED":
        _update_end_to_end_audit_go(audit)
    else:
        _update_end_to_end_audit_not_go(audit)
    return 0


def _load_runtime_environment() -> dict[str, Any]:
    keys = ("SEC_USER_AGENT", "ALPHA_VANTAGE_API_KEY")
    candidates = []
    for path in (ROOT / ".env", ROOT.parent / ".env"):
        if path not in candidates:
            candidates.append(path)
    found = find_dotenv(filename=".env", usecwd=True)
    if found:
        found_path = Path(found)
        if found_path not in candidates:
            candidates.append(found_path)

    dotenv_status = {
        str(path): {
            "exists": path.exists(),
            "keys": {
                key: {
                    "present": False,
                    "non_empty": False,
                }
                for key in keys
            },
        }
        for path in candidates
    }
    loaded_sources: dict[str, str] = {}
    for key in keys:
        process_value = os.getenv(key)
        if process_value is not None and process_value.strip():
            loaded_sources[key] = "PROCESS_ENV"
            continue
        if process_value is not None and not process_value.strip():
            os.environ.pop(key, None)
        loaded_sources[key] = "NOT_AVAILABLE"
        for path in candidates:
            if not path.exists():
                continue
            values = dotenv_values(path)
            present = key in values
            value = values.get(key)
            non_empty = value is not None and str(value).strip() != ""
            dotenv_status[str(path)]["keys"][key] = {"present": present, "non_empty": non_empty}
            if non_empty:
                os.environ[key] = str(value)
                loaded_sources[key] = "DOTENV"
                break
    return {
        "repo_root": str(ROOT),
        "current_working_directory": str(Path.cwd()),
        "expected_dotenv_path": str(ROOT / ".env"),
        "dotenv_path_found": any(item["exists"] for item in dotenv_status.values()),
        "dotenv_candidates": dotenv_status,
        "sources": loaded_sources,
        "process_after_load": {
            key: {"configured": bool(os.getenv(key)), "non_empty": bool(os.getenv(key) and os.getenv(key, "").strip())}
            for key in keys
        },
    }


def _environment_preflight(runtime_env: dict[str, Any]) -> dict[str, Any]:
    configured = {
        "SEC_USER_AGENT": bool(os.getenv("SEC_USER_AGENT")),
        "ALPHA_VANTAGE_API_KEY": bool(os.getenv("ALPHA_VANTAGE_API_KEY")),
        "STOOQ_QUOTE": True,
        "FRANKFURTER_FX": True,
        "OPEN_ER_FX": True,
    }
    blockers = []
    if not configured["SEC_USER_AGENT"]:
        blockers.append("ENVIRONMENT_BLOCKED: SEC_USER_AGENT missing")
    return {
        "configured": configured,
        "dotenv_path_found": runtime_env["dotenv_path_found"],
        "SEC_USER_AGENT_SOURCE": runtime_env["sources"].get("SEC_USER_AGENT", "NOT_AVAILABLE"),
        "ALPHA_VANTAGE_API_KEY_SOURCE": runtime_env["sources"].get("ALPHA_VANTAGE_API_KEY", "NOT_AVAILABLE"),
        "runtime_environment": runtime_env,
        "environment_blockers": blockers,
    }


def _run_company(
    session: Session,
    target: ValidationTarget,
    provider_failures: list[dict[str, Any]],
    engine_blockers: list[str],
) -> dict[str, Any]:
    company = get_or_create_company(
        session,
        name=target.name,
        ticker=target.ticker,
        currency=target.currency,
        country=target.country,
    )
    if target.alpha_symbol:
        upsert_provider_symbol(session, company, provider="alphavantage", purpose="fundamentals", symbol=target.alpha_symbol)
    analysis = create_analysis(session, company=company, as_of_date=ANALYSIS_AS_OF_DATE)

    financial_result = _sync_financials(session, analysis, provider_failures)
    _sync_estimates(session, analysis, target, provider_failures)
    first_state = refresh_local_analysis_stages(session, analysis)
    _sync_market(session, analysis, target, first_state, provider_failures)
    state = refresh_local_analysis_stages(session, analysis)
    second_state = refresh_local_analysis_stages(session, analysis)
    idempotency = {
        stage: {
            "first_snapshot": state.stages[stage].snapshot_id,
            "second_snapshot": second_state.stages[stage].snapshot_id,
            "idempotent": state.stages[stage].snapshot_id == second_state.stages[stage].snapshot_id,
        }
        for stage in state.stages
    }

    blockers = _company_blockers(state)
    if blockers:
        engine_blockers.extend(f"{target.ticker}: {item}" for item in blockers)

    history_rows = _history_coverage_rows(target.ticker, state)
    return {
        "company": {
            "analysis_id": analysis.id,
            "analysis_as_of_date": analysis.as_of_date.isoformat(),
            "financial_source": financial_result.selected_source,
            "financial_attempts": [asdict(item) for item in financial_result.attempts],
            "stage_statuses": {stage: item.status for stage, item in state.stages.items()},
            "history_years": list(state.history_years),
            "listing": _listing_context(state),
        },
        "company_row": _company_row(target.ticker, analysis.id, financial_result, state, blockers),
        "stage_rows": _stage_rows(target.ticker, state),
        "history_rows": history_rows,
        "idempotency": idempotency,
    }


def _sync_financials(session: Session, analysis, provider_failures: list[dict[str, Any]]) -> FinancialSourceResult:
    try:
        sec = SECCompanyFactsProvider()
        alpha = AlphaVantageProvider() if os.getenv("ALPHA_VANTAGE_API_KEY") else None
        return sync_best_available_financials(
            session,
            analysis,
            sec_provider=sec,
            alpha_provider=alpha,
            allow_alpha_fallback=alpha is not None,
            esef_filing_limit=12,
        )
    except Exception as exc:
        provider_failures.append(_failure(analysis.company.ticker, "financial_import", exc))
        return FinancialSourceResult(None, 0, (), None)


def _sync_estimates(session: Session, analysis, target: ValidationTarget, provider_failures: list[dict[str, Any]]) -> None:
    if not os.getenv("ALPHA_VANTAGE_API_KEY") or not target.alpha_symbol:
        return
    try:
        sync_alphavantage_estimates(session, analysis, AlphaVantageProvider(), symbol=target.alpha_symbol)
    except Exception as exc:
        provider_failures.append(_failure(target.ticker, "estimates", exc))


def _sync_market(session: Session, analysis, target: ValidationTarget, state, provider_failures: list[dict[str, Any]]) -> None:
    try:
        net_debt = _latest_net_debt(state)
        quote = _quote(target)
        cik_row = get_provider_symbol(session, analysis.company, provider="sec", purpose="cik")
        if cik_row is None:
            raise MarketProviderError("No SEC CIK available for share data after financial import.")
        shares = SECShareDataProvider().latest_share_data(cik_row.symbol, ticker=target.ticker, as_of_date=analysis.as_of_date)
        listing = ListingData(
            ticker=target.ticker,
            exchange=target.exchange,
            trading_currency=target.trading_currency,
            security_type=target.security_type,
            primary_listing=True,
            adr_ratio=Decimal(target.adr_ratio) if target.adr_ratio else None,
            underlying_share_ratio=Decimal(target.underlying_share_ratio) if target.underlying_share_ratio else None,
            provider="phase8a_validation_target",
        )
        if target.security_type.upper() in {"ADR", "ADS"}:
            shares = NormalizedShareData(
                ticker=shares.ticker,
                shares_outstanding=shares.shares_outstanding,
                diluted_weighted_average_shares=shares.diluted_weighted_average_shares,
                basic_weighted_average_shares=shares.basic_weighted_average_shares,
                fiscal_year=shares.fiscal_year,
                share_date=shares.share_date,
                filing_date=shares.filing_date,
                provider=shares.provider,
                source=shares.source,
                source_url=shares.source_url,
                provider_field=shares.provider_field,
                unit=shares.unit,
                provenance=shares.provenance,
                share_basis="ORDINARY_SHARES",
            )
        fx = _fx(net_debt.currency if net_debt else analysis.company.currency, target.trading_currency, quote.price_date or analysis.as_of_date)
        snapshot = MarketDataSnapshot(
            company=analysis.company.name,
            analysis_as_of_date=analysis.as_of_date,
            listing=listing,
            quote=quote,
            share_data=shares,
            financial_statement_currency=analysis.company.currency,
            net_debt=net_debt,
            fx_rate=fx,
        )
        metrics = derive_market_metrics(snapshot)
        inputs_hash = "|".join(item.inputs_hash for item in metrics)
        persist_market_snapshot(session, analysis, snapshot, inputs_hash=inputs_hash)
    except Exception as exc:
        provider_failures.append(_failure(target.ticker, "market_data", exc))


def _quote(target: ValidationTarget):
    try:
        return StooqQuoteProvider().latest_quote(
            target.quote_symbol,
            ticker=target.ticker,
            exchange=target.exchange,
            currency=target.trading_currency,
            security_type=target.security_type,
        )
    except Exception:
        if not os.getenv("ALPHA_VANTAGE_API_KEY") or not target.alpha_symbol:
            raise
        return AlphaVantageQuoteProvider().latest_quote(
            target.alpha_symbol,
            ticker=target.ticker,
            exchange=target.exchange,
            currency=target.trading_currency,
            security_type=target.security_type,
        )


def _fx(from_currency: str | None, to_currency: str, fx_date: date) -> FXRate | None:
    if not from_currency or from_currency.upper() == to_currency.upper():
        return None
    try:
        return FrankfurterFXProvider().rate(from_currency, to_currency, fx_date)
    except Exception:
        return OpenExchangeRateFXProvider().latest_rate(from_currency, to_currency)


def _latest_net_debt(state) -> NetDebtInput | None:
    results = state.stages["CALCULATION"].payload.get("results", ())
    net_debt_rows = [
        item for item in results
        if item.get("metric_id") == "net_debt" and item.get("status") == "AVAILABLE" and item.get("value") is not None
    ]
    if not net_debt_rows:
        return None
    latest = sorted(net_debt_rows, key=lambda item: int(item["fiscal_year"]))[-1]
    currency = None
    for fact in state.stages["CALCULATION"].payload.get("base_facts", {}).get(str(latest["fiscal_year"]), []):
        if fact.get("currency"):
            currency = fact["currency"]
            break
    return NetDebtInput(
        fiscal_year=int(latest["fiscal_year"]),
        value=Decimal(str(latest["value"])),
        currency=currency,
        source="calculation_stage_snapshot",
        inputs_hash=latest.get("inputs_hash"),
    )


def _company_blockers(state) -> list[str]:
    blockers = []
    for stage in ("FINANCIAL_DATA", "CALCULATION", "HISTORICAL_ANALYSIS", "BUSINESS_QUALITY", "MARKET_DATA"):
        if state.stages[stage].status != "READY":
            blockers.append(f"{stage}:{state.stages[stage].status}")
    if state.stages["VALUATION"].status not in {"READY_FOR_PREVIEW", "READY"}:
        blockers.append(f"VALUATION:{state.stages['VALUATION'].status}")
    return blockers


def _company_row(ticker: str, analysis_id: int, financial: FinancialSourceResult, state, blockers: list[str]) -> dict[str, Any]:
    quality = state.stages["BUSINESS_QUALITY"].payload.get("result", {})
    market = state.stages["MARKET_DATA"].payload
    assumptions = state.stages["ASSUMPTIONS"].payload
    valuation = state.stages["VALUATION"].payload
    preview = valuation.get("preview", {})
    return {
        "ticker": ticker,
        "analysis_id": analysis_id,
        "analysis_as_of_date": state.as_of_date,
        "financial_status": state.stages["FINANCIAL_DATA"].status,
        "financial_source": financial.selected_source or "",
        "financial_years": " ".join(str(year) for year in state.stages["FINANCIAL_DATA"].payload.get("years", ())),
        "calculation_status": state.stages["CALCULATION"].status,
        "calculation_years": " ".join(str(year) for year in state.stages["CALCULATION"].payload.get("years", ())),
        "historical_status": state.stages["HISTORICAL_ANALYSIS"].status,
        "history_years": " ".join(str(year) for year in state.history_years),
        "quality_status": state.stages["BUSINESS_QUALITY"].status,
        "quality_score": quality.get("overall_score"),
        "quality_assessment": quality.get("assessment"),
        "market_status": state.stages["MARKET_DATA"].status,
        "market_price": market.get("price"),
        "price_date": market.get("price_date"),
        "market_cap": market.get("market_cap"),
        "enterprise_value": market.get("enterprise_value"),
        "trading_currency": market.get("trading_currency"),
        "financial_currency": market.get("payload", {}).get("financial_statement_currency"),
        "assumption_status": state.stages["ASSUMPTIONS"].status,
        "assumption_confidence": assumptions.get("assumption_set", {}).get("confidence"),
        "assumption_warnings": "; ".join(assumptions.get("assumption_set", {}).get("warnings", ())),
        "valuation_status": state.stages["VALUATION"].status,
        "bear_fair_value": preview.get("bear", {}).get("fair_value_per_unit"),
        "base_fair_value": preview.get("base", {}).get("fair_value_per_unit"),
        "bull_fair_value": preview.get("bull", {}).get("fair_value_per_unit"),
        "market_snapshot_id": state.market_snapshot_id or "",
        "valuation_mode": valuation.get("mode"),
        "overall_validation_status": "PASS" if not blockers else "BLOCKED",
        "blockers": "; ".join(blockers),
    }


def _stage_rows(ticker: str, state) -> list[dict[str, Any]]:
    return [
        {
            "ticker": ticker,
            "stage": stage,
            "status": item.status,
            "snapshot_id": item.snapshot_id or "",
            "engine_version": item.version or "",
            "inputs_hash": item.inputs_hash or "",
            "warnings": "; ".join(item.warnings),
            "blockers": "; ".join(item.blockers),
        }
        for stage, item in state.stages.items()
    ]


def _history_coverage_rows(ticker: str, state) -> list[dict[str, Any]]:
    rows_by_metric: dict[str, dict[str, Any]] = {}
    base_years: dict[str, set[int]] = {}
    for facts in state.stages["CALCULATION"].payload.get("base_facts", {}).values():
        for fact in facts:
            if fact.get("value") is not None:
                base_years.setdefault(fact["metric"], set()).add(int(fact["fiscal_year"]))
    for metric, years_set in base_years.items():
        rows_by_metric[metric] = _coverage_row(ticker, metric, sorted(years_set))

    series = state.stages["HISTORICAL_ANALYSIS"].payload.get("series", {})
    for metric, points in series.items():
        years = sorted(int(item["fiscal_year"]) for item in points if item.get("status") == "AVAILABLE" and item.get("value") is not None)
        rows_by_metric[metric] = _coverage_row(ticker, metric, years)
    return [rows_by_metric[key] for key in sorted(rows_by_metric)]


def _coverage_row(ticker: str, metric: str, years: list[int]) -> dict[str, Any]:
    missing = sorted(set(range(min(years), max(years) + 1)) - set(years)) if years else []
    return {
        "ticker": ticker,
        "metric": metric,
        "available_fiscal_years": " ".join(str(year) for year in years),
        "year_count": len(years),
        "earliest_year": min(years) if years else "",
        "latest_year": max(years) if years else "",
        "missing_years": " ".join(str(year) for year in missing),
        "status": "AVAILABLE" if years else "UNAVAILABLE",
    }


def _listing_context(state) -> dict[str, Any]:
    payload = state.stages["MARKET_DATA"].payload.get("payload", {})
    listing = payload.get("listing", {})
    shares = payload.get("shares", {})
    return {
        "ticker": listing.get("ticker"),
        "exchange": listing.get("exchange"),
        "security_type": listing.get("security_type"),
        "trading_currency": listing.get("trading_currency"),
        "financial_currency": payload.get("financial_statement_currency"),
        "adr_ratio": listing.get("adr_ratio"),
        "underlying_share_ratio": listing.get("underlying_share_ratio"),
        "share_basis": shares.get("share_basis"),
    }


def _asml_long_history(history_rows: list[dict[str, Any]]) -> dict[str, Any]:
    required = {
        "revenue",
        "operating_income",
        "net_income",
        "operating_cash_flow",
        "capital_expenditures",
        "depreciation_amortization",
        "free_cash_flow",
    }
    core = {
        row["metric"]: row
        for row in history_rows
        if row["ticker"] == "ASML"
        and row["metric"] in required
    }
    missing_metrics = sorted(required - set(core))
    counts = [int(core.get(metric, {}).get("year_count", 0)) for metric in required]
    min_count = min(counts) if counts else 0
    status = "PASS_10Y" if min_count >= 10 else "PARTIAL_PASS_5PLUS" if min_count >= 5 else "FAIL_LONG_HISTORY_PIPELINE"
    return {
        "status": status,
        "metrics": core,
        "missing_required_metrics": missing_metrics,
        "minimum_core_year_count": min_count,
    }


def _decision(
    companies: dict[str, Any],
    provider_failures: list[dict[str, Any]],
    engine_blockers: list[str],
    asml_long_history: dict[str, Any],
) -> str:
    if provider_failures and len(companies) < len(TARGETS):
        return "VALIDATION INCONCLUSIVE - ENVIRONMENT / PROVIDER BLOCKED"
    if engine_blockers:
        return "NO-GO - REAL COMPANY END-TO-END VALIDATION"
    if asml_long_history.get("status") == "FAIL_LONG_HISTORY_PIPELINE":
        return "NO-GO - REAL COMPANY END-TO-END VALIDATION"
    if set(companies) == {target.ticker for target in TARGETS}:
        return "GO - REAL COMPANY END-TO-END VALIDATION PASSED"
    return "VALIDATION INCONCLUSIVE - ENVIRONMENT / PROVIDER BLOCKED"


def _failure(ticker: str, stage: str, exc: Exception) -> dict[str, Any]:
    message = str(exc)
    lowered = message.lower()
    if "api key" in lowered or "user_agent" in lowered or "fehlt" in lowered:
        category = "ENVIRONMENT_BLOCKED"
    elif "rate" in lowered or "timeout" in lowered or "temporar" in lowered:
        category = "PROVIDER_TEMPORARY_FAILURE"
    elif "coverage" in lowered or "not found" in lowered or "keine" in lowered:
        category = "DATA_COVERAGE_BLOCKER"
    else:
        category = "ENGINE_ERROR"
    return {"ticker": ticker, "stage": stage, "category": category, "message": message}


def _write_outputs(audit: dict[str, Any], company_rows: list[dict[str, Any]], stage_rows: list[dict[str, Any]], history_rows: list[dict[str, Any]]) -> None:
    (DIAGNOSTICS / "PHASE_8A_REAL_COMPANY_VALIDATION.json").write_text(canonical_json(audit), encoding="utf-8")
    (DIAGNOSTICS / "PHASE_8A_REAL_COMPANY_VALIDATION.md").write_text(_markdown(audit), encoding="utf-8")
    _write_csv(DIAGNOSTICS / "phase8a_company_results.csv", company_rows, _company_fields())
    _write_csv(DIAGNOSTICS / "phase8a_stage_results.csv", stage_rows, ["ticker", "stage", "status", "snapshot_id", "engine_version", "inputs_hash", "warnings", "blockers"])
    _write_csv(DIAGNOSTICS / "phase8a_history_coverage.csv", history_rows, ["ticker", "metric", "available_fiscal_years", "year_count", "earliest_year", "latest_year", "missing_years", "status"])


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _company_fields() -> list[str]:
    return [
        "ticker", "analysis_id", "analysis_as_of_date", "financial_status", "financial_source", "financial_years",
        "calculation_status", "calculation_years", "historical_status", "history_years", "quality_status",
        "quality_score", "quality_assessment", "market_status", "market_price", "price_date", "market_cap",
        "enterprise_value", "trading_currency", "financial_currency", "assumption_status", "assumption_confidence",
        "assumption_warnings", "valuation_status", "bear_fair_value", "base_fair_value", "bull_fair_value",
        "market_snapshot_id", "valuation_mode", "overall_validation_status", "blockers",
    ]


def _markdown(audit: dict[str, Any]) -> str:
    companies = "\n".join(
        f"## {idx}. {ticker}\n```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```"
        for idx, (ticker, data) in enumerate(audit["companies"].items(), start=5)
    )
    failures = "\n".join(f"- {item['ticker']} {item['stage']}: {item['category']} - {item['message']}" for item in audit["provider_failures"]) or "- keine"
    blockers = "\n".join(f"- {item}" for item in audit["engine_blockers"]) or "- keine"
    env = json.dumps(audit["environment"], ensure_ascii=False, indent=2)
    return f"""# PHASE_8A_REAL_COMPANY_VALIDATION

## 1. Executive Summary
{audit["decision"]}

## 2. Environment Preflight
```json
{env}
```

## 3. Validation DB
`{audit["validation_db"]}`

## 4. Production Code Path
Diagnostics CSV input: `{audit["production_uses_diagnostics_csv"]}`

{companies}

## 6. ASML Long-History Proof
```json
{json.dumps(audit["asml_long_history"], ensure_ascii=False, indent=2)}
```

## 11. Financial Data Results
Siehe `diagnostics/phase8a_company_results.csv`.

## 12. Calculation Results
Siehe `diagnostics/phase8a_stage_results.csv`.

## 13. Historical Analysis Results
Siehe `diagnostics/phase8a_history_coverage.csv`.

## 14. Business Quality Results
Siehe Company- und Stage-CSV.

## 15. Market Data Results
Siehe Company- und Stage-CSV.

## 16. Assumption Results
Review Required ist fuer echte Unternehmen erlaubt und kein Engine-Fehler.

## 17. Valuation Preview Results
Siehe `bear_fair_value`, `base_fair_value`, `bull_fair_value` in Company-CSV.

## 18. Snapshot / Reopen / Immutability
```json
{json.dumps({"reopen_checks": audit["reopen_checks"], "idempotency_checks": audit["idempotency_checks"]}, ensure_ascii=False, indent=2)}
```

## 19. Test Suite
Normaler Testlauf bleibt separat: `pytest -q`.

## Provider Failures
{failures}

## Engine Blockers
{blockers}

## 20. GO / NO-GO
{audit["decision"]}
"""


def _update_end_to_end_audit_go(audit: dict[str, Any]) -> None:
    path = DIAGNOSTICS / "END_TO_END_WORKFLOW_AUDIT.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    data["decision"] = "GO - END-TO-END ANALYSIS WORKFLOW V1 PRODUCTION READY / FROZEN"
    data["blockers"] = []
    data["phase8a_validation"] = {
        "decision": audit["decision"],
        "validation_db": audit["validation_db"],
        "companies": list(audit["companies"]),
        "asml_long_history": audit["asml_long_history"],
    }
    path.write_text(canonical_json(data), encoding="utf-8")
    md = DIAGNOSTICS / "END_TO_END_WORKFLOW_AUDIT.md"
    if md.exists():
        text = md.read_text(encoding="utf-8")
        text = text.replace("NO-GO - END-TO-END ANALYSIS WORKFLOW V1", data["decision"])
        md.write_text(text, encoding="utf-8")


def _update_end_to_end_audit_not_go(audit: dict[str, Any]) -> None:
    path = DIAGNOSTICS / "END_TO_END_WORKFLOW_AUDIT.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    data["decision"] = "NO-GO - END-TO-END ANALYSIS WORKFLOW V1"
    data["blockers"] = audit.get("engine_blockers", ()) or audit.get("environment_blockers", ())
    data["phase8a_validation"] = {
        "decision": audit["decision"],
        "validation_db": audit["validation_db"],
        "companies": list(audit["companies"]),
        "asml_long_history": audit["asml_long_history"],
    }
    path.write_text(canonical_json(data), encoding="utf-8")
    md = DIAGNOSTICS / "END_TO_END_WORKFLOW_AUDIT.md"
    if md.exists():
        text = md.read_text(encoding="utf-8")
        text = text.replace(
            "GO - END-TO-END ANALYSIS WORKFLOW V1 PRODUCTION READY / FROZEN",
            "NO-GO - END-TO-END ANALYSIS WORKFLOW V1",
        )
        text = text.replace(
            "GO – END-TO-END ANALYSIS WORKFLOW V1 PRODUCTION READY / FROZEN",
            "NO-GO - END-TO-END ANALYSIS WORKFLOW V1",
        )
        md.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
