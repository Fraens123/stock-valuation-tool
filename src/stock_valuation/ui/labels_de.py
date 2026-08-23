from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


STATUS_LABELS_DE = {
    "READY": "Bereit",
    "REVIEW_REQUIRED": "Prüfung erforderlich",
    "READY_FOR_PREVIEW": "Bewertungsvorschau verfügbar",
    "BLOCKED": "Blockiert",
    "NOT_RUN": "Noch nicht ausgeführt",
    "STALE": "Nicht mehr aktuell",
    "UNAVAILABLE": "Nicht verfügbar",
    "AVAILABLE": "Verfügbar",
    "NOT_MEANINGFUL": "Nicht sinnvoll interpretierbar",
    "NOT_CURRENTLY_IMPLEMENTED": "Noch nicht in der aktuellen Engine verfügbar",
    "primary_source": "Verfügbar",
    "primary_semantic_review_required": "Prüfung erforderlich",
    "primary_reviewed_pass": "Verfügbar",
    "confirmed_override": "Verfügbar",
    "safe_standard_mapping": "Verfügbar",
    "provider_unverified": "Prüfung erforderlich",
    "review_stale": "Prüfung nicht mehr aktuell",
    "reviewed_pass": "Verfügbar",
    "derive_required": "Abgeleitete Kennzahl",
    "ASSUMPTION_PREVIEW": "Bewertungsvorschau",
    "APPROVED": "Freigegeben",
    "DRAFT": "Entwurf",
    "IN_PROGRESS": "In Bearbeitung",
    "COMPLETED": "Abgeschlossen",
    "ARCHIVED": "Archiviert",
}


ISSUE_LABELS_DE = {
    "MISSING_NET_DEBT": "Nettoverschuldung fehlt",
    "MISSING_ENTERPRISE_VALUE": "Unternehmenswert kann noch nicht vollständig berechnet werden",
    "MISSING_EBITDA": "EBITDA ist noch nicht verfügbar",
    "MISSING_INPUT": "Eingabewert fehlt",
    "MISSING_OWNER_EARNINGS_HISTORY": "Owner-Earnings-Historie fehlt",
    "MISSING_INTANGIBLE_PURCHASES": "Käufe immaterieller Anlagewerte fehlen",
    "MISSING_PREVIOUS_OPERATING_WORKING_CAPITAL": "Vorjahreswert für Operating Working Capital fehlt",
    "MISSING_CURRENT_OPERATING_WORKING_CAPITAL": "Aktueller Wert für Operating Working Capital fehlt",
    "MISSING_FAIR_PE": "Faires KGV fehlt",
    "FAIR_PE_NOT_POSITIVE": "Faires KGV ist nicht positiv",
    "MISSING_RISK_FREE_RATE": "Risikofreier Zinssatz fehlt",
    "MISSING_DISCOUNT_INPUT": "Eingabe für Diskontierungszins fehlt",
    "MISSING_LAST_OWNER_EARNINGS": "Owner Earnings des letzten Planjahres fehlen",
    "MISSING_TERMINAL_VALUE": "Ewige Rente fehlt",
    "MISSING_PRESENT_VALUE_TERMINAL_VALUE": "Barwert der ewigen Rente fehlt",
    "MISSING_SHARES_OUTSTANDING": "Aktienzahl fehlt",
    "MISSING_MARKET_PRICE": "Aktueller Kurs fehlt",
    "MISSING_EQUITY_VALUE_OR_SHARES": "Eigenkapitalwert oder Aktienzahl fehlt",
    "MISSING_FAIR_VALUE_PER_SHARE": "Fairer Aktienkurs fehlt",
    "MISSING_FAIR_VALUE_OR_MARKET_PRICE": "Fairer Wert oder aktueller Kurs fehlt",
    "CURRENCY_MATCH": "Währungen passen zusammen",
    "FX_REQUIRED": "Wechselkurs erforderlich",
    "FX_UNAVAILABLE": "Wechselkurs nicht verfügbar",
    "APPROVAL_STALE": "Frühere Freigabe ist nicht mehr aktuell",
    "EV_REVIEW_REQUIRED": "Unternehmenswert noch nicht vollständig berechenbar",
    "EV_READY": "Unternehmenswert verfügbar",
    "MARKET_CAP_READY": "Marktkapitalisierung verfügbar",
    "UNAVAILABLE": "Nicht verfügbar",
}


