from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from stock_valuation.analyses.input_service import upsert_manual_financial_override
from stock_valuation.analyses.service import ensure_editable
from stock_valuation.data.audit import run_deterministic_audit
from stock_valuation.data.preferred_data import FIELD_DEFINITIONS
from stock_valuation.data.resolution import load_preferred_financial_facts
from stock_valuation.database.ai_review_models import (
    AIReviewFinding,
    AIReviewPackageSnapshot,
    AIReviewRun,
)
from stock_valuation.database.models import Analysis, FinancialFactSnapshot


class AIReviewError(RuntimeError):
    """Raised when a ChatGPT review package/result is invalid or cannot be imported."""


REVIEW_SCHEMA_VERSION = "1.0"
VALID_VERDICTS = {"PASS", "WARN", "FAIL", "UNKLAR"}
EXTENSION_REVIEW_WINDOW_YEARS = 10


@dataclass(frozen=True)
class ReviewPackage:
    filename: str
    content: bytes
    package_id: str
    years_requested: int
    fact_count: int
    result_filename: str


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned.strip("._") or "company"


def _review_facts(
    session: Session,
    analysis: Analysis,
    years: int,
) -> list[FinancialFactSnapshot]:
    """Return recent full facts plus unresolved SEC extension candidates from the 10-year window.

    This avoids forcing a full 10-year deep review just because one old filing uses a company-
    specific XBRL concept. The normal selected years remain fully reviewed; extension candidates
    from the historical mapping window are appended so one ChatGPT package can close those gaps.
    """
    preferred = load_preferred_financial_facts(session, analysis.id)
    eligible = [
        fact
        for fact in preferred
        if fact.value is not None
        and not fact.is_cross_check_only
        and fact.statement in {"income_statement", "balance_sheet", "cash_flow"}
    ]
    available_years = sorted({fact.period_end.year for fact in eligible})
    selected_years = set(available_years[-max(1, years) :])
    recent = [fact for fact in eligible if fact.period_end.year in selected_years]

    if available_years:
        last_year = available_years[-1]
        first_mapping_year = last_year - EXTENSION_REVIEW_WINDOW_YEARS + 1
        extension_candidates = [
            fact
            for fact in eligible
            if fact.provider == "sec_filing_extension"
            and first_mapping_year <= fact.period_end.year <= last_year
        ]
    else:
        extension_candidates = []

    unique = {fact.id: fact for fact in [*recent, *extension_candidates]}
    return sorted(unique.values(), key=lambda row: (row.period_end, row.statement, row.metric))


def _package_payload(
    analysis: Analysis,
    facts: list[FinancialFactSnapshot],
    years: int,
) -> dict[str, Any]:
    # Keep this payload limited to snapshot identity/data. The package_id therefore remains stable
    # when explanatory review instructions improve, while still changing whenever snapshot facts do.
    mapping_candidate_count = sum(fact.provider == "sec_filing_extension" for fact in facts)
    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "analysis": {
            "analysis_id": analysis.id,
            "company_name": analysis.company.name,
            "ticker": analysis.company.ticker,
            "isin": analysis.company.isin,
            "exchange": analysis.company.exchange,
            "analysis_as_of_date": analysis.as_of_date.isoformat(),
            "revision": analysis.revision_number,
        },
        "years_requested": years,
        "mapping_candidate_count": mapping_candidate_count,
        "facts": [
            {
                "fact_id": fact.id,
                "period_end": fact.period_end.isoformat(),
                "statement": fact.statement,
                "metric": fact.metric,
                "value": str(fact.value),
                "currency": fact.currency,
                "unit": fact.unit,
                "provider": fact.provider,
                "provider_field": fact.provider_field,
                "source_type": fact.source_type,
                "source_url": fact.source_url,
                "note": fact.note,
            }
            for fact in facts
        ],
    }


