from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html import unescape
from html.parser import HTMLParser
from typing import Iterable

from stock_valuation.data.providers.sec import CONCEPT_MAP, POSITIVE_OUTFLOW_METRICS
from stock_valuation.data.providers.sec_filing import (
    BALANCE_METRICS,
    CASH_FLOW_METRICS,
    SECFilingFallbackProvider,
    SECFilingGap,
)
from stock_valuation.data.types import NormalizedFinancialFact


@dataclass(frozen=True)
class SECFilingTextResult:
    facts: tuple[NormalizedFinancialFact, ...]
    unresolved: tuple[SECFilingGap, ...]
    filings_checked: int


@dataclass(frozen=True)
class _HTMLTable:
    rows: tuple[tuple[str, ...], ...]
    text: str


@dataclass(frozen=True)
class _TextCandidate:
    metric: str
    label: str
    raw_value: str
    value: Decimal
    score: float
    scale: Decimal


_EXPLICIT_ALIASES: dict[str, tuple[str, ...]] = {
    "dividends_paid": (
        "dividends paid",
        "dividend paid",
        "cash dividends paid",
        "payments of dividends",
        "dividends paid to shareholders",
    ),
    "operating_cash_flow": (
        "net cash provided by operating activities",
        "net cash from operating activities",
        "cash flow from operating activities",
        "cash flows from operating activities",
        "net cash generated from operating activities",
    ),
    "short_term_debt": (
        "short term debt",
        "short-term debt",
        "short term borrowings",
        "short-term borrowings",
        "current borrowings",
        "current portion of long term debt",
        "current portion of long-term debt",
        "current maturities of long term debt",
        "current maturities of long-term debt",
    ),
}
_FORBIDDEN_PHRASES: dict[str, tuple[str, ...]] = {
    "dividends_paid": (
        "dividend per share",
        "dividends per share",
        "proposed dividend",
        "dividend proposed",
        "dividend payable",
        "dividends payable",
        "dividend declared",
        "dividends declared",
        "dividend received",
    ),
    "operating_cash_flow": ("investing activities", "financing activities"),
    "short_term_debt": ("accounts payable", "trade payable", "lease liabilit"),
}
_STOPWORDS = {"a", "an", "and", "at", "by", "for", "from", "in", "of", "on", "the", "to", "used"}


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[_HTMLTable] = []
        self._depth = 0
        self._rows: list[tuple[str, ...]] = []
        self._text: list[str] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[no-untyped-def]
        tag = tag.casefold()
        if tag == "table":
            if self._depth == 0:
                self._rows, self._text = [], []
            self._depth += 1
        elif self._depth and tag == "tr":
            self._row = []
        elif self._depth and tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(_clean(" ".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            cells = tuple(cell for cell in self._row if cell)
            if cells:
                self._rows.append(cells)
            self._row = None
        elif tag == "table" and self._depth:
            self._depth -= 1
            if self._depth == 0:
                self.tables.append(_HTMLTable(tuple(self._rows), _clean(" ".join(self._text))))
                self._rows, self._text = [], []

    def handle_data(self, data: str) -> None:
        if not self._depth:
            return
        text = _clean(data)
        if not text:
            return
        self._text.append(text)
        if self._cell is not None:
            self._cell.append(text)


def _clean(value: str) -> str:
    return " ".join(unescape(value or "").replace("\xa0", " ").split())


def _phrase(value: str) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value or "")
    tokens = re.findall(r"[a-z0-9]+", text.casefold())
    return " ".join(token for token in tokens if token not in _STOPWORDS)


def _aliases(metric: str) -> tuple[str, ...]:
    raw = [metric.replace("_", " "), *_EXPLICIT_ALIASES.get(metric, ())]
    raw.extend(
        re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", concept)
        for _taxonomy, concept in CONCEPT_MAP.get(metric, ())
    )
    output: list[str] = []
    for item in raw:
        normalized = _phrase(item)
        if normalized and normalized not in output:
            output.append(normalized)
    return tuple(output)


def _label_score(metric: str, label: str) -> float:
    normalized = _phrase(label)
    if not normalized:
        return 0.0
    if any(_phrase(item) in normalized for item in _FORBIDDEN_PHRASES.get(metric, ())):
        return 0.0
    candidate = set(normalized.split())
    best = 0.0
    for alias in _aliases(metric):
        alias_tokens = set(alias.split())
        if alias in normalized or normalized in alias:
            best = max(best, 1.0)
            continue
        overlap = len(candidate & alias_tokens)
        if overlap < 2:
            continue
        precision = overlap / len(candidate)
        recall = overlap / len(alias_tokens)
        best = max(best, 2 * precision * recall / (precision + recall))
    return best


def _number(raw: str) -> Decimal | None:
    text = _clean(raw)
    if not text or text in {"-", "—", "–", "n/a", "N/A"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    text = re.sub(r"(?i)(eur|usd|gbp|jpy|chf|cad|aud)", "", text)
    text = text.replace("€", "").replace("$", "").replace("£", "")
    text = re.sub(r"[^0-9,.-]", "", text)
    if not text or text in {"-", ".", ","}:
        return None
    if "," in text and "." in text:
        text = text.replace(",", "")
    elif "," in text:
        if re.fullmatch(r"-?\d{1,3}(,\d{3})+", text):
            text = text.replace(",", "")
        elif text.count(",") == 1:
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    return -value if negative else value


def _scale(text: str) -> Decimal:
    value = _clean(text).casefold()
    scale_patterns = (
        (
            r"(?:\bin\b|\bamounts?\s+in\b|\beur\s+in\b|\busd\s+in\b|€\s*in|\$\s*in|\beur\b|\busd\b|€|\$)\s*(?:billions?|bn)\b",
            Decimal("1000000000"),
        ),
        (
            r"(?:\bin\b|\bamounts?\s+in\b|\beur\s+in\b|\busd\s+in\b|€\s*in|\$\s*in|\beur\b|\busd\b|€|\$)\s*(?:millions?|mn)\b",
            Decimal("1000000"),
        ),
        (
            r"(?:\bin\b|\bamounts?\s+in\b|\beur\s+in\b|\busd\s+in\b|€\s*in|\$\s*in|\beur\b|\busd\b|€|\$)\s*(?:thousands?|000s)\b",
            Decimal("1000"),
        ),
        (r"\bmillions?\s+of\s+(?:euros?|dollars?)\b", Decimal("1000000")),
        (r"\bthousands?\s+of\s+(?:euros?|dollars?)\b", Decimal("1000")),
    )
    for pattern, factor in scale_patterns:
        if re.search(pattern, value):
            return factor
    return Decimal("1")


def _year_column(table: _HTMLTable, row_index: int, year: int) -> int | None:
    target = str(year)
    for row in reversed(table.rows[:row_index]):
        for index, cell in enumerate(row):
            if re.search(rf"(?<!\d){target}(?!\d)", cell):
                return index
    return None


def _row_candidate(table: _HTMLTable, row_index: int, metric: str, year: int) -> _TextCandidate | None:
    row = table.rows[row_index]
    label_info = next(
        ((index, cell) for index, cell in enumerate(row) if re.search(r"[A-Za-z]", cell) and _number(cell) is None),
        None,
    )
    if label_info is None:
        return None
    label_index, label = label_info
    score = _label_score(metric, label)
    if score < 0.72:
        return None
    values = [
        (index, cell, parsed)
        for index, cell in enumerate(row)
        if index > label_index and (parsed := _number(cell)) is not None
    ]
    if not values:
        return None
    year_column = _year_column(table, row_index, year)
    chosen = next((item for item in values if item[0] == year_column), values[0])
    _, raw_value, parsed = chosen
    factor = _scale(table.text)
    return _TextCandidate(metric, label, raw_value, parsed * factor, score, factor)


def parse_filing_table_candidates(
    html: str,
    *,
    metrics: Iterable[str],
    year: int,
) -> dict[str, _TextCandidate]:
    """Find strongly labelled filing-table rows; returned rows are review candidates only."""
    parser = _TableParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return {}
    output: dict[str, _TextCandidate] = {}
    for metric in sorted(set(metrics)):
        ranked = [
            candidate
            for table in parser.tables
            for row_index in range(len(table.rows))
            if (candidate := _row_candidate(table, row_index, metric, year)) is not None
        ]
        if ranked:
            ranked.sort(key=lambda item: (item.score, len(item.label)), reverse=True)
            output[metric] = ranked[0]
    return output


def _statement(metric: str) -> str:
    if metric in CASH_FLOW_METRICS:
        return "cash_flow"
    if metric in BALANCE_METRICS:
        return "balance_sheet"
    return "income_statement"


class SECFilingTextFallbackProvider:
    """Create blocked review candidates from labelled rows in official SEC filing tables."""

    def __init__(self, filing_provider: SECFilingFallbackProvider) -> None:
        self.filing_provider = filing_provider

    def candidate_facts(
        self,
        cik: str,
        gaps: Iterable[SECFilingGap],
        base_facts: Iterable[NormalizedFinancialFact],
    ) -> SECFilingTextResult:
        targets = [gap for gap in gaps if gap.status != "no_filing"]
        passthrough = [gap for gap in gaps if gap.status == "no_filing"]
        if not targets:
            return SECFilingTextResult((), tuple(passthrough), 0)

        usable = [fact for fact in base_facts if fact.value is not None and fact.period_type == "FY"]
        currencies = Counter(str(fact.currency).upper() for fact in usable if fact.currency)
        currency = currencies.most_common(1)[0][0] if currencies else None
        target_by_year: dict[int, set[str]] = {}
        for gap in targets:
            target_by_year.setdefault(gap.year, set()).add(gap.metric)

        found: dict[tuple[str, int], NormalizedFinancialFact] = {}
        checked = 0
        retrieved = datetime.now(timezone.utc)
        for year, metrics in sorted(target_by_year.items()):
            for filing in self.filing_provider.filings_for_year(cik, year):
                remaining = {metric for metric in metrics if (metric, year) not in found}
                if not remaining:
                    break
                if not filing.primary_document:
                    continue
                source_url = self.filing_provider._archive_base(cik, filing) + filing.primary_document
                try:
                    html = self.filing_provider._get_text(source_url)
                except Exception:
                    continue
                checked += 1
                candidates = parse_filing_table_candidates(
                    html,
                    metrics=remaining,
                    year=filing.report_date.year,
                )
                for metric, candidate in candidates.items():
                    value = abs(candidate.value) if metric in POSITIVE_OUTFLOW_METRICS else candidate.value
                    found[(metric, year)] = NormalizedFinancialFact(
                        statement=_statement(metric),
                        metric=metric,
                        period_end=filing.report_date,
                        period_type="FY",
                        value=value,
                        provider_value=candidate.value,
                        currency=currency,
                        unit="currency",
                        provider="sec_filing_text_candidate",
                        provider_field=f"text-table:{candidate.label[:140]}",
                        filing_date=filing.filing_date,
                        retrieved_at=retrieved,
                        is_cross_check_only=False,
                        note=(
                            "SEC Tabellen-/Text-Kandidat aus dem offiziellen Originalfiling; noch nicht "
                            "semantisch freigegeben. "
                            f"Tabellenbezeichnung={candidate.label!r}; Rohwert={candidate.raw_value!r}; "
                            f"erkannter Skalierungsfaktor={candidate.scale:f}; Matching-Score={candidate.score:.2f}."
                        ),
                        source_url=source_url,
                    )

        unresolved = list(passthrough)
        for gap in targets:
            if (gap.metric, gap.year) not in found:
                unresolved.append(
                    SECFilingGap(
                        gap.metric,
                        gap.year,
                        "no_text_candidate",
                        "Auch in den Tabellen des offiziellen SEC-Filings wurde kein ausreichend eindeutiger Zahlenkandidat gefunden; Wert bleibt offen.",
                        gap.filing_url,
                    )
                )
        facts = tuple(found[key] for key in sorted(found, key=lambda item: (item[1], item[0])))
        return SECFilingTextResult(facts, tuple(unresolved), checked)
