"""
llm/pdf_generator.py
Generates a clean, professional PDF resume that matches the original formatting.

Layout rules:
- Header block (name, contact, title) is read from the resume text itself — no auto-generated
  duplicate header.  The "Tailored for:" label is intentionally omitted.
- Job title lines are detected by year patterns (2024, Jan 2025, etc.) → bold
- Company/location lines are detected by "·" or " — " → italic
- ALL-CAPS lines → section header with thin rule above
- Bullet lines → indented
- Everything else → body paragraph
- Margins and leading tuned to fit a typical 1-page resume into ≤2 PDF pages.
"""
import re
import io
import logging
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT

logger = logging.getLogger(__name__)

# ── Year pattern used to identify job-title lines ──────────────────────────────
_YEAR_RE = re.compile(r'\b(19|20)\d{2}\b')


def generate_resume_pdf(resume_text: str, job_title: str, company: str, applicant: dict) -> bytes:
    """
    Convert a plain-text tailored resume into a clean PDF that mirrors the
    original resume's look.  Returns raw PDF bytes.
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )

    # ── Styles ─────────────────────────────────────────────────────────────────
    name_style = ParagraphStyle(
        "Name",
        fontSize=18,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#111111"),
        alignment=TA_CENTER,
        spaceAfter=2,
        leading=22,
    )
    contact_style = ParagraphStyle(
        "Contact",
        fontSize=8.5,
        fontName="Helvetica",
        textColor=colors.HexColor("#444444"),
        alignment=TA_CENTER,
        spaceAfter=2,
        leading=12,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        fontSize=9,
        fontName="Helvetica",
        textColor=colors.HexColor("#333333"),
        alignment=TA_CENTER,
        spaceAfter=3,
        leading=12,
    )
    section_style = ParagraphStyle(
        "Section",
        fontSize=9.5,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#111111"),
        spaceBefore=6,
        spaceAfter=2,
        leading=12,
    )
    jobtitle_style = ParagraphStyle(
        "JobTitle",
        fontSize=9.5,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#111111"),
        spaceAfter=1,
        leading=13,
    )
    company_style = ParagraphStyle(
        "Company",
        fontSize=9,
        fontName="Helvetica-Oblique",
        textColor=colors.HexColor("#555555"),
        spaceAfter=1,
        leading=12,
    )
    body_style = ParagraphStyle(
        "Body",
        fontSize=9.5,
        fontName="Helvetica",
        textColor=colors.HexColor("#222222"),
        spaceAfter=2,
        leading=13,
    )
    bullet_style = ParagraphStyle(
        "Bullet",
        fontSize=9.5,
        fontName="Helvetica",
        textColor=colors.HexColor("#222222"),
        leftIndent=12,
        bulletIndent=3,
        spaceAfter=2,
        leading=13,
    )

    story = []
    lines = resume_text.split("\n")
    i = 0

    # ── Header block ───────────────────────────────────────────────────────────
    # Read consecutive non-empty lines at the top as the header.
    # First line  → name (large, centered, bold)
    # Rest        → contact / subtitle lines (small, centered)
    # Stop at the first blank line — that ends the header.

    header_lines = []
    while i < len(lines) and lines[i].strip():
        header_lines.append(lines[i].strip())
        i += 1

    if header_lines:
        # ── Name ──────────────────────────────────────────────────────────────
        story.append(Paragraph(header_lines[0], name_style))

        # ── Contact line – built from applicant dict so links are always current
        # LinkedIn and Portfolio are rendered as clickable PDF hyperlinks.
        _contact_re = re.compile(r'@|linkedin|http|portfolio|^\+1', re.IGNORECASE)
        contact_parts = []
        if applicant.get("email"):
            contact_parts.append(applicant["email"])
        if applicant.get("phone"):
            contact_parts.append(applicant["phone"])
        if applicant.get("location"):
            contact_parts.append(applicant["location"])
        if applicant.get("linkedin"):
            url = applicant["linkedin"]
            label = url.replace("https://", "").replace("http://", "")
            contact_parts.append(f'<a href="{url}" color="#0070f3">{label}</a>')
        if applicant.get("portfolio"):
            url = applicant["portfolio"]
            label = url.replace("https://", "").replace("http://", "")
            contact_parts.append(f'<a href="{url}" color="#0070f3">{label}</a>')

        if contact_parts:
            story.append(Paragraph("  ·  ".join(contact_parts), contact_style))

        # ── Title / subtitle line – any non-contact header lines after the first
        for hline in header_lines[1:]:
            if _contact_re.search(hline) or hline.startswith("+1"):
                continue   # skip – covered by the applicant-dict contact line above
            story.append(Paragraph(hline, subtitle_style))

    # Horizontal rule after header
    story.append(HRFlowable(
        width="100%", thickness=0.75,
        color=colors.HexColor("#bbbbbb"),
        spaceBefore=4, spaceAfter=5,
    ))

    # Skip blank lines that follow the header
    while i < len(lines) and not lines[i].strip():
        i += 1

    # ── Body ───────────────────────────────────────────────────────────────────
    while i < len(lines):
        line = lines[i].strip()
        i += 1

        # Blank line → small vertical gap
        if not line:
            story.append(Spacer(1, 3))
            continue

        # Section headers: ALL CAPS, more than 2 chars
        if line.isupper() and len(line) > 2:
            story.append(HRFlowable(
                width="100%", thickness=0.4,
                color=colors.HexColor("#dddddd"),
                spaceBefore=2, spaceAfter=0,
            ))
            story.append(Paragraph(line, section_style))
            continue

        # Job title lines: contain a 4-digit year → bold
        if _YEAR_RE.search(line):
            story.append(Paragraph(line, jobtitle_style))
            continue

        # Company / location lines: contain "·" or " — "
        if "·" in line or " — " in line or "—" in line:
            story.append(Paragraph(line, company_style))
            continue

        # Bullet points with explicit markers
        if line.startswith(("•", "-", "–", "*", "•")):
            text = line.lstrip("••-–* ").strip()
            story.append(Paragraph(f"• {text}", bullet_style))
            continue

        # Default: body paragraph
        story.append(Paragraph(line, body_style))

    # ── Build ──────────────────────────────────────────────────────────────────
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
