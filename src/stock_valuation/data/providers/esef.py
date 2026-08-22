from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from stock_valuation.data.types import NormalizedFinancialFact


IFRS_TAG_MAP: dict[str, tuple[str, ...]] = {
    "revenue": ("ifrs-full:Revenue",),
    "cost_of_revenue": ("ifrs-full:CostOfSales",),
    "gross_profit": ("ifrs-full:GrossProfit",),
    "operating_income": (
        "ifrs-full:ProfitLossFromOperatingActivities",
        "ifrs-full:OperatingProfitLoss",
    ),
    "pretax_income": ("ifrs-full:ProfitLossBeforeTax",),
    "net_income": ("ifrs-full:ProfitLoss",),
    "total_assets": ("ifrs-full:Assets",),
    "current_assets": ("ifrs-full:CurrentAssets",),
    "cash_and_equivalents": ("ifrs-full:CashAndCashEquivalents",),
    "accounts_receivable": (
        "ifrs-full:TradeAndOtherCurrentReceivables",
        "ifrs-full:TradeReceivables",
    ),
    "inventory": ("ifrs-full:Inventories",),
    "ppe_net": ("ifrs-full:PropertyPlantAndEquipment",),
    "goodwill": ("ifrs-full:Goodwill",),
    "total_liabilities": ("ifrs-full:Liabilities",),
    "current_liabilities": ("ifrs-full:CurrentLiabilities",),
    "accounts_payable": (
        "ifrs-full:TradeAndOtherCurrentPayables",
        "ifrs-full:TradePayables",
    ),
    "short_term_debt": ("ifrs-full:CurrentBorrowings",),
    "long_term_debt": ("ifrs-full:NoncurrentBorrowings",),
    "shareholders_equity": ("ifrs-full:Equity",),
    "operating_cash_flow": ("ifrs-full:CashFlowsFromUsedInOperatingActivities",),
    "capital_expenditures": (
        "ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
    ),
    "intangible_purchases": (
        "ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities",
    ),
    "depreciation_amortization": ("ifrs-full:DepreciationAndAmortisationExpense",),
    "dividends_paid": ("ifrs-full:DividendsPaidClassifiedAsFinancingActivities",),
}

POSITIVE_OUTFLOW_METRICS = {"capital_expenditures", "intangible_purchases", "dividends_paid"}


class ESEFParseError(RuntimeError):
    pass


@dataclass(frozen=True)
class ContextInfo:
    context_id: str
    instant: date | None
    start: date | None
    end: date | None
    dimensional: bool

    @property
    def period_end(self) -> date | None:
        return self.instant or self.end

    @property
    def annual_duration(self) -> bool:
        if self.start is None or self.end is None:
            return False
        days = (self.end - self.start).days + 1
        return 300 <= days <= 430


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag.split(":")[-1]


def _date(text: str | None) -> date | None:
    if not text:
        return None
    try:
        return date.fromisoformat(text.strip()[:10])
    except ValueError:
        return None


def _extract_xhtml(content: bytes, filename: str | None = None) -> tuple[bytes, str]:
    name = filename or "report.xhtml"
    if content.startswith(b"PK") or name.lower().endswith(".zip"):
        try:
            with ZipFile(BytesIO(content)) as archive:
                candidates = [
                    item
                    for item in archive.namelist()
                    if PurePosixPath(item).suffix.lower() in {".xhtml", ".html", ".htm"}
                    and not item.startswith("__MACOSX/")
                ]
                if not candidates:
                    raise ESEFParseError("Im ESEF-ZIP wurde keine XHTML/HTML-Berichtsdatei gefunden.")
                # Main ESEF report is normally the largest XHTML file.
                candidate = max(candidates, key=lambda item: archive.getinfo(item).file_size)
                return archive.read(candidate), candidate
        except BadZipFile as exc:
            raise ESEFParseError("Die hochgeladene ZIP-Datei ist kein gültiges ESEF-Paket.") from exc
    return content, name


def _contexts(root: ET.Element) -> dict[str, ContextInfo]:
    result: dict[str, ContextInfo] = {}
    for element in root.iter():
        if _local_name(element.tag) != "context":
            continue
        context_id = element.attrib.get("id")
        if not context_id:
            continue
        instant = start = end = None
        dimensional = False
        for child in element.iter():
            local = _local_name(child.tag)
            if local == "instant":
                instant = _date(child.text)
            elif local == "startDate":
                start = _date(child.text)
            elif local == "endDate":
                end = _date(child.text)
            elif local in {"explicitMember", "typedMember"}:
                dimensional = True
        result[context_id] = ContextInfo(
            context_id=context_id,
            instant=instant,
            start=start,
            end=end,
            dimensional=dimensional,
        )
    return result


