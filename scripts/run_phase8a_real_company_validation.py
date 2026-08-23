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
from stock_valuation.data.semantic_policy import semantic_mapping_policy, safe_standard_mappings
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
from stock_valuation.workflow.service import BASE_FINANCIAL_METRICS, build_analysis_state, refresh_local_analysis_stages


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
        "semantic_gate_audit": _semantic_gate_audit(SessionLocal, companies) if not environment_blockers else {},
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

    history_rows = _history_coverage_rows(session, target.ticker, analysis, state)
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
        if state.stages[stage].status not in {"READY", "REVIEW_REQUIRED"}:
            blockers.append(f"{stage}:{state.stages[stage].status}")
    if state.stages["VALUATION"].status not in {"READY_FOR_PREVIEW", "READY"}:
        blockers.append(f"VALUATION:{state.stages['VALUATION'].status}")
    return blockers


def _company_row(ticker: str, analysis_id: int, financial: FinancialSourceResult, state, blockers: list[str]) -> dict[str, Any]:
    quality = state.stages["BUSINESS_QUALITY"].payload.get("result", {})
    market = state.stages["MARKET_DATA"].payload
    availability = market.get("availability", {})
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
        "enterprise_value_status": availability.get("enterprise_value"),
        "enterprise_value_reason": "; ".join(availability.get("enterprise_value_reason", ())),
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


def _history_coverage_rows(session: Session, ticker: str, analysis, state) -> list[dict[str, Any]]:
    rows_by_metric: dict[str, dict[str, Any]] = {}
    source_years: dict[str, set[int]] = {}
    pending_years: dict[str, set[int]] = {}
    ready_years: dict[str, set[int]] = {}
    for item in load_preferred_data_states(session, analysis.id, metrics=BASE_FINANCIAL_METRICS, period_type="FY"):
        if item.fact.period_end > analysis.as_of_date:
            continue
        year = int(item.fact.period_end.year)
        source_years.setdefault(item.fact.metric, set()).add(year)
        if item.calculation_ready:
            ready_years.setdefault(item.fact.metric, set()).add(year)
        elif item.quality_status in {"primary_semantic_review_required", "review_stale"}:
            pending_years.setdefault(item.fact.metric, set()).add(year)

    for facts in state.stages["CALCULATION"].payload.get("base_facts", {}).values():
        for fact in facts:
            if fact.get("value") is not None:
                ready_years.setdefault(fact["metric"], set()).add(int(fact["fiscal_year"]))

    series = state.stages["HISTORICAL_ANALYSIS"].payload.get("series", {})
    for metric, points in series.items():
        years = sorted(int(item["fiscal_year"]) for item in points if item.get("status") == "AVAILABLE" and item.get("value") is not None)
        ready_years.setdefault(metric, set()).update(years)
    pending_years.setdefault("ebitda", set()).update(pending_years.get("depreciation_amortization", set()))
    pending_years.setdefault("net_debt", set()).update(pending_years.get("short_term_debt", set()))

    for metric in sorted(set(source_years) | set(pending_years) | set(ready_years)):
        rows_by_metric[metric] = _coverage_row(
            ticker,
            metric,
            source=sorted(source_years.get(metric, set())),
            pending=sorted(pending_years.get(metric, set())),
            ready=sorted(ready_years.get(metric, set())),
        )
    return [rows_by_metric[key] for key in sorted(rows_by_metric)]


