from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

import requests

from stock_valuation.data.providers.response_cache import ProviderResponseCache
from stock_valuation.data.providers.sec import ANNUAL_FORMS, CONCEPT_MAP, POSITIVE_OUTFLOW_METRICS
from stock_valuation.data.types import NormalizedFinancialFact


SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_SUBMISSION_FILE_URL = "https://data.sec.gov/submissions/{name}"
SEC_ARCHIVE_BASE = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/"

XBRLI_NS = "http://www.xbrl.org/2003/instance"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

BALANCE_METRICS = {
    "total_assets",
    "current_assets",
    "cash_and_equivalents",
    "short_term_investments",
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
}
CASH_FLOW_METRICS = {
    "operating_cash_flow",
    "capital_expenditures",
    "intangible_purchases",
    "depreciation_amortization",
    "dividends_paid",
}


class SECFilingFallbackError(RuntimeError):
    pass


@dataclass(frozen=True)
class SECFilingRef:
    accession_number: str
    filing_date: date
    report_date: date
    form: str
    primary_document: str | None = None

    @property
    def accession_compact(self) -> str:
        return self.accession_number.replace("-", "")


@dataclass(frozen=True)
class SECFilingGap:
    metric: str
    year: int
    status: str
    reason: str
    filing_url: str | None = None


@dataclass(frozen=True)
class SECFilingFallbackResult:
    facts: tuple[NormalizedFinancialFact, ...]
    unresolved: tuple[SECFilingGap, ...]
    filings_checked: int


@dataclass(frozen=True)
class _Context:
    period_end: date
    period_start: date | None
    has_dimensions: bool


@dataclass(frozen=True)
class _InstanceFact:
    taxonomy: str
    concept: str
    context_ref: str
    unit: str
    value: Decimal


def _date(raw: Any) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        return None


