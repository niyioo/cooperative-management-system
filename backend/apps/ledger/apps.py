from django.apps import AppConfig


class LedgerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ledger"
    label = "ledger"
    verbose_name = "Ledger"

    def ready(self):
        from . import corrections  # noqa: F401  (registers the REVERSAL posting hook)
