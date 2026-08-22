from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from stock_valuation.analyses.input_service import upsert_manual_financial_override
from stock_valuation.analyses.service import ensure_editable
from stock_valuation.data.audit import run_deterministic_audit
from stock_valuation.data.resolution import load_preferred_financial_facts
from stock_valuation.database.ai_review_models import AIReviewFinding, AIReviewRun
from stock_valuation.database.models import Analysis, FinancialFactSnapshot


class AIReviewError(RuntimeError):
    """Raised when the external AI review cannot produce a usable result."""


DEFAULT_REVIEW_MODEL = "gpt-5.4"


REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "fact_id": {"type": "integer"},
                    "official_value": {"type": ["number", "null"]},
                    "status": {
                        "type": "string",
                        "enum": ["PASS", "WARN", "FAIL", "UNKLAR"],
                    },
                    "official_label": {"type": ["string", "null"]},
                    "source_title": {"type": ["string", "null"]},
                    "source_url": {"type": ["string", "null"]},
                    "reason": {"type": "string"},
                },
                "required": [
                    "fact_id",
                    "official_value",
                    "status",
                    "official_label",
                    "source_title",
                    "source_url",
                    "reason",
                ],
            },
        },
    },
    "required": ["summary", "findings"],
}


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _review_facts(session: Session, analysis: Analysis, years: int) -> list[FinancialFactSnapshot]:
    preferred = load_preferred_financial_facts(session, analysis.id)
    available_years = sorted({fact.period_end.year for fact in preferred if fact.value is not None})
    selected_years = set(available_years[-max(1, years) :])
    return [
        fact
        for fact in preferred
        if fact.value is not None
        and fact.period_end.year in selected_years
        and not fact.is_cross_check_only
        and fact.statement in {"income_statement", "balance_sheet", "cash_flow"}
    ]


def _build_review_input(session: Session, analysis: Analysis, facts: list[FinancialFactSnapshot]) -> str:
    deterministic = run_deterministic_audit(session, analysis)
    check_lines = [
        f"{item.year} | {item.status} | {item.label} | deviation_pct={item.deviation_pct} | {item.detail}"
        for item in deterministic
    ]
    fact_lines = [
        " | ".join(
            [
                f"fact_id={fact.id}",
                f"period_end={fact.period_end.isoformat()}",
                f"statement={fact.statement}",
                f"metric={fact.metric}",
                f"value={fact.value}",
                f"currency={fact.currency or ''}",
                f"unit={fact.unit or ''}",
                f"provider={fact.provider or ''}",
                f"provider_field={fact.provider_field or ''}",
            ]
        )
        for fact in sorted(facts, key=lambda row: (row.period_end, row.statement, row.metric))
    ]

    return f"""Prüfe historische Finanzdaten für eine fundamentale Unternehmensanalyse.

UNTERNEHMEN
Name: {analysis.company.name}
Ticker: {analysis.company.ticker}
ISIN: {analysis.company.isin or 'nicht hinterlegt'}
Börse/Region: {analysis.company.exchange or 'nicht hinterlegt'}
Analyse-Stichtag: {analysis.as_of_date}

QUELLENREGELN
- Nutze Websuche aktiv.
- Bevorzuge strikt: offizieller Annual Report / 10-K / 20-F / regulatorisches Filing; danach offizielle Investor-Relations-Finanzstatements.
- Sekundärquellen dürfen nur zur Orientierung dienen und niemals allein eine Korrektur begründen.
- Prüfe Geschäftsjahr, Berichtswährung, Einheit, Rechnungslegungsstandard und Konsolidierungskreis.
- Verwechsle keine Quartalswerte mit Jahreswerten.
- Providerfelder können semantisch breiter oder enger sein als die offizielle Abschlusszeile. Wenn die Definition nicht identisch ist: UNKLAR oder FAIL mit Erklärung, nicht gewaltsam gleichsetzen.
- Restatements sind zu beachten. Verwende die am Analyse-Stichtag maßgebliche veröffentlichte Zahl, soweit eindeutig feststellbar.
- Gib `official_value` immer in derselben Basiseinheit wie der importierte Wert zurück (z. B. 281724000000 statt 281724 Mio.).
- Wenn keine belastbare Primärquelle gefunden wird: official_value=null, status=UNKLAR.
- PASS: gleicher wirtschaftlicher Sachverhalt und <=0,5 % Abweichung.
- WARN: gleicher Sachverhalt und >0,5 bis <=2 % Abweichung oder geringe nachvollziehbare Rundungs-/Darstellungsfrage.
- FAIL: >2 % Abweichung oder klar falsche semantische Zuordnung.
- Für WARN/FAIL muss eine konkrete offizielle Quellen-URL angegeben werden, wenn eine sichere offizielle Zahl vorliegt.
- Ändere keine Daten. Du lieferst ausschließlich Prüfergebnisse.

WICHTIG FÜR DIE AUSGABE
- Gib genau einen Finding-Eintrag für jeden unten übergebenen `fact_id` zurück.
- `fact_id` muss unverändert übernommen werden.
- Erfinde keine zusätzlichen fact_ids.

IMPORTIERTE FAKTEN
{chr(10).join(fact_lines)}

BEREITS DURCHGEFÜHRTE INTERNE PLAUSIBILITÄTSCHECKS
{chr(10).join(check_lines) if check_lines else 'Keine.'}
"""