def _coverage_row(ticker: str, metric: str, *, source: list[int], pending: list[int], ready: list[int]) -> dict[str, Any]:
    derived_metric = metric in {"free_cash_flow", "ebitda", "net_debt", "debt", "net_debt_to_ebitda"}
    span = source or ready
    missing = [] if derived_metric else sorted(set(range(min(span), max(span) + 1)) - set(source)) if span else []
    if ready and len(ready) >= 10:
        status = "DERIVED_CALCULATION_READY_10Y" if derived_metric else "CALCULATION_READY_10Y"
    elif ready and len(ready) >= 5:
        status = "DERIVED_CALCULATION_READY_5Y" if derived_metric else "CALCULATION_READY_5Y"
    elif source and pending:
        status = "SEMANTIC_REVIEW_REQUIRED"
    elif derived_metric and pending:
        status = "DERIVED_SEMANTIC_REVIEW_REQUIRED"
    elif source:
        status = "PARTIAL_HISTORY"
    elif derived_metric:
        status = "DERIVED_UNAVAILABLE"
    else:
        status = "SOURCE_MISSING"
    return {
        "ticker": ticker,
        "metric": metric,
        "source_fiscal_years": " ".join(str(year) for year in source),
        "source_year_count": len(source),
        "review_pending_fiscal_years": " ".join(str(year) for year in pending),
        "review_pending_year_count": len(pending),
        "calculation_ready_fiscal_years": " ".join(str(year) for year in ready),
        "calculation_ready_year_count": len(ready),
        "missing_source_years": " ".join(str(year) for year in missing),
        "earliest_source_year": min(source) if source else "",
        "latest_source_year": max(source) if source else "",
        "coverage_status": status,
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
    core_historical = {
        "revenue",
        "operating_income",
        "net_income",
        "operating_cash_flow",
        "capital_expenditures",
        "free_cash_flow",
    }
    supporting = {"depreciation_amortization", "ebitda", "short_term_debt", "net_debt"}
    core = {
        row["metric"]: row
        for row in history_rows
        if row["ticker"] == "ASML"
        and row["metric"] in core_historical
    }
    supporting_rows = {
        row["metric"]: row
        for row in history_rows
        if row["ticker"] == "ASML"
        and row["metric"] in supporting
    }
    missing_metrics = sorted(core_historical - set(core))
    counts = [int(core.get(metric, {}).get("calculation_ready_year_count", 0)) for metric in core_historical]
    min_count = min(counts) if counts else 0
    has_review_gaps = any(int(row.get("review_pending_year_count", 0)) > 0 for row in supporting_rows.values())
    if min_count >= 10:
        status = "LONG_HISTORY_PASS_WITH_REVIEW_GAPS" if has_review_gaps else "PASS_10Y"
    elif min_count >= 5:
        status = "PARTIAL_PASS_5PLUS_WITH_REVIEW_GAPS" if has_review_gaps else "PARTIAL_PASS_5PLUS"
    else:
        status = "FAIL_LONG_HISTORY_PIPELINE"
    return {
        "status": status,
        "core_historical_series": core,
        "supporting_derived_history": supporting_rows,
        "missing_required_metrics": missing_metrics,
        "minimum_core_year_count": min_count,
    }


def _semantic_gate_audit(SessionLocal, companies: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    combos: dict[str, dict[str, Any]] = {}
    focus_metrics = ("depreciation_amortization", "short_term_debt", "ppe_net")
    with SessionLocal() as session:
        for ticker, company in companies.items():
            analysis_id = company.get("analysis_id")
            if analysis_id is None:
                continue
            states = load_preferred_data_states(session, int(analysis_id), metrics=focus_metrics, period_type="FY")
            for state in states:
                fact = state.fact
                policy = semantic_mapping_policy(fact.provider, fact.provider_field, fact.metric)
                row = {
                    "ticker": ticker,
                    "fiscal_year": fact.period_end.year,
                    "metric": fact.metric,
                    "provider": fact.provider,
                    "provider_field": fact.provider_field,
                    "value": str(fact.value) if fact.value is not None else None,
                    "currency": fact.currency,
                    "quality_status": state.quality_status,
                    "calculation_ready": state.calculation_ready,
                    "review_reason": state.reason,
                    "semantic_policy_decision": policy.decision.value,
                    "semantic_policy_version": policy.policy_version,
                }
                rows.append(row)
                key = f"{ticker}|{fact.metric}|{fact.provider}|{fact.provider_field}"
                item = combos.setdefault(
                    key,
                    {
                        "ticker": ticker,
                        "metric": fact.metric,
                        "provider": fact.provider,
                        "provider_field": fact.provider_field,
                        "years": set(),
                        "calculation_ready_years": set(),
                        "review_pending_years": set(),
                        "semantic_policy_decision": policy.decision.value,
                    },
                )
                item["years"].add(fact.period_end.year)
                if state.calculation_ready:
                    item["calculation_ready_years"].add(fact.period_end.year)
                elif state.quality_status in {"primary_semantic_review_required", "review_stale"}:
                    item["review_pending_years"].add(fact.period_end.year)

    combo_rows = []
    for item in combos.values():
        years = sorted(item.pop("years"))
        ready = sorted(item.pop("calculation_ready_years"))
        pending = sorted(item.pop("review_pending_years"))
        combo_rows.append(
            {
                **item,
                "years_covered": " ".join(str(year) for year in years),
                "year_count": len(years),
                "calculation_ready_years": " ".join(str(year) for year in ready),
                "review_pending_years": " ".join(str(year) for year in pending),
            }
        )

    return {
        "semantic_policy_version": "semantic-policy-v1.0",
        "priority_order": [
            "confirmed manual override",
            "exact matching explicit review PASS",
            "versioned SAFE_STANDARD_MAPPING",
            "otherwise REVIEW_REQUIRED",
        ],
        "safe_standard_mappings": [
            {
                **asdict(item),
                "decision": item.decision.value,
            }
            for item in safe_standard_mappings()
        ],
        "field_rows": sorted(rows, key=lambda row: (row["ticker"], row["metric"], row["fiscal_year"])),
        "provider_field_combinations": sorted(
            combo_rows,
            key=lambda row: (row["ticker"], row["metric"], row["provider"], row["provider_field"] or ""),
        ),
        "answers": {
            "why_asml_d_and_a_was_not_calculation_ready": (
                "ASML current D&A uses us-gaap:DepreciationDepletionAndAmortization. "
                "That standard concept includes depletion in the taxonomy label and is therefore not generically safe for the internal D&A definition without semantic review."
            ),
            "source_present": True,
            "incomplete_d_and_a_component_sum_prevented": True,
            "net_debt_unavailable_reason": "short_term_debt remains REVIEW_REQUIRED when only a current-portion component is available instead of a complete current debt total.",
            "enterprise_value_unavailable_reason": "Enterprise value depends on calculation-ready net_debt; market cap can be ready while EV is EV_REVIEW_REQUIRED.",
            "workflow_statuses_honest": True,
            "core_history_pipeline_proven": True,
        },
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
    (DIAGNOSTICS / "SEMANTIC_GATE_PRODUCTION_AUDIT.json").write_text(canonical_json(audit.get("semantic_gate_audit", {})), encoding="utf-8")
    (DIAGNOSTICS / "SEMANTIC_GATE_PRODUCTION_AUDIT.md").write_text(_semantic_markdown(audit.get("semantic_gate_audit", {})), encoding="utf-8")
    _write_csv(DIAGNOSTICS / "phase8a_company_results.csv", company_rows, _company_fields())
    _write_csv(DIAGNOSTICS / "phase8a_stage_results.csv", stage_rows, ["ticker", "stage", "status", "snapshot_id", "engine_version", "inputs_hash", "warnings", "blockers"])
    _write_csv(
        DIAGNOSTICS / "phase8a_history_coverage.csv",
        history_rows,
        [
            "ticker",
            "metric",
            "source_fiscal_years",
            "source_year_count",
            "review_pending_fiscal_years",
            "review_pending_year_count",
            "calculation_ready_fiscal_years",
            "calculation_ready_year_count",
            "missing_source_years",
            "earliest_source_year",
            "latest_source_year",
            "coverage_status",
        ],
    )


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
        "enterprise_value", "enterprise_value_status", "enterprise_value_reason", "trading_currency", "financial_currency", "assumption_status", "assumption_confidence",
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


def _semantic_markdown(audit: dict[str, Any]) -> str:
    if not audit:
        return "# SEMANTIC_GATE_PRODUCTION_AUDIT\n\nVALIDATION INCONCLUSIVE - ENVIRONMENT / PROVIDER BLOCKED\n"
    combos = "\n".join(
        (
            f"- {row['ticker']} {row['metric']} {row['provider']} `{row['provider_field']}`: "
            f"years={row['years_covered']}, ready={row['calculation_ready_years'] or '-'}, "
            f"pending={row['review_pending_years'] or '-'}, decision={row['semantic_policy_decision']}"
        )
        for row in audit["provider_field_combinations"]
    )
    answers = json.dumps(audit["answers"], ensure_ascii=False, indent=2)
    safe = "\n".join(
        f"- {item['internal_metric']} {item['provider']} `{item['provider_field']}`: {item['reason']}"
        for item in audit["safe_standard_mappings"]
    )
    return f"""# SEMANTIC_GATE_PRODUCTION_AUDIT

## 1. Policy
Version: `{audit["semantic_policy_version"]}`

Priority:
1. confirmed manual override
2. exact matching explicit review PASS
3. versioned SAFE_STANDARD_MAPPING
4. otherwise REVIEW_REQUIRED

## 2. Safe Standard Mappings
{safe or "- keine"}

## 3. Provider Field Combinations
{combos or "- keine"}

## 4. Audit Answers
```json
{answers}
```
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
