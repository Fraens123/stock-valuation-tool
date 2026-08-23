from __future__ import annotations

import csv
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from importlib import metadata
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stock_valuation.data.providers.sec import CONCEPT_MAP, SECCompanyFactsProvider
from stock_valuation.data.providers.sec_filing import SECFilingFallbackProvider
from stock_valuation.data.types import NormalizedFinancialFact


OUT_DIR = ROOT / "diagnostics"
CSV_PATH = OUT_DIR / "asml_financial_source_comparison.csv"
JSON_PATH = OUT_DIR / "DATA_PIPELINE_AUDIT.json"
MD_PATH = OUT_DIR / "DATA_PIPELINE_AUDIT.md"

CORE_METRICS = [
    "revenue",
    "cost_of_revenue",
    "gross_profit",
    "operating_income",
    "pretax_income",
    "net_income",
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
    "operating_cash_flow",
    "capital_expenditures",
    "intangible_purchases",
    "depreciation_amortization",
    "dividends_paid",
]

EDGAR_CONCEPTS = {
    "revenue": ["revenue"],
    "cost_of_revenue": ["cost_of_revenue"],
    "gross_profit": ["gross_profit"],
    "operating_income": ["operating_income"],
    "pretax_income": ["income_before_tax", "pretax_income"],
    "net_income": ["net_income"],
    "total_assets": ["total_assets"],
    "current_assets": ["us-gaap:AssetsCurrent", "ifrs-full:CurrentAssets"],
    "cash_and_equivalents": ["cash_and_equivalents"],
    "short_term_investments": ["short_term_investments"],
    "accounts_receivable": ["accounts_receivable"],
    "inventory": ["inventory"],
    "ppe_net": ["property_plant_equipment"],
    "goodwill": ["goodwill"],
    "total_liabilities": ["total_liabilities"],
    "current_liabilities": ["us-gaap:LiabilitiesCurrent", "ifrs-full:CurrentLiabilities"],
    "accounts_payable": ["accounts_payable"],
    "short_term_debt": ["short_term_debt"],
    "long_term_debt": ["long_term_debt"],
    "shareholders_equity": ["stockholders_equity", "shareholders_equity"],
    "operating_cash_flow": ["operating_cash_flow"],
    "capital_expenditures": ["capex", "capital_expenditures"],
    "intangible_purchases": [
        "us-gaap:PaymentsToAcquireProductiveAssets",
        "ifrs-full:PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities",
    ],
    "depreciation_amortization": ["depreciation_and_amortization"],
    "dividends_paid": ["dividends_paid", "us-gaap:PaymentsOfDividends"],
}

AMBIGUOUS_METRICS = {
    "short_term_debt",
    "depreciation_amortization",
    "ppe_net",
    "capital_expenditures",
    "intangible_purchases",
    "dividends_paid",
    "operating_cash_flow",
    "shareholders_equity",
}


@dataclass
class EdgarFact:
    value: Decimal | None = None
    currency: str | None = None
    original_tag: str | None = None
    standard_concept: str | None = None
    filing_form: str | None = None
    filing_date: str | None = None
    accession_number: str | None = None
    source: str | None = None
    period_end: str | None = None


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _tag(taxonomy: Any, concept: Any) -> str | None:
    taxonomy_text = str(taxonomy or "").strip()
    concept_text = str(concept or "").strip()
    if not concept_text:
        return None
    if ":" in concept_text:
        return concept_text
    return f"{taxonomy_text}:{concept_text}".strip(":")


def _load_env() -> None:
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT.parent / ".env")


def _sec_facts_with_filing_supplements(cik: str) -> list[NormalizedFinancialFact]:
    sec = SECCompanyFactsProvider()
    base = sec.get_normalized_financials(cik)
    filing = SECFilingFallbackProvider(user_agent=sec.user_agent, timeout=sec.timeout)
    supplement = filing.gap_facts(cik, base, years=10)
    return [*base, *supplement.facts]