def _package_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _store_review_package_snapshot(
    session: Session,
    analysis: Analysis,
    *,
    package_id: str,
    payload: dict[str, Any],
    content: str,
    result_filename: str,
) -> None:
    existing = session.scalar(
        select(AIReviewPackageSnapshot).where(AIReviewPackageSnapshot.package_id == package_id)
    )
    if existing is not None:
        return
    session.add(
        AIReviewPackageSnapshot(
            analysis_id=analysis.id,
            package_id=package_id,
            schema_version=REVIEW_SCHEMA_VERSION,
            years_requested=int(payload["years_requested"]),
            payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            content_markdown=content,
            result_filename=result_filename,
        )
    )
    session.commit()


def _load_package_snapshot(
    session: Session,
    package_id: str,
) -> tuple[AIReviewPackageSnapshot, dict[str, Any]] | None:
    row = session.scalar(
        select(AIReviewPackageSnapshot).where(AIReviewPackageSnapshot.package_id == package_id)
    )
    if row is None:
        return None
    try:
        payload = json.loads(row.payload_json)
    except json.JSONDecodeError as exc:
        raise AIReviewError("Gespeicherter Review-Package-Snapshot ist beschädigt.") from exc
    if not isinstance(payload, dict):
        raise AIReviewError("Gespeicherter Review-Package-Snapshot hat kein gültiges JSON-Objekt.")
    return row, payload


