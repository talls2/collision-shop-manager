"""
PDFService: Generate estimate sheets, invoices, and work orders as PDF.
Uses ReportLab for PDF generation.
"""
import io
import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

# Logo bundled with the backend so it's always available, regardless of CWD
LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.png")


def _fmt(n):
    """Format number as currency."""
    if n is None:
        return "$0.00"
    return f"${float(n):,.2f}"


def _date(d):
    if not d:
        return "—"
    try:
        return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%m/%d/%Y")
    except Exception:
        return d or "—"


def _build_header(story, styles, shop, doc_type, doc_number, date_str):
    """Build common document header: logo on the left, shop info on the right."""
    shop_name = shop.get("shop_name", "Auto Body Shop") if shop else "Auto Body Shop"
    shop_addr = ""
    if shop:
        parts = [shop.get("address", ""), shop.get("city", ""), shop.get("state", "")]
        shop_addr = ", ".join(p for p in parts if p)
        if shop.get("zip_code"):
            shop_addr += " " + shop["zip_code"]
    shop_phone = shop.get("phone", "") if shop else ""
    shop_email = shop.get("email", "") if shop else ""

    # ── Right column: shop info text ──
    title_style = ParagraphStyle("ShopTitle", parent=styles["Title"],
                                  fontSize=18, textColor=colors.HexColor("#1a5c2a"),
                                  spaceAfter=2, alignment=TA_RIGHT)
    info_style = ParagraphStyle("ShopInfo", parent=styles["Normal"],
                                 fontSize=9, alignment=TA_RIGHT,
                                 textColor=colors.HexColor("#475569"))

    info_lines = [Paragraph(shop_name, title_style)]
    if shop_addr:
        info_lines.append(Paragraph(shop_addr, info_style))
    contact_parts = [p for p in [shop_phone, shop_email] if p]
    if contact_parts:
        info_lines.append(Paragraph(" | ".join(contact_parts), info_style))

    # ── Left column: logo (if available) ──
    if os.path.exists(LOGO_PATH):
        # Logo is 1080x500 (~2.16:1). Render at ~2.4" wide.
        logo = Image(LOGO_PATH, width=2.4 * inch, height=2.4 / 2.16 * inch)
        left_cell = logo
    else:
        left_cell = Paragraph("", styles["Normal"])

    header_table = Table([[left_cell, info_lines]], colWidths=[2.6 * inch, 4.7 * inch])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))

    # Document type header
    header_style = ParagraphStyle("DocHeader", parent=styles["Heading1"],
                                   fontSize=16, textColor=colors.HexColor("#1e293b"),
                                   alignment=TA_LEFT)
    story.append(Paragraph(f"{doc_type}: {doc_number}", header_style))
    story.append(Paragraph(f"Date: {date_str}", styles["Normal"]))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1")))
    story.append(Spacer(1, 12))


def _build_signature_block(story, styles, ro):
    """
    Render the work-authorization signature area. If ro has a customer_signature
    (a base64-encoded PNG data URL), embed the image. Otherwise leave the
    classic blank sign-here line for paper signing.
    """
    import base64
    sig_data_url = ro.get("customer_signature") or ""
    sig_date = ro.get("customer_signature_date") or ""

    if sig_data_url and sig_data_url.startswith("data:image"):
        try:
            _, b64 = sig_data_url.split(",", 1)
            raw = base64.b64decode(b64)
            img = Image(io.BytesIO(raw), width=2.5 * inch, height=0.9 * inch)
            sig_label = Paragraph("<b>Customer Signature:</b>", styles["Normal"])
            date_str = _date(sig_date) if sig_date else ""
            date_cell = Paragraph(f"<b>Date:</b> {date_str}" if date_str else "<b>Date:</b> ________________", styles["Normal"])
            t = Table([[sig_label, img, date_cell]], colWidths=[110, 200, 180])
            t.setStyle(TableStyle([
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("LINEBELOW", (1, 0), (1, 0), 0.5, colors.HexColor("#94a3b8")),
            ]))
            story.append(t)
            return
        except Exception:
            pass  # fall through to blank line on any image decoding issue

    # No signature on file — keep the classic paper-signing line.
    sig_data = [["Customer Signature: ______________________________", "", "Date: ________________"]]
    t = Table(sig_data, colWidths=[250, 40, 200])
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9)]))
    story.append(t)


