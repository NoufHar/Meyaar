from __future__ import annotations

from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from pypdf import PdfReader, PdfWriter


def _safe(value: Any) -> str:
    return str(value if value is not None else "-").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _breakable_identifier(value: Any) -> str:
    """Allow long UUIDs/identifiers to wrap without changing their text."""
    return _safe(value)


def build_report_pdf(payload: dict[str, Any]) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("MeyaarTitle", parent=styles["Title"], textColor=colors.HexColor("#0B1F36"), fontSize=22, leading=26, alignment=TA_CENTER)
    heading = ParagraphStyle("MeyaarHeading", parent=styles["Heading2"], textColor=colors.HexColor("#145FF5"), fontSize=13, leading=17, spaceBefore=8, spaceAfter=7)
    body = ParagraphStyle("MeyaarBody", parent=styles["BodyText"], textColor=colors.HexColor("#334155"), fontSize=8.5, leading=12)
    table_body = ParagraphStyle("MeyaarTableBody", parent=body, fontSize=7.2, leading=9.2, splitLongWords=True, wordWrap="CJK")
    table_header = ParagraphStyle("MeyaarTableHeader", parent=table_body, fontName="Helvetica-Bold", textColor=colors.white, leading=9.5)
    story = [Paragraph("MEYAAR", title), Paragraph("Geospatial Data Quality Report", ParagraphStyle("subtitle", parent=body, alignment=TA_CENTER)), Spacer(1, 8 * mm)]

    is_vector = "validation" in payload
    score = payload.get("compliance_score", 0)
    summary_data = [
        ["Dataset", _safe(payload.get("filename"))],
        ["Analysis status", _safe(payload.get("status"))],
        ["Compliance score", f"{_safe(score)}%"],
        ["Analysis type", "Vector validation" if is_vector else "Image quality and vision"],
    ]
    summary = Table(summary_data, colWidths=[45 * mm, 115 * mm])
    summary.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF2FF")), ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0B1F36")), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#CBD5E1")), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 7)]))
    story += [summary, Spacer(1, 7 * mm), Paragraph("Findings", heading)]

    if is_vector:
        rows = payload.get("validation", {}).get("errors", [])
        analyses = {item.get("result_id"): item for item in payload.get("analysis", {}).get("analyses", [])}
        table_rows = [[Paragraph(label, table_header) for label in ["Rule", "Feature", "Severity", "Finding / recommendation"]]]
        for row in rows[:100]:
            analysis = analyses.get(row.get("result_id"), {})
            detail = analysis.get("explanation") or row.get("details") or "-"
            recommendation = analysis.get("recommendation")
            if recommendation:
                detail = f"{detail}\nRecommendation: {recommendation}"
            table_rows.append([
                Paragraph(_breakable_identifier(row.get("rule_id")), table_body),
                Paragraph(_breakable_identifier(row.get("feature_id")), table_body),
                Paragraph(_safe(row.get("severity")), table_body),
                Paragraph(_safe(detail).replace("\n", "<br/>"), table_body),
            ])
    else:
        rows = payload.get("issues", [])
        table_rows = [[Paragraph(label, table_header) for label in ["Finding", "Severity", "Details"]]]
        for row in rows[:100]:
            table_rows.append([
                Paragraph(_breakable_identifier(row.get("error_type")), table_body),
                Paragraph(_safe(row.get("severity")), table_body),
                Paragraph(_safe(row.get("message")), table_body),
            ])

    if len(table_rows) == 1:
        story.append(Paragraph("No findings were reported by the available checks.", body))
    else:
        widths = [19 * mm, 43 * mm, 19 * mm, 79 * mm] if is_vector else [45 * mm, 25 * mm, 90 * mm]
        table = Table(table_rows, colWidths=widths, repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#145FF5")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 7.2), ("GRID", (0, 0), (-1, -1), .3, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")])]))
        story.append(table)

    if not is_vector and payload.get("geotiff"):
        story += [PageBreak(), Paragraph("GeoTIFF metadata", heading), Paragraph(_safe(payload["geotiff"]), body)]
    story += [Spacer(1, 8 * mm), Paragraph("This is an internal Meyaar quality assessment and is not an official GeoSA certification.", body)]
    document.build(story)
    return buffer.getvalue()


def build_combined_report_pdf(payloads: list[dict[str, Any]]) -> bytes:
    """Merge complete per-analysis reports while preserving a clear page boundary between files."""
    writer = PdfWriter()
    for payload in payloads:
        reader = PdfReader(BytesIO(build_report_pdf(payload)))
        for page in reader.pages:
            writer.add_page(page)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()
