from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_valuation.runtime_dependencies import ensure_runtime_dependencies

ensure_runtime_dependencies()

from datetime import date
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st
from sqlalchemy import select

from stock_valuation.analyses.input_service import (
    store_risk_free_rate,
    upsert_guidance,
    upsert_manual_input,
)
from stock_valuation.analyses.service import AnalysisFrozenError, get_analysis, list_analyses
from stock_valuation.data.providers.ecb import ECBRiskFreeRateProvider
from stock_valuation.database.models import (
    AnalysisStatus,
    FinancialFactSnapshot,
    GuidanceSnapshot,
    ManualInputSnapshot,
)
from stock_valuation.database.session import get_session, init_database
from stock_valuation.ui.navigation import render_navigation


init_database()
st.set_page_config(page_title="Manuelle Daten & Guidance", layout="wide")
render_navigation()

STATUS_LABELS = {
    AnalysisStatus.DRAFT: "Entwurf",
    AnalysisStatus.IN_PROGRESS: "In Bearbeitung",
    AnalysisStatus.COMPLETED: "Abgeschlossen",
    AnalysisStatus.ARCHIVED: "Archiviert",
}


def _analysis_label(analysis) -> str:
    return (
        f"{analysis.company.name} · {analysis.as_of_date} · "
        f"R{analysis.revision_number} · {STATUS_LABELS.get(analysis.status, analysis.status.value)}"
    )


def _number(raw: str) -> Decimal | None:
    text = raw.strip().replace(" ", "").replace(",", ".")
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Ungültige Zahl: {raw}") from exc


st.title("Manuelle Daten")
st.caption(
    "Hier werden zusätzliche externe Werte, Management Guidance und später Bewertungsannahmen "
    "zentral im Analyse-Snapshot erfasst. Korrekturen importierter Abschlusswerte erfolgen direkt "
    "auf der Seite **Finanzdaten**."
)

with get_session() as session:
    analyses = list_analyses(session, include_archived=True)
    options = {_analysis_label(a): a.id for a in analyses}

if not options:
    st.info("Zuerst eine Analyse anlegen.")
    st.stop()

current_id = st.session_state.get("selected_analysis_id")
option_ids = list(options.values())
selected = st.selectbox(
    "Analyse",
    list(options),
    index=option_ids.index(current_id) if current_id in option_ids else 0,
)
analysis_id = options[selected]
st.session_state["selected_analysis_id"] = analysis_id

with get_session() as session:
    analysis = get_analysis(session, analysis_id)
    if analysis is None:
        st.error("Analyse nicht gefunden.")
        st.stop()
    editable = analysis.status in {AnalysisStatus.DRAFT, AnalysisStatus.IN_PROGRESS}
    st.write(
        f"**{analysis.company.name}** · {analysis.company.ticker} · "
        f"Revision {analysis.revision_number} · {STATUS_LABELS.get(analysis.status, analysis.status.value)}"
    )

if not editable:
    st.info(
        "Dieser Snapshot ist eingefroren. Werte können angesehen, aber nicht geändert werden. "
        "Für neue Daten eine neue Revision erstellen."
    )

manual_tab, guidance_tab, risk_tab = st.tabs(
    ["Aktienfinder / zusätzliche Werte", "Management Guidance", "Risikofreier Zins"]
)

with manual_tab:
    st.subheader("Zusätzliche manuelle Eingabe")
    st.write(
        "Für Daten, die bewusst aus Aktienfinder oder einer anderen Quelle ergänzt werden. "
        "Jeder Wert erhält Quelle, Periode und Kommentar."
    )
    with st.form("manual-input"):
        metric = st.text_input("Interner Schlüssel / Metrik", placeholder="z. B. eps_estimate")
        period = st.text_input("Periode", placeholder="z. B. FY2027")
        value_raw = st.text_input("Wert")
        c1, c2 = st.columns(2)
        with c1:
            currency = st.text_input("Währung (optional)", value=analysis.company.currency)
        with c2:
            unit = st.text_input("Einheit", placeholder="currency, %, per_share, ...")
        source_name = st.text_input("Quelle", value="Aktienfinder")
        overrides_metric = st.text_input(
            "Überschreibt automatischen Schlüssel (optional)",
            help="Für echte Abschlusskorrekturen besser die Seite Finanzdaten verwenden.",
        )
        note = st.text_area("Kommentar / Begründung")
        save_manual = st.form_submit_button("Manuellen Wert speichern", disabled=not editable)

    if save_manual:
        try:
            if not metric.strip():
                raise ValueError("Metrik ist erforderlich.")
            with get_session() as session:
                current = get_analysis(session, analysis_id)
                if current is None:
                    raise ValueError("Analyse nicht gefunden.")
                upsert_manual_input(
                    session,
                    current,
                    metric=metric.strip(),
                    period=period.strip() or None,
                    value=_number(value_raw),
                    source_name=source_name.strip() or "Aktienfinder",
                    currency=currency.strip() or None,
                    unit=unit.strip() or None,
                    note=note,
                    overrides_metric=overrides_metric.strip() or None,
                )
            st.success("Manueller Wert gespeichert.")
            st.rerun()
        except (ValueError, AnalysisFrozenError) as exc:
            st.error(str(exc))

    with get_session() as session:
        rows = session.scalars(
            select(ManualInputSnapshot)
            .where(ManualInputSnapshot.analysis_id == analysis_id)
            .order_by(ManualInputSnapshot.period, ManualInputSnapshot.metric)
        ).all()
    if rows:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Metrik": row.metric,
                        "Periode": row.period,
                        "Wert": float(row.value) if row.value is not None else None,
                        "Einheit": row.unit,
                        "Währung": row.currency,
                        "Quelle": row.source_name,
                        "Override": row.overrides_metric,
                        "Eingabe": row.entered_at,
                        "Kommentar": row.note,
                    }
                    for row in rows
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

