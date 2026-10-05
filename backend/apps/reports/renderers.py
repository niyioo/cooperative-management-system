"""
Render a report Result as JSON (on-screen table), Excel or PDF.

Every rendering carries the same header: cooperative name, report title, the
filters applied, and who generated it and when, so a printed or e-mailed
copy is self-explanatory.
"""
import io
from xml.sax.saxutils import escape
from datetime import date, datetime
from decimal import Decimal

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.common.spreadsheets import workbook_bytes
from apps.common.serializers import money_to_str
from apps.configuration.models import CooperativeSettings

from .engine import DATE, INT, MONEY, PDF_ROWS, PERCENT, SCREEN_ROWS, XLSX_ROWS, filter_description

NAVY = "293C9C"
STRIPE = "F3F5FB"


def _text(value, kind):
    """Plain-text form of a cell (PDF and summaries)."""
    if value is None or value == "":
        return ""
    if kind == MONEY:
        return f"{Decimal(value):,.2f}"
    if kind == PERCENT:
        return f"{Decimal(value).normalize():f}%"
    if kind == INT:
        return f"{value:,}"
    if isinstance(value, datetime):
        return f"{timezone.localtime(value):%d/%m/%Y}"
    if isinstance(value, date):
        return f"{value:%d/%m/%Y}"
    return str(value)


def _header(result, lookups, user):
    coop = CooperativeSettings.load()
    generated = timezone.localtime(result.generated_at)
    return {
        "cooperative": coop.name,
        "institution": coop.parent_institution,
        "filters": filter_description(result, lookups),
        "generated": f"{generated:%d %b %Y %H:%M} by {user.full_name}",
    }


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def to_json(result, lookups, user):
    header = _header(result, lookups, user)
    rows = result.rows[:SCREEN_ROWS]
    return money_to_str({
        "key": result.report.key,
        "title": result.report.title,
        "description": result.report.description,
        "cooperative": header["cooperative"],
        "generated_at": result.generated_at,
        "filters": [{"label": label, "value": value} for label, value in header["filters"]],
        "applied": {k: (str(v) if not isinstance(v, int) else v) for k, v in result.params.items()},
        "columns": [{"key": c.key, "label": c.label, "kind": c.kind, "total": c.total} for c in result.columns],
        "rows": rows,
        "total_rows": len(result.rows),
        "truncated": len(result.rows) > SCREEN_ROWS,
        "totals": result.totals(),
        "summary": [{"label": label, "value": value, "kind": kind} for label, value, kind in result.summary],
    })


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------

def to_xlsx(result, lookups, user):
    header = _header(result, lookups, user)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = result.report.title[:31]
    columns = result.columns

    sheet.append([header["cooperative"]])
    sheet["A1"].font = Font(bold=True, size=14, color=NAVY)
    sheet.append([result.report.title])
    sheet["A2"].font = Font(bold=True, size=12)
    for label, value in header["filters"]:
        sheet.append([f"{label}: {value}"])
    sheet.append([f"Generated {header['generated']}"])
    sheet.append([])

    header_row = sheet.max_row + 1
    sheet.append([c.label + (" (₦)" if c.kind == MONEY else "") for c in columns])
    for cell in sheet[header_row]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(vertical="center", wrap_text=True)

    rows = result.rows[:XLSX_ROWS]
    for r in rows:
        values = []
        for c in columns:
            v = r.get(c.key)
            if isinstance(v, datetime):
                v = timezone.localtime(v).replace(tzinfo=None)
            values.append(v)
        sheet.append(values)
    first_data, last_data = header_row + 1, sheet.max_row

    totals = result.totals()
    if totals:
        sheet.append([("Totals" if i == 0 else totals.get(c.key)) for i, c in enumerate(columns)])
        for cell in sheet[sheet.max_row]:
            cell.font = Font(bold=True)

    for idx, c in enumerate(columns, start=1):
        letter = get_column_letter(idx)
        fmt = {MONEY: "#,##0.00", DATE: "DD/MM/YYYY", INT: "#,##0", PERCENT: '0.00##"%"'}.get(c.kind)
        if fmt:
            for row in sheet.iter_rows(min_row=first_data, max_row=sheet.max_row, min_col=idx, max_col=idx):
                row[0].number_format = fmt
                if c.kind in (MONEY, INT, PERCENT):
                    row[0].alignment = Alignment(horizontal="right")
        width = max([len(c.label) + 4] + [len(_text(r.get(c.key), c.kind)) + 2 for r in rows[:200]])
        sheet.column_dimensions[letter].width = min(max(width, 10), 48)

    if rows:
        sheet.auto_filter.ref = f"A{header_row}:{get_column_letter(len(columns))}{last_data}"
    sheet.freeze_panes = f"A{header_row + 1}"

    if result.summary:
        sheet.append([])
        sheet.append(["Summary"])
        sheet.cell(row=sheet.max_row, column=1).font = Font(bold=True, color=NAVY)
        for label, value, kind in result.summary:
            sheet.append([label, value])
            if kind == MONEY:
                sheet.cell(row=sheet.max_row, column=2).number_format = "#,##0.00"
    if len(result.rows) > XLSX_ROWS:
        sheet.append([f"Only the first {XLSX_ROWS:,} of {len(result.rows):,} rows are included. Narrow the filters for the rest."])

    return workbook_bytes(workbook)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

