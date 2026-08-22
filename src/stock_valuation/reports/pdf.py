from __future__ import annotations

from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from stock_valuation.database.models import (
    Analysis,
    EstimateSnapshot,
    FinancialFactSnapshot,
    GuidanceSnapshot,
    ManualInputSnapshot,
    QualitativeAssessment,
    ValuationAssumption,
    ValuationResult,
)


def snapshot_report_filename(analysis: Analysis) -> str:
    ticker = "".join(ch for ch in analysis.company.ticker if ch.isalnum() or ch in "-_" )
    return f"{ticker}_{analysis.as_of_date.isoformat()}_R{analysis.revision_number}_Analyse.pdf"


def _count(session: Session, model, analysis_id: int) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(model).where(model.analysis_id == analysis_id)
        )
        or 0
    )


def build_snapshot_report(session: Session, analysis: Analysis) -> bytes:
    """Build a reproducible PDF exclusively from the selected stored snapshot.

    This function deliberately performs no API calls and does not use today's market
    data. Future report sections must follow the same rule.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=f"{analysis.company.name} Analyse R{analysis.revision_number}",
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    styles = getSampleStyleSheet()

    story = [
        Paragraph("Unternehmensanalyse & Bewertung", styles["Title"]),
        Spacer(1, 8),
        Paragraph(escape(analysis.company.name), styles["Heading1"]),
    ]

    metadata = [
        ["Ticker", analysis.company.ticker],
        ["ISIN", analysis.company.isin or "—"],
        ["Börse", analysis.company.exchange or "—"],
        ["Analyse-Stichtag", analysis.as_of_date.isoformat()],
        ["Revision", str(analysis.revision_number)],
        ["Status", analysis.status.value],
        [
            "Aktienkurs zum Stichtag",
            (
                f"{float(analysis.market_price):,.2f} {analysis.market_price_currency or analysis.company.currency}"
                if analysis.market_price is not None
                else "—"
            ),
        ],
    ]
    table = Table(metadata, colWidths=[55 * mm, 105 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.lightgrey),
            ]
        )
    )
    story.extend([table, Spacer(1, 14)])

    if analysis.notes:
        story.extend(
            [
                Paragraph("Notizen / Investmentthese", styles["Heading2"]),
                Paragraph(escape(analysis.notes).replace("\n", "<br/>") , styles["BodyText"]),
                Spacer(1, 12),
            ]
        )

    story.append(Paragraph("Snapshot-Inhalt", styles["Heading2"]))
    counts = [
        ["Gespeicherte Fundamentaldaten", _count(session, FinancialFactSnapshot, analysis.id)],
        ["Analystenschätzungen", _count(session, EstimateSnapshot, analysis.id)],
        ["Management-Guidance", _count(session, GuidanceSnapshot, analysis.id)],
        ["Manuelle Inputs", _count(session, ManualInputSnapshot, analysis.id)],
        ["Qualitative Bewertungen", _count(session, QualitativeAssessment, analysis.id)],
        ["Bewertungsannahmen", _count(session, ValuationAssumption, analysis.id)],
        ["Bewertungsergebnisse", _count(session, ValuationResult, analysis.id)],
    ]
    count_table = Table(counts, colWidths=[105 * mm, 35 * mm])
    count_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.35, colors.lightgrey),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([count_table, Spacer(1, 14)])

    results = session.scalars(
        select(ValuationResult)
        .where(ValuationResult.analysis_id == analysis.id)
        .order_by(ValuationResult.method, ValuationResult.scenario, ValuationResult.metric)
    ).all()
    if results:
        story.append(Paragraph("Bewertungsergebnisse", styles["Heading2"]))
        result_rows = [["Methode", "Szenario", "Kennzahl", "Wert"]]
        for result in results:
            result_rows.append(
                [
                    result.method,
                    result.scenario,
                    result.metric,
                    "—" if result.value is None else f"{float(result.value):,.2f} {result.currency or ''}".strip(),
                ]
            )
        result_table = Table(result_rows, repeatRows=1, colWidths=[35 * mm, 28 * mm, 55 * mm, 38 * mm])
        result_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.lightgrey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
                ]
            )
        )
        story.extend([result_table, Spacer(1, 14)])

    story.extend(
        [
            Paragraph("Methodischer Hinweis", styles["Heading2"]),
            Paragraph(
                "Dieser Bericht wird ausschließlich aus dem ausgewählten Analyse-Snapshot erzeugt. "
                "Er enthält keine nachträglich geladenen Live-Daten. Der vollständige Analysebericht "
                "wird in späteren Projektphasen um die fachlichen Kapitel erweitert.",
                styles["BodyText"],
            ),
        ]
    )

    doc.build(story)
    return buffer.getvalue()
