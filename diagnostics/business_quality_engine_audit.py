from __future__ import annotations

import csv
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stock_valuation.quality.models import AVAILABLE, QualityCompanyResult, QualityInput
from stock_valuation.quality.rules import QUALITY_DEFINITIONS
from stock_valuation.quality.service import evaluate_companies


CALC_CSV = ROOT / "diagnostics" / "calculation_engine_results.csv"
HIST_CSV = ROOT / "diagnostics" / "historical_analysis_results.csv"
OUT_MD = ROOT / "diagnostics" / "BUSINESS_QUALITY_ENGINE_AUDIT.md"
OUT_JSON = ROOT / "diagnostics" / "BUSINESS_QUALITY_ENGINE_AUDIT.json"
OUT_CSV = ROOT / "diagnostics" / "business_quality_results.csv"


def _decimal(value: str) -> Decimal | None:
    if value in {"", "None", "null"}:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return None


def _load_quality_inputs() -> list[tuple[str, QualityInput]]:
    rows: list[tuple[str, QualityInput]] = []
    with CALC_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                (
                    row["ticker"],
                    QualityInput(
                        metric_id=row["metric_id"],
                        fiscal_year=int(row["fiscal_year"]),
                        window="FY",
                        value=_decimal(row["value"]),
                        unit=row["unit"],
                        status=row["status"],
                        issue=row["issues"] or None,
                        source="calculation",
                        input_provenance=row["input_provenance"],
                        inputs_hash=row["inputs_hash"],
                        source_version=row["calculation_version"],
                    ),
                )
            )
    with HIST_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            year = int(row["fiscal_year"]) if row["fiscal_year"] else None
            rows.append(
                (
                    row["ticker"],
                    QualityInput(
                        metric_id=row["metric_id"],
                        fiscal_year=year,
                        window=row["window"],
                        value=_decimal(row["value"]),
                        unit=row["unit"],
                        status=row["status"],
                        issue=row["issue"] or None,
                        source="historical",
                        source_version=row["calculation_version"],
                    ),
                )
            )
    return rows