with guidance_tab:
    st.subheader("Management Guidance")
    st.write(
        "Management Guidance bleibt getrennt vom Analystenkonsens. Low/High-Korridore können "
        "später die ersten DCF-Jahre verankern."
    )
    with st.form("guidance"):
        metric = st.text_input("Metrik", placeholder="revenue oder gross_margin")
        period = st.text_input("Periode", placeholder="FY2026")
        c1, c2, c3 = st.columns(3)
        with c1:
            low_raw = st.text_input("Low")
        with c2:
            point_raw = st.text_input("Punktwert (optional)")
        with c3:
            high_raw = st.text_input("High")
        c1, c2 = st.columns(2)
        with c1:
            currency = st.text_input("Währung", value=analysis.company.currency, key="guid_currency")
        with c2:
            unit = st.text_input("Einheit", placeholder="currency, ratio, %", key="guid_unit")
        publication_date = st.date_input("Veröffentlichungsdatum", value=date.today())
        source_url = st.text_input("Quellen-URL")
        note = st.text_area("Kommentar", key="guid_note")
        save_guidance = st.form_submit_button("Guidance speichern", disabled=not editable)

    if save_guidance:
        try:
            if not metric.strip() or not period.strip():
                raise ValueError("Metrik und Periode sind erforderlich.")
            with get_session() as session:
                current = get_analysis(session, analysis_id)
                if current is None:
                    raise ValueError("Analyse nicht gefunden.")
                upsert_guidance(
                    session,
                    current,
                    metric=metric.strip(),
                    period=period.strip(),
                    low=_number(low_raw),
                    point_estimate=_number(point_raw),
                    high=_number(high_raw),
                    currency=currency.strip() or None,
                    unit=unit.strip() or None,
                    publication_date=publication_date,
                    source_url=source_url,
                    note=note,
                )
            st.success("Management Guidance gespeichert.")
            st.rerun()
        except (ValueError, AnalysisFrozenError) as exc:
            st.error(str(exc))

    with get_session() as session:
        rows = session.scalars(
            select(GuidanceSnapshot)
            .where(GuidanceSnapshot.analysis_id == analysis_id)
            .order_by(GuidanceSnapshot.period, GuidanceSnapshot.metric)
        ).all()
    if rows:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Metrik": row.metric,
                        "Periode": row.period,
                        "Low": float(row.low) if row.low is not None else None,
                        "Punkt": float(row.point_estimate) if row.point_estimate is not None else None,
                        "High": float(row.high) if row.high is not None else None,
                        "Einheit": row.unit,
                        "Währung": row.currency,
                        "Veröffentlicht": row.publication_date,
                        "Quelle": row.source_url,
                        "Kommentar": row.note,
                    }
                    for row in rows
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

with risk_tab:
    st.subheader("EUR risikofreier Zins")
    st.write(
        "V1 verwendet als Marktanker die Euro-Area-AAA-Zinskurve der ECB, 10-jährige Spot Rate. "
        "Der Beobachtungswert wird im Analyse-Snapshot eingefroren."
    )
    if editable and st.button("Aktuellen ECB 10Y AAA Zins laden"):
        try:
            provider = ECBRiskFreeRateProvider()
            with st.spinner("Lade ECB-Zins …"):
                observation = provider.get_latest_eur_aaa_10y()
                with get_session() as session:
                    current = get_analysis(session, analysis_id)
                    if current is None:
                        raise ValueError("Analyse nicht gefunden.")
                    store_risk_free_rate(session, current, observation)
            st.success(
                f"Gespeichert: {observation.percent_per_annum:.4f} % p.a. "
                f"vom {observation.observation_date}."
            )
            st.rerun()
        except (ValueError, AnalysisFrozenError) as exc:
            st.error(str(exc))
        except Exception as exc:
            st.exception(exc)

    with get_session() as session:
        rate = session.scalar(
            select(FinancialFactSnapshot).where(
                FinancialFactSnapshot.analysis_id == analysis_id,
                FinancialFactSnapshot.statement == "market",
                FinancialFactSnapshot.metric == "risk_free_rate_eur_aaa_10y",
            )
        )
    if rate is not None and rate.value is not None:
        st.metric("Gespeicherter risikofreier Zins", f"{float(rate.value) * 100:.4f} %")
        st.caption(
            f"Beobachtung: {rate.period_end} · Quelle: ECB · Serie: {rate.provider_field} · "
            f"Abruf: {rate.retrieved_at}"
        )
    else:
        st.caption("Für diese Analyse ist noch kein ECB-Zins gespeichert.")

st.warning(
    "Der risikofreie Zins ist nur eine Komponente der Eigenkapitalkosten. "
    "Die Risikoaufschlags-/Risiko-KGV-Logik folgt erst nach methodischer Validierung."
)