METRIC_LABELS_DE = {
    "revenue": "Umsatz",
    "gross_profit": "Bruttoergebnis",
    "operating_income": "Betriebsergebnis",
    "net_income": "Jahresüberschuss",
    "total_assets": "Gesamtvermögen",
    "current_assets": "Umlaufvermögen",
    "cash_and_equivalents": "Liquide Mittel",
    "accounts_receivable": "Forderungen",
    "inventory": "Vorräte",
    "ppe_net": "Sachanlagen",
    "goodwill": "Goodwill",
    "total_liabilities": "Gesamtverbindlichkeiten",
    "current_liabilities": "Kurzfristige Verbindlichkeiten",
    "accounts_payable": "Verbindlichkeiten aus Lieferungen und Leistungen",
    "short_term_debt": "Kurzfristige Finanzschulden",
    "long_term_debt": "Langfristige Finanzschulden",
    "shareholders_equity": "Eigenkapital",
    "operating_cash_flow": "Operativer Cashflow",
    "capital_expenditures": "Sachinvestitionen",
    "free_cash_flow": "Freier Cashflow (FCF)",
    "depreciation_amortization": "Abschreibungen und Amortisation",
    "dividends_paid": "Dividendenzahlungen",
    "gross_margin": "Bruttomarge",
    "operating_margin": "Operative Marge",
    "net_margin": "Nettomarge",
    "ebitda": "EBITDA",
    "ebitda_margin": "EBITDA-Marge",
    "return_on_assets": "Vermögensrendite (ROA)",
    "return_on_equity": "Eigenkapitalrendite (ROE)",
    "equity_ratio": "Eigenkapitalquote",
    "debt_to_assets": "Schuldenquote",
    "debt_to_equity": "Debt to Equity",
    "net_debt": "Nettoverschuldung",
    "net_debt_to_ebitda": "Nettoverschuldung / EBITDA",
    "current_ratio": "Liquidität 3. Grades (Current Ratio)",
    "quick_ratio": "Liquidität 2. Grades (Quick Ratio)",
    "cash_ratio": "Liquidität 1. Grades (Cash Ratio)",
    "operating_cash_flow_margin": "Operative Cashflow-Marge",
    "capex_ratio": "Sachinvestitionen / operativer Cashflow",
    "free_cash_flow_margin": "FCF-Marge",
    "working_capital": "Nettoumlaufvermögen (Working Capital)",
    "working_capital_to_revenue": "Working Capital / Umsatz",
    "receivables_days": "Forderungslaufzeit / Debitorenlaufzeit",
    "payables_days": "Verbindlichkeitenlaufzeit / Kreditorenlaufzeit",
    "inventory_intensity": "Vorratsintensität",
    "inventory_days": "Lagerdauer",
    "market_cap": "Marktkapitalisierung",
    "enterprise_value": "Unternehmenswert (Enterprise Value, EV)",
    "latest_fy_pe": "Kurs-Gewinn-Verhältnis (KGV)",
    "latest_fy_pb": "Kurs-Buchwert-Verhältnis (KBV)",
    "latest_fy_p_ocf": "Kurs-Cashflow-Verhältnis (KCV)",
    "latest_fy_ev_ebit": "EV / EBIT",
    "latest_fy_ev_ebitda": "EV / EBITDA",
    "latest_fy_ev_sales": "EV / Umsatz",
    "latest_fy_ev_fcf": "EV / FCF",
    "latest_fy_p_fcf": "Kurs-FCF-Verhältnis",
    "earnings_yield": "Gewinnrendite",
    "fcf_yield": "FCF-Rendite",
    "base_fcf": "Ausgangs-Cashflow",
    "growth_rate": "Wachstumsrate",
    "discount_rate": "Geforderte Eigenkapitalrendite / Diskontierungszins",
    "terminal_growth_rate": "Ewige Wachstumsrate",
    "projection_years": "Planungszeitraum",
    "bear": "Pessimistisches Szenario (Bear)",
    "base": "Basisszenario",
    "bull": "Optimistisches Szenario (Bull)",
    "margin_of_safety": "Sicherheitsmarge",
    "fair_value": "Fairer Wert",
}


def status_label(value: Any) -> str:
    text = str(value or "").strip()
    return STATUS_LABELS_DE.get(text, STATUS_LABELS_DE.get(text.upper(), text or "Nicht verfügbar"))


def issue_label(value: Any) -> str:
    text = str(value or "").strip()
    return ISSUE_LABELS_DE.get(text, ISSUE_LABELS_DE.get(text.upper(), status_label(text)))


def metric_label(metric: str) -> str:
    return METRIC_LABELS_DE.get(metric, metric.replace("_", " ").title())


def format_date_de(value: Any) -> str:
    if value in (None, ""):
        return "-"
    text = str(value)
    parts = text[:10].split("-")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        return f"{parts[2]}.{parts[1]}.{parts[0]}"
    return text


def format_number_de(value: Any, *, decimals: int = 1, suffix: str = "") -> str:
    if value in (None, ""):
        return "Nicht verfügbar"
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return str(value)
    formatted = f"{number:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted}{suffix}"


def format_percent_de(value: Any, *, decimals: int = 1) -> str:
    if value in (None, ""):
        return "Nicht verfügbar"
    try:
        number = Decimal(str(value)) * Decimal("100")
    except (InvalidOperation, ValueError, TypeError):
        return str(value)
    return format_number_de(number, decimals=decimals, suffix=" %")


def format_multiple_de(value: Any, *, decimals: int = 2) -> str:
    if value in (None, ""):
        return "Nicht verfügbar"
    return format_number_de(value, decimals=decimals, suffix="x")


def format_currency_compact_de(value: Any, currency: str | None = None) -> str:
    if value in (None, ""):
        return "Nicht verfügbar"
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return str(value)
    abs_number = abs(number)
    if abs_number >= Decimal("1000000000"):
        scaled = number / Decimal("1000000000")
        unit = "Mrd."
    elif abs_number >= Decimal("1000000"):
        scaled = number / Decimal("1000000")
        unit = "Mio."
    else:
        scaled = number
        unit = ""
    tail = f" {unit}" if unit else ""
    cur = f" {currency}" if currency else ""
    return f"{format_number_de(scaled, decimals=1)}{tail}{cur}"