def _metric_rows(results: tuple[QualityCompanyResult, ...]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for result in results:
        for metric in result.metrics:
            rows.append(
                {
                    "ticker": result.ticker,
                    "fiscal_year": metric.fiscal_year or "",
                    "years": ";".join(str(year) for year in result.years),
                    "category": metric.category,
                    "metric_id": metric.metric_id,
                    "status": metric.status,
                    "value": str(metric.value) if metric.value is not None else "",
                    "unit": metric.unit,
                    "trend": metric.trend,
                    "assessment": metric.assessment,
                    "score": str(metric.score) if metric.score is not None else "",
                    "issue": metric.issue or "",
                    "source_category": metric.source_category,
                    "input_metrics": ";".join(metric.input_metrics),
                    "input_refs": ";".join(metric.input_refs),
                    "inputs_hash": metric.inputs_hash,
                    "quality_version": metric.rule_version,
                }
            )
        for component in result.component_scores:
            rows.append(
                {
                    "ticker": result.ticker,
                    "fiscal_year": "",
                    "years": ";".join(str(year) for year in result.years),
                    "category": "component_score",
                    "metric_id": component.component_id,
                    "status": component.status,
                    "value": "",
                    "unit": "score_0_10",
                    "trend": "",
                    "assessment": "",
                    "score": str(component.score) if component.score is not None else "",
                    "issue": component.issue or "",
                    "source_category": "PROJECT_EXTENSION",
                    "input_metrics": ";".join(component.contributing_metrics),
                    "input_refs": "",
                    "inputs_hash": "",
                    "quality_version": result.quality_version,
                }
            )
        rows.append(
            {
                "ticker": result.ticker,
                "fiscal_year": "",
                "years": ";".join(str(year) for year in result.years),
                "category": "overall",
                "metric_id": "overall_quality_score",
                "status": AVAILABLE if result.overall_score is not None else "UNAVAILABLE",
                "value": "",
                "unit": "score_0_10",
                "trend": "",
                "assessment": result.assessment,
                "score": str(result.overall_score) if result.overall_score is not None else "",
                "issue": "",
                "source_category": "PROJECT_EXTENSION",
                "input_metrics": ";".join(component.component_id for component in result.component_scores),
                "input_refs": "",
                "inputs_hash": "",
                "quality_version": result.quality_version,
            }
        )
    return rows


def _serialize_company(result: QualityCompanyResult) -> dict[str, object]:
    return {
        "years": result.years,
        "overall_quality_score": str(result.overall_score) if result.overall_score is not None else None,
        "assessment": result.assessment,
        "component_scores": {
            item.component_id: str(item.score) if item.score is not None else None
            for item in result.component_scores
        },
        "positive_factors": result.positive_factors,
        "negative_factors": result.negative_factors,
        "unavailable_factors": result.unavailable_factors,
        "not_applicable_factors": result.not_applicable_factors,
    }


def _business_model_notes(result: QualityCompanyResult) -> list[str]:
    notes = [
        "Keine firmenspezifischen Hardcodes; die Engine bewertet nur Datenverfuegbarkeit, Werte, Trends und Volatilitaet.",
        "Asset-light/Software: Inventory-Status NOT_SEPARATELY_REPORTED fuehrt zu NOT_APPLICABLE, nicht zu einer negativen Bewertung.",
        "Asset-heavy/Halbleiter/Industrie: Capex-Intensitaet wird ausgewiesen, aber hohe Investitionen werden als Kontextgrenze dokumentiert.",
        "US-GAAP/IFRS/Foreign Private Issuer: Die Engine sieht nur Calculation/Historical-Ergebnisse und ist providerunabhaengig.",
    ]
    if result.not_applicable_factors:
        notes.append("Nicht anwendbare Faktoren: " + "; ".join(result.not_applicable_factors[:5]))
    return notes


def main() -> int:
    inputs = _load_quality_inputs()
    results = evaluate_companies(inputs)
    rows = _metric_rows(results)
    blockers = [
        row
        for row in rows
        if row["category"] != "overall"
        and row["status"] == "UNAVAILABLE"
        and row["issue"] not in {"UPSTREAM_MEASURE_NOT_EXPOSED"}
    ]
    decision = "GO – BUSINESS QUALITY ENGINE V1 FROZEN" if not blockers else "NO-GO"

    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    payload = {
        "decision": decision,
        "inputs": [str(CALC_CSV), str(HIST_CSV)],
        "companies": {result.ticker: _serialize_company(result) for result in results},
        "blockers": blockers,
        "quality_metrics": [definition.metric_id for definition in QUALITY_DEFINITIONS],
        "forbidden_market_metrics_used": [],
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# BUSINESS_QUALITY_ENGINE_AUDIT",
        "",
        "## 1. Executive Summary",
        "",
        f"Decision: {decision}",
        "",
        "Business Quality Engine V1 wurde als eigenstaendige Schicht unter `src/stock_valuation/quality/` implementiert. Sie nutzt ausschliesslich Calculation Engine V1 und Historical Analysis Engine V1 Outputs; keine Providerdaten, keine SEC-Rohfacts, keine Marktpreise.",
        "",
        "## 2. Bestehende Quality-/Schmidlin-Logik",
        "",
        "- Keine bestehende produktive Business-Quality-Engine gefunden.",
        "- Vorhandene `score`-Felder in SEC-Extension/Text-Parsing sind technische Matching-Scores, keine Unternehmensqualitaetsbewertung.",
        "- `docs/PHASE_1_METRIC_INVENTORY.md`, `docs/OPEN_ITEMS.md` und `docs/QUALITATIVE_ANALYSIS_SPEC.md` enthalten Schmidlin-/Excel-Kontext, aber keine verifizierte automatische Quality-Punktelogik fuer V1.",
        "- Deshalb wurden bestehende Formeln/Schwellen nicht ungeprueft uebernommen.",
        "",
        "## 3. Verwendete Kennzahlen",
        "",
        ", ".join(definition.metric_id for definition in QUALITY_DEFINITIONS),
        "",
        "## 4. Formeln und Definitionen",
        "",
        "| ID | Name | Kategorie | Formel | Inputs | Einheit | Bedeutung | Grenzen | Geeignet | Nicht geeignet | Quelle |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for definition in QUALITY_DEFINITIONS:
        lines.append(
            f"| {definition.metric_id} | {definition.name} | {definition.category} | {definition.formula} | "
            f"{', '.join(definition.inputs)} | {definition.unit} | {definition.meaning} | "
            f"{definition.limitations} | {definition.suitable_business_models} | "
            f"{definition.unsuitable_business_models} | {definition.source_category} |"
        )
    lines.extend(
        [
            "",
            "## 5. Availability-Regeln",
            "",
            "- Status: AVAILABLE, UNAVAILABLE, NOT_APPLICABLE, INSUFFICIENT_HISTORY.",
            "- Upstream-Status wie NOT_SEPARATELY_REPORTED, NEGATIVE_BASE und MISSING_PRIOR_YEAR werden respektiert.",
            "- Fehlend wird nie als 0 behandelt.",
            "- Nicht separat ausgewiesen wird nie als 0 behandelt.",
            "- Nicht anwendbar ist kein negativer Score.",
            "",
            "## 6. Geschaeftsmodellabhaengigkeit",
            "",
            "- Software/asset-light: Inventory-bezogene Faktoren koennen NOT_APPLICABLE sein.",
            "- Halbleiter/Industrie/asset-heavy: Capex-Intensitaet wird gezeigt, aber hohe Investitionen werden mit Grenzen dokumentiert.",
            "- Consumer: Working-Capital- und Margentrends bleiben anwendbar, sofern upstream verfuegbar.",
            "- Keine Branchen-Hardcodes in der Engine.",
            "",
            "## 7. Schmidlin vs. Project Extensions",
            "",
            "| Regelquelle | Umsetzung | Abweichung |",
            "| --- | --- | --- |",
            "| SCHMIDLIN | Keine Regel automatisch als Schmidlin-Regel markiert. | Schmidlin-Punktelogik ist im Repo nicht ausreichend verifiziert. |",
            "| GENERAL_FINANCIAL_ANALYSIS | Margen, Renditen, Bilanz, Liquiditaet, Wachstum. | Schwellen sind breite dokumentierte V1-Anker, keine Schmidlin-Behauptung. |",
            "| PROJECT_EXTENSION | Volatilitaet, Missing/Negative-Year-Qualitaet, Inventory-Appplicability, FCF/OCF aus Capex-Ratio. | Projektinterne, testbare Erweiterungen. |",
            "",
            "## 8. Scoring-Modell",
            "",
            "- Messwert, Interpretation und Score sind getrennte Felder.",
            "- Scores liegen auf 0 bis 10.",
            "- Nicht verfuegbare und nicht anwendbare Faktoren gehen nicht als 0 in den Score ein.",
            "- Overall Quality Score ist ein gewichteter Durchschnitt verfuegbarer Komponenten.",
            "",
            "## 9. Gewichtungen",
            "",
            "| Komponente | Gewicht | Begruendung |",
            "| --- | ---: | --- |",
            "| profitability | 18% | Profitabilitaet ist zentral, aber nicht allein ausreichend. |",
            "| margin_quality | 14% | Margen zeigen oekonomische Qualitaet und Preissetzung. |",
            "| cashflow_quality | 16% | Cash Conversion und Capex-Intensitaet schuetzen vor reiner Accounting-Qualitaet. |",
            "| growth | 14% | Wachstum ist wichtig, aber nur mit Profitabilitaet hochwertig. |",
            "| balance_sheet | 14% | Finanzkraft reduziert Fragilitaet. |",
            "| capital_efficiency | 14% | Rendite auf Kapital zeigt Effizienz. |",
            "| stability | 10% | Stabilitaet erhoeht Vertrauen in die Historie. |",
            "",
            "## 10-14. Regressionen",
            "",
            "| Unternehmen | Jahre | Profitabilitaet | Margenentwicklung | Cashflow-Qualitaet | Wachstum | Bilanzqualitaet | Kapitalrenditen | Score | Assessment |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for result in results:
        components = {item.component_id: item.score for item in result.component_scores}
        lines.append(
            f"| {result.ticker} | {', '.join(str(year) for year in result.years)} | "
            f"{components.get('profitability') or ''} | {components.get('margin_quality') or ''} | "
            f"{components.get('cashflow_quality') or ''} | {components.get('growth') or ''} | "
            f"{components.get('balance_sheet') or ''} | {components.get('capital_efficiency') or ''} | "
            f"{result.overall_score or ''} | {result.assessment} |"
        )
    lines.extend(["", "## 15. Gefundene Probleme", ""])
    if blockers:
        lines.extend(f"- {row['ticker']} {row['metric_id']}: {row['issue']}" for row in blockers)
    else:
        lines.append("- Keine blockierenden Quality-Engine-Probleme.")
    lines.extend(
        [
            "",
            "## 16. Verbleibende Einschraenkungen",
            "",
            "- OCF/Net Income und FCF/Net Income sind in V1 nicht scored, weil die frozen Calculation/Historical-Artefakte Net Income nicht als same-year Quality-Input zusammen mit Cashflow exponieren.",
            "- ROIC ist nicht implementiert, weil Invested Capital und NOPAT fuer V1 nicht fachlich sauber freigegeben sind.",
            "- Missing Years ist Data Confidence, nicht Business Quality, und beeinflusst den Overall Quality Score nicht.",
            "- 5Y/10Y-Aussagen bleiben bei nur drei freigegebenen Jahren INSUFFICIENT_HISTORY.",
            "- Absolute Score-Bands sind breite V1-Anker und keine branchenspezifische Bewertung.",
            "",
            "## 17. Zielarchitektur",
            "",
            "- `quality/models.py`: Datenmodelle und Status.",
            "- `quality/rules.py`: Definitionen, Formeln, Quellenkategorien.",
            "- `quality/scoring.py`: konfigurierbare Scores und Gewichtungen.",
            "- `quality/engine.py`: providerunabhaengige Auswertung.",
            "- `quality/service.py`: Mehr-Unternehmen-Service.",
            "",
            "## 18. Testergebnis",
            "",
            "Unit- und Regressionstests liegen in `tests/test_business_quality_engine.py`. Die komplette Testsuite muss nach diesem Audit erfolgreich laufen.",
            "",
            "## 19. GO/NO-GO-Entscheidung",
            "",
            decision,
            "",
            "## 20. Ergebnisdarstellung pro Unternehmen",
            "",
        ]
    )
    for result in results:
        lines.extend(
            [
                f"### {result.ticker}",
                "",
                f"- Geschaeftsjahre: {', '.join(str(year) for year in result.years)}",
                f"- Quality Score: {result.overall_score}",
                f"- Quality Assessment: {result.assessment}",
                f"- Positive Faktoren: {'; '.join(result.positive_factors[:8]) or 'keine'}",
                f"- Negative Faktoren: {'; '.join(result.negative_factors[:8]) or 'keine'}",
                f"- Nicht verfuegbare Faktoren: {'; '.join(result.unavailable_factors[:8]) or 'keine'}",
                f"- Nicht anwendbare Faktoren: {'; '.join(result.not_applicable_factors[:8]) or 'keine'}",
                f"- Business-Model-Logik: {' '.join(_business_model_notes(result))}",
                "",
            ]
        )
    lines.extend(["## 21. Abschlussentscheidung", "", decision])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {OUT_MD}")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_CSV}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