def build_chatgpt_review_package(
    session: Session,
    analysis: Analysis,
    *,
    years: int = 3,
) -> ReviewPackage:
    """Build a self-contained Markdown package for review in the normal ChatGPT product.

    No external API call is performed. The package contains the selected stored facts, internal
    consistency checks, internal field semantics, a strict research brief and the exact JSON schema
    to return to the app.
    """
    years = max(1, int(years))
    facts = _review_facts(session, analysis, years)
    if not facts:
        raise AIReviewError("Keine prüfbaren Jahresabschlussdaten im Snapshot vorhanden.")

    payload = _package_payload(analysis, facts, years)
    package_id = _package_id(payload)
    deterministic = run_deterministic_audit(session, analysis)
    selected_years = {fact.period_end.year for fact in facts}
    checks = [item for item in deterministic if item.year in selected_years]
    mapping_candidate_count = int(payload.get("mapping_candidate_count") or 0)

    ticker = _safe_filename_part(analysis.company.ticker.upper())
    result_filename = (
        f"{ticker}_{analysis.as_of_date.isoformat()}_R{analysis.revision_number}_chatgpt_review_result.json"
    )
    filename = (
        f"{ticker}_{analysis.as_of_date.isoformat()}_R{analysis.revision_number}_chatgpt_review_package.md"
    )

    fact_json = json.dumps(payload["facts"], ensure_ascii=False, indent=2)
    relevant_definitions = {
        metric: FIELD_DEFINITIONS[metric]
        for metric in sorted({fact.metric for fact in facts})
        if metric in FIELD_DEFINITIONS
    }
    definition_json = json.dumps(relevant_definitions, ensure_ascii=False, indent=2)
    check_json = json.dumps(
        [
            {
                "year": item.year,
                "status": item.status,
                "check": item.label,
                "deviation_pct": str(item.deviation_pct) if item.deviation_pct is not None else None,
                "detail": item.detail,
            }
            for item in checks
        ],
        ensure_ascii=False,
        indent=2,
    )

    mapping_note = (
        f" Zusätzlich enthält das Paket {mapping_candidate_count} noch nicht freigegebene "
        f"SEC-Company-Extension-Kandidat(en) aus dem letzten {EXTENSION_REVIEW_WINDOW_YEARS}-Jahres-Fenster."
        if mapping_candidate_count
        else ""
    )

    content = f"""# ChatGPT-Prüfpaket – historische Finanzdaten

## Auftrag an ChatGPT

Prüfe die unten enthaltenen historischen Finanzzahlen **mit Websuche gegen belastbare offizielle Primärquellen** und erstelle am Ende eine **JSON-Datei** mit dem Namen:

`{result_filename}`

Die JSON-Datei wird anschließend in das lokale Aktienanalyse-Tool zurückgeladen. Gib deshalb keine Korrektur frei, die du nicht sauber aus einer offiziellen Quelle belegen kannst.

## Identität des Prüfpakets

- Schema-Version: `{REVIEW_SCHEMA_VERSION}`
- Package-ID: `{package_id}`
- Unternehmen: {analysis.company.name}
- Ticker: {analysis.company.ticker}
- ISIN: {analysis.company.isin or 'nicht hinterlegt'}
- Börse/Region: {analysis.company.exchange or 'nicht hinterlegt'}
- Analyse-Stichtag: {analysis.as_of_date}
- Revision: R{analysis.revision_number}
- Vollständig zu prüfende aktuelle Geschäftsjahre: {years}
- Fakten im Paket: {len(facts)}
- SEC-Company-Extension-Mappingkandidaten: {mapping_candidate_count}

Die ausgewählten aktuellen Geschäftsjahre werden vollständig geprüft.{mapping_note}

## Verbindliche Prüfregeln

1. Nutze Websuche aktiv.
2. Quellenpriorität: offizieller Annual Report / 10-K / 20-F / regulatorisches Filing; danach offizielle Investor-Relations-Finanzstatements.
3. Sekundärquellen dürfen nur zur Orientierung dienen und niemals allein eine Korrektur begründen.
4. Prüfe Geschäftsjahr, Berichtswährung, Einheit, Rechnungslegungsstandard und Konsolidierungskreis.
5. Verwechsle keine Quartalswerte mit Jahreswerten.
6. Providerfelder können semantisch breiter oder enger sein als die offizielle Abschlusszeile. Die unten angegebenen **internen Felddefinitionen sind verbindlich**. Wenn die Definition nicht identisch ist: `UNKLAR` oder `FAIL` mit Erklärung, nicht gewaltsam gleichsetzen.
7. **Sonderregel `provider=sec_filing_extension`:** Das ist nur ein maschinell erkannter Kandidat aus einem firmeneigenen XBRL-Tag, keine bereits akzeptierte Zuordnung. Prüfe `provider_field`, `note`, den offiziellen Filing-Link und die wirtschaftliche Bedeutung besonders streng. `PASS` ist nur erlaubt, wenn der Kandidat exakt dasselbe interne Feld abbildet.
8. **Bei `short_term_debt`:** Prüfe ausdrücklich, ob der Kandidat sämtliche kurzfristigen zinstragenden Schulden gemäß interner Definition umfasst. Falls mehrere Komponenten addiert werden müssen, darf der einzelne Kandidat nicht `PASS` bekommen. Gib bei sicher ermittelbarer Gesamtsumme `FAIL` mit der korrekten `official_value` und offizieller Quelle zurück.
9. Beachte Restatements. Verwende die am Analyse-Stichtag maßgebliche veröffentlichte Zahl, soweit eindeutig feststellbar.
10. `official_value` muss immer in derselben Basiseinheit wie der importierte Wert stehen. Beispiel: 281724000000 statt 281724 Mio.
11. Wenn keine belastbare Primärquelle gefunden wird: `official_value=null`, `status=UNKLAR`.
12. Statusregeln:
    - `PASS`: gleicher wirtschaftlicher Sachverhalt und <= 0,5 % Abweichung.
    - `WARN`: gleicher Sachverhalt und > 0,5 bis <= 2 % Abweichung oder geringe nachvollziehbare Rundungs-/Darstellungsfrage.
    - `FAIL`: > 2 % Abweichung oder klar falsche/zu enge/zu breite semantische Zuordnung.
    - `UNKLAR`: keine sichere Zuordnung/Primärquelle.
13. Für `WARN`/`FAIL` muss bei sicherer offizieller Zahl eine konkrete offizielle Quellen-URL angegeben werden.
14. Ändere keine Daten. Du lieferst ausschließlich Prüfergebnisse.
15. Gib **genau einen Finding-Eintrag für jeden `fact_id`** zurück und erfinde keine zusätzlichen IDs.
16. Die Felder `package_id`, `schema_version`, `years_requested` und die Unternehmensidentität müssen unverändert übernommen werden.
17. Erstelle am Ende die JSON-Datei zum Herunterladen. Kein Markdown in der JSON-Datei.

## Verbindliche interne Felddefinitionen

Diese Definitionen legen fest, welchen wirtschaftlichen Sachverhalt unser internes Feld meint. Ein Providerwert darf nur `PASS` sein, wenn er **dieselbe Semantik** besitzt.

```json
{definition_json}
```

## Erwartetes Ergebnisformat

```json
{{
  "schema_version": "{REVIEW_SCHEMA_VERSION}",
  "package_id": "{package_id}",
  "years_requested": {years},
  "company": {{
    "name": {json.dumps(analysis.company.name, ensure_ascii=False)},
    "ticker": {json.dumps(analysis.company.ticker)},
    "analysis_as_of_date": "{analysis.as_of_date.isoformat()}",
    "revision": {analysis.revision_number}
  }},
  "summary": "Kurze Zusammenfassung der Datenqualität",
  "findings": [
    {{
      "fact_id": 123,
      "official_value": 123456789.0,
      "status": "PASS",
      "official_label": "Originalbezeichnung im Abschluss",
      "source_title": "Annual Report 2025",
      "source_url": "https://offizielle-quelle.example/report",
      "reason": "Kurze fachliche Begründung"
    }}
  ]
}}
```

## Importierte Fakten

```json
{fact_json}
```

## Bereits durchgeführte lokale Plausibilitätschecks

Diese Checks sind nur Hinweise und ersetzen die Primärquellenprüfung nicht.

```json
{check_json}
```

## Abschluss

Prüfe alle Fakten. Erzeuge anschließend ausschließlich die angeforderte Datei `{result_filename}` im oben definierten JSON-Format. Unsichere Fälle als `UNKLAR` kennzeichnen; niemals raten.
"""

    _store_review_package_snapshot(
        session,
        analysis,
        package_id=package_id,
        payload=payload,
        content=content,
        result_filename=result_filename,
    )

    return ReviewPackage(
        filename=filename,
        content=content.encode("utf-8"),
        package_id=package_id,
        years_requested=years,
        fact_count=len(facts),
        result_filename=result_filename,
    )


