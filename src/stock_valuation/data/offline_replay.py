from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from stock_valuation.analyses.ai_review_service import (
    AIReviewError,
    build_chatgpt_review_package,
    import_chatgpt_review_result,
)
from stock_valuation.analyses.service import create_analysis
from stock_valuation.companies.provider_symbols import upsert_provider_symbol
from stock_valuation.companies.service import get_company_by_ticker, get_or_create_company
from stock_valuation.database.models import FinancialFactSnapshot


class OfflineReplayError(RuntimeError):
    """Raised when an exported ChatGPT review package cannot be replayed safely."""


@dataclass(frozen=True)
class ParsedReviewPackage:
    package_id: str
    company_name: str
    ticker: str
    isin: str | None
    exchange: str | None
    as_of_date: date
    revision: int
    years_requested: int
    facts: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class OfflineReplaySummary:
    company_id: int
    analysis_id: int
    ticker: str
    fact_count: int
    review_finding_count: int
    old_package_id: str
    new_package_id: str


def _decode(content: bytes | str) -> str:
    if isinstance(content, bytes):
        try:
            return content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise OfflineReplayError("Prüfpaket ist kein gültiges UTF-8.") from exc
    return content


def _identity_value(text: str, label: str) -> str:
    match = re.search(rf"^- {re.escape(label)}:\s*(.+?)\s*$", text, flags=re.MULTILINE)
    if not match:
        raise OfflineReplayError(f"Im Prüfpaket fehlt `{label}`.")
    return match.group(1).strip().strip("`")


def parse_review_package(content: bytes | str) -> ParsedReviewPackage:
    text = _decode(content)
    block = re.search(
        r"## Importierte Fakten\s*```json\s*(\[.*?\])\s*```",
        text,
        flags=re.DOTALL,
    )
    if not block:
        raise OfflineReplayError("Im Prüfpaket wurde der JSON-Block `Importierte Fakten` nicht gefunden.")
    try:
        facts_raw = json.loads(block.group(1))
    except json.JSONDecodeError as exc:
        raise OfflineReplayError("Der Faktenblock im Prüfpaket ist kein gültiges JSON.") from exc
    if not isinstance(facts_raw, list) or not facts_raw:
        raise OfflineReplayError("Das Prüfpaket enthält keine importierbaren Fakten.")

    package_id = _identity_value(text, "Package-ID")
    company_name = _identity_value(text, "Unternehmen")
    ticker = _identity_value(text, "Ticker").upper()
    isin_text = _identity_value(text, "ISIN")
    exchange_text = _identity_value(text, "Börse/Region")
    as_of_raw = _identity_value(text, "Analyse-Stichtag")
    revision_raw = _identity_value(text, "Revision")
    years_raw = _identity_value(text, "Zu prüfende Geschäftsjahre")

    try:
        as_of_date = date.fromisoformat(as_of_raw)
        revision = int(revision_raw.removeprefix("R"))
        years_requested = int(years_raw)
    except ValueError as exc:
        raise OfflineReplayError("Stichtag, Revision oder Jahresanzahl im Prüfpaket ist ungültig.") from exc

    return ParsedReviewPackage(
        package_id=package_id,
        company_name=company_name,
        ticker=ticker,
        isin=None if isin_text.lower() == "nicht hinterlegt" else isin_text,
        exchange=None if exchange_text.lower() == "nicht hinterlegt" else exchange_text,
        as_of_date=as_of_date,
        revision=revision,
        years_requested=years_requested,
        facts=tuple(facts_raw),
    )


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise OfflineReplayError(f"Ungültiger Zahlenwert im Prüfpaket: {value!r}") from exc


def _validate_result_against_package(parsed: ParsedReviewPackage, content: bytes | str) -> dict[str, Any]:
    text = _decode(content)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OfflineReplayError("Prüfergebnis ist kein gültiges JSON.") from exc
    if not isinstance(payload, dict):
        raise OfflineReplayError("Prüfergebnis muss ein JSON-Objekt sein.")
    if payload.get("package_id") != parsed.package_id:
        raise OfflineReplayError("Prüfpaket und Prüfergebnis haben unterschiedliche Package-IDs.")
    company = payload.get("company")
    if not isinstance(company, dict) or str(company.get("ticker") or "").upper() != parsed.ticker:
        raise OfflineReplayError("Ticker im Prüfergebnis passt nicht zum Prüfpaket.")
    if str(company.get("analysis_as_of_date") or "") != parsed.as_of_date.isoformat():
        raise OfflineReplayError("Analyse-Stichtag im Prüfergebnis passt nicht zum Prüfpaket.")
    if int(payload.get("years_requested") or 0) != parsed.years_requested:
        raise OfflineReplayError("Jahresanzahl im Prüfergebnis passt nicht zum Prüfpaket.")

    old_fact_ids = {int(row["fact_id"]) for row in parsed.facts if "fact_id" in row}
    findings = payload.get("findings")
    if not isinstance(findings, list):
        raise OfflineReplayError("Prüfergebnis enthält keine gültige `findings`-Liste.")
    finding_ids = {int(row.get("fact_id") or 0) for row in findings if isinstance(row, dict)}
    if finding_ids != old_fact_ids:
        raise OfflineReplayError(
            "Die Fact-IDs im Prüfergebnis entsprechen nicht vollständig dem exportierten Prüfpaket."
        )
    return payload


