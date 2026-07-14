from django.apps import AppConfig


class StoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'store'

    def ready(self):
        from . import checks  # noqa: F401
        from . import rating_signals  # noqa: F401
