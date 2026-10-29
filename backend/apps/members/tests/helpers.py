import io

from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook
from PIL import Image


def pdf_file(name="document.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF", content_type="application/pdf")


def disguised_file(name="document.pdf"):
    """An executable pretending to be a PDF."""
    return SimpleUploadedFile(name, b"MZ\x90\x00\x03\x00\x00\x00", content_type="application/pdf")


def png_file(name="photo.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (41, 60, 156)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def xlsx_file(header, rows, name="members.xlsx"):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Members"
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return SimpleUploadedFile(
        name, buffer.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def csv_file(header, rows, name="members.csv"):
    lines = [",".join(header)] + [",".join(str(c) for c in row) for row in rows]
    return SimpleUploadedFile(name, ("\n".join(lines) + "\n").encode(), content_type="text/csv")
