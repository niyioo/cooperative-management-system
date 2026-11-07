"""
upload_to callables. Stored names are random, so original file names (which
often contain personal information) never appear in paths or URLs.
"""
import uuid
from pathlib import Path

from django.utils import timezone


def _path(prefix, filename):
    ext = Path(filename).suffix.lower()
    return f"{prefix}/{timezone.localdate():%Y/%m}/{uuid.uuid4().hex}{ext}"


def member_photo_path(instance, filename):
    return _path("members/photos", filename)


def member_document_path(instance, filename):
    return _path("members/documents", filename)


def loan_document_path(instance, filename):
    return _path("loans/documents", filename)


def closure_attachment_path(instance, filename):
    return _path("closures/attachments", filename)


def batch_source_path(instance, filename):
    return _path("ledger/batches", filename)


def cooperative_logo_path(instance, filename):
    return _path("configuration", filename)


def member_import_path(instance, filename):
    return _path("members/imports", filename)
