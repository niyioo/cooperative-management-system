from django.apps import AppConfig


class ClosuresConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.closures"
    label = "closures"
    verbose_name = "Account Closures"

    def ready(self):
        from apps.ledger.batches import register

        from .services import ClosureSettlementBatchHandler

        register(ClosureSettlementBatchHandler())