def _build_info_table(story, styles, left_data, right_data):
    """Build a two-column info section (customer/vehicle or insurance info)."""
    left_rows = [[Paragraph(f"<b>{k}:</b>", styles["Normal"]),
                   Paragraph(str(v), styles["Normal"])] for k, v in left_data]
    right_rows = [[Paragraph(f"<b>{k}:</b>", styles["Normal"]),
                    Paragraph(str(v), styles["Normal"])] for k, v in right_data]

    max_len = max(len(left_rows), len(right_rows))
    while len(left_rows) < max_len:
        left_rows.append(["", ""])
    while len(right_rows) < max_len:
        right_rows.append(["", ""])

    combined = []
    for i in range(max_len):
        combined.append(left_rows[i] + [""] + right_rows[i])

    col_widths = [90, 170, 20, 90, 170]
    t = Table(combined, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))


def _build_lines_table(story, styles, lines, show_cost=False):
    """Build the line items table."""
    header = ["#", "Type", "Operation", "Description", "Qty", "Hours", "Rate", "Total"]
    if show_cost:
        header.insert(-1, "Cost")

    rows = [header]
    for line in lines:
        ln = line.get("line_number", "")
        lt = (line.get("line_type", "") or "").title()
        op = (line.get("operation", "") or "").title()
        desc = line.get("description", "")
        qty = line.get("quantity", 1)
        hours = line.get("labor_hours", 0) or line.get("paint_hours", 0) or 0
        rate = line.get("labor_rate", 0) or line.get("paint_rate", 0) or 0
        total = line.get("line_total", 0) or 0

        row = [str(ln), lt, op, desc, f"{qty:.0f}",
               f"{hours:.1f}" if hours else "—",
               _fmt(rate) if rate else "—",
               _fmt(total)]
        if show_cost:
            cost = line.get("part_cost", 0) or 0
            row.insert(-1, _fmt(cost) if cost else "—")
        rows.append(row)

    if show_cost:
        col_widths = [25, 50, 55, 145, 30, 40, 50, 50, 55]
    else:
        col_widths = [25, 55, 60, 175, 35, 45, 55, 60]

    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (4, 0), (-1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))


def _build_totals(story, styles, data, is_invoice=False):
    """Build the totals summary section."""
    right_style = ParagraphStyle("RightAlign", parent=styles["Normal"],
                                  alignment=TA_RIGHT, fontSize=10)
    bold_right = ParagraphStyle("BoldRight", parent=right_style,
                                 fontName="Helvetica-Bold", fontSize=11)

    totals_data = [
        ["Labor:", _fmt(data.get("subtotal_labor", 0))],
        ["Parts:", _fmt(data.get("subtotal_parts", 0))],
        ["Paint:", _fmt(data.get("subtotal_paint", 0))],
    ]
    if data.get("subtotal_sublet"):
        totals_data.append(["Sublet:", _fmt(data["subtotal_sublet"])])
    if data.get("subtotal_other"):
        totals_data.append(["Other:", _fmt(data["subtotal_other"])])
    if data.get("tax_exempt"):
        totals_data.append(["Tax:", "EXEMPT"])
    elif data.get("tax_amount"):
        totals_data.append(["Tax:", _fmt(data["tax_amount"])])
    totals_data.append(["TOTAL:", _fmt(data.get("total_amount", 0))])

    if is_invoice:
        totals_data.append(["Amount Paid:", _fmt(data.get("amount_paid", 0))])
        totals_data.append(["BALANCE DUE:", _fmt(data.get("balance_due", 0))])
        if data.get("deductible"):
            totals_data.append(["Deductible:", _fmt(data["deductible"])])

    totals_rows = []
    for label, val in totals_data:
        is_bold = label in ("TOTAL:", "BALANCE DUE:")
        s = bold_right if is_bold else right_style
        totals_rows.append([
            Paragraph(f"<b>{label}</b>" if is_bold else label, s),
            Paragraph(f"<b>{val}</b>" if is_bold else val, s),
        ])

    t = Table(totals_rows, colWidths=[120, 100])
    t.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("LINEABOVE", (0, -1 if not is_invoice else -3), (-1, -1 if not is_invoice else -3),
         1.5, colors.HexColor("#1e293b")),
    ]))

    # Right-align the totals table
    wrapper = Table([[None, t]], colWidths=[320, 220])
    wrapper.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(wrapper)


