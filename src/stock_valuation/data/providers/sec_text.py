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
    "operating_cash_flow": (
        "investing activities",
        "financing activities",
    ),
    "short_term_debt": (
        "accounts payable",
        "trade payable",
        "lease liabilit",
    ),
}

_STOPWORDS = {
    "a",
    "an",
    "and",
    "at",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "the",
    "to",
    "used",
}


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[_HTMLTable] = []
        self._table_depth = 0
        self._rows: list[tuple[str, ...]] = []
        self._table_text: list[str] = []
        self._row: list[str] | None = None
        self._cell_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[no-untyped-def]
        lowered = tag.casefold()
        if lowered == "table":
            if self._table_depth == 0:
                self._rows = []
                self._table_text = []
            self._table_depth += 1
            return
        if self._table_depth <= 0:
            return
        if lowered == "tr":
            self._row = []
        elif lowered in {"td", "th"} and self._row is not None:
            self._cell_parts = []

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered in {"td", "th"} and self._cell_parts is not None and self._row is not None:
            self._row.append(_clean_text(" ".join(self._cell_parts)))
            self._cell_parts = None
            return
        if lowered == "tr" and self._row is not None:
            cells = tuple(cell for cell in self._row if cell)
            if cells:
                self._rows.append(cells)
            self._row = None
            return
        if lowered == "table" and self._table_depth > 0:
            self._table_depth -= 1
            if self._table_depth == 0:
                self.tables.append(
                    _HTMLTable(
                        rows=tuple(self._rows),
                        text=_clean_text(" ".join(self._table_text)),
                    )
                )
                self._rows = []
                self._table_text = []

    def handle_data(self, data: str) -> None:
        if self._table_depth <= 0:
            return
        text = _clean_text(data)
        if not text:
            return
        self._table_text.append(text)
        if self._cell_parts is not None:
            self._cell_parts.append(text)


def _clean_text(value: str) -> str:
    return " ".join(unescape(value or "").replace("\xa0", " ").split())


def _words(value: str) -> tuple[str, ...]:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value or "")
    tokens = re.findall(r"[a-z0-9]+", text.casefold())
    return tuple(token for token in tokens if token not in _STOPWORDS)


def _phrase(value: str) -> str:
    return " ".join(_words(value))