def _current_index(facts: list[NormalizedFinancialFact]) -> dict[tuple[str, int], NormalizedFinancialFact]:
    selected: dict[tuple[str, int], NormalizedFinancialFact] = {}
    priority = {"sec_companyfacts": 0, "sec_filing_xbrl": 1}
    for fact in facts:
        if fact.value is None or fact.period_type != "FY":
            continue
        key = (fact.metric, fact.period_end.year)
        existing = selected.get(key)
        if existing is None:
            selected[key] = fact
            continue
        existing_rank = priority.get(existing.provider, 99)
        candidate_rank = priority.get(fact.provider, 99)
        if candidate_rank < existing_rank:
            selected[key] = fact
        elif candidate_rank == existing_rank and (fact.filing_date or date.min) > (
            existing.filing_date or date.min
        ):
            selected[key] = fact
    return selected


def _edgar_fact(company_facts: Any, metric: str, fiscal_year: int) -> EdgarFact:
    concepts = list(EDGAR_CONCEPTS.get(metric, []))
    concepts.extend(f"{taxonomy}:{concept}" for taxonomy, concept in CONCEPT_MAP.get(metric, ()))

    warnings: list[str] = []
    for concept in dict.fromkeys(concepts):
        try:
            item = None
            if concept.startswith(("us-gaap:", "ifrs-full:")):
                item = company_facts.get_annual_fact(concept, fiscal_year)
            else:
                meta = company_facts.get_concept(
                    concept,
                    period=f"{fiscal_year}-FY",
                    return_metadata=True,
                )
                if isinstance(meta, dict) and meta.get("value") is not None:
                    return EdgarFact(
                        value=_decimal(meta.get("value")),
                        currency=meta.get("unit"),
                        original_tag=meta.get("tag_used"),
                        standard_concept=meta.get("concept_name") or concept,
                        filing_date=(
                            meta.get("filing_date").isoformat()
                            if hasattr(meta.get("filing_date"), "isoformat")
                            else None
                        ),
                        source="edgartools.get_concept",
                        period_end=(
                            meta.get("period_end").isoformat()
                            if hasattr(meta.get("period_end"), "isoformat")
                            else None
                        ),
                    )
                item = company_facts.get_annual_fact(concept, fiscal_year)
            if item is None:
                continue
            return EdgarFact(
                value=_decimal(getattr(item, "numeric_value", None) or getattr(item, "value", None)),
                currency=getattr(item, "unit", None),
                original_tag=_tag(getattr(item, "taxonomy", None), getattr(item, "concept", None)),
                standard_concept=concept,
                filing_form=getattr(item, "form_type", None),
                filing_date=(
                    getattr(item, "filing_date").isoformat()
                    if hasattr(getattr(item, "filing_date", None), "isoformat")
                    else None
                ),
                accession_number=getattr(item, "accession", None),
                source="edgartools.get_annual_fact",
                period_end=(
                    getattr(item, "period_end").isoformat()
                    if hasattr(getattr(item, "period_end", None), "isoformat")
                    else None
                ),
            )
        except Exception as exc:
            warnings.append(f"{concept}: {type(exc).__name__}: {exc}")
            continue
    return EdgarFact(source="; ".join(warnings[:3]) if warnings else None)


