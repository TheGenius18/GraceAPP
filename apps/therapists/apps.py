from django.apps import AppConfig


class TherapistsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.therapists'


class UsersConfig(AppConfig):
    name = 'apps.users'

    def ready(self):
        import apps.users.signals
