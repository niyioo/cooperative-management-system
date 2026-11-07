def months_between(start, end):
    """Whole months from `start` to `end` (negative if end is earlier)."""
    return (end.year - start.year) * 12 + (end.month - start.month) - (end.day < start.day)
