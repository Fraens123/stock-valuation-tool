from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Iterable

from stock_valuation.data.providers.sec import CONCEPT_MAP, POSITIVE_OUTFLOW_METRICS
from stock_valuation.data.providers.sec_filing import (
    BALANCE_METRICS,
    CASH_FLOW_METRICS,
    SECFilingFallbackProvider,
    SECFilingGap,
    SECFilingRef,
    XBRLI_NS,
    XSI_NS,
)
from stock_valuation.data.types import NormalizedFinancialFact


LINK_NS = "http://www.xbrl.org/2003/linkbase"
XLINK_NS = "http://www.w3.org/1999/xlink"

_STOPWORDS = {"a", "an", "and", "by", "for", "from", "in", "of", "the", "to", "used"}
_SYNONYMS = {
    "activities": "activity",
    "activity": "activity",
    "borrowings": "borrowing",
    "borrowed": "borrowing",
    "dividends": "dividend",
    "flows": "flow",
    "operating": "operation",
    "operations": "operation",
    "paid": "payment",
    "payments": "payment",
    "paying": "payment",
    "provided": "provide",
    "provides": "provide",
    "receivables": "receivable",
    "securities": "security",
    "shareholders": "shareholder",
}

# These exclusions protect the three most error-prone semantic families. They do not assert that a
# remaining candidate is correct; they merely keep obviously different concepts out of the review
# queue. Every surviving company-extension candidate is still blocked until semantic PASS.
_FORBIDDEN_TOKENS: dict[str, set[str]] = {
    "dividends_paid": {"declared", "payable", "proposed", "received", "receivable"},
    "operating_cash_flow": {"financing", "investing"},
    "short_term_debt": {"lease", "payable", "trade"},
}


@dataclass(frozen=True)
class SECCompanyExtensionResult:
    facts: tuple[NormalizedFinancialFact, ...]
    unresolved: tuple[SECFilingGap, ...]
    filings_checked: int


@dataclass(frozen=True)
class _Context:
    period_end: object
    period_start: object | None
    has_dimensions: bool


@dataclass(frozen=True)
class _Candidate:
    namespace: str
    concept: str
    label: str | None
    unit: str
    value: Decimal
    score: float


def _split_tag(tag: str) -> tuple[str, str]:
    if tag.startswith("{") and "}" in tag:
        namespace, local = tag[1:].split("}", 1)
        return namespace, local
    return "", tag


def _date(raw):
    from datetime import date

    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        return None


def _decimal(raw) -> Decimal | None:
    if raw in (None, ""):
        return None
    text = str(raw).strip().replace(",", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


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
        period_end = _date(
            instant.text if instant is not None else end.text if end is not None else None
        )
        period_start = _date(start.text) if start is not None else None
        if period_end is not None:
            result[context_id] = _Context(period_end, period_start, has_dimensions)
    return result


def _parse_units(root: ET.Element) -> dict[str, str]:
    result: dict[str, str] = {}
    for node in root.findall(f".//{{{XBRLI_NS}}}unit"):
        unit_id = node.attrib.get("id")
        measure = node.find(f"{{{XBRLI_NS}}}measure")
        if unit_id and measure is not None and measure.text:
            result[unit_id] = measure.text.split(":")[-1].strip()
    return result


def _is_company_namespace(namespace: str) -> bool:
    lowered = namespace.casefold()
    if not lowered:
        return False
    blocked = (
        "xbrl.org",
        "xbrl.sec.gov",
        "fasb.org",
        "ifrs.org",
        "w3.org",
    )
    return not any(marker in lowered for marker in blocked)


def _semantic_tokens(value: str) -> set[str]:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value or "")
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).casefold()
    result: set[str] = set()
    for token in text.split():
        if token in _STOPWORDS:
            continue
        token = _SYNONYMS.get(token, token)
        if token.endswith("ies") and len(token) > 4:
            token = token[:-3] + "y"
        elif token.endswith("s") and len(token) > 4 and token not in {"assets"}:
            token = token[:-1]
        result.add(token)
    return result


def _metric_aliases(metric: str) -> list[set[str]]:
    aliases = [_semantic_tokens(metric)]
    for _taxonomy, concept in CONCEPT_MAP.get(metric, ()):
        aliases.append(_semantic_tokens(concept))
    return [tokens for tokens in aliases if tokens]