WEIGHTS = {MONEY: 2.0, DATE: 1.6, INT: 1.2, PERCENT: 1.2}
WIDE_TEXT = {"member": 3.2, "description": 4.0, "account": 3.0, "product": 2.4, "reason": 2.2, "type": 2.4, "email": 3.0}


NO_WRAP = {"membership_number", "reference", "account_number"}


def _column_widths(columns, rows, available, font_size):
    """Identifiers get exactly the width of their longest value (they must not wrap); the rest share what's left by weight."""
    fixed = {}
    for i, c in enumerate(columns):
        if c.key in NO_WRAP:
            longest = max([stringWidth(c.label, "Helvetica-Bold", font_size)]
                          + [stringWidth(_text(r.get(c.key), c.kind), "Helvetica", font_size) for r in rows[:500]])
            fixed[i] = longest + 8  # cell padding
    weights = {i: WEIGHTS.get(c.kind, WIDE_TEXT.get(c.key, 1.8)) for i, c in enumerate(columns) if i not in fixed}
    remaining = max(available - sum(fixed.values()), available * 0.4)
    total = sum(weights.values()) or 1
    return [fixed.get(i, remaining * weights.get(i, 0) / total) for i in range(len(columns))]


def to_pdf(result, lookups, user):
    header = _header(result, lookups, user)
    report = result.report
    pagesize = landscape(A4) if report.landscape else A4
    buffer = io.BytesIO()
    margin = 12 * mm
    doc = SimpleDocTemplate(buffer, pagesize=pagesize, leftMargin=margin, rightMargin=margin, topMargin=margin, bottomMargin=margin,
                            title=report.title, author=header["cooperative"])
    styles = getSampleStyleSheet()
    navy = colors.HexColor(f"#{NAVY}")
    columns = result.columns
    font_size = 8 if len(columns) <= 9 else 6.5
    cell_style = styles["BodyText"].clone("cell", fontSize=font_size, leading=font_size + 2)
    head_style = cell_style.clone("head", textColor=colors.white, fontName="Helvetica-Bold")
    small = styles["BodyText"].clone("small", fontSize=8, leading=10)
    styles["Title"].textColor = navy

    story = [
        Paragraph(escape(header["cooperative"]), styles["Title"]),
        Paragraph(escape(header["institution"]), styles["BodyText"]),
        Spacer(1, 3 * mm),
        Paragraph(f"<b>{report.title}</b>", styles["Heading2"]),
    ]
    for label, value in header["filters"]:
        story.append(Paragraph(f"<b>{label}:</b> {escape(value)}", small))
    story.append(Paragraph(f"<b>Generated:</b> {escape(header['generated'])}", small))
    story.append(Spacer(1, 4 * mm))

    # ReportLab's built-in fonts have no naira sign, so money columns say NGN.
    data = [[Paragraph(c.label + (" (NGN)" if c.kind == MONEY else ""), head_style) for c in columns]]
    rows = result.rows[:PDF_ROWS]
    for r in rows:
        data.append([
            Paragraph(escape(_text(r.get(c.key), c.kind)), cell_style) if c.kind not in WEIGHTS and c.key not in NO_WRAP else _text(r.get(c.key), c.kind)
            for c in columns
        ])
    if not rows:
        data.append([Paragraph("No records match these filters.", cell_style)] + [""] * (len(columns) - 1))
    totals = result.totals()
    if totals:
        data.append([("Totals" if i == 0 else _text(totals.get(c.key), c.kind)) for i, c in enumerate(columns)])

    widths = _column_widths(columns, rows, pagesize[0] - 2 * margin, font_size)
    table = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1 if not totals else -2), [colors.white, colors.HexColor(f"#{STRIPE}")]),
    ]
    for i, c in enumerate(columns):
        if c.kind in (MONEY, INT, PERCENT):
            style.append(("ALIGN", (i, 1), (i, -1), "RIGHT"))
    if totals:
        style += [("LINEABOVE", (0, -1), (-1, -1), 0.8, navy), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")]
    table.setStyle(TableStyle(style))
    story.append(table)

    if len(result.rows) > PDF_ROWS:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(f"Only the first {PDF_ROWS:,} of {len(result.rows):,} rows are printed. Use the Excel export for the full list.", small))
    if result.summary:
        story.append(Spacer(1, 5 * mm))
        summary = Table([[label, _text(value, kind)] for label, value, kind in result.summary], hAlign="LEFT")
        summary.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ]))
        story.append(Paragraph("<b>Summary</b>", small))
        story.append(summary)

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(margin, 7 * mm, f"{header['cooperative']} · {report.title}")
        canvas.drawRightString(pagesize[0] - margin, 7 * mm, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
