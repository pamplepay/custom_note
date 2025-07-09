from django.apps import AppConfig


class CustUserConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "Cust_User"

    def ready(self):
        import Cust_User.signals
