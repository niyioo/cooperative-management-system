from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = 'Core System'

    def ready(self):
        """
        This method is called when Django starts. 
        It imports the signals so they are registered with the models.
        """
        try:
            import apps.core.signals  # ✅ This is the "Magic" line
        except ImportError:
            pass