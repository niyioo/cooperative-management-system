from django.apps import AppConfig


class LoansConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.loans"
    label = "loans"
    verbose_name = "Loans"

    def ready(self):
        from apps.ledger.batches import register

        from . import services  # noqa: F401  (registers ledger posting hooks)
        from .batches import LoanRepaymentBatchHandler

        register(LoanRepaymentBatchHandler())