def execute_ai_review(
    session: Session,
    analysis: Analysis,
    *,
    years: int = 3,
    model: str | None = None,
    client: Any | None = None,
) -> AIReviewRun:
    """Run a web-enabled OpenAI review and persist proposed differences without changing facts."""
    ensure_editable(analysis)
    facts = _review_facts(session, analysis, years)
    if not facts:
        raise AIReviewError("Keine prüfbaren Jahresabschlussdaten im Snapshot vorhanden.")

    api_key = os.getenv("OPENAI_API_KEY")
    if client is None:
        if not api_key:
            raise AIReviewError("OPENAI_API_KEY fehlt in der lokalen `.env`.")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise AIReviewError("OpenAI-Python-SDK ist nicht installiert.") from exc
        client = OpenAI(api_key=api_key)

    selected_model = model or os.getenv("OPENAI_REVIEW_MODEL") or DEFAULT_REVIEW_MODEL
    prompt = _build_review_input(session, analysis, facts)

    try:
        response = client.responses.create(
            model=selected_model,
            tools=[{"type": "web_search"}],
            tool_choice="auto",
            input=prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "financial_statement_review",
                    "strict": True,
                    "schema": REVIEW_SCHEMA,
                },
                "verbosity": "low",
            },
            include=["web_search_call.action.sources"],
            store=False,
        )
    except Exception as exc:  # SDK/API errors have changed class names over time.
        raise AIReviewError(f"OpenAI-KI-Prüfung fehlgeschlagen: {exc}") from exc

    output_text = getattr(response, "output_text", None)
    if not output_text:
        raise AIReviewError("Die KI-Prüfung lieferte keine strukturierte Textausgabe.")
    try:
        payload = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise AIReviewError("Die KI-Prüfung lieferte kein gültiges JSON.") from exc

    returned = payload.get("findings")
    if not isinstance(returned, list):
        raise AIReviewError("Die KI-Prüfung enthielt keine Finding-Liste.")

    fact_by_id = {fact.id: fact for fact in facts}
    returned_by_id: dict[int, dict[str, Any]] = {}
    for item in returned:
        if not isinstance(item, dict):
            continue
        fact_id = item.get("fact_id")
        if isinstance(fact_id, int) and fact_id in fact_by_id and fact_id not in returned_by_id:
            returned_by_id[fact_id] = item

    run = AIReviewRun(
        analysis_id=analysis.id,
        model=selected_model,
        years_requested=years,
        status="completed",
        response_id=getattr(response, "id", None),
        summary=str(payload.get("summary") or ""),
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
                "reason": "Die KI-Ausgabe enthielt für diesen eingereichten Fakt keinen Eintrag.",
            }
        official_value = _decimal(item.get("official_value"))
        deviation = None
        if official_value is not None and fact.value not in (None, Decimal("0")):
            deviation = abs(official_value - fact.value) / abs(fact.value) * Decimal("100")

        verdict = str(item.get("status") or "UNKLAR").upper()
        if verdict not in {"PASS", "WARN", "FAIL", "UNKLAR"}:
            verdict = "UNKLAR"

        session.add(
            AIReviewFinding(
                run_id=run.id,
                analysis_id=analysis.id,
                period_end=fact.period_end,
                statement=fact.statement,
                metric=fact.metric,
                imported_value=fact.value,
                official_value=official_value,
                currency=fact.currency,
                deviation_pct=deviation,
                verdict=verdict,
                provider=fact.provider,
                provider_field=fact.provider_field,
                official_label=item.get("official_label"),
                source_title=item.get("source_title"),
                source_url=item.get("source_url"),
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
        source_name=finding.source_title or finding.official_label or "KI-geprüfte Primärquelle",
        source_url=finding.source_url,
        note=(
            f"Vom Nutzer aus KI-Prüfung übernommen. {finding.reason or ''} "
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
