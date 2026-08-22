from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from stock_valuation.data.resolution import load_preferred_financial_facts
from stock_valuation.database.models import Analysis, FinancialFactSnapshot


@dataclass(frozen=True)
class AuditCheck:
    year: int
    check_id: str
    label: str
    status: str
    deviation_pct: Decimal | None
    detail: str


def _relative_difference(left: Decimal, right: Decimal) -> Decimal | None:
    if right == 0:
        return None
    return abs(left - right) / abs(right) * Decimal("100")


def run_deterministic_audit(session: Session, analysis: Analysis) -> list[AuditCheck]:
    """Run provider-independent consistency checks on preferred stored annual facts."""
    facts = load_preferred_financial_facts(session, analysis.id)
    by_year: dict[int, dict[str, FinancialFactSnapshot]] = {}
    for fact in facts:
        if fact.value is None:
            continue
        by_year.setdefault(fact.period_end.year, {})[fact.metric] = fact

    checks: list[AuditCheck] = []
    for year in sorted(by_year)[-5:]:
        row = by_year[year]

        revenue = row.get("revenue")
        cost = row.get("cost_of_revenue")
        gross = row.get("gross_profit")
        if revenue and cost and gross:
            expected = revenue.value - cost.value
            deviation = _relative_difference(gross.value, expected)
            status = "PASS" if deviation is not None and deviation <= Decimal("0.5") else "CHECK"
            checks.append(
                AuditCheck(
                    year,
                    "gross_profit_identity",
                    "Bruttogewinn = Umsatz − Umsatzkosten",
                    status,
                    deviation,
                    f"gemeldet {gross.value}; rechnerisch {expected}",
                )
            )

        assets = row.get("total_assets")
        liabilities = row.get("total_liabilities")
        equity = row.get("shareholders_equity")
        if assets and liabilities and equity:
            expected = liabilities.value + equity.value
            deviation = _relative_difference(assets.value, expected)
            status = "PASS" if deviation is not None and deviation <= Decimal("2") else "CHECK"
            checks.append(
                AuditCheck(
                    year,
                    "balance_sheet_identity",
                    "Bilanzsumme ≈ Verbindlichkeiten + Eigenkapital",
                    status,
                    deviation,
                    f"Assets {assets.value}; Liabilities + Equity {expected}",
                )
            )

        current_assets = row.get("current_assets")
        if assets and current_assets:
            status = "PASS" if current_assets.value <= assets.value else "CHECK"
            checks.append(
                AuditCheck(
                    year,
                    "current_assets_le_assets",
                    "Umlaufvermögen ≤ Bilanzsumme",
                    status,
                    None,
                    f"Current Assets {current_assets.value}; Total Assets {assets.value}",
                )
            )

        current_liabilities = row.get("current_liabilities")
        if liabilities and current_liabilities:
            status = "PASS" if current_liabilities.value <= liabilities.value else "CHECK"
            checks.append(
                AuditCheck(
                    year,
                    "current_liabilities_le_liabilities",
                    "Kurzfristige Verbindlichkeiten ≤ Gesamtverbindlichkeiten",
                    status,
                    None,
                    f"Current Liabilities {current_liabilities.value}; Total Liabilities {liabilities.value}",
                )
            )

        cash = row.get("cash_and_equivalents")
        if cash and current_assets:
            status = "PASS" if cash.value <= current_assets.value else "CHECK"
            checks.append(
                AuditCheck(
                    year,
                    "cash_le_current_assets",
                    "Cash ≤ Umlaufvermögen",
                    status,
                    None,
                    f"Cash {cash.value}; Current Assets {current_assets.value}",
                )
            )

    return checks