def _decimal(raw: Any) -> Decimal | None:
    if raw in (None, ""):
        return None
    text = str(raw).strip().replace(",", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _taxonomy_from_namespace(namespace: str) -> str | None:
    lowered = namespace.casefold()
    if "fasb.org/us-gaap" in lowered or "/us-gaap/" in lowered:
        return "us-gaap"
    if "ifrs" in lowered and ("taxonomy" in lowered or "ifrs-full" in lowered):
        return "ifrs-full"
    return None


def _split_tag(tag: str) -> tuple[str, str]:
    if tag.startswith("{") and "}" in tag:
        namespace, local = tag[1:].split("}", 1)
        return namespace, local
    return "", tag


def _statement_for_metric(metric: str) -> str:
    if metric in CASH_FLOW_METRICS:
        return "cash_flow"
    if metric in BALANCE_METRICS:
        return "balance_sheet"
    return "income_statement"


def _rows_from_columns(payload: dict[str, Any]) -> list[dict[str, Any]]:
    required = ["accessionNumber", "filingDate", "reportDate", "form"]
    if not all(isinstance(payload.get(key), list) for key in required):
        return []
    lengths = [len(payload[key]) for key in required]
    if not lengths:
        return []
    count = min(lengths)
    primary = payload.get("primaryDocument")
    rows: list[dict[str, Any]] = []
    for index in range(count):
        rows.append(
            {
                "accessionNumber": payload["accessionNumber"][index],
                "filingDate": payload["filingDate"][index],
                "reportDate": payload["reportDate"][index],
                "form": payload["form"][index],
                "primaryDocument": (
                    primary[index] if isinstance(primary, list) and index < len(primary) else None
                ),
            }
        )
    return rows


def _filing_refs(payload: dict[str, Any]) -> list[SECFilingRef]:
    recent = payload.get("filings", {}).get("recent") if isinstance(payload.get("filings"), dict) else None
    columns = recent if isinstance(recent, dict) else payload
    refs: list[SECFilingRef] = []
    for row in _rows_from_columns(columns if isinstance(columns, dict) else {}):
        form = str(row.get("form") or "")
        filing_date = _date(row.get("filingDate"))
        report_date = _date(row.get("reportDate"))
        accession = str(row.get("accessionNumber") or "").strip()
        if form not in ANNUAL_FORMS or filing_date is None or report_date is None or not accession:
            continue
        refs.append(
            SECFilingRef(
                accession_number=accession,
                filing_date=filing_date,
                report_date=report_date,
                form=form,
                primary_document=str(row.get("primaryDocument") or "").strip() or None,
            )
        )
    return refs


def _parse_contexts(root: ET.Element) -> dict[str, _Context]:
    result: dict[str, _Context] = {}
    for node in root.findall(f".//{{{XBRLI_NS}}}context"):
        context_id = node.attrib.get("id")
        if not context_id:
            continue
        segment = node.find(f".//{{{XBRLI_NS}}}segment")
        scenario = node.find(f".//{{{XBRLI_NS}}}scenario")
        has_dimensions = bool(
            (segment is not None and list(segment)) or (scenario is not None and list(scenario))
        )
        period = node.find(f"{{{XBRLI_NS}}}period")
        if period is None:
            continue
        instant = period.find(f"{{{XBRLI_NS}}}instant")
        end = period.find(f"{{{XBRLI_NS}}}endDate")
        start = period.find(f"{{{XBRLI_NS}}}startDate")
        period_end = _date(instant.text if instant is not None else end.text if end is not None else None)
        period_start = _date(start.text) if start is not None else None
        if period_end is None:
            continue
        result[context_id] = _Context(period_end, period_start, has_dimensions)
    return result


def _parse_units(root: ET.Element) -> dict[str, str]:
    result: dict[str, str] = {}
    for node in root.findall(f".//{{{XBRLI_NS}}}unit"):
        unit_id = node.attrib.get("id")
        measure = node.find(f"{{{XBRLI_NS}}}measure")
        if not unit_id or measure is None or not measure.text:
            continue
        result[unit_id] = measure.text.split(":")[-1].strip()
    return result


def parse_xbrl_instance(
    content: str,
    *,
    report_date: date,
    filing_date: date,
    form: str,
    source_url: str,
    expected_currency: str | None = None,
) -> list[NormalizedFinancialFact]:
    """Parse entity-wide annual standard concepts from one SEC XBRL instance document.

    The parser deliberately ignores company-extension concepts and dimensional contexts. It is a
    targeted fallback for gaps in Company Facts, not a replacement for a full XBRL processor.
    """
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise SECFilingFallbackError(f"SEC-XBRL-Instanz konnte nicht gelesen werden: {exc}") from exc

    _, root_local = _split_tag(root.tag)
    if root_local.casefold() != "xbrl":
        raise SECFilingFallbackError("SEC-Datei ist keine XBRL-Instanz.")

    contexts = _parse_contexts(root)
    units = _parse_units(root)
    reverse_map: dict[tuple[str, str], tuple[str, int]] = {}
    for metric, candidates in CONCEPT_MAP.items():
        for priority, pair in enumerate(candidates):
            reverse_map[pair] = (metric, priority)

    selected: dict[str, tuple[int, _InstanceFact]] = {}
    for node in list(root):
        namespace, concept = _split_tag(node.tag)
        taxonomy = _taxonomy_from_namespace(namespace)
        if taxonomy is None:
            continue
        mapped = reverse_map.get((taxonomy, concept))
        if mapped is None:
            continue
        metric, priority = mapped
        context_ref = str(node.attrib.get("contextRef") or "")
        unit_ref = str(node.attrib.get("unitRef") or "")
        context = contexts.get(context_ref)
        unit = units.get(unit_ref)
        if context is None or unit is None or context.has_dimensions:
            continue
        if context.period_end != report_date:
            continue
        if metric in BALANCE_METRICS:
            if context.period_start is not None:
                continue
        else:
            if context.period_start is None:
                continue
            duration_days = (context.period_end - context.period_start).days
            if duration_days < 300 or duration_days > 380:
                continue
        if expected_currency and unit.upper() != expected_currency.upper():
            continue
        if unit.upper() in {"SHARES", "PURE"} or "PER" in unit.upper():
            continue
        if node.attrib.get(f"{{{XSI_NS}}}nil", "false").casefold() == "true":
            continue
        value = _decimal(node.text)
        if value is None:
            continue
        candidate = _InstanceFact(taxonomy, concept, context_ref, unit, value)
        existing = selected.get(metric)
        if existing is None or priority < existing[0]:
            selected[metric] = (priority, candidate)

    retrieved = datetime.now(timezone.utc)
    output: list[NormalizedFinancialFact] = []
    for metric, (_, fact) in selected.items():
        economic_value = abs(fact.value) if metric in POSITIVE_OUTFLOW_METRICS else fact.value
        output.append(
            NormalizedFinancialFact(
                statement=_statement_for_metric(metric),
                metric=metric,
                period_end=report_date,
                period_type="FY",
                value=economic_value,
                provider_value=fact.value,
                currency=fact.unit,
                unit="currency",
                provider="sec_filing_xbrl",
                provider_field=f"{fact.taxonomy}:{fact.concept}",
                filing_date=filing_date,
                retrieved_at=retrieved,
                note=f"Original SEC filing fallback; form={form}",
                source_url=source_url,
            )
        )
    return sorted(output, key=lambda row: row.metric)


class SECFilingFallbackProvider:
    """Targeted original-filing fallback for gaps left by SEC Company Facts."""

    def __init__(
        self,
        user_agent: str | None = None,
        timeout: int = 30,
        *,
        use_cache: bool = True,
    ) -> None:
        self.user_agent = (user_agent or os.getenv("SEC_USER_AGENT") or "").strip()
        self.timeout = timeout
        self.use_cache = use_cache
        self.cache = ProviderResponseCache("sec_filing")
        self.cache_hits = 0
        self.network_requests = 0
        if not self.user_agent:
            raise ValueError("SEC_USER_AGENT fehlt für den Original-Filing-Fallback.")

    @property
    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"}

    def _get_json(self, url: str) -> dict[str, Any]:
        params = {"url": url}
        if self.use_cache:
            cached = self.cache.get("GET_JSON", params)
            if cached is not None:
                self.cache_hits += 1
                return cached
        try:
            response = requests.get(url, headers=self._headers, timeout=self.timeout)
            self.network_requests += 1
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise SECFilingFallbackError(f"SEC-Filing-Abruf fehlgeschlagen: {exc}") from exc
        if not isinstance(payload, dict):
            raise SECFilingFallbackError("SEC lieferte beim Filing-Abruf kein JSON-Objekt.")
        if self.use_cache:
            self.cache.put("GET_JSON", params, payload)
        return payload

    def _get_text(self, url: str) -> str:
        params = {"url": url}
        if self.use_cache:
            cached = self.cache.get_text("GET_TEXT", params)
            if cached is not None:
                self.cache_hits += 1
                return cached
        try:
            response = requests.get(url, headers=self._headers, timeout=self.timeout)
            self.network_requests += 1
            response.raise_for_status()
            text = response.text
        except requests.RequestException as exc:
            raise SECFilingFallbackError(f"SEC-Filing-Dokument konnte nicht geladen werden: {exc}") from exc
        if self.use_cache:
            self.cache.put_text("GET_TEXT", params, text)
        return text

    def list_annual_filings(self, cik: str, *, target_years: Iterable[int] | None = None) -> list[SECFilingRef]:
        normalized = str(cik).strip().replace("CIK", "").zfill(10)
        payload = self._get_json(SEC_SUBMISSIONS_URL.format(cik=normalized))
        refs = _filing_refs(payload)
        targets = set(target_years or [])

        filings = payload.get("filings") if isinstance(payload.get("filings"), dict) else {}
        extra_files = filings.get("files") if isinstance(filings, dict) else []
        if isinstance(extra_files, list):
            for item in extra_files:
                if not isinstance(item, dict) or not item.get("name"):
                    continue
                if targets:
                    filing_from = _date(item.get("filingFrom"))
                    filing_to = _date(item.get("filingTo"))
                    relevant_filing_years = {year for target in targets for year in (target, target + 1)}
                    if filing_from and filing_to and not any(
                        filing_from.year <= year <= filing_to.year for year in relevant_filing_years
                    ):
                        continue
                extra = self._get_json(SEC_SUBMISSION_FILE_URL.format(name=item["name"]))
                refs.extend(_filing_refs(extra))

        deduped = {ref.accession_number: ref for ref in refs}
        return sorted(deduped.values(), key=lambda ref: (ref.report_date, ref.filing_date))

    def find_filing(self, cik: str, year: int) -> SECFilingRef | None:
        candidates = [
            ref
            for ref in self.list_annual_filings(cik, target_years=[year])
            if ref.report_date.year == year
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda ref: (ref.filing_date, ref.form))[-1]

    def _archive_base(self, cik: str, filing: SECFilingRef) -> str:
        cik_number = str(int(str(cik).strip().replace("CIK", "")))
        return SEC_ARCHIVE_BASE.format(cik=cik_number, accession=filing.accession_compact)

    def _instance_document(self, cik: str, filing: SECFilingRef) -> tuple[str, str] | None:
        base = self._archive_base(cik, filing)
        index = self._get_json(base + "index.json")
        directory = index.get("directory") if isinstance(index, dict) else None
        items = directory.get("item") if isinstance(directory, dict) else None
        if not isinstance(items, list):
            return None
        names = [str(item.get("name") or "") for item in items if isinstance(item, dict)]
        excluded_suffixes = ("_cal.xml", "_def.xml", "_lab.xml", "_pre.xml")
        candidates = [name for name in names if name.casefold().endswith("_htm.xml")]
        candidates += [
            name
            for name in names
            if name.casefold().endswith(".xml")
            and name not in candidates
            and not name.casefold().endswith(excluded_suffixes)
            and name.casefold() not in {"filingsummary.xml"}
        ]
        for name in candidates:
            url = base + name
            try:
                text = self._get_text(url)
                root = ET.fromstring(text)
            except (SECFilingFallbackError, ET.ParseError):
                continue
            _, local = _split_tag(root.tag)
            if local.casefold() == "xbrl":
                return url, text
        return None

    def gap_facts(
        self,
        cik: str,
        base_facts: list[NormalizedFinancialFact],
        *,
        years: int = 10,
    ) -> SECFilingFallbackResult:
        usable = [fact for fact in base_facts if fact.value is not None and fact.period_type == "FY"]
        if not usable:
            return SECFilingFallbackResult((), (), 0)
        last_year = max(fact.period_end.year for fact in usable)
        first_year = last_year - max(1, int(years)) + 1
        metrics = {fact.metric for fact in usable}
        present = {(fact.metric, fact.period_end.year) for fact in usable}
        missing = {
            (metric, year)
            for metric in metrics
            for year in range(first_year, last_year + 1)
            if (metric, year) not in present
        }
        if not missing:
            return SECFilingFallbackResult((), (), 0)

        currencies = Counter(
            str(fact.currency).upper()
            for fact in usable
            if fact.currency and first_year <= fact.period_end.year <= last_year
        )
        expected_currency = currencies.most_common(1)[0][0] if currencies else None

        output: list[NormalizedFinancialFact] = []
        unresolved: list[SECFilingGap] = []
        filings_checked = 0
        for year in sorted({year for _, year in missing}):
            needed = {metric for metric, target_year in missing if target_year == year}
            filing = self.find_filing(cik, year)
            if filing is None:
                unresolved.extend(
                    SECFilingGap(metric, year, "no_filing", "Kein passendes SEC-Jahresfiling gefunden.")
                    for metric in sorted(needed)
                )
                continue
            instance = self._instance_document(cik, filing)
            filing_url = self._archive_base(cik, filing) + (filing.primary_document or "")
            if instance is None:
                unresolved.extend(
                    SECFilingGap(
                        metric,
                        year,
                        "no_xbrl_instance",
                        "Originalfiling gefunden, aber keine lesbare XBRL-Instanz im Archiv.",
                        filing_url,
                    )
                    for metric in sorted(needed)
                )
                continue
            instance_url, content = instance
            filings_checked += 1
            parsed = parse_xbrl_instance(
                content,
                report_date=filing.report_date,
                filing_date=filing.filing_date,
                form=filing.form,
                source_url=instance_url,
                expected_currency=expected_currency,
            )
            by_metric = {fact.metric: fact for fact in parsed}
            for metric in sorted(needed):
                fact = by_metric.get(metric)
                if fact is not None:
                    output.append(fact)
                else:
                    unresolved.append(
                        SECFilingGap(
                            metric,
                            year,
                            "semantic_review_required",
                            "Im Originalfiling wurde für dieses Feld kein erlaubter Standard-XBRL-Tag gefunden; Company-Extension oder Textzeile muss semantisch geprüft werden.",
                            filing_url,
                        )
                    )

        return SECFilingFallbackResult(tuple(output), tuple(unresolved), filings_checked)
