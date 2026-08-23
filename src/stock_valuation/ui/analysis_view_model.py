from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from stock_valuation.ui.analysis_layout import ANALYSIS_SECTIONS, AnalysisPoint, AnalysisSection, NOT_CURRENTLY_IMPLEMENTED
from stock_valuation.ui.labels_de import (
    format_currency_compact_de,
    format_date_de,
    format_multiple_de,
    format_number_de,
    format_percent_de,
    issue_label,
    status_label,
)


@dataclass(frozen=True)
class RenderedPoint:
    key: str
    label: str
    info_key: str
    backend_key: str | None
    status: str
    status_label: str
    values_by_year: dict[int, str]
    latest_value: str
    reason: str | None = None
    technical_status: str | None = None


@dataclass(frozen=True)
class RenderedSection:
    key: str
    title: str
    intro: str
    points: tuple[RenderedPoint, ...]


@dataclass(frozen=True)
class AnalysisViewModel:
    company_name: str
    ticker: str
    as_of_date: str
    market_price: str
    trading_currency: str
    financial_currency: str
    history_label: str
    status_line: dict[str, str]
    status_info_keys: dict[str, str]
    sections: tuple[RenderedSection, ...]
    market_notes: tuple[str, ...]
    assumption_rows: tuple[dict[str, Any], ...]
    scenario_rows: tuple[dict[str, Any], ...]
    valuation_mode_label: str
    technical_payload: dict[str, Any]


def build_analysis_view_model(state, *, book_valuation_result: Any | None = None) -> AnalysisViewModel:
    calc = state.stages["CALCULATION"].payload
    market = state.stages["MARKET_DATA"].payload
    assumptions = state.stages["ASSUMPTIONS"].payload
    valuation = state.stages["VALUATION"].payload
    financial_currency = market.get("payload", {}).get("financial_statement_currency") or _company_currency(state)
    trading_currency = market.get("trading_currency") or financial_currency
    history_years = sorted({int(year) for year in calc.get("base_facts", {}) if str(year).isdigit()})
    sections = tuple(
        _render_section(section, calc, market, valuation, financial_currency, trading_currency, book_valuation_result)
        for section in ANALYSIS_SECTIONS
    )
    status_line = {
        "Daten": status_label(state.stages["FINANCIAL_DATA"].status),
        "Historie": status_label(state.stages["HISTORICAL_ANALYSIS"].status),
        "Marktdaten": _market_status_label(state.stages["MARKET_DATA"].payload, state.stages["MARKET_DATA"].status),
        "Bewertungsannahmen": status_label(state.stages["ASSUMPTIONS"].status),
        "Bewertung": status_label(state.stages["VALUATION"].status),
    }
    return AnalysisViewModel(
        company_name=state.company_name,
        ticker=state.ticker,
        as_of_date=format_date_de(state.as_of_date),
        market_price=format_currency_compact_de(market.get("price"), trading_currency),
        trading_currency=trading_currency,
        financial_currency=financial_currency,
        history_label=_history_label(history_years),
        status_line=status_line,
        status_info_keys={
            "Daten": "status_financial_data",
            "Historie": "status_history",
            "Marktdaten": "status_market",
            "Bewertungsannahmen": "status_assumptions",
            "Bewertung": "status_valuation",
        },
        sections=sections,
        market_notes=_market_notes(market, trading_currency, financial_currency),
        assumption_rows=_assumption_rows(assumptions),
        scenario_rows=_scenario_rows(valuation),
        valuation_mode_label="Freigegebene Bewertung" if valuation.get("mode") == "FINAL" else "Bewertungsvorschau",
        technical_payload={
            "stages": {
                stage: {
                    "technical_status_code": item.status,
                    "engine_version": item.version,
                    "snapshot_id": item.snapshot_id,
                    "inputs_hash": item.inputs_hash,
                    "warnings": item.warnings,
                    "blockers": item.blockers,
                }
                for stage, item in state.stages.items()
            },
            "market": market,
        },
    )


def available_years(vm: AnalysisViewModel, *, default: int = 5) -> list[int]:
    years = sorted({year for section in vm.sections for point in section.points for year in point.values_by_year})
    return years[-default:] if len(years) > default else years


