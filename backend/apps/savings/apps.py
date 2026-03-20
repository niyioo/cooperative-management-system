from django.apps import AppConfig

class SavingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.savings'
    verbose_name = 'Savings & Wallets'

    def ready(self):
        # We import it here so the @receiver decorators are registered
        import apps.savings.signals  # noqa: F401