# backend/chartofaccounts/apps.py

from django.apps import AppConfig


class ChartOfAccountsConfig(AppConfig):
    """
    Django AppConfig for the Chart of Accounts module.

    WHY 'chartofaccounts' INSTEAD OF 'accounts'?
        The name 'accounts' is too generic for an ERP system. It could be
        confused with Django's built-in auth (which manages user accounts),
        or with third-party packages like django-allauth. Using
        'chartofaccounts' makes the purpose immediately clear and avoids
        any naming collisions as the project grows.

    The 'name' attribute must exactly match the Python package (folder) name.
    Django uses this to locate the app's models, migrations, and admin config.
    """
    name = 'chartofaccounts'
    verbose_name = 'Chart of Accounts'