def table_rows(section: RenderedSection, years: list[int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for point in section.points:
        row = {"Kennzahl": point.label, "Status": point.status_label}
        for year in years:
            row[str(year)] = point.values_by_year.get(year, "Nicht verfügbar")
        rows.append(row)
    return rows


def _render_section(
    section: AnalysisSection,
    calc: dict[str, Any],
    market: dict[str, Any],
    valuation: dict[str, Any],
    financial_currency: str,
    trading_currency: str,
    book_valuation_result: Any | None,
) -> RenderedSection:
    return RenderedSection(
        section.key,
        section.title,
        section.intro,
        tuple(_render_point(point, calc, market, valuation, financial_currency, trading_currency, book_valuation_result) for point in section.points),
    )


def _render_point(
    point: AnalysisPoint,
    calc: dict[str, Any],
    market: dict[str, Any],
    valuation: dict[str, Any],
    financial_currency: str,
    trading_currency: str,
    book_valuation_result: Any | None,
) -> RenderedPoint:
    if point.status == NOT_CURRENTLY_IMPLEMENTED:
        return RenderedPoint(
            point.key,
            point.label,
            point.info_key,
            point.backend_key,
            "NOT_CURRENTLY_IMPLEMENTED",
            "Noch nicht in der aktuellen Engine verfügbar",
            {},
            "Nicht verfügbar",
            "Diese Kennzahl ist in der aktuellen Berechnungs- oder Bewertungsengine noch nicht umgesetzt.",
            "NOT_CURRENTLY_IMPLEMENTED",
        )
    if point.source == "base":
        values, technical = _base_values(calc, point.backend_key or "", point.unit_hint, financial_currency)
    elif point.source == "calculation":
        values, technical = _calculation_values(calc, point.backend_key or "", point.unit_hint, financial_currency)
    elif point.source == "market":
        values, technical = _market_value(market, point.backend_key or "", point.unit_hint, trading_currency)
    elif point.source == "valuation":
        values, technical = _valuation_value(valuation, point.backend_key or "", point.unit_hint)
    elif point.source == "quality":
        values, technical = _quality_value(calc, point.backend_key or "")
    elif point.source == "book":
        values, technical = _book_value(book_valuation_result, point.backend_key or point.key, point.unit_hint, financial_currency)
    else:
        values, technical = ({}, None)
    latest = _latest(values)
    return RenderedPoint(
        point.key,
        point.label,
        point.info_key,
        point.backend_key,
        technical or ("AVAILABLE" if values else "UNAVAILABLE"),
        _point_status_label(technical, values),
        values,
        latest,
        _point_reason(technical),
        technical,
    )


def _base_values(calc: dict[str, Any], metric: str, unit_hint: str, currency: str) -> tuple[dict[int, str], str | None]:
    output: dict[int, str] = {}
    status: str | None = None
    for year, facts in calc.get("base_facts", {}).items():
        row = next((item for item in facts if item.get("metric") == metric), None)
        if row is None:
            continue
        output[int(year)] = _format_value(row.get("value"), unit_hint, row.get("currency") or currency)
        status = row.get("source_status") or status
    return output, status


def _calculation_values(calc: dict[str, Any], metric: str, unit_hint: str, currency: str) -> tuple[dict[int, str], str | None]:
    output: dict[int, str] = {}
    status: str | None = None
    for item in calc.get("results", []):
        if item.get("metric_id") != metric:
            continue
        year = int(item["fiscal_year"])
        if item.get("status") == "AVAILABLE":
            output[year] = _format_value(item.get("value"), unit_hint, currency)
        status = item.get("status") or status
    return output, status


def _market_value(market: dict[str, Any], metric: str, unit_hint: str, currency: str) -> tuple[dict[int, str], str | None]:
    value = market.get(metric)
    availability = market.get("availability", {})
    status = availability.get(metric) or ("AVAILABLE" if value is not None else "UNAVAILABLE")
    if value is None and metric == "enterprise_value":
        return {}, "EV_REVIEW_REQUIRED"
    return ({0: _format_value(value, unit_hint, currency)} if value is not None else {}, status)


def _valuation_value(valuation: dict[str, Any], metric: str, unit_hint: str) -> tuple[dict[int, str], str | None]:
    rows = valuation.get("multiples", [])
    row = next((item for item in rows if item.get("metric_id") == metric), None)
    if row is None:
        return {}, "UNAVAILABLE"
    status = row.get("status")
    if row.get("value") is None:
        return {}, status
    return ({int(row.get("fiscal_year") or 0): _format_value(row.get("value"), unit_hint, None)}, status)


def _quality_value(calc: dict[str, Any], metric: str) -> tuple[dict[int, str], str | None]:
    return {}, "AVAILABLE" if metric else "UNAVAILABLE"


def _book_value(result: Any | None, key: str, unit_hint: str, currency: str) -> tuple[dict[int, str], str | None]:
    if result is None:
        return {}, "UNAVAILABLE"
    values = getattr(result, "values", None)
    if values is None and isinstance(result, dict):
        values = result.get("values")
    item = values.get(key) if isinstance(values, dict) else None
    if item is None:
        return {}, "UNAVAILABLE"
    value = getattr(item, "value", None) if not isinstance(item, dict) else item.get("value")
    status = getattr(item, "status", None) if not isinstance(item, dict) else item.get("status")
    unit = getattr(item, "unit", None) if not isinstance(item, dict) else item.get("unit")
    if value is None:
        return {}, status or "UNAVAILABLE"
    hint = "percent" if unit == "decimal_ratio" else "multiple" if unit == "multiple" else unit_hint
    return {0: _format_value(value, hint, currency)}, status or "AVAILABLE"


def _format_value(value: Any, unit_hint: str, currency: str | None) -> str:
    if value in (None, ""):
        return "Nicht verfügbar"
    if unit_hint == "percent":
        return format_percent_de(value)
    if unit_hint == "multiple":
        return format_multiple_de(value)
    if unit_hint == "days":
        return format_number_de(value, decimals=0, suffix=" Tage")
    if unit_hint == "number":
        return format_number_de(value, decimals=0)
    return format_currency_compact_de(value, currency)


def _latest(values: dict[int, str]) -> str:
    if not values:
        return "Nicht verfügbar"
    return values[sorted(values)[-1]]


def _point_status_label(status: str | None, values: dict[int, str]) -> str:
    if status == "EV_REVIEW_REQUIRED":
        return "Unternehmenswert noch nicht vollständig berechenbar"
    if status == "EV_READY":
        return issue_label(status)
    if status and status not in {"AVAILABLE", "primary_source", "confirmed_override", "safe_standard_mapping"}:
        return status_label(status)
    return "Verfügbar" if values else "Nicht verfügbar"


def _point_reason(status: str | None) -> str | None:
    if status == "EV_REVIEW_REQUIRED":
        return "Für die Berechnung fehlt noch eine fachlich freigegebene Nettoverschuldung."
    if status in {"UNAVAILABLE", "NOT_MEANINGFUL"}:
        return issue_label(status)
    return None


def _market_status_label(market: dict[str, Any], stage_status: str) -> str:
    ev_status = market.get("availability", {}).get("enterprise_value")
    if ev_status == "EV_REVIEW_REQUIRED":
        return "Teilweise verfügbar"
    return status_label(stage_status)


def _market_notes(market: dict[str, Any], trading_currency: str, financial_currency: str) -> tuple[str, ...]:
    notes = [f"Abschlusswährung: {financial_currency}", f"Handelswährung: {trading_currency}"]
    payload = market.get("payload", {})
    listing = payload.get("listing", {})
    if listing.get("security_type", "").upper() in {"ADR", "ADS"}:
        notes.append("ADR-/ADS-Bezug wird über die gespeicherten Listing- und Aktienzahl-Daten berücksichtigt.")
    reason = market.get("availability", {}).get("enterprise_value_reason", ())
    if reason:
        notes.append("Unternehmenswert: " + ", ".join(issue_label(item) for item in reason))
    return tuple(notes)


def _assumption_rows(payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    rows = []
    for key, item in payload.get("recommendations", {}).items():
        unit = item.get("unit")
        value = item.get("recommended_value")
        approved = item.get("approved_value")
        rows.append(
            {
                "key": key,
                "Annahme": _assumption_label(key),
                "Empfehlung": format_percent_de(value) if unit == "decimal_ratio" else _format_value(value, "number" if key == "projection_years" else "currency", None),
                "Freigegeben": format_percent_de(approved) if unit == "decimal_ratio" else _format_value(approved, "number" if key == "projection_years" else "currency", None),
                "Status": status_label(item.get("status")),
                "Quelle": item.get("source_type") or "-",
                "Hauptanker": item.get("primary_anchor") or "-",
                "Begründung": item.get("reasoning_summary") or "-",
                "raw": item,
            }
        )
    order = {"base_fcf": 0, "growth_rate": 1, "discount_rate": 2, "terminal_growth_rate": 3, "projection_years": 4}
    return tuple(sorted(rows, key=lambda row: order.get(row["key"], 99)))


def _scenario_rows(valuation: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    preview = valuation.get("preview", {})
    order = {"bear": 0, "base": 1, "bull": 2}
    rows = []
    for scenario, item in sorted(preview.items(), key=lambda pair: order.get(pair[0], 99)):
        rows.append(
            {
                "Szenario": {"bear": "Pessimistisches Szenario (Bear)", "base": "Basisszenario", "bull": "Optimistisches Szenario (Bull)"}.get(scenario, scenario),
                "Fairer Wert": format_currency_compact_de(item.get("fair_value_per_unit")),
                "Aktueller Kurs": format_currency_compact_de(item.get("market_price")),
                "Abweichung zum Kurs": format_percent_de(item.get("upside_downside")),
                "Sicherheitsmarge": format_percent_de(item.get("margin_of_safety")),
                "Status": status_label(item.get("status")),
            }
        )
    return tuple(rows)


def _assumption_label(key: str) -> str:
    return {
        "base_fcf": "Ausgangs-Cashflow",
        "growth_rate": "Wachstumsrate",
        "discount_rate": "Geforderte Eigenkapitalrendite / Diskontierungszins",
        "terminal_growth_rate": "Ewige Wachstumsrate",
        "projection_years": "Planungszeitraum",
    }.get(key, key)


def _history_label(years: list[int]) -> str:
    if not years:
        return "Nicht verfügbar"
    return f"{len(years)} Geschäftsjahre ({years[0]}-{years[-1]})"


def _company_currency(state) -> str:
    return getattr(state, "financial_currency", None) or "EUR"
