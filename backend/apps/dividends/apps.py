from django.apps import AppConfig


class DividendsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.dividends"
    label = "dividends"
    verbose_name = "Dividends"

    def ready(self):
        from apps.ledger.batches import register

        from .services import DividendPaymentBatchHandler  # also registers ledger posting hooks

        register(DividendPaymentBatchHandler())