def generate_estimate_pdf(estimate, lines, shop=None):
    """Generate an estimate PDF document."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=0.6 * inch, rightMargin=0.6 * inch,
                            topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    styles = getSampleStyleSheet()
    story = []

    est_num = estimate.get("estimate_number", "")
    est_date = _date(estimate.get("estimate_date") or estimate.get("created_at", "")[:10])

    _build_header(story, styles, shop, "ESTIMATE", est_num, est_date)

    # Customer / Vehicle info
    cust_name = estimate.get("company_name") or \
        " ".join(x for x in [estimate.get("first_name"), estimate.get("last_name")] if x).strip() or "—"

    veh = " ".join(str(x) for x in [
        estimate.get("vehicle_year") or estimate.get("year"),
        estimate.get("vehicle_make") or estimate.get("make"),
        estimate.get("vehicle_model") or estimate.get("model"),
    ] if x) or "—"

    # Build the customer's primary contact address and (separately) the billing
    # address. Same logic as the invoice PDF — keep these in sync if you change one.
    def _clean(v):
        return (str(v).strip() if v not in (None, "") else "")
    def _addr(prefix=""):
        ln1 = _clean(estimate.get(f"{prefix}address"))
        city = _clean(estimate.get(f"{prefix}city"))
        state = _clean(estimate.get(f"{prefix}state"))
        zip_code = _clean(estimate.get(f"{prefix}zip" if prefix else "customer_zip"))
        ln2_parts = []
        if city: ln2_parts.append(city)
        if state or zip_code: ln2_parts.append(" ".join(x for x in [state, zip_code] if x))
        ln2 = ", ".join(ln2_parts)
        return "<br/>".join(p for p in [ln1, ln2] if p)
    primary_addr = _addr("customer_")
    billing_addr = _addr("billing_")
    cust_block = cust_name + (("<br/>" + primary_addr) if primary_addr else "")
    bill_to_value = billing_addr or primary_addr or "—"

    left_data = [
        ("Customer", cust_block),
        ("Bill To", bill_to_value),
        ("Vehicle", veh),
        ("VIN", estimate.get("vin", "—")),
        ("Color", estimate.get("color", "—")),
    ]
    right_data = [
        ("Insurance", estimate.get("insurance_name") or estimate.get("company_name_ins", "—")),
        ("Claim #", estimate.get("claim_number", "—")),
        ("Deductible", _fmt(estimate.get("deductible", 0))),
        ("Status", (estimate.get("status", "") or "").title()),
    ]

    _build_info_table(story, styles, left_data, right_data)

    # Damage description
    if estimate.get("damage_description"):
        story.append(Paragraph("<b>Damage Description:</b>", styles["Normal"]))
        story.append(Paragraph(estimate["damage_description"], styles["Normal"]))
        story.append(Spacer(1, 10))

    # Line items
    if lines:
        story.append(Paragraph("<b>Line Items</b>", styles["Heading3"]))
        _build_lines_table(story, styles, lines)

    # Totals
    _build_totals(story, styles, estimate)

    # Footer
    story.append(Spacer(1, 24))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1")))
    story.append(Spacer(1, 8))
    footer_style = ParagraphStyle("Footer", parent=styles["Normal"],
                                   fontSize=8, textColor=colors.HexColor("#94a3b8"))
    story.append(Paragraph("This estimate is valid for 30 days from the date above. "
                           "Actual repair costs may vary upon teardown and inspection.", footer_style))

    doc.build(story)
    buf.seek(0)
    return buf


def generate_invoice_pdf(ro, lines, payments=None, shop=None):
    """Generate an invoice/final bill PDF from a repair order."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=0.6 * inch, rightMargin=0.6 * inch,
                            topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    styles = getSampleStyleSheet()
    story = []

    ro_num = ro.get("ro_number", "")
    ro_date = _date(ro.get("create_date") or ro.get("created_at", "")[:10])

    _build_header(story, styles, shop, "INVOICE", ro_num, ro_date)

    # Customer / Vehicle info — keys come from `c.first_name`/`c.last_name` joined
    # in get_full, NOT prefixed customer_first/customer_last. Was rendering "—"
    # for individual (non-company) customers because of the wrong key names.
    cust_name = ro.get("company_name") or \
        " ".join(x for x in [ro.get("first_name"), ro.get("last_name")] if x).strip() or "—"

    veh = " ".join(str(x) for x in [
        ro.get("vehicle_year") or ro.get("year"),
        ro.get("vehicle_make") or ro.get("make"),
        ro.get("vehicle_model") or ro.get("model"),
    ] if x) or "—"

    # Adapt the primary identifier and usage label to the vehicle type so trailers
    # show "Serial #" instead of "VIN" and equipment shows "Engine Hours".
    vt = (ro.get("vehicle_type") or "").lower()
    is_trailer = vt.startswith("trailer_")
    is_equipment = vt == "equipment"
    id_label = "Serial #" if (is_trailer or is_equipment) else "VIN"
    if is_equipment:
        usage_label = "Engine Hours"
        usage_value = f"{ro['engine_hours']:,}" if ro.get("engine_hours") else "Unknown"
    elif is_trailer:
        usage_label = None  # trailers don't track mileage
        usage_value = None
    else:
        usage_label = "Mileage"
        usage_value = f"{ro['mileage']:,}" if ro.get("mileage") else "Unknown"

    # Build the customer's primary contact address and (separately) the billing
    # address. Strip whitespace so " " values don't sneak through as truthy.
    def _clean(v):
        return (str(v).strip() if v not in (None, "") else "")
    def _addr(prefix=""):
        ln1 = _clean(ro.get(f"{prefix}address"))
        city = _clean(ro.get(f"{prefix}city"))
        state = _clean(ro.get(f"{prefix}state"))
        zip_code = _clean(ro.get(f"{prefix}zip" if prefix else "customer_zip"))
        ln2_parts = []
        if city:
            ln2_parts.append(city)
        if state or zip_code:
            ln2_parts.append(" ".join(x for x in [state, zip_code] if x))
        ln2 = ", ".join(ln2_parts)
        # ReportLab Paragraph uses <br/> for line breaks, not \n
        return "<br/>".join(p for p in [ln1, ln2] if p)
    primary_addr = _addr("customer_")
    billing_addr = _addr("billing_")

    # Pack the primary address right under the name in the same cell so it
    # reads "Demo Customer Co / 100 Example St / Springfield, MA 01101" — typical invoice format.
    cust_block = cust_name + (("<br/>" + primary_addr) if primary_addr else "")

    # Always show Bill To row — fall back to the primary address if no
    # separate billing address is on file, then to "—" if there's nothing.
    bill_to_value = billing_addr or primary_addr or "—"

    left_data = [
        ("Customer", cust_block),
        ("Bill To", bill_to_value),
        ("Vehicle", veh),
        (id_label, ro.get("vin", "—")),
    ]
    if usage_label:
        left_data.append((usage_label, usage_value))
    right_data = [
        ("Insurance", ro.get("insurance_name", "—")),
        ("Claim #", ro.get("claim_number", "—")),
        ("Deductible", _fmt(ro.get("deductible", 0))),
        ("Date In", _date(ro.get("vehicle_arrived_date"))),
    ]

    _build_info_table(story, styles, left_data, right_data)

    # Line items
    if lines:
        story.append(Paragraph("<b>Repair Operations</b>", styles["Heading3"]))
        _build_lines_table(story, styles, lines, show_cost=False)

    # Totals
    _build_totals(story, styles, ro, is_invoice=True)

    # Payments
    if payments:
        story.append(Spacer(1, 16))
        story.append(Paragraph("<b>Payments Received</b>", styles["Heading3"]))
        pay_rows = [["Date", "Method", "Payer", "Reference", "Amount"]]
        for p in payments:
            pay_rows.append([
                _date(p.get("payment_date")),
                (p.get("payment_method", "") or "").replace("_", " ").title(),
                p.get("payer_name", "—"),
                p.get("reference_number", "—"),
                _fmt(p.get("amount", 0)),
            ])
        t = Table(pay_rows, colWidths=[80, 80, 120, 100, 80])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ]))
        story.append(t)

    # Signature block — if a customer signature is on file, embed the image.
    # Otherwise show the blank "sign here" line for on-paper signing.
    story.append(Spacer(1, 30))
    _build_signature_block(story, styles, ro)

    # Footer
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1")))
    footer_style = ParagraphStyle("Footer", parent=styles["Normal"],
                                   fontSize=8, textColor=colors.HexColor("#94a3b8"))
    story.append(Paragraph("Thank you for your business. Payment is due upon delivery of vehicle.", footer_style))

    doc.build(story)
    buf.seek(0)
    return buf