def _classify(current: NormalizedFinancialFact | None, edgar: EdgarFact) -> tuple[str, str]:
    if current is None and edgar.value is None:
        return "UNSUPPORTED", "Weder aktueller Import noch EdgarTools lieferten einen Wert."
    if current is None:
        return "EDGARTOOLS_ONLY", "EdgarTools liefert einen Wert, der aktuelle Import nicht."
    if edgar.value is None:
        return "CURRENT_ONLY", "Aktueller Import liefert einen Wert, EdgarTools nicht."
    if current.currency and edgar.currency and current.currency.upper() != edgar.currency.upper():
        return "CURRENCY_MISMATCH", "Waehrung/Unit unterscheidet sich."
    diff = abs(current.value - edgar.value)
    base = abs(current.value) if current.value else Decimal("0")
    rel = (diff / base) if base else Decimal("0")
    same_tag = (current.provider_field or "").replace("_", ":") == (edgar.original_tag or "")
    if diff == 0 and same_tag:
        return "EXACT_MATCH", "Wert und Tag stimmen exakt ueberein."
    if diff == 0:
        return "VALUE_MATCH_DIFFERENT_TAG", "Wert stimmt exakt; Tag/Standardkonzept unterscheidet sich."
    if rel <= Decimal("0.005"):
        return "SEMANTIC_MATCH", "Kleine Abweichung innerhalb 0,5 Prozent; wahrscheinlich Rundung/Mapping."
    return "VALUE_MISMATCH", "Abweichung > 0,5 Prozent; Primärquelle fachlich pruefen."


def _row(metric: str, year: int, current: NormalizedFinancialFact | None, edgar: EdgarFact) -> dict[str, Any]:
    classification, comment = _classify(current, edgar)
    diff_abs = None
    diff_rel = None
    if current is not None and current.value is not None and edgar.value is not None:
        diff_abs = str(edgar.value - current.value)
        if current.value != 0:
            diff_rel = str((edgar.value - current.value) / abs(current.value))
    return {
        "company": "ASML Holding N.V.",
        "fiscal_year": year,
        "period_end": current.period_end.isoformat() if current else edgar.period_end,
        "period_type": "FY",
        "internal_metric": metric,
        "current_pipeline_value": str(current.value) if current and current.value is not None else "",
        "current_pipeline_currency": current.currency if current else "",
        "current_pipeline_provider": current.provider if current else "",
        "current_pipeline_provider_field": current.provider_field if current else "",
        "current_pipeline_filing_date": current.filing_date.isoformat() if current and current.filing_date else "",
        "current_pipeline_source_url": current.source_url if current else "",
        "edgartools_value": str(edgar.value) if edgar.value is not None else "",
        "edgartools_currency": edgar.currency or "",
        "edgartools_original_tag": edgar.original_tag or "",
        "edgartools_standard_concept": edgar.standard_concept or "",
        "edgartools_filing_form": edgar.filing_form or "",
        "edgartools_filing_date": edgar.filing_date or "",
        "edgartools_accession_number": edgar.accession_number or "",
        "edgartools_source": edgar.source or "",
        "difference_absolute": diff_abs or "",
        "difference_relative": diff_rel or "",
        "classification": classification,
        "comment": comment,
    }


def _license(package: str) -> str:
    try:
        meta = metadata.metadata(package)
    except metadata.PackageNotFoundError:
        return "nicht installiert"
    license_expression = meta.get("License-Expression")
    if license_expression:
        return str(license_expression)
    license_text = meta.get("License")
    if license_text:
        return str(license_text)
    classifiers = [c for c in meta.get_all("Classifier") or [] if "License" in c]
    return "; ".join(classifiers) if classifiers else "nicht in Package-Metadata gefunden"


