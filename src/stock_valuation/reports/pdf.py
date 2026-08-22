from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from stock_valuation.database.models import Analysis


def build_snapshot_report(analysis: Analysis) -> bytes:
    """Build a minimal PDF from the selected stored analysis snapshot.

    The report must never fetch live data. Future sections are populated only from
    snapshot tables belonging to ``analysis.id``.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=f"{analysis.company.name} Analyse")
    styles = getSampleStyleSheet()

    story = [
        Paragraph("Unternehmensanalyse & Bewertung", styles["Title"]),
        Spacer(1, 16),
        Paragraph(analysis.company.name, styles["Heading1"]),
        Paragraph(f"Ticker: {analysis.company.ticker}", styles["BodyText"]),
        Paragraph(f"Analyse-Stichtag: {analysis.as_of_date}", styles["BodyText"]),
        Paragraph(f"Revision: {analysis.revision_number}", styles["BodyText"]),
        Paragraph(f"Status: {analysis.status.value}", styles["BodyText"]),
        Spacer(1, 16),
        Paragraph(
            "Dieser Report ist ein früher technischer Prototyp. Die vollständigen "
            "Analysekapitel werden gemäß docs/REPORT_SPEC.md ergänzt.",
            styles["BodyText"],
        ),
    ]
    doc.build(story)
    return buffer.getvalue()
