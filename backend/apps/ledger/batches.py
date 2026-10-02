"""
Batch handler registry. Each batch type (contributions, opening balances,
loan repayments, payouts…) is implemented by the module that owns it and
registered from its AppConfig.ready(), so the ledger stays module-agnostic.
"""
from apps.common.exceptions import DomainError


class BatchHandler:
    """Base class. Subclasses implement the parts their batch type supports."""

    batch_type = None
    permissions = ()  # needed, in addition to manage_batches, to create this batch type
    accepts_files = True
    file_options = ()  # names of extra form fields the upload accepts (e.g. "product", "period")

    def validate_file(self, header, data, options):
        """Return (lines, report). Lines are handler-specific dicts passed to create_lines()."""
        raise NotImplementedError

    def create_lines(self, actor, batch, lines):
        raise NotImplementedError

    def revalidate(self, batch):
        """Re-check PENDING lines just before posting. Return [{"reference", "member", "errors"}]."""
        return []

    def after_post(self, batch):
        """Hook after all lines are posted (e.g. mark a savings cycle as paid out)."""

    def after_reject(self, batch):
        """Hook after a batch is rejected or discarded."""

    def template(self):
        """Excel template bytes for uploads, or None."""
        return None


_HANDLERS = {}


def register(handler):
    _HANDLERS[handler.batch_type] = handler
    return handler


def get_handler(batch_type):
    try:
        return _HANDLERS[batch_type]
    except KeyError:
        raise DomainError(f"Batches of type {batch_type} are not supported yet.", code="unsupported_batch_type") from None


def uploadable_types():
    return [t for t, h in _HANDLERS.items() if h.accepts_files]