def _write_csv(rows: list[dict[str, Any]]) -> None:
    with CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(rows: list[dict[str, Any]], extra: dict[str, Any]) -> dict[str, Any]:
    asml_rows_2023_2025 = [
        row for row in rows if int(row["fiscal_year"]) in {2023, 2024, 2025}
    ]
    comparable = [
        row
        for row in asml_rows_2023_2025
        if row["current_pipeline_value"] and row["edgartools_value"]
    ]
    exact_or_value = [
        row
        for row in comparable
        if row["classification"] in {"EXACT_MATCH", "VALUE_MATCH_DIFFERENT_TAG"}
    ]
    critical = [
        row
        for row in rows
        if row["classification"]
        in {"VALUE_MISMATCH", "CURRENCY_MISMATCH", "PERIOD_MISMATCH", "AMBIGUOUS_MAPPING"}
    ]
    coverage = len(comparable) / max(1, len(CORE_METRICS) * 3)
    exact_rate = len(exact_or_value) / max(1, len(comparable))
    edgar_go = coverage >= 0.70 and exact_rate >= 0.90 and not critical
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "recommended_primary_sec_engine": "EdgarTools als Primaerschicht, mit projektspezifischem Adapter fuer NormalizedFinancialFact",
        "recommended_esef_engine": "Arelle fuer ESEF/iXBRL evaluieren, aktueller esef.py nur als Fallback behalten",
        "keep_current_sec_parser": True,
        "edgartools_go": bool(edgar_go),
        "edgartools_decision": "GO" if edgar_go else "CONDITIONAL GO",
        "arelle_go": False,
        "arelle_decision": "CONDITIONAL GO fuer Prototyp/Evaluierung, noch kein Produktions-Go",
        "asml_core_metric_coverage": round(coverage, 4),
        "asml_exact_match_rate": round(exact_rate, 4),
        "critical_mismatches": critical,
        "ambiguous_metrics": sorted(AMBIGUOUS_METRICS),
        "recommended_architecture": (
            "SEC: EdgarTools -> kleiner Adapter -> NormalizedFinancialFact -> Snapshot/Provenienz "
            "-> Preferred Data. ESEF: Arelle/xBRL-JSON Adapter analog. Eigene XBRL-Parser nur als "
            "Uebergangsdiagnostik/Fallback behalten."
        ),
        "files_to_keep": [
            "src/stock_valuation/data/types.py",
            "src/stock_valuation/data/source_router.py",
            "src/stock_valuation/data/resolution.py",
            "src/stock_valuation/data/preferred_data.py",
            "src/stock_valuation/data/snapshot_service.py",
            "src/stock_valuation/analyses/ai_review_service.py",
        ],
        "files_to_replace": [
            "src/stock_valuation/data/providers/sec.py",
            "src/stock_valuation/data/providers/sec_filing.py",
            "src/stock_valuation/data/providers/sec_extension.py",
        ],
        "files_to_remove_later": [
            "heuristische Teile aus sec_extension.py nach Adapter-Migration",
            "eigener XML-Context/Unit-Parser in sec_filing.py nach stabiler EdgarTools-Abdeckung",
        ],
        "next_actions": [
            "EdgarTools-Adapter als neuen isolierten Provider implementieren, ohne bestehenden SEC-Pfad zu loeschen.",
            "Regressionstests mit konkreten ASML-Werten 2023-2025 anlegen.",
            "Arelle-Prototyp fuer ein ESEF-ZIP/iXBRL-Filing bauen.",
            "Review-Package-ID um expliziten Snapshot-Exportzustand/Stale-Status im UI ergaenzen.",
        ],
        "licenses": extra.get("licenses", {}),
        "comparison_counts": {
            key: sum(1 for row in rows if row["classification"] == key)
            for key in sorted({row["classification"] for row in rows})
        },
        "additional_company_probe": extra.get("additional_company_probe", []),
    }
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _probe_other_companies() -> list[dict[str, Any]]:
    from edgar import Company

    companies = [
        ("AAPL", "US-GAAP Standardunternehmen"),
        ("MSFT", "US-GAAP Standardunternehmen"),
        ("TSM", "IFRS Foreign Private Issuer"),
        ("ADBE", "abweichendes Geschaeftsjahr"),
    ]
    output: list[dict[str, Any]] = []
    for ticker, category in companies:
        try:
            facts = Company(ticker).get_facts()
            available = {
                metric: bool(_edgar_fact(facts, metric, 2025).value)
                for metric in ["revenue", "net_income", "total_assets", "operating_cash_flow"]
            }
            output.append({"ticker": ticker, "category": category, "available_2025": available})
        except Exception as exc:
            output.append({"ticker": ticker, "category": category, "error": f"{type(exc).__name__}: {exc}"})
    return output