def _score(metric: str, concept: str, label: str | None) -> float:
    candidate_tokens = _semantic_tokens(" ".join(part for part in (concept, label or "") if part))
    if not candidate_tokens:
        return 0.0
    if candidate_tokens & _FORBIDDEN_TOKENS.get(metric, set()):
        return 0.0

    best = 0.0
    for alias_tokens in _metric_aliases(metric):
        overlap = len(candidate_tokens & alias_tokens)
        if overlap == 0:
            continue
        denominator = min(len(candidate_tokens), len(alias_tokens))
        if denominator <= 0:
            continue
        score = overlap / denominator
        # Single-word matches are only useful when the internal/standard concept is itself very
        # distinctive. Otherwise two matching semantic tokens are required.
        if overlap == 1 and min(len(candidate_tokens), len(alias_tokens)) > 1:
            score *= 0.55
        best = max(best, score)
    return best


def parse_label_linkbase(content: str) -> dict[str, str]:
    """Return human-readable labels keyed by linkbase concept fragments.

    Linkbases are optional for this fallback. If a filing does not expose a usable label linkbase,
    the extension concept name remains available for candidate matching and review.
    """
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return {}

    locators: dict[str, str] = {}
    labels: dict[str, str] = {}
    arcs: list[tuple[str, str]] = []
    xlink_label = f"{{{XLINK_NS}}}label"
    xlink_href = f"{{{XLINK_NS}}}href"
    xlink_from = f"{{{XLINK_NS}}}from"
    xlink_to = f"{{{XLINK_NS}}}to"

    for node in root.findall(f".//{{{LINK_NS}}}loc"):
        label_id = node.attrib.get(xlink_label)
        href = node.attrib.get(xlink_href)
        if label_id and href and "#" in href:
            locators[label_id] = href.rsplit("#", 1)[-1]
    for node in root.findall(f".//{{{LINK_NS}}}label"):
        label_id = node.attrib.get(xlink_label)
        text = " ".join("".join(node.itertext()).split())
        if label_id and text:
            labels[label_id] = text
    for node in root.findall(f".//{{{LINK_NS}}}labelArc"):
        source = node.attrib.get(xlink_from)
        target = node.attrib.get(xlink_to)
        if source and target:
            arcs.append((source, target))

    result: dict[str, str] = {}
    for source, target in arcs:
        fragment = locators.get(source)
        text = labels.get(target)
        if fragment and text:
            result.setdefault(fragment, text)
    return result


def _label_for_concept(labels: dict[str, str], concept: str) -> str | None:
    lowered = concept.casefold()
    exact = labels.get(concept)
    if exact:
        return exact
    for fragment, label in labels.items():
        candidate = fragment.casefold()
        if candidate == lowered or candidate.endswith("_" + lowered) or candidate.endswith(lowered):
            return label
    return None


def _candidate_facts_from_instance(
    content: str,
    *,
    target_metrics: set[str],
    report_date,
    filing_date,
    form: str,
    source_url: str,
    expected_currency: str | None,
    labels: dict[str, str],
) -> dict[str, NormalizedFinancialFact]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return {}
    contexts = _parse_contexts(root)
    units = _parse_units(root)
    raw_candidates: list[tuple[str, str, str | None, str, Decimal, str]] = []

    for node in list(root):
        namespace, concept = _split_tag(node.tag)
        if not _is_company_namespace(namespace):
            continue
        context_ref = str(node.attrib.get("contextRef") or "")
        unit_ref = str(node.attrib.get("unitRef") or "")
        context = contexts.get(context_ref)
        unit = units.get(unit_ref)
        if context is None or unit is None or context.has_dimensions:
            continue
        if context.period_end != report_date:
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
        label = _label_for_concept(labels, concept)
        raw_candidates.append((namespace, concept, label, unit, value, context_ref))

    output: dict[str, NormalizedFinancialFact] = {}
    retrieved = datetime.now(timezone.utc)
    for metric in sorted(target_metrics):
        ranked: list[_Candidate] = []
        for namespace, concept, label, unit, value, context_ref in raw_candidates:
            context = contexts[context_ref]
            if metric in BALANCE_METRICS:
                if context.period_start is not None:
                    continue
            else:
                if context.period_start is None:
                    continue
                duration_days = (context.period_end - context.period_start).days
                if duration_days < 300 or duration_days > 380:
                    continue
            score = _score(metric, concept, label)
            if score < 0.45:
                continue
            ranked.append(_Candidate(namespace, concept, label, unit, value, score))
        if not ranked:
            continue
        ranked.sort(key=lambda item: (item.score, len(_semantic_tokens(item.concept))), reverse=True)
        best = ranked[0]
        alternatives = ranked[1:4]
        economic_value = abs(best.value) if metric in POSITIVE_OUTFLOW_METRICS else best.value
        alt_text = "; ".join(
            f"{item.concept} ({item.label or 'ohne Label'})={item.value} {item.unit}, score={item.score:.2f}"
            for item in alternatives
        )
        note = (
            f"SEC Company-Extension-Kandidat für internes Feld {metric}; noch nicht semantisch freigegeben. "
            f"Concept={best.concept}; Label={best.label or '—'}; Namespace={best.namespace}; "
            f"Matching-Score={best.score:.2f}."
        )
        if alt_text:
            note += " Weitere plausible Extension-Fakten im selben Filing: " + alt_text
        output[metric] = NormalizedFinancialFact(
            statement=(
                "cash_flow"
                if metric in CASH_FLOW_METRICS
                else "balance_sheet"
                if metric in BALANCE_METRICS
                else "income_statement"
            ),
            metric=metric,
            period_end=report_date,
            period_type="FY",
            value=economic_value,
            provider_value=best.value,
            currency=best.unit,
            unit="currency",
            provider="sec_filing_extension",
            provider_field=f"company-extension:{best.concept}",
            filing_date=filing_date,
            retrieved_at=retrieved,
            is_cross_check_only=False,
            note=note,
            source_url=source_url,
        )
    return output