def import_chatgpt_review_result(
    session: Session,
    analysis: Analysis,
    content: bytes | str,
) -> AIReviewRun:
    """Validate and persist a ChatGPT-generated review JSON without changing financial facts."""
    ensure_editable(analysis)
    try:
        text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
        payload = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AIReviewError("Die hochgeladene Prüfergebnis-Datei ist kein gültiges UTF-8-JSON.") from exc

    if not isinstance(payload, dict):
        raise AIReviewError("Das Prüfergebnis muss ein JSON-Objekt sein.")
    if payload.get("schema_version") != REVIEW_SCHEMA_VERSION:
        raise AIReviewError(
            f"Falsche Schema-Version. Erwartet wird {REVIEW_SCHEMA_VERSION}."
        )

    years_raw = payload.get("years_requested")
    if not isinstance(years_raw, int) or years_raw < 1 or years_raw > 10:
        raise AIReviewError("`years_requested` fehlt oder ist ungültig.")

    package_id = str(payload.get("package_id") or "")
    stored_package = _load_package_snapshot(session, package_id)
    if stored_package is None:
        raise AIReviewError(
            "Die Package-ID ist nicht als exportierter Review-Snapshot bekannt. Bitte das Ergebnis "
            "gegen das exakt exportierte Pruefpaket einlesen oder ein neues Paket erzeugen."
        )
    package_row, package_payload = stored_package
    if package_row.analysis_id != analysis.id:
        raise AIReviewError("Die Package-ID gehoert nicht zur ausgewaehlten Analyse.")
    if package_payload.get("schema_version") != REVIEW_SCHEMA_VERSION:
        raise AIReviewError("Gespeicherter Review-Snapshot hat eine falsche Schema-Version.")
    if package_payload.get("years_requested") != years_raw:
        raise AIReviewError("`years_requested` passt nicht zum exportierten Review-Snapshot.")

    company = payload.get("company")
    if not isinstance(company, dict):
        raise AIReviewError("Unternehmensidentität fehlt im Prüfergebnis.")
    if str(company.get("ticker") or "").upper() != analysis.company.ticker.upper():
        raise AIReviewError("Ticker im Prüfergebnis passt nicht zur ausgewählten Analyse.")
    if str(company.get("analysis_as_of_date") or "") != analysis.as_of_date.isoformat():
        raise AIReviewError("Analyse-Stichtag im Prüfergebnis passt nicht zur ausgewählten Analyse.")
    if int(company.get("revision") or 0) != analysis.revision_number:
        raise AIReviewError("Revision im Prüfergebnis passt nicht zur ausgewählten Analyse.")

    snapshot_facts = package_payload.get("facts")
    if not isinstance(snapshot_facts, list):
        raise AIReviewError("Gespeicherter Review-Snapshot enthaelt keine Faktenliste.")
    fact_by_id: dict[int, dict[str, Any]] = {}
    for fact in snapshot_facts:
        if not isinstance(fact, dict) or not isinstance(fact.get("fact_id"), int):
            raise AIReviewError("Gespeicherter Review-Snapshot enthaelt ungueltige Fakten.")
        fact_by_id[fact["fact_id"]] = fact

    returned = payload.get("findings")
    if not isinstance(returned, list):
        raise AIReviewError("Das Prüfergebnis enthält keine gültige `findings`-Liste.")

    returned_by_id: dict[int, dict[str, Any]] = {}
    for item in returned:
        if not isinstance(item, dict):
            raise AIReviewError("Jeder Eintrag in `findings` muss ein JSON-Objekt sein.")
        fact_id = item.get("fact_id")
        if not isinstance(fact_id, int) or fact_id not in fact_by_id:
            raise AIReviewError(f"Unbekannte oder ungültige fact_id im Prüfergebnis: {fact_id!r}.")
        if fact_id in returned_by_id:
            raise AIReviewError(f"fact_id {fact_id} kommt im Prüfergebnis mehrfach vor.")
        returned_by_id[fact_id] = item

    try:
        current_package = build_chatgpt_review_package(session, analysis, years=years_raw)
        package_is_stale = current_package.package_id != package_id
    except AIReviewError:
        package_is_stale = True
    package_row.status = "stale_imported" if package_is_stale else "imported"

    run = AIReviewRun(
        analysis_id=analysis.id,
        model="chatgpt_file_review",
        years_requested=years_raw,
        status="completed_stale_snapshot" if package_is_stale else "completed",
        response_id=package_id,
        summary=(
            str(payload.get("summary") or "")
            + (" [Review wurde gegen einen inzwischen stale Snapshot importiert.]" if package_is_stale else "")
        ).strip(),
        completed_at=datetime.now(UTC),
    )
    session.add(run)
    session.flush()

    for fact_id, fact in fact_by_id.items():
        item = returned_by_id.get(fact_id)
        if item is None:
            item = {
                "official_value": None,
                "status": "UNKLAR",
                "official_label": None,
                "source_title": None,
                "source_url": None,
                "reason": "Das zurückgeladene ChatGPT-Ergebnis enthielt für diesen Fakt keinen Eintrag.",
            }

        official_value = _decimal(item.get("official_value"))
        verdict = str(item.get("status") or "UNKLAR").upper()
        if verdict not in VALID_VERDICTS:
            verdict = "UNKLAR"

        imported_value = _decimal(fact.get("value"))
        try:
            period_end = date.fromisoformat(str(fact.get("period_end") or ""))
        except ValueError as exc:
            raise AIReviewError("Gespeicherter Review-Snapshot enthaelt ein ungueltiges period_end.") from exc

        deviation = None
        if official_value is not None and imported_value not in (None, Decimal("0")):
            deviation = abs(official_value - imported_value) / abs(imported_value) * Decimal("100")

        session.add(
            AIReviewFinding(
                run_id=run.id,
                analysis_id=analysis.id,
                period_end=period_end,
                statement=str(fact.get("statement") or ""),
                metric=str(fact.get("metric") or ""),
                imported_value=imported_value,
                official_value=official_value,
                currency=(str(fact.get("currency")) if fact.get("currency") else None),
                deviation_pct=deviation,
                verdict=verdict,
                provider=(str(fact.get("provider")) if fact.get("provider") else None),
                provider_field=(str(fact.get("provider_field")) if fact.get("provider_field") else None),
                official_label=(
                    str(item.get("official_label")) if item.get("official_label") else None
                ),
                source_title=(
                    str(item.get("source_title")) if item.get("source_title") else None
                ),
                source_url=(str(item.get("source_url")) if item.get("source_url") else None),
                reason=str(item.get("reason") or ""),
            )
        )

    session.commit()
    return load_ai_review_run(session, run.id) or run


