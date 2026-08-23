from __future__ import annotations

import gzip
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from stock_valuation.data.providers.base import ProviderResponseError
from stock_valuation.data.providers.esef import IFRS_TAG_MAP, POSITIVE_OUTFLOW_METRICS
from stock_valuation.data.providers.response_cache import DEFAULT_PROVIDER_CACHE_DIR, ProviderResponseCache
from stock_valuation.data.types import NormalizedFinancialFact


ESEF_API_BASE = "https://filings.xbrl.org/api"
ESEF_SITE_BASE = "https://filings.xbrl.org/"


class ESEFRegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class ESEFFiling:
    api_id: str
    lei: str
    entity_name: str | None
    country: str | None
    period_end: date | None
    processed: str | None
    json_url: str | None
    package_url: str | None
    report_url: str | None
    viewer_url: str | None


def _date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _decimal(value: Any) -> Decimal | None:
    if value in (None, "", "-", "—"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _statement_for(metric: str) -> str:
    if metric in {
        "operating_cash_flow",
        "capital_expenditures",
        "intangible_purchases",
        "depreciation_amortization",
        "dividends_paid",
    }:
        return "cash_flow"
    if metric in {
        "total_assets",
        "current_assets",
        "cash_and_equivalents",
        "accounts_receivable",
        "inventory",
        "ppe_net",
        "goodwill",
        "total_liabilities",
        "current_liabilities",
        "accounts_payable",
        "short_term_debt",
        "long_term_debt",
        "shareholders_equity",
    }:
        return "balance_sheet"
    return "income_statement"


def _period_info(value: str) -> tuple[date | None, bool]:
    """Return economic period end and whether the period is an annual duration."""
    raw = value.strip()
    if not raw:
        return None, False
    if "/" not in raw:
        return _date(raw), False
    start_raw, end_raw = raw.split("/", 1)
    start = _date(start_raw)
    exclusive_end = _date(end_raw)
    if start is None or exclusive_end is None:
        return None, False
    economic_end = exclusive_end - timedelta(days=1)
    days = (exclusive_end - start).days
    return economic_end, 300 <= days <= 430


def normalize_esef_xbrl_json(
    payload: dict[str, Any],
    *,
    source_note: str | None = None,
) -> list[NormalizedFinancialFact]:
    """Normalize standard IFRS facts from an xBRL-JSON report.

    Company extension concepts are deliberately not guessed. They remain a later semantic-review
    concern; this automatic path only accepts standard ``ifrs-full`` concepts in IFRS_TAG_MAP.
    """
    facts_root = payload.get("facts") or {}
    if not isinstance(facts_root, dict):
        return []

    tag_to_metric = {
        tag.casefold(): metric
        for metric, tags in IFRS_TAG_MAP.items()
        for tag in tags
    }
    retrieved = datetime.now(timezone.utc)
    selected: dict[tuple[str, date], NormalizedFinancialFact] = {}

    for fact_payload in facts_root.values():
        if not isinstance(fact_payload, dict):
            continue
        dimensions = fact_payload.get("dimensions") or {}
        if not isinstance(dimensions, dict):
            continue
        concept = str(dimensions.get("concept") or "").strip()
        metric = tag_to_metric.get(concept.casefold())
        if metric is None:
            continue

        # Main consolidated facts only. Additional taxonomy dimensions usually indicate a segment,
        # class or other disaggregation and must not silently replace the group total.
        allowed_dimensions = {"concept", "entity", "period", "unit", "language", "noteId"}
        if any(key not in allowed_dimensions for key in dimensions):
            continue

        period_end, annual_duration = _period_info(str(dimensions.get("period") or ""))
        if period_end is None:
            continue
        statement = _statement_for(metric)
        if statement != "balance_sheet" and not annual_duration:
            continue

        provider_value = _decimal(fact_payload.get("value"))
        if provider_value is None:
            continue
        economic_value = abs(provider_value) if metric in POSITIVE_OUTFLOW_METRICS else provider_value

        unit = str(dimensions.get("unit") or "").strip()
        currency = unit.split(":", 1)[-1].upper() if unit else None
        if currency and ("/" in currency or "PER" in currency):
            continue

        fact = NormalizedFinancialFact(
            statement=statement,
            metric=metric,
            period_end=period_end,
            period_type="FY",
            value=economic_value,
            provider_value=provider_value,
            currency=currency,
            unit="currency",
            provider="esef_xbrl_json",
            provider_field=concept,
            retrieved_at=retrieved,
            note=source_note,
        )
        selected.setdefault((metric, period_end), fact)

    return sorted(selected.values(), key=lambda row: (row.period_end, row.metric))


class ESEFRegistryProvider:
    """Public filings.xbrl.org discovery/download adapter keyed by LEI."""

    def __init__(self, timeout: int = 45, *, use_cache: bool = True) -> None:
        self.timeout = timeout
        self.use_cache = use_cache
        self.cache = ProviderResponseCache("esef_registry")
        self.binary_cache_root = DEFAULT_PROVIDER_CACHE_DIR / "esef_registry_files"
        self.cache_hits = 0
        self.network_requests = 0

    def _get_json(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.use_cache:
            cached = self.cache.get(endpoint, params)
            if cached is not None:
                self.cache_hits += 1
                return cached
        try:
            response = requests.get(
                f"{ESEF_API_BASE}/{endpoint.lstrip('/')}",
                params=params,
                headers={"Accept": "application/vnd.api+json"},
                timeout=self.timeout,
            )
            self.network_requests += 1
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise ESEFRegistryError(f"ESEF-Registry-Abruf fehlgeschlagen: {exc}") from exc
        except ValueError as exc:
            raise ProviderResponseError("filings.xbrl.org lieferte kein gültiges JSON.") from exc
        if not isinstance(payload, dict):
            raise ProviderResponseError("filings.xbrl.org lieferte ein unerwartetes Antwortformat.")
        if self.use_cache:
            self.cache.put(endpoint, params, payload)
        return payload

    @staticmethod
    def _included_entities(payload: dict[str, Any]) -> dict[str, tuple[str | None, str | None]]:
        result: dict[str, tuple[str | None, str | None]] = {}
        included = payload.get("included") or []
        if not isinstance(included, list):
            return result
        for row in included:
            if not isinstance(row, dict) or row.get("type") != "entity":
                continue
            attrs = row.get("attributes") or {}
            if not isinstance(attrs, dict):
                attrs = {}
            result[str(row.get("id") or "")] = (
                str(attrs.get("identifier") or "").strip().upper() or None,
                str(attrs.get("name") or "").strip() or None,
            )
        return result

    def list_filings(self, lei: str, *, limit: int = 10) -> list[ESEFFiling]:
        normalized_lei = lei.strip().upper()
        payload = self._get_json(
            "filings",
            {
                "filter[entity.identifier]": normalized_lei,
                "include": "entity",
                "sort": "-processed",
                "page[number]": 1,
                "page[size]": max(1, min(int(limit), 50)),
            },
        )
        entities = self._included_entities(payload)
        rows = payload.get("data") or []
        if not isinstance(rows, list):
            return []

        filings: list[ESEFFiling] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            attrs = row.get("attributes") or {}
            relationships = row.get("relationships") or {}
            if not isinstance(attrs, dict):
                attrs = {}
            entity_id = ""
            if isinstance(relationships, dict):
                entity_rel = relationships.get("entity") or {}
                if isinstance(entity_rel, dict):
                    entity_data = entity_rel.get("data") or {}
                    if isinstance(entity_data, dict):
                        entity_id = str(entity_data.get("id") or "")
            included_lei, entity_name = entities.get(entity_id, (None, None))
            filing_lei = included_lei or normalized_lei

            def absolute_url(key: str) -> str | None:
                value = str(attrs.get(key) or "").strip()
                return urljoin(ESEF_SITE_BASE, value) if value else None

            filings.append(
                ESEFFiling(
                    api_id=str(row.get("id") or ""),
                    lei=filing_lei,
                    entity_name=entity_name,
                    country=str(attrs.get("country") or "").strip().upper() or None,
                    period_end=_date(attrs.get("period_end")),
                    processed=str(attrs.get("processed") or "").strip() or None,
                    json_url=absolute_url("json_url"),
                    package_url=absolute_url("package_url"),
                    report_url=absolute_url("report_url"),
                    viewer_url=absolute_url("viewer_url"),
                )
            )
        return filings

    def _binary_cache_path(self, url: str) -> Path:
        import hashlib

        suffixes = Path(urlparse(url).path).suffixes
        suffix = "".join(suffixes[-2:]) if suffixes else ".bin"
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.binary_cache_root / f"{digest}{suffix}"

    def _download(self, url: str) -> bytes:
        path = self._binary_cache_path(url)
        if self.use_cache and path.exists():
            self.cache_hits += 1
            return path.read_bytes()
        try:
            response = requests.get(url, timeout=self.timeout)
            self.network_requests += 1
            response.raise_for_status()
            content = response.content
        except requests.RequestException as exc:
            raise ESEFRegistryError(f"ESEF-Datei konnte nicht geladen werden: {exc}") from exc
        if self.use_cache:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return content

    def get_xbrl_json(self, filing: ESEFFiling) -> dict[str, Any]:
        if not filing.json_url:
            raise ESEFRegistryError("Für dieses ESEF-Filing ist kein xBRL-JSON verfügbar.")
        content = self._download(filing.json_url)
        if filing.json_url.lower().endswith(".gz"):
            try:
                content = gzip.decompress(content)
            except OSError as exc:
                raise ESEFRegistryError("Das ESEF-xBRL-JSON konnte nicht entpackt werden.") from exc
        try:
            import json

            payload = json.loads(content.decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ESEFRegistryError("Das ESEF-xBRL-JSON ist ungültig.") from exc
        if not isinstance(payload, dict):
            raise ESEFRegistryError("Das ESEF-xBRL-JSON hat ein unerwartetes Format.")
        return payload

    def get_normalized_financials(self, lei: str, *, filing_limit: int = 8) -> list[NormalizedFinancialFact]:
        filings = self.list_filings(lei, limit=max(filing_limit * 2, filing_limit))
        # Newest processed filings come first. Keep one language/version per reporting period and
        # let newer filings supply comparative/restated values before older filings are considered.
        unique_periods: list[ESEFFiling] = []
        seen_periods: set[date] = set()
        for filing in filings:
            if filing.period_end is None or filing.period_end in seen_periods or not filing.json_url:
                continue
            seen_periods.add(filing.period_end)
            unique_periods.append(filing)
            if len(unique_periods) >= filing_limit:
                break

        selected: dict[tuple[str, date], NormalizedFinancialFact] = {}
        for filing in unique_periods:
            try:
                payload = self.get_xbrl_json(filing)
            except ESEFRegistryError:
                continue
            source_note = (
                f"filings.xbrl.org filing={filing.api_id}; LEI={filing.lei}; "
                f"period={filing.period_end}; json={filing.json_url}"
            )
            for fact in normalize_esef_xbrl_json(payload, source_note=source_note):
                selected.setdefault((fact.metric, fact.period_end), fact)

        return sorted(selected.values(), key=lambda row: (row.period_end, row.metric))
