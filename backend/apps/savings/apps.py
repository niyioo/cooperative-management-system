from django.apps import AppConfig


class SavingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.savings"
    label = "savings"
    verbose_name = "Savings"

    def ready(self):
        from apps.ledger.batches import register

        from .batches import ContributionBatchHandler, CyclePayoutBatchHandler, OpeningBalanceBatchHandler

        register(ContributionBatchHandler())
        register(OpeningBalanceBatchHandler())
        register(CyclePayoutBatchHandler())