def replay_review_files(
    session: Session,
    package_content: bytes | str,
    result_content: bytes | str,
) -> OfflineReplaySummary:
    """Rebuild a development snapshot from an exported package and its review result.

    This is intentionally an offline/development path. It reconstructs only the facts contained in
    the review package (typically 2-5 years), not the complete historical Alpha Vantage dataset.
    Old database fact IDs are remapped to newly created rows and the result package is rewritten in
    memory to the new package identity before it is passed through the normal review importer.
    """
    parsed = parse_review_package(package_content)
    old_result = _validate_result_against_package(parsed, result_content)

    existing = get_company_by_ticker(session, parsed.ticker)
    if existing is not None:
        raise OfflineReplayError(
            f"{parsed.ticker} ist bereits gespeichert. Für einen sauberen Offline-Replay das bestehende Unternehmen zuerst löschen."
        )

    currencies = [str(row.get("currency") or "").strip().upper() for row in parsed.facts]
    currency = next((value for value in currencies if value), "USD")
    company = get_or_create_company(
        session,
        name=parsed.company_name,
        ticker=parsed.ticker,
        currency=currency,
        isin=parsed.isin,
        exchange=parsed.exchange,
        country=parsed.exchange,
    )
    upsert_provider_symbol(
        session,
        company,
        provider="alphavantage",
        purpose="fundamentals",
        symbol=parsed.ticker,
        currency=currency,
        note="Offline-Replay aus einem zuvor exportierten ChatGPT-Prüfpaket; kein API-Request.",
    )
    analysis = create_analysis(session, company=company, as_of_date=parsed.as_of_date)

    old_to_new: dict[int, int] = {}
    for row in parsed.facts:
        try:
            old_id = int(row["fact_id"])
            period_end = date.fromisoformat(str(row["period_end"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise OfflineReplayError("Ein Fakteneintrag enthält keine gültige Fact-ID oder Periode.") from exc
        value = _decimal(row.get("value"))
        fact = FinancialFactSnapshot(
            analysis_id=analysis.id,
            statement=str(row.get("statement") or ""),
            metric=str(row.get("metric") or ""),
            period_end=period_end,
            period_type="FY",
            value=value,
            provider_value=value,
            currency=str(row.get("currency") or "").strip().upper() or None,
            unit=str(row.get("unit") or "").strip() or None,
            provider=str(row.get("provider") or "").strip() or None,
            provider_field=str(row.get("provider_field") or "").strip() or None,
            source_type=str(row.get("source_type") or "").strip() or None,
            source_url=str(row.get("source_url") or "").strip() or None,
            is_cross_check_only=False,
            note="Offline-Replay aus exportiertem ChatGPT-Prüfpaket.",
        )
        session.add(fact)
        session.flush()
        old_to_new[old_id] = fact.id
    session.commit()

    new_package = build_chatgpt_review_package(
        session,
        analysis,
        years=parsed.years_requested,
    )
    transformed = deepcopy(old_result)
    transformed["package_id"] = new_package.package_id
    transformed["company"] = {
        "name": analysis.company.name,
        "ticker": analysis.company.ticker,
        "analysis_as_of_date": analysis.as_of_date.isoformat(),
        "revision": analysis.revision_number,
    }
    for finding in transformed["findings"]:
        finding["fact_id"] = old_to_new[int(finding["fact_id"])]

    try:
        run = import_chatgpt_review_result(
            session,
            analysis,
            json.dumps(transformed, ensure_ascii=False).encode("utf-8"),
        )
    except AIReviewError as exc:
        raise OfflineReplayError(f"Rekonstruierte Prüfergebnisse konnten nicht importiert werden: {exc}") from exc

    return OfflineReplaySummary(
        company_id=company.id,
        analysis_id=analysis.id,
        ticker=company.ticker,
        fact_count=len(parsed.facts),
        review_finding_count=len(run.findings),
        old_package_id=parsed.package_id,
        new_package_id=new_package.package_id,
    )
