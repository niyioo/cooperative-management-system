from django.apps import AppConfig


class InvestmentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.investments"
    label = "investments"
    verbose_name = "Investments"

    def ready(self):
        from apps.ledger.batches import register

        from . import services  # noqa: F401  (registers ledger posting hooks)
        from .batches import InvestmentContributionBatchHandler, InvestmentOpeningBalanceBatchHandler

        register(InvestmentContributionBatchHandler())
        register(InvestmentOpeningBalanceBatchHandler())
