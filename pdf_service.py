import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

PDF_DIR = os.path.join(os.path.dirname(__file__), "static", "rfq_pdfs")


# Brand colors
DARK_BLUE  = colors.HexColor("#1B2A4A")
MID_BLUE   = colors.HexColor("#2563EB")
LIGHT_BLUE = colors.HexColor("#EFF6FF")
GRAY       = colors.HexColor("#64748B")
LIGHT_GRAY = colors.HexColor("#F8FAFC")
BORDER     = colors.HexColor("#CBD5E1")
WHITE      = colors.white


def generate_rfq_pdf(rfq: dict, pr: dict, vendor: dict | None) -> str:
    os.makedirs(PDF_DIR, exist_ok=True)
    filename = f"{rfq['rfq_number'].replace('/', '-')}.pdf"
    filepath = os.path.join(PDF_DIR, filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    story  = []

    # ── Header ──────────────────────────────────────────────
    header_data = [[
        Paragraph(
            "<font color='#FFFFFF'><b>REQUEST FOR QUOTATION</b></font>",
            ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=20,
                           textColor=WHITE, leading=24)
        ),
        Paragraph(
            f"<font color='#93C5FD'><b>{rfq['rfq_number']}</b></font><br/>"
            f"<font color='#BFDBFE'>Issued: {datetime.now().strftime('%d %b %Y')}</font>",
            ParagraphStyle("ref", fontName="Helvetica", fontSize=10,
                           textColor=WHITE, alignment=TA_RIGHT, leading=16)
        ),
    ]]
    header_table = Table(header_data, colWidths=[11*cm, 6*cm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), DARK_BLUE),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 18),
        ("BOTTOMPADDING", (0,0), (-1,-1), 18),
        ("LEFTPADDING",   (0,0), (0,-1),  16),
        ("RIGHTPADDING",  (-1,0),(-1,-1), 16),
        ("ROUNDEDCORNERS",(0,0), (-1,-1), [6,6,6,6]),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.5*cm))

    # ── Company + Vendor info row ────────────────────────────
    company_block = _info_block(
        "FROM (Buyer)",
        ["AVERROA Manufacturing Co.",
         "Industrial Zone, Damascus, Syria",
         "procurement@averroa.com",
         "+963 11 000 0000"]
    )
    vendor_name    = vendor["name"]    if vendor else "—"
    vendor_email   = vendor["email"]   if vendor else "—"
    vendor_country = vendor["country"] if vendor else "—"
    vendor_block   = _info_block(
        "TO (Vendor)",
        [vendor_name, vendor_country, vendor_email]
    )
    info_table = Table([[company_block, vendor_block]],
                       colWidths=[8.5*cm, 8.5*cm])
    info_table.setStyle(TableStyle([
        ("VALIGN",  (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0), (0,-1), 0),
        ("RIGHTPADDING", (-1,0),(-1,-1), 0),
        ("INNERGRID", (0,0), (-1,-1), 0, WHITE),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.4*cm))

    # ── Reference numbers row ───────────────────────────────
    ref_data = [[
        _label_value("RFQ Number",      rfq["rfq_number"]),
        _label_value("PR Reference",    pr["pr_number"]),
        _label_value("Request Date",    pr["requested_date"]),
        _label_value("Quotation Due",   rfq["quotation_due_date"]),
    ]]
    ref_table = Table(ref_data, colWidths=[4.25*cm]*4)
    ref_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), LIGHT_BLUE),
        ("TOPPADDING",    (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("BOX",  (0,0), (-1,-1), 0.5, BORDER),
        ("LINEAFTER", (0,0), (2,-1), 0.5, BORDER),
        ("ROUNDEDCORNERS",(0,0), (-1,-1), [4,4,4,4]),
    ]))
    story.append(ref_table)
    story.append(Spacer(1, 0.5*cm))

    # ── Materials table ──────────────────────────────────────
    story.append(Paragraph(
        "Material Details",
        ParagraphStyle("sec", fontName="Helvetica-Bold", fontSize=11,
                       textColor=DARK_BLUE, spaceAfter=6)
    ))

    mat_header = ["#", "Material Description", "Quantity", "Unit", "Specifications"]
    mat_rows   = [
        ["01", pr["raw_material_name"], f"{pr['quantity']:g}", pr["unit_of_measure"],
         pr["notes"] if pr["notes"] else "As per standard spec"]
    ]
    mat_data  = [mat_header] + mat_rows
    mat_table = Table(mat_data, colWidths=[1*cm, 6.5*cm, 2.5*cm, 2*cm, 5*cm])
    mat_table.setStyle(TableStyle([
        # Header row
        ("BACKGROUND",    (0,0), (-1,0),  DARK_BLUE),
        ("TEXTCOLOR",     (0,0), (-1,0),  WHITE),
        ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,0),  9),
        ("TOPPADDING",    (0,0), (-1,0),  10),
        ("BOTTOMPADDING", (0,0), (-1,0),  10),
        ("ALIGN",         (0,0), (-1,0),  "CENTER"),
        # Data rows
        ("FONTNAME",      (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE",      (0,1), (-1,-1), 9),
        ("TOPPADDING",    (0,1), (-1,-1), 8),
        ("BOTTOMPADDING", (0,1), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("ALIGN",         (2,1), (3,-1),  "CENTER"),
        ("BACKGROUND",    (0,1), (-1,-1), LIGHT_GRAY),
        ("GRID",          (0,0), (-1,-1), 0.5, BORDER),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, LIGHT_GRAY]),
    ]))
    story.append(mat_table)
    story.append(Spacer(1, 0.5*cm))

    # ── Requester info ───────────────────────────────────────
    story.append(Paragraph(
        f"Requested by: <b>{pr['requester']}</b>",
        ParagraphStyle("req", fontName="Helvetica", fontSize=9,
                       textColor=GRAY, spaceAfter=4)
    ))

    # ── Instructions box ─────────────────────────────────────
    instructions = [
        "1. Please provide your best price including delivery to our factory.",
        "2. Quote validity must be minimum 30 days from quotation date.",
        "3. Please confirm lead time and payment terms in your response.",
        "4. Send your quotation to: procurement@averroa.com",
        f"5. Quotation must be received by: <b>{rfq['quotation_due_date']}</b>",
    ]
    inst_paras = [Paragraph(
        line,
        ParagraphStyle("inst", fontName="Helvetica", fontSize=9,
                       textColor=DARK_BLUE, leading=14, spaceAfter=2)
    ) for line in instructions]

    inst_box = Table(
        [[Paragraph("Vendor Instructions",
                    ParagraphStyle("ihead", fontName="Helvetica-Bold",
                                   fontSize=10, textColor=WHITE))],
         *[[p] for p in inst_paras]],
        colWidths=[17*cm]
    )
    inst_box.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  MID_BLUE),
        ("BACKGROUND",    (0,1), (-1,-1), LIGHT_BLUE),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 12),
        ("BOX",  (0,0), (-1,-1), 0.5, MID_BLUE),
    ]))
    story.append(inst_box)
    story.append(Spacer(1, 0.8*cm))

    # ── Signature block ──────────────────────────────────────
    sig_data = [[
        _sig_line("Prepared by"),
        _sig_line("Authorized by"),
        _sig_line("Vendor Acknowledgement"),
    ]]
    sig_table = Table(sig_data, colWidths=[5.5*cm, 5.5*cm, 6*cm])
    sig_table.setStyle(TableStyle([
        ("VALIGN",  (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0), (0,-1), 0),
        ("RIGHTPADDING", (-1,0),(-1,-1), 0),
    ]))
    story.append(sig_table)

    # ── Footer ───────────────────────────────────────────────
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Paragraph(
        "This document is generated by AVERROA Procurement System. "
        "For queries contact: procurement@averroa.com",
        ParagraphStyle("footer", fontName="Helvetica", fontSize=7,
                       textColor=GRAY, alignment=TA_CENTER, spaceBefore=4)
    ))

    doc.build(story)
    return filename


