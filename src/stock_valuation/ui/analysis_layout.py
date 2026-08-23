from __future__ import annotations

from dataclasses import dataclass


SUPPORTED = "SUPPORTED"
PARTIAL = "PARTIAL"
NOT_CURRENTLY_IMPLEMENTED = "NOT_CURRENTLY_IMPLEMENTED"


PRIMARY_ANALYSIS_ORDER = (
    "Unternehmensüberblick",
    "Gewinn- und Verlustrechnung",
    "Bilanz",
    "Cashflow",
    "Ertrag und Rentabilität",
    "Finanzielle Stabilität",
    "Verschuldung",
    "Kapitalbindung / Working Capital",
    "Cashflow-Qualität / Kapitalallokation",
    "Bewertungskennzahlen",
    "DCF-Bewertung",
    "Multiplikatoren-/Qualitätsbetrachtung",
    "Zusammenfassung",
)


@dataclass(frozen=True)
class AnalysisPoint:
    key: str
    label: str
    backend_key: str | None
    info_key: str
    source: str
    status: str = SUPPORTED
    unit_hint: str = "currency"


@dataclass(frozen=True)
class AnalysisSection:
    key: str
    title: str
    intro: str
    points: tuple[AnalysisPoint, ...]


ANALYSIS_SECTIONS: tuple[AnalysisSection, ...] = (
    AnalysisSection(
        "income_statement",
        "1. Gewinn- und Verlustrechnung",
        "Zuerst wird sichtbar, wie Umsatz und Ergebnis entstehen.",
        (
            AnalysisPoint("revenue", "Umsatz", "revenue", "revenue", "base"),
            AnalysisPoint("gross_profit", "Bruttoergebnis", "gross_profit", "gross_profit", "base"),
            AnalysisPoint("operating_income", "Betriebsergebnis", "operating_income", "operating_income", "base"),
            AnalysisPoint("net_income", "Jahresüberschuss", "net_income", "net_income", "base"),
            AnalysisPoint("ebitda", "EBITDA", "ebitda", "ebitda", "calculation"),
        ),
    ),
    AnalysisSection(
        "balance_sheet",
        "2. Bilanz",
        "Danach folgt die Kapital- und Vermögensstruktur.",
        (
            AnalysisPoint("cash_and_equivalents", "Liquide Mittel", "cash_and_equivalents", "cash_and_equivalents", "base"),
            AnalysisPoint("accounts_receivable", "Forderungen", "accounts_receivable", "accounts_receivable", "base"),
            AnalysisPoint("inventory", "Vorräte", "inventory", "inventory", "base"),
            AnalysisPoint("ppe_net", "Sachanlagen", "ppe_net", "ppe_net", "base"),
            AnalysisPoint("goodwill", "Goodwill", "goodwill", "goodwill", "base", PARTIAL),
            AnalysisPoint("total_assets", "Gesamtvermögen", "total_assets", "total_assets", "base"),
            AnalysisPoint("shareholders_equity", "Eigenkapital", "shareholders_equity", "shareholders_equity", "base"),
            AnalysisPoint("current_liabilities", "Kurzfristige Verbindlichkeiten", "current_liabilities", "current_liabilities", "base"),
            AnalysisPoint("accounts_payable", "Verbindlichkeiten aus Lieferungen und Leistungen", "accounts_payable", "accounts_payable", "base"),
            AnalysisPoint("short_term_debt", "Kurzfristige Finanzschulden", "short_term_debt", "short_term_debt", "base"),
            AnalysisPoint("long_term_debt", "Langfristige Finanzschulden", "long_term_debt", "long_term_debt", "base"),
            AnalysisPoint("total_liabilities", "Gesamtverbindlichkeiten", "total_liabilities", "total_liabilities", "base"),
        ),
    ),
    AnalysisSection(
        "cash_flow",
        "3. Cashflow",
        "Dieser Abschnitt zeigt, wie viel Cash aus dem Geschäft entsteht und was nach Investitionen übrig bleibt.",
        (
            AnalysisPoint("operating_cash_flow", "Operativer Cashflow", "operating_cash_flow", "operating_cash_flow", "base"),
            AnalysisPoint("capital_expenditures", "Sachinvestitionen", "capital_expenditures", "capital_expenditures", "base"),
            AnalysisPoint("free_cash_flow", "Freier Cashflow (FCF)", "free_cash_flow", "free_cash_flow", "calculation"),
            AnalysisPoint("dividends_paid", "Dividendenzahlungen", "dividends_paid", "dividends_paid", "base", PARTIAL),
        ),
    ),
    AnalysisSection(
        "profitability",
        "4. Ertrag und Rentabilität",
        "Margen und Kapitalrenditen zeigen, wie stark und effizient das Geschäftsmodell arbeitet.",
        (
            AnalysisPoint("gross_margin", "Bruttomarge", "gross_margin", "gross_margin", "calculation", unit_hint="percent"),
            AnalysisPoint("operating_margin", "Operative Marge", "operating_margin", "operating_margin", "calculation", unit_hint="percent"),
            AnalysisPoint("net_margin", "Nettomarge", "net_margin", "net_margin", "calculation", unit_hint="percent"),
            AnalysisPoint("ebitda_margin", "EBITDA-Marge", "ebitda_margin", "ebitda_margin", "calculation", unit_hint="percent"),
            AnalysisPoint("return_on_equity", "Eigenkapitalrendite (ROE)", "return_on_equity", "return_on_equity", "calculation", unit_hint="percent"),
            AnalysisPoint("return_on_assets", "Vermögensrendite (ROA)", "return_on_assets", "return_on_assets", "calculation", unit_hint="percent"),
            AnalysisPoint("operating_cash_flow_margin", "Operative Cashflow-Marge", "operating_cash_flow_margin", "operating_cash_flow_margin", "calculation", unit_hint="percent"),
            AnalysisPoint("free_cash_flow_margin", "FCF-Marge", "free_cash_flow_margin", "free_cash_flow_margin", "calculation", unit_hint="percent"),
        ),
    ),
    AnalysisSection(
        "financial_stability",
        "5. Finanzielle Stabilität und Liquidität",
        "Hier wird geprüft, ob Bilanz und kurzfristige Liquidität tragfähig wirken.",
        (
            AnalysisPoint("equity_ratio", "Eigenkapitalquote", "equity_ratio", "equity_ratio", "calculation", unit_hint="percent"),
            AnalysisPoint("cash_ratio", "Liquidität 1. Grades (Cash Ratio)", "cash_ratio", "cash_ratio", "calculation", unit_hint="multiple"),
            AnalysisPoint("quick_ratio", "Liquidität 2. Grades (Quick Ratio)", "quick_ratio", "quick_ratio", "calculation", unit_hint="multiple"),
            AnalysisPoint("current_ratio", "Liquidität 3. Grades (Current Ratio)", "current_ratio", "current_ratio", "calculation", unit_hint="multiple"),
            AnalysisPoint("anlage_deckung", "Anlagendeckung", None, "equity_ratio", "unsupported", NOT_CURRENTLY_IMPLEMENTED),
        ),
    ),
    AnalysisSection(
        "debt",
        "6. Verschuldung",
        "Verschuldung wird getrennt von Liquidität betrachtet, weil sie Unternehmenswert und Risiko beeinflusst.",
        (
            AnalysisPoint("debt_to_assets", "Schuldenquote", "debt_to_assets", "debt_to_assets", "calculation", unit_hint="percent"),
            AnalysisPoint("debt_to_equity", "Debt to Equity", "debt_to_equity", "debt_to_equity", "calculation", unit_hint="multiple"),
            AnalysisPoint("net_debt", "Nettoverschuldung", "net_debt", "net_debt", "calculation"),
            AnalysisPoint("net_debt_to_ebitda", "Nettoverschuldung / EBITDA", "net_debt_to_ebitda", "net_debt_to_ebitda", "calculation", unit_hint="multiple"),
            AnalysisPoint("long_term_debt_to_equity", "Long-Term Debt to Equity", None, "debt_to_equity", "unsupported", NOT_CURRENTLY_IMPLEMENTED),
            AnalysisPoint("short_term_debt_to_equity", "Short-Term Debt to Equity", None, "debt_to_equity", "unsupported", NOT_CURRENTLY_IMPLEMENTED),
            AnalysisPoint("interest_coverage", "Zinsdeckungsgrad", None, "operating_income", "unsupported", NOT_CURRENTLY_IMPLEMENTED),
            AnalysisPoint("net_cash_per_share", "Netto-Cash je Aktie", None, "net_debt", "unsupported", NOT_CURRENTLY_IMPLEMENTED),
        ),
    ),
    AnalysisSection(
        "working_capital",
        "7. Kapitalbindung / Working Capital",
        "Dieser Abschnitt zeigt, wie viel Kapital im laufenden Geschäft gebunden ist.",
        (
            AnalysisPoint("working_capital", "Nettoumlaufvermögen (Working Capital)", "working_capital", "working_capital", "calculation"),
            AnalysisPoint("working_capital_to_revenue", "Working Capital / Umsatz", "working_capital_to_revenue", "working_capital_to_revenue", "calculation", unit_hint="percent"),
            AnalysisPoint("receivables_days", "Forderungslaufzeit / Debitorenlaufzeit", "receivables_days", "receivables_days", "calculation", unit_hint="days"),
            AnalysisPoint("payables_days", "Verbindlichkeitenlaufzeit / Kreditorenlaufzeit", "payables_days", "payables_days", "calculation", unit_hint="days"),
            AnalysisPoint("inventory_intensity", "Vorratsintensität", "inventory_intensity", "inventory_intensity", "calculation", unit_hint="percent"),
            AnalysisPoint("inventory_days", "Lagerdauer", "inventory_days", "inventory_days", "calculation", unit_hint="days"),
            AnalysisPoint("working_capital_difference", "Differenz Working Capital", None, "working_capital", "unsupported", NOT_CURRENTLY_IMPLEMENTED),
        ),
    ),
    AnalysisSection(
        "cashflow_quality_allocation",
        "9. Cashflow-Qualität / Kapitalallokation",
        "Hier wird sichtbar, wie Cashflow, Investitionen und Ausschüttungen zusammenspielen.",
        (
            AnalysisPoint("operating_cash_flow_margin", "Operative Cashflow-Marge", "operating_cash_flow_margin", "operating_cash_flow_margin", "calculation", unit_hint="percent"),
            AnalysisPoint("free_cash_flow_margin", "FCF-Marge", "free_cash_flow_margin", "free_cash_flow_margin", "calculation", unit_hint="percent"),
            AnalysisPoint("capex_ratio", "Sachinvestitionen / operativer Cashflow", "capex_ratio", "capex_ratio", "calculation", unit_hint="percent"),
            AnalysisPoint("dividends_paid", "Dividendenzahlungen", "dividends_paid", "dividends_paid", "base", PARTIAL),
        ),
    ),
    AnalysisSection(
        "valuation_multiples",
        "10. Bewertungskennzahlen",
        "Bewertungskennzahlen ordnen Marktpreis, Ertragskraft, Cashflow und Unternehmenswert ein.",
        (
            AnalysisPoint("market_cap", "Marktkapitalisierung", "market_cap", "market_cap", "market"),
            AnalysisPoint("enterprise_value", "Unternehmenswert (EV)", "enterprise_value", "enterprise_value", "market"),
            AnalysisPoint("latest_fy_pe", "Kurs-Gewinn-Verhältnis (KGV)", "latest_fy_pe", "latest_fy_pe", "valuation", unit_hint="multiple"),
            AnalysisPoint("latest_fy_p_fcf", "Kurs-FCF-Verhältnis", "latest_fy_p_fcf", "latest_fy_p_fcf", "valuation", unit_hint="multiple"),
            AnalysisPoint("latest_fy_ev_ebit", "EV / EBIT", "latest_fy_ev_ebit", "latest_fy_ev_ebit", "valuation", unit_hint="multiple"),
            AnalysisPoint("latest_fy_ev_ebitda", "EV / EBITDA", "latest_fy_ev_ebitda", "latest_fy_ev_ebitda", "valuation", unit_hint="multiple"),
            AnalysisPoint("price_to_book", "Kurs-Buchwert-Verhältnis (KBV)", None, "shareholders_equity", "unsupported", NOT_CURRENTLY_IMPLEMENTED),
            AnalysisPoint("price_to_cash_flow", "Kurs-Cashflow-Verhältnis (KCV)", None, "operating_cash_flow", "unsupported", NOT_CURRENTLY_IMPLEMENTED),
            AnalysisPoint("ev_to_sales", "EV / Umsatz", None, "enterprise_value", "unsupported", NOT_CURRENTLY_IMPLEMENTED),
            AnalysisPoint("ev_to_fcf", "EV / FCF", None, "enterprise_value", "unsupported", NOT_CURRENTLY_IMPLEMENTED),
        ),
    ),
    AnalysisSection(
        "dcf",
        "11. DCF-Bewertung",
        "Die DCF-Bewertung wird als nachvollziehbare Schrittfolge gezeigt.",
        (
            AnalysisPoint("base_fcf", "Schritt 1 - Ausgangs-Cashflow bestimmen", "base_fcf", "base_fcf", "assumption"),
            AnalysisPoint("growth_rate", "Schritt 2 - Wachstum festlegen", "growth_rate", "growth_rate", "assumption", unit_hint="percent"),
            AnalysisPoint("discount_rate", "Schritt 3 - Diskontierungszins festlegen", "discount_rate", "discount_rate", "assumption", unit_hint="percent"),
            AnalysisPoint("terminal_growth_rate", "Schritt 4 - Ewige Wachstumsrate festlegen", "terminal_growth_rate", "terminal_growth_rate", "assumption", unit_hint="percent"),
            AnalysisPoint("projection_years", "Schritt 5 - Planungszeitraum prüfen", "projection_years", "projection_years", "assumption", unit_hint="number"),
            AnalysisPoint("fair_value", "Schritt 6 - Fairen Wert je Aktie bestimmen", "fair_value", "fair_value", "valuation"),
            AnalysisPoint("margin_of_safety", "Schritt 7 - Sicherheitsmarge betrachten", "margin_of_safety", "margin_of_safety", "valuation", unit_hint="percent"),
        ),
    ),
    AnalysisSection(
        "quality",
        "12. Multiplikatoren-/Qualitätsbetrachtung",
        "Qualität, Bewertungsniveau und Datenvertrauen werden getrennt gelesen.",
        (
            AnalysisPoint("quality_summary", "Unternehmensqualität", "quality_summary", "quality_summary", "quality", unit_hint="number"),
            AnalysisPoint("data_confidence", "Datenvertrauen", "data_confidence", "data_confidence", "quality", unit_hint="number"),
        ),
    ),
    AnalysisSection(
        "summary",
        "13. Zusammenfassung",
        "Am Ende werden Stärken, offene Prüfungen und die Bewertungsbandbreite zusammengeführt.",
        (
            AnalysisPoint("summary", "Zusammenfassung", "summary", "summary", "summary"),
        ),
    ),
)


TABLE_SECTION_KEYS = tuple(section.key for section in ANALYSIS_SECTIONS)