def _concept_aliases(metric: str) -> tuple[str, ...]:
    aliases: list[str] = [metric.replace("_", " ")]
    aliases.extend(_EXPLICIT_ALIASES.get(metric, ()))
    for _taxonomy, concept in CONCEPT_MAP.get(metric, ()):
        aliases.append(re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", concept))
    normalized = []
    for alias in aliases:
        value = _phrase(alias)
        if value and value not in normalized:
            normalized.append(value)
    return tuple(normalized)


def _label_score(metric: str, label: str) -> float:
    normalized = _phrase(label)
    if not normalized:
        return 0.0
    lowered = normalized.casefold()
    if any(_phrase(item) in lowered for item in _FORBIDDEN_PHRASES.get(metric, ())):
        return 0.0

    candidate_tokens = set(normalized.split())
    best = 0.0
    for alias in _concept_aliases(metric):
        alias_tokens = set(alias.split())
        if not alias_tokens:
            continue
        if alias in normalized or normalized in alias:
            best = max(best, 1.0)
            continue
        overlap = len(candidate_tokens & alias_tokens)
        if overlap < 2:
            continue
        precision = overlap / len(candidate_tokens)
        recall = overlap / len(alias_tokens)
        score = (2 * precision * recall) / (precision + recall) if precision + recall else 0.0
        best = max(best, score)
    return best


def _decimal_from_cell(raw: str) -> Decimal | None:
    text = _clean_text(raw)
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


def _scale_from_text(text: str) -> Decimal:
    lowered = _clean_text(text).casefold()
    patterns = (
        (r"\b(in|amounts? in|€|eur|usd|\$)\s*(billions?|bn)\b", Decimal("1000000000")),
        (r"\b(in|amounts? in|€|eur|usd|\$)\s*(millions?|mn)\b", Decimal("1000000")),
        (r"\b(in|amounts? in|€|eur|usd|\$)\s*(thousands?|000s)\b", Decimal("1000")),
        (r"\bmillions? of (euros?|dollars?)\b", Decimal("1000000")),
        (r"\bthousands? of (euros?|dollars?)\b", Decimal("1000")),
    )
    for pattern, scale in patterns:
        if re.search(pattern, lowered):
            return scale
    return Decimal("1")


def _target_column(table: _HTMLTable, row_index: int, year: int) -> int | None:
    year_text = str(year)
    for header in reversed(table.rows[:row_index]):
        for index, cell in enumerate(header):
            if re.search(rf"(?<!\d){re.escape(year_text)}(?!\d)", cell):
                return index
    return None


def _row_label_and_index(row: tuple[str, ...]) -> tuple[str, int] | None:
    for index, cell in enumerate(row):
        if re.search(r"[A-Za-z]", cell) and _decimal_from_cell(cell) is None:
            return cell, index
    return None


def _candidate_from_row(
    table: _HTMLTable,
    row_index: int,
    *,
    metric: str,
    year: int,
) -> _TextCandidate | None:
    row = table.rows[row_index]
    label_info = _row_label_and_index(row)
    if label_info is None:
        return None
    label, label_index = label_info
    score = _label_score(metric, label)
    if score < 0.72:
        return None

    column = _target_column(table, row_index, year)
    candidate_cells: list[tuple[int, str, Decimal]] = []
    for index, cell in enumerate(row):
        if index <= label_index:
            continue
        value = _decimal_from_cell(cell)
        if value is not None:
            candidate_cells.append((index, cell, value))
    if not candidate_cells:
        return None

    chosen = next((item for item in candidate_cells if item[0] == column), None)
    if chosen is None:
        chosen = candidate_cells[0]
    _, raw_value, parsed = chosen
    scale = _scale_from_text(table.text)
    return _TextCandidate(metric, label, raw_value, parsed * scale, score, scale)


def parse_filing_table_candidates(
    html: str,
    *,
    metrics: Iterable[str],
    year: int,
) -> dict[str, _TextCandidate]:
    """Find high-confidence labelled table rows, without declaring their semantics correct.

    The result is only a review candidate. Even an exact-looking table label remains blocked in
    Preferred Data until the normal semantic review returns PASS.
    """
    parser = _TableParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return {}

    output: dict[str, _TextCandidate] = {}
    for metric in sorted(set(metrics)):
        ranked: list[_TextCandidate] = []
        for table in parser.tables:
            for row_index in range(len(table.rows)):
                candidate = _candidate_from_row(table, row_index, metric=metric, year=year)
                if candidate is not None:
                    ranked.append(candidate)
        if not ranked:
            continue
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
    """Create review-only candidates from labelled rows in official SEC filing tables.

    This is the final automated SEC fallback after Company Facts, standard XBRL and company-XBRL
    extensions. It deliberately does not treat text/table extraction as calculation-ready data.
    """

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
        expected_currency = currencies.most_common(1)[0][0] if currencies else None

        target_by_year: dict[int, set[str]] = {}
        for gap in targets:
            target_by_year.setdefault(gap.year, set()).add(gap.metric)

        found: dict[tuple[str, int], NormalizedFinancialFact] = {}
        filings_checked = 0
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
                    content = self.filing_provider._get_text(source_url)
                except Exception:
                    continue
                filings_checked += 1
                candidates = parse_filing_table_candidates(
                    content,
                    metrics=remaining,
                    year=filing.report_date.year,
                )
                for metric, candidate in candidates.items():
                    economic_value = (
                        abs(candidate.value) if metric in POSITIVE_OUTFLOW_METRICS else candidate.value
                    )
                    scale_text = f"{candidate.scale:f}"
                    note = (
                        "SEC Tabellen-/Text-Kandidat aus dem offiziellen Originalfiling; noch nicht "
                        "semantisch freigegeben. "
                        f"Tabellenbezeichnung={candidate.label!r}; Rohwert={candidate.raw_value!r}; "
                        f"erkannter Skalierungsfaktor={scale_text}; Matching-Score={candidate.score:.2f}."
                    )
                    found[(metric, year)] = NormalizedFinancialFact(
                        statement=_statement(metric),
                        metric=metric,
                        period_end=filing.report_date,
                        period_type="FY",
                        value=economic_value,
                        provider_value=candidate.value,
                        currency=expected_currency,
                        unit="currency",
                        provider="sec_filing_text_candidate",
                        provider_field=f"text-table:{candidate.label[:140]}",
                        filing_date=filing.filing_date,
                        retrieved_at=retrieved,
                        is_cross_check_only=False,
                        note=note,
                        source_url=source_url,
                    )

        unresolved = list(passthrough)
        for gap in targets:
            if (gap.metric, gap.year) in found:
                continue
            unresolved.append(
                SECFilingGap(
                    metric=gap.metric,
                    year=gap.year,
                    status="no_text_candidate",
                    reason=(
                        "Auch in den Tabellen des offiziellen SEC-Filings wurde kein ausreichend "
                        "eindeutiger beschrifteter Zahlenkandidat gefunden; Wert bleibt offen."
                    ),
                    filing_url=gap.filing_url,
                )
            )

        facts = tuple(found[key] for key in sorted(found, key=lambda item: (item[1], item[0])))
        return SECFilingTextResult(facts, tuple(unresolved), filings_checked)