def build_ai_review_prompt(session: Session, analysis: Analysis, *, years: int = 3) -> str:
    """Build a self-contained deep-review prompt from the stored snapshot.

    The prompt is intentionally model/provider agnostic. A future API integration can execute
    this exact package with a web-enabled model. Until then it can be copied into ChatGPT.
    """
    facts = load_preferred_financial_facts(session, analysis.id)
    available_years = sorted({fact.period_end.year for fact in facts})
    selected_years = set(available_years[-years:])
    selected = [fact for fact in facts if fact.period_end.year in selected_years]
    checks = run_deterministic_audit(session, analysis)

    fact_lines = []
    for fact in sorted(selected, key=lambda item: (item.period_end.year, item.metric)):
        if fact.value is None:
            continue
        fact_lines.append(
            " | ".join(
                [
                    str(fact.period_end.year),
                    fact.metric,
                    str(fact.value),
                    fact.currency or "",
                    fact.provider or "",
                    fact.provider_field or "",
                    fact.source_url or "",
                ]
            )
        )

    check_lines = [
        f"{item.year} | {item.status} | {item.label} | Abweichung={item.deviation_pct} | {item.detail}"
        for item in checks
    ]

    return f"""Du bist Datenprüfer für eine fundamentale Aktienanalyse.

Unternehmen: {analysis.company.name}
Ticker: {analysis.company.ticker}
ISIN: {analysis.company.isin or 'nicht hinterlegt'}
Analyse-Stichtag: {analysis.as_of_date}

AUFGABE
Prüfe die unten importierten Finanzzahlen gegen belastbare öffentliche Primärquellen. Bevorzuge in dieser Reihenfolge:
1. offiziellen Geschäftsbericht / Annual Report / 10-K / 20-F / regulatorisches Filing,
2. Investor-Relations-Finanzstatements,
3. erst danach hochwertige Sekundärquellen zum Cross-Check.

Regeln:
- Keine Zahl aufgrund bloßer Plausibilität als korrekt markieren.
- Geschäftsjahr, Berichtswährung, Einheit und Konsolidierungskreis beachten.
- Quartalszahlen nicht mit Jahreszahlen verwechseln.
- Providerfelder können semantisch breiter oder enger sein als die Unternehmenszeile.
- Restatements und abweichende Rechnungslegungsstandards ausdrücklich nennen.
- Keine stillen Korrekturen durchführen.
- Wenn eine Zahl nicht sicher prüfbar ist, Status UNKLAR statt raten.
- Für jede vorgeschlagene Korrektur eine konkrete offizielle Quellen-URL und die offizielle Abschlussbezeichnung nennen.

IMPORTIERTE FAKTEN
Format: Jahr | interner Schlüssel | Wert | Währung | Quelle | Provider-Feld | gespeicherte Quell-URL
{chr(10).join(fact_lines)}

INTERNE PLAUSIBILITÄTSCHECKS
{chr(10).join(check_lines) if check_lines else 'Keine Checks verfügbar.'}

AUSGABE
Erstelle zuerst eine kurze Zusammenfassung der Datenqualität. Danach eine Tabelle mit exakt diesen Spalten:
Jahr | Interner Schlüssel | Importierter Wert | Offizieller Wert | Abweichung % | Status (PASS/WARN/FAIL/UNKLAR) | Offizielle Bezeichnung | Offizielle Quelle | Begründung

Prüfe besonders Umsatz, Gross Profit, Operating Income/EBIT, Net Income, Total Assets, Equity, Cash, Forderungen, Vorräte, Verbindlichkeiten, Operating Cash Flow, CAPEX und D&A. Weisen Providerfeld und offizielle Zeile unterschiedliche Definitionen auf, erkläre die Abweichung statt Werte gewaltsam gleichzusetzen.

Schließe mit einer Liste 'Korrekturvorschläge'. Jeder Eintrag muss enthalten:
- Jahr
- interner Schlüssel
- vorgeschlagener Wert
- Währung
- offizielle Quelle
- Begründung
Wenn keine Korrektur sicher belegt ist, schreibe ausdrücklich 'Keine sichere Korrektur'.
"""