def load_ai_review_run(session: Session, run_id: int) -> AIReviewRun | None:
    return session.scalar(
        select(AIReviewRun)
        .options(selectinload(AIReviewRun.findings))
        .where(AIReviewRun.id == run_id)
    )


def latest_ai_review_run(session: Session, analysis_id: int) -> AIReviewRun | None:
    run_id = session.scalar(
        select(AIReviewRun.id)
        .where(AIReviewRun.analysis_id == analysis_id)
        .order_by(AIReviewRun.created_at.desc(), AIReviewRun.id.desc())
        .limit(1)
    )
    return load_ai_review_run(session, run_id) if run_id is not None else None


def accept_ai_review_finding(
    session: Session,
    analysis: Analysis,
    finding_id: int,
) -> AIReviewFinding:
    ensure_editable(analysis)
    finding = session.get(AIReviewFinding, finding_id)
    if finding is None or finding.analysis_id != analysis.id:
        raise ValueError("KI-Prüffund wurde nicht gefunden.")
    if finding.official_value is None:
        raise ValueError("Dieser Prüffund enthält keinen sicheren offiziellen Zahlenwert.")
    if finding.verdict not in {"WARN", "FAIL"}:
        raise ValueError("Nur WARN/FAIL-Korrekturvorschläge können übernommen werden.")
    if not finding.source_url:
        raise ValueError("Für die Übernahme fehlt eine offizielle Quellen-URL.")

    upsert_manual_financial_override(
        session,
        analysis,
        metric=finding.metric,
        period_end=finding.period_end,
        value=finding.official_value,
        currency=finding.currency,
        unit="currency",
        statement=finding.statement,
        source_name=(
            finding.source_title or finding.official_label or "ChatGPT-geprüfte Primärquelle"
        ),
        source_url=finding.source_url,
        note=(
            f"Vom Nutzer aus ChatGPT-Dateiprüfung übernommen. {finding.reason or ''} "
            f"Importierter Wert: {finding.imported_value}."
        ).strip(),
    )
    finding.decision = "accepted"
    finding.decided_at = datetime.now(UTC)
    session.commit()
    return finding


def reject_ai_review_finding(
    session: Session,
    analysis: Analysis,
    finding_id: int,
) -> AIReviewFinding:
    ensure_editable(analysis)
    finding = session.get(AIReviewFinding, finding_id)
    if finding is None or finding.analysis_id != analysis.id:
        raise ValueError("KI-Prüffund wurde nicht gefunden.")
    finding.decision = "rejected"
    finding.decided_at = datetime.now(UTC)
    session.commit()
    return finding
