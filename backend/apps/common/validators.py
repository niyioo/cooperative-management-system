from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator

MONTH_VALIDATORS = [MinValueValidator(1), MaxValueValidator(12)]

document_extension_validator = FileExtensionValidator(["pdf", "jpg", "jpeg", "png"])
image_extension_validator = FileExtensionValidator(["jpg", "jpeg", "png"])
spreadsheet_extension_validator = FileExtensionValidator(["xlsx", "csv"])


def validate_file_size(file):
    limit = settings.MAX_UPLOAD_SIZE_BYTES
    if file.size > limit:
        raise ValidationError(f"File is too large. Maximum size is {limit // (1024 * 1024)} MB.")


# File signatures ("magic numbers"). Extensions can be faked; content can't.
_SIGNATURES = {
    "pdf": [b"%PDF-"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "xlsx": [b"PK\x03\x04"],
}


def validate_file_signature(file):
    """Reject uploads whose content does not match their extension (e.g. an .exe renamed to .pdf)."""
    name = getattr(file, "name", "") or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    expected = _SIGNATURES.get(ext)
    if not expected:
        return
    position = file.tell() if hasattr(file, "tell") else None
    file.seek(0)
    head = file.read(16)
    file.seek(position or 0)
    if not any(head.startswith(sig) for sig in expected):
        raise ValidationError(f"The file content does not match its .{ext} extension.")
