from django.db.models.functions import Upper

from .models import Member

IDENTIFIER_FIELDS = ("membership_number", "staff_number", "ippis_number")


def members_by_identifier(values):
    """
    values: {"membership_number": {...}, "staff_number": {...}, "ippis_number": {...}}
    (upper-cased). Returns {(field, VALUE): Member} in three queries at most.
    """
    found = {}
    for field in IDENTIFIER_FIELDS:
        wanted = {v for v in values.get(field, ()) if v}
        if not wanted:
            continue
        rows = Member.objects.annotate(_key=Upper(field)).filter(_key__in=wanted).select_related("user")
        for member in rows:
            found[(field, member._key)] = member
    return found
