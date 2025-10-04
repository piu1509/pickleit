from django.apps import AppConfig
from django.conf import settings


class UserConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.user'

    def ready(self):
        import apps.user.signals
        # from apps.user.signals import register_signals_for_app
        # for app in settings.INSTALLED_APPS:
        #     # Exclude Django and third-party apps
        #     if not app.startswith('django.') and not app.startswith('third_party_app'):
        #         register_signals_for_app(app)