def _units(root: ET.Element) -> dict[str, str]:
    result: dict[str, str] = {}
    for element in root.iter():
        if _local_name(element.tag) != "unit":
            continue
        unit_id = element.attrib.get("id")
        if not unit_id:
            continue
        measure = None
        for child in element.iter():
            if _local_name(child.tag) == "measure" and child.text:
                measure = child.text.strip().split(":")[-1]
                break
        if measure:
            result[unit_id] = measure
    return result


def _parse_number(text: str, format_name: str | None) -> Decimal | None:
    raw = text.replace("\u00a0", " ").replace("\u202f", " ").strip()
    raw = "".join(raw.split())
    if not raw or raw in {"-", "—", "–"}:
        return None
    negative_parentheses = raw.startswith("(") and raw.endswith(")")
    if negative_parentheses:
        raw = raw[1:-1]

    fmt = (format_name or "").lower()
    if "comma-decimal" in fmt:
        raw = raw.replace(".", "").replace(",", ".")
    elif "dot-decimal" in fmt:
        raw = raw.replace(",", "")
    else:
        if "," in raw and "." in raw:
            if raw.rfind(",") > raw.rfind("."):
                raw = raw.replace(".", "").replace(",", ".")
            else:
                raw = raw.replace(",", "")
        elif "," in raw:
            tail = raw.rsplit(",", 1)[-1]
            raw = raw.replace(".", "")
            raw = raw.replace(",", "." if len(tail) <= 2 else "")

    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    return -value if negative_parentheses else value


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


def parse_esef_ixbrl(content: bytes, *, filename: str | None = None) -> list[NormalizedFinancialFact]:
    xhtml, inner_name = _extract_xhtml(content, filename)
    try:
        root = ET.fromstring(xhtml)
    except ET.ParseError as exc:
        raise ESEFParseError(
            "Die ESEF-Berichtsdatei ist kein wohlgeformtes XHTML/XML oder verwendet ein nicht unterstütztes Format."
        ) from exc

    context_index = _contexts(root)
    unit_index = _units(root)
    tag_to_metric = {
        tag.casefold(): metric for metric, tags in IFRS_TAG_MAP.items() for tag in tags
    }
    retrieved = datetime.now(timezone.utc)

    selected: dict[tuple[str, date], NormalizedFinancialFact] = {}
    for element in root.iter():
        if _local_name(element.tag) != "nonFraction":
            continue
        name = str(element.attrib.get("name") or "").strip()
        metric = tag_to_metric.get(name.casefold())
        if metric is None:
            continue
        context_ref = element.attrib.get("contextRef")
        context = context_index.get(context_ref or "")
        if context is None or context.dimensional or context.period_end is None:
            continue

        statement = _statement_for(metric)
        if statement != "balance_sheet" and not context.annual_duration:
            continue

        text = "".join(element.itertext())
        value = _parse_number(text, element.attrib.get("format"))
        if value is None:
            continue
        scale_raw = element.attrib.get("scale")
        try:
            scale = int(scale_raw) if scale_raw is not None else 0
        except ValueError:
            scale = 0
        provider_value = value * (Decimal(10) ** scale)
        if str(element.attrib.get("sign") or "").strip() == "-":
            provider_value = -provider_value
        economic_value = (
            abs(provider_value) if metric in POSITIVE_OUTFLOW_METRICS else provider_value
        )
        unit_ref = element.attrib.get("unitRef")
        currency = unit_index.get(unit_ref or "")

        fact = NormalizedFinancialFact(
            statement=statement,
            metric=metric,
            period_end=context.period_end,
            period_type="FY",
            value=economic_value,
            provider_value=provider_value,
            currency=currency,
            unit="currency",
            provider="esef_ixbrl",
            provider_field=name,
            retrieved_at=retrieved,
            note=f"ESEF/iXBRL source file: {inner_name}; context={context.context_id}",
        )
        key = (metric, context.period_end)
        # Main-statement standard tag + non-dimensional context should normally be unique.
        # Keep the first deterministic occurrence rather than mixing contexts.
        selected.setdefault(key, fact)

    return sorted(selected.values(), key=lambda fact: (fact.period_end, fact.metric))
