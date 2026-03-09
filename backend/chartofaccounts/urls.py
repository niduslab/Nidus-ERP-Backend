# backend/chartofaccounts/urls.py

"""
Company-scoped URL routes for the Chart of Accounts.

All URLs here are included under:
    api/companies/<uuid:company_id>/

So every view here automatically receives company_id from the URL.

NOTE: The custom CoA template download endpoint is NOT here because
it doesn't need a company_id (the template is downloaded before a
company exists). That URL lives in companies/urls.py instead.
"""

from django.urls import path
from . import views

app_name = 'chartofaccounts'

urlpatterns = [

    path(
        'classifications/',
        views.ClassificationListCreateView.as_view(),
        name='classification-list-create',
    ),

    path(
        'accounts/',
        views.AccountListCreateView.as_view(),
        name='account-list-create',
    ),

    path(
        'accounts/<uuid:account_id>/',
        views.AccountDetailView.as_view(),
        name='account-detail',
    ),

    path(
        'accounts/<uuid:account_id>/delete/',
        views.AccountDeleteView.as_view(),
        name='account-delete',
    ),

    path(
        'accounts/<uuid:account_id>/deactivate/',
        views.AccountDeactivateView.as_view(),
        name='account-deactivate',
    ),

    path(
        'accounts/<uuid:account_id>/activate/',
        views.AccountActivateView.as_view(),
        name='account-activate',
    ),

    path(
        'system-accounts/',
        views.SystemAccountMappingListView.as_view(),
        name='system-account-list',
    ),

    path(
        'chart-of-accounts/',
        views.ChartOfAccountsTreeView.as_view(),
        name='chart-of-accounts-tree',
    ),
]