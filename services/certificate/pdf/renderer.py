from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

from models.certificate import Certificate


def render_certificate_pdf(cert: Certificate) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=3 * cm,
        bottomMargin=3 * cm,
        leftMargin=3 * cm,
        rightMargin=3 * cm,
    )

    styles = getSampleStyleSheet()
    center = ParagraphStyle("center", parent=styles["Normal"], alignment=TA_CENTER)
    title_style = ParagraphStyle(
        "title", parent=center, fontSize=28, leading=34,
        textColor=colors.HexColor("#1a1a2e"), spaceAfter=0.5 * cm,
    )
    subtitle_style = ParagraphStyle(
        "subtitle", parent=center, fontSize=14, leading=20,
        textColor=colors.HexColor("#444444"),
    )
    name_style = ParagraphStyle(
        "name", parent=center, fontSize=32, leading=40,
        textColor=colors.HexColor("#c8a400"), spaceAfter=0.3 * cm,
    )
    body_style = ParagraphStyle(
        "body", parent=center, fontSize=13, leading=18,
        textColor=colors.HexColor("#333333"),
    )
    small_style = ParagraphStyle(
        "small", parent=center, fontSize=10, leading=14,
        textColor=colors.HexColor("#888888"),
    )

    completed_date = cert.completed_at.strftime("%B %d, %Y")
    issued_date = cert.issued_at.strftime("%B %d, %Y")

    story = [
        Spacer(1, 1 * cm),
        Paragraph("Certificate of Completion", title_style),
        Spacer(1, 0.3 * cm),
        Paragraph("This is to certify that", subtitle_style),
        Spacer(1, 0.8 * cm),
        Paragraph(cert.student_name, name_style),
        Spacer(1, 0.5 * cm),
        Paragraph("has successfully completed the course", body_style),
        Spacer(1, 0.5 * cm),
        Paragraph(f"<b>{cert.course_title}</b>", body_style),
        Spacer(1, 0.8 * cm),
        Paragraph(f"Completed on: {completed_date}", small_style),
        Spacer(1, 0.2 * cm),
        Paragraph(f"Certificate ID: {cert.id}", small_style),
        Spacer(1, 0.2 * cm),
        Paragraph(f"Issued: {issued_date}", small_style),
        Spacer(1, 1 * cm),
        Paragraph("SmartCourse", subtitle_style),
    ]

    doc.build(story)
    return buffer.getvalue()