def generate_work_order_pdf(ro, lines, shop=None):
    """Generate a work order PDF for the shop floor."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=0.6 * inch, rightMargin=0.6 * inch,
                            topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    styles = getSampleStyleSheet()
    story = []

    ro_num = ro.get("ro_number", "")
    _build_header(story, styles, shop, "WORK ORDER", ro_num,
                  _date(ro.get("create_date") or ro.get("created_at", "")[:10]))

    # Customer + vehicle info
    cust_name = ro.get("company_name") or \
        " ".join(x for x in [ro.get("first_name"), ro.get("last_name")] if x).strip() or "—"

    veh = " ".join(str(x) for x in [
        ro.get("vehicle_year") or ro.get("year"),
        ro.get("vehicle_make") or ro.get("make"),
        ro.get("vehicle_model") or ro.get("model"),
    ] if x) or "—"

    left_data = [
        ("Customer", cust_name),
        ("Vehicle", veh),
        ("Color", ro.get("color") or ro.get("vehicle_color") or "—"),
        ("VIN", ro.get("vin", "—")),
        ("Priority", (ro.get("priority", "normal") or "normal").title()),
    ]
    right_data = [
        ("Technician", f"{ro.get('tech_first', '')} {ro.get('tech_last', '')}".strip() or "—"),
        ("Painter", f"{ro.get('painter_first', '')} {ro.get('painter_last', '')}".strip() or "—"),
        ("Target Date", _date(ro.get("target_delivery_date"))),
        ("Status", (ro.get("status", "") or "").replace("_", " ").title()),
    ]

    _build_info_table(story, styles, left_data, right_data)

    # Line items with checkboxes
    if lines:
        story.append(Paragraph("<b>Operations</b>", styles["Heading3"]))
        header = ["Done", "#", "Type", "Description", "Hours", "Notes"]
        rows = [header]
        for line in lines:
            hours = line.get("labor_hours", 0) or line.get("paint_hours", 0) or 0
            rows.append([
                "[ ]",
                str(line.get("line_number", "")),
                (line.get("line_type", "") or "").title(),
                line.get("description", ""),
                f"{hours:.1f}" if hours else "—",
                "",
            ])

        t = Table(rows, colWidths=[35, 25, 50, 220, 45, 120])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 8),
        ]))
        story.append(t)

    # Notes section
    story.append(Spacer(1, 20))
    story.append(Paragraph("<b>Notes:</b>", styles["Normal"]))
    if ro.get("notes"):
        story.append(Paragraph(ro["notes"], styles["Normal"]))
    story.append(Spacer(1, 8))
    for _ in range(4):
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"),
                                spaceBefore=12))

    doc.build(story)
    buf.seek(0)
    return buf


# ═════════════════════════════════════════════════════════════════
# REPORT PDF (generic tabular report)
# Used by Reports → Export PDF buttons. Any tabular report can be
# rendered by passing a title, headers, and rows.
# ═════════════════════════════════════════════════════════════════
def generate_report_pdf(title, headers, rows, shop=None, subtitle=None,
                         summary_stats=None, footer_note=None,
                         col_widths=None, landscape_mode=False,
                         align_right=None):
    """
    Render a tabular report as PDF.

    - title: big header ("Production Summary", "AR Aging", etc.)
    - headers: list of column header strings
    - rows: list of lists (each inner list = one row, values pre-formatted)
    - subtitle: small line under the title (e.g. date range, generated at)
    - summary_stats: optional list of (label, value) pairs for a stat grid
    - footer_note: small italic caption at the bottom
    - align_right: iterable of column indices to right-align
    """
    from reportlab.lib.pagesizes import letter as _letter, landscape as _landscape

    buf = io.BytesIO()
    page_size = _landscape(_letter) if landscape_mode else _letter
    doc = SimpleDocTemplate(buf, pagesize=page_size,
                            leftMargin=0.5 * inch, rightMargin=0.5 * inch,
                            topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    styles = getSampleStyleSheet()
    story = []

    generated = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    _build_header(story, styles, shop, "REPORT", title, generated)

    if subtitle:
        subtitle_style = ParagraphStyle("Subtitle", parent=styles["Normal"],
                                         fontSize=10, textColor=colors.HexColor("#475569"),
                                         spaceAfter=8)
        story.append(Paragraph(subtitle, subtitle_style))
        story.append(Spacer(1, 6))

    # Summary stat grid (label + value pairs shown in a compact table)
    if summary_stats:
        stat_data = []
        row_pair = []
        for label, value in summary_stats:
            row_pair.append(Paragraph(
                f"<font size=8 color='#64748b'>{label}</font><br/>"
                f"<font size=12 color='#0f172a'><b>{value}</b></font>",
                styles["Normal"]
            ))
            if len(row_pair) == 4:
                stat_data.append(row_pair)
                row_pair = []
        if row_pair:
            while len(row_pair) < 4:
                row_pair.append("")
            stat_data.append(row_pair)
        if stat_data:
            page_w = doc.width
            stat_col = page_w / 4
            t = Table(stat_data, colWidths=[stat_col] * 4)
            t.setStyle(TableStyle([
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            story.append(t)
            story.append(Spacer(1, 14))

    # Main table
    if headers and rows is not None:
        table_data = [headers] + (rows if rows else [["(no data)"] + [""] * (len(headers) - 1)])

        if col_widths is None:
            page_w = doc.width
            col_widths = [page_w / len(headers)] * len(headers)

        t = Table(table_data, colWidths=col_widths, repeatRows=1)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5c2a")),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, 0), 9),
            ("FONTSIZE",   (0, 1), (-1, -1), 8.5),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",(0, 0), (-1, -1), 6),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                [colors.white, colors.HexColor("#f8fafc")]),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#164e22")),
            ("GRID",      (0, 1), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ]
        if align_right:
            for col in align_right:
                style_cmds.append(("ALIGN", (col, 1), (col, -1), "RIGHT"))
        t.setStyle(TableStyle(style_cmds))
        story.append(t)

    if footer_note:
        story.append(Spacer(1, 12))
        footer_style = ParagraphStyle("ReportFooter", parent=styles["Normal"],
                                       fontSize=8, textColor=colors.HexColor("#94a3b8"),
                                       alignment=TA_LEFT)
        story.append(Paragraph(footer_note, footer_style))

    doc.build(story)
    buf.seek(0)
    return buf
