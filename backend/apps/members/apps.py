from django.apps import AppConfig

class MembersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    # ✅ THIS IS THE MISSING LINE
    name = 'apps.members'
    verbose_name = 'Members Directory'

    def ready(self):
        import apps.members.signals