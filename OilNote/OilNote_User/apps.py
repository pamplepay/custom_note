from django.apps import AppConfig


class OilNoteUserConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "OilNote_User"
    verbose_name = '1. 고객 정보'

    def ready(self):
        import OilNote_User.signals