# ── Helpers ──────────────────────────────────────────────────

def _info_block(title: str, lines: list[str]) -> Table:
    rows = [[Paragraph(
        title,
        ParagraphStyle("ibtitle", fontName="Helvetica-Bold", fontSize=8,
                       textColor=GRAY, spaceAfter=4)
    )]]
    for line in lines:
        rows.append([Paragraph(
            line,
            ParagraphStyle("ibline", fontName="Helvetica", fontSize=9,
                           textColor=DARK_BLUE, leading=13)
        )])
    t = Table(rows, colWidths=[8*cm])
    t.setStyle(TableStyle([
        ("LEFTPADDING",  (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING",   (0,0), (-1,-1), 2),
        ("BOTTOMPADDING",(0,0), (-1,-1), 2),
    ]))
    return t


def _label_value(label: str, value: str) -> Table:
    t = Table([
        [Paragraph(label, ParagraphStyle("lbl", fontName="Helvetica",
                                          fontSize=7, textColor=GRAY))],
        [Paragraph(str(value), ParagraphStyle("val", fontName="Helvetica-Bold",
                                               fontSize=9, textColor=DARK_BLUE))],
    ], colWidths=[4*cm])
    t.setStyle(TableStyle([
        ("LEFTPADDING",  (0,0), (-1,-1), 0),
        ("TOPPADDING",   (0,0), (-1,-1), 0),
        ("BOTTOMPADDING",(0,0), (-1,-1), 0),
    ]))
    return t


def _sig_line(label: str) -> Table:
    t = Table([
        [Paragraph("", ParagraphStyle("sl", fontSize=9))],
        [HRFlowable(width="90%", thickness=0.5, color=DARK_BLUE)],
        [Paragraph(label, ParagraphStyle("sll", fontName="Helvetica",
                                          fontSize=8, textColor=GRAY))],
    ], colWidths=[5.5*cm])
    t.setStyle(TableStyle([
        ("TOPPADDING",   (0,0), (-1,0), 28),
        ("TOPPADDING",   (0,1), (-1,-1), 4),
        ("LEFTPADDING",  (0,0), (-1,-1), 0),
    ]))
    return t
