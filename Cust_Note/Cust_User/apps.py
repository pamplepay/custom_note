from django.apps import AppConfig


class CustUserConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "Cust_User"
    verbose_name = '1. 고객 관리'

    def ready(self):
        import Cust_User.signals
