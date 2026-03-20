from django.apps import AppConfig

class MembersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    verbose_name = 'apps.members'

    def ready(self):
        import apps.members.signals