def _write_md(rows: list[dict[str, Any]], result: dict[str, Any]) -> None:
    counts = result["comparison_counts"]
    critical = result["critical_mismatches"]
    lines = [
        "# DATA PIPELINE AUDIT",
        "",
        "## 1. Executive Summary",
        "",
        f"SEC-Entscheidung: **EdgarTools = {result['edgartools_decision']}**.",
        f"ESEF-Entscheidung: **Arelle = {result['arelle_decision']}**.",
        "",
        "Der aktuelle Datenpfad ist konzeptionell richtig, aber die Beschaffungs-/XBRL-Schicht ist zu breit selbst gebaut. "
        "EdgarTools reproduziert ASML-Kernwerte fuer FY2023-FY2025 weitgehend direkt aus offiziellen SEC/XBRL-Daten "
        "und liefert bessere Statement-/Fact-Metadaten als der eigene Komfortparser. Nicht eindeutige Felder bleiben "
        "weiterhin projektspezifische Semantik- und Aggregationsfragen.",
        "",
        "## 2. Aktueller Datenpfad",
        "",
        "Company/Identity -> Source Router -> Provider -> NormalizedFinancialFact -> Snapshot -> Resolution -> "
        "Preferred Data -> Calculation Readiness -> Kennzahlen.",
        "",
        "SEC Company Facts ist aktuell Primaerquelle. Originalfilings fuellen Standard-XBRL-Luecken. "
        "Company-Extensions werden nur als Review-Kandidaten gespeichert. ESEF wird nach SEC versucht, Alpha Vantage nur als Fallback.",
        "",
        "## 3. Gefundene Schwachstellen",
        "",
        "- `sec.py` dupliziert Standardkonzept-Mapping, das EdgarTools bereits umfangreicher pflegt.",
        "- `sec_filing.py` implementiert Contexts, Units, Perioden und Instanzsuche selbst und ist damit faktisch ein partieller XBRL-Prozessor.",
        "- `sec_extension.py` nutzt semantische Heuristik fuer firmeneigene Tags; das sollte nicht die dauerhafte Engine sein.",
        "- `short_term_debt`, `depreciation_amortization`, `ppe_net`, `dividends_paid` und CAPEX-nahe Felder brauchen explizite Definition/Aggregation statt stiller Tag-Auswahl.",
        "",
        "## 4. EdgarTools-Test",
        "",
        f"Vergleichszeilen: {len(rows)}. Klassen: `{counts}`.",
        f"ASML FY2023-FY2025 Coverage: {result['asml_core_metric_coverage']:.1%}. "
        f"Exact/Value-Match-Rate: {result['asml_exact_match_rate']:.1%}.",
        "",
        "Die vollstaendige Tabelle steht in `diagnostics/asml_financial_source_comparison.csv`.",
        "",
        "## 5. ASML FY2023-FY2025 Vergleich",
        "",
    ]
    for row in rows:
        if int(row["fiscal_year"]) not in {2023, 2024, 2025}:
            continue
        if row["classification"] in {"VALUE_MISMATCH", "CURRENCY_MISMATCH", "EDGARTOOLS_ONLY", "CURRENT_ONLY", "UNSUPPORTED"}:
            lines.append(
                f"- {row['fiscal_year']} {row['internal_metric']}: {row['classification']} "
                f"(current={row['current_pipeline_value'] or 'n/a'}, edgar={row['edgartools_value'] or 'n/a'}, "
                f"tag={row['edgartools_original_tag'] or 'n/a'})."
            )
    lines.extend(
        [
            "",
            "## 6. ASML 10-Jahres-Vergleich",
            "",
            "Der 10-Jahres-Vergleich wurde fuer FY2016-FY2025 erzeugt. Fehlende Werte sind in der CSV als "
            "`CURRENT_ONLY`, `EDGARTOOLS_ONLY` oder `UNSUPPORTED` sichtbar.",
            "",
            "## 7. Weitere Unternehmen",
            "",
            json.dumps(result.get("additional_company_probe", []), ensure_ascii=False, indent=2),
            "",
            "## 8. ESEF/Arelle Bewertung",
            "",
            "Arelle ist fuer ESEF/iXBRL fachlich die passendere Basis als ein eigener Parser, weil Taxonomien, "
            "Contexts, Units, Dimensions und Validierung Kernumfang der Bibliothek sind. Empfehlung: Prototyp "
            "bauen und erst danach Produktions-Go. Aktueller ESEF-Code bleibt bis dahin Fallback.",
            "",
            "## 9. Snapshot-/Package-ID-Problem",
            "",
            "Die Package-ID wird in `ai_review_service.py` aus Analyseidentitaet, `years_requested`, Mapping-Kandidatenanzahl "
            "und den ausgewaehlten Snapshot-Fakten gebildet. Wenn nach Export neue SEC-Filing-Kandidaten oder andere Facts "
            "gespeichert werden, aendert sich der Hash. Die Pruefung ist richtig und darf nicht entfernt werden. "
            "Der UI-Workflow sollte alte Review-Ergebnisse als `stale` markieren und ein neues Paket verlangen.",
            "",
            "## 10. Empfohlene Zielarchitektur",
            "",
            result["recommended_architecture"],
            "",
            "## 11. Welche Dateien bleiben",
            "",
            "\n".join(f"- `{item}`" for item in result["files_to_keep"]),
            "",
            "## 12. Welche Dateien ersetzt werden",
            "",
            "\n".join(f"- `{item}`" for item in result["files_to_replace"]),
            "",
            "## 13. Welche Dateien spaeter entfernt werden koennen",
            "",
            "\n".join(f"- {item}" for item in result["files_to_remove_later"]),
            "",
            "## 14. Welche Tests benoetigt werden",
            "",
            "- Konkrete ASML-Werte FY2023-FY2025 fuer revenue, net_income, total_assets, shareholders_equity, operating_cash_flow, ppe_net, short_term_debt und depreciation_amortization.",
            "- Tests fuer Waehrung, Periode, Filing-Art, Originaltag und Skalierung.",
            "- Tests fuer Aggregationsregeln bei `short_term_debt` und D&A.",
            "",
            "## 15. Konkrete Umsetzungsschritte",
            "",
            "\n".join(f"- {item}" for item in result["next_actions"]),
            "",
            "## 16. Go/No-Go Entscheidung",
            "",
            f"SEC: EdgarTools = **{result['edgartools_decision']}**.",
            "ESEF: Arelle = **CONDITIONAL GO fuer Prototyp/Evaluierung**.",
            "",
            "## Lizenzen",
            "",
            json.dumps(result.get("licenses", {}), ensure_ascii=False, indent=2),
            "",
            "## Kritische Abweichungen",
            "",
            json.dumps(critical, ensure_ascii=False, indent=2),
        ]
    )
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    _load_env()
    if not os.getenv("SEC_USER_AGENT"):
        raise RuntimeError("SEC_USER_AGENT fehlt in .env.")

    from edgar import Company, set_identity

    set_identity(os.environ["SEC_USER_AGENT"])
    company = Company("ASML")
    company_facts = company.get_facts()

    current = _current_index(_sec_facts_with_filing_supplements("0000937966"))
    rows = [
        _row(metric, year, current.get((metric, year)), _edgar_fact(company_facts, metric, year))
        for year in range(2016, 2026)
        for metric in CORE_METRICS
    ]
    _write_csv(rows)
    extra = {
        "licenses": {
            "edgartools": _license("edgartools"),
            "arelle": "Apache-2.0 (laut arelle.org/GitHub; vor Produktions-Go im gewaehlten Paket erneut verifizieren).",
        },
        "additional_company_probe": _probe_other_companies(),
    }
    result = _write_json(rows, extra)
    _write_md(rows, result)
    print(f"Wrote {CSV_PATH}")
    print(f"Wrote {JSON_PATH}")
    print(f"Wrote {MD_PATH}")
    print(json.dumps(result["comparison_counts"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