class SECCompanyExtensionProvider:
    """Find reviewable company-extension facts for gaps left by standardized SEC XBRL.

    This provider never declares an extension mapping correct. It only produces a best candidate
    with provenance and optional alternatives. Downstream Preferred Data keeps every candidate
    blocked until a matching ChatGPT semantic review returns PASS or the user accepts an override.
    """

    def __init__(self, filing_provider: SECFilingFallbackProvider) -> None:
        self.filing_provider = filing_provider

    def _label_map(self, cik: str, filing: SECFilingRef) -> dict[str, str]:
        base = self.filing_provider._archive_base(cik, filing)
        try:
            index = self.filing_provider._get_json(base + "index.json")
        except Exception:
            return {}
        directory = index.get("directory") if isinstance(index, dict) else None
        items = directory.get("item") if isinstance(directory, dict) else None
        if not isinstance(items, list):
            return {}
        names = [str(item.get("name") or "") for item in items if isinstance(item, dict)]
        label_files = [name for name in names if name.casefold().endswith("_lab.xml")]
        result: dict[str, str] = {}
        for name in label_files[:3]:
            try:
                result.update(parse_label_linkbase(self.filing_provider._get_text(base + name)))
            except Exception:
                continue
        return result

    def candidate_facts(
        self,
        cik: str,
        gaps: Iterable[SECFilingGap],
        base_facts: Iterable[NormalizedFinancialFact],
    ) -> SECCompanyExtensionResult:
        targets = [gap for gap in gaps if gap.status == "semantic_review_required"]
        passthrough = [gap for gap in gaps if gap.status != "semantic_review_required"]
        if not targets:
            return SECCompanyExtensionResult((), tuple(passthrough), 0)

        usable = [fact for fact in base_facts if fact.value is not None and fact.period_type == "FY"]
        currencies = Counter(str(fact.currency).upper() for fact in usable if fact.currency)
        expected_currency = currencies.most_common(1)[0][0] if currencies else None

        found: dict[tuple[str, int], NormalizedFinancialFact] = {}
        checked = 0
        target_by_year: dict[int, set[str]] = {}
        for gap in targets:
            target_by_year.setdefault(gap.year, set()).add(gap.metric)

        for year, metrics in sorted(target_by_year.items()):
            filings = self.filing_provider.filings_for_year(cik, year)
            for filing in filings:
                remaining = {
                    metric for metric in metrics if (metric, year) not in found
                }
                if not remaining:
                    break
                instance = self.filing_provider._instance_document(cik, filing)
                if instance is None:
                    continue
                instance_url, content = instance
                checked += 1
                labels = self._label_map(cik, filing)
                candidates = _candidate_facts_from_instance(
                    content,
                    target_metrics=remaining,
                    report_date=filing.report_date,
                    filing_date=filing.filing_date,
                    form=filing.form,
                    source_url=instance_url,
                    expected_currency=expected_currency,
                    labels=labels,
                )
                for metric, fact in candidates.items():
                    found.setdefault((metric, year), fact)

        unresolved = list(passthrough)
        for gap in targets:
            if (gap.metric, gap.year) in found:
                continue
            unresolved.append(
                SECFilingGap(
                    gap.metric,
                    gap.year,
                    "no_extension_candidate",
                    "Auch im Company-XBRL wurde kein ausreichend plausibler Extension-Kandidat gefunden; Wert bleibt offen.",
                    gap.filing_url,
                )
            )

        facts = tuple(
            found[key]
            for key in sorted(found, key=lambda item: (item[1], item[0]))
        )
        return SECCompanyExtensionResult(facts, tuple(unresolved), checked)
