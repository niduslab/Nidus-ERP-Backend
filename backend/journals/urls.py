# backend/journals/urls.py

from django.urls import path
from . import views

app_name = 'journals'

urlpatterns = [

    # ── Journal CRUD ──
    path(
        'journal-entries/',
        views.JournalListCreateView.as_view(),
        name='journal-list-create',
    ),
    # ── Bulk Import ──
    path(
        'journal-entries/bulk-import/template/',
        views.BulkImportTemplateDownloadView.as_view(),
        name='bulk-import-template',
    ),
    path(
        'journal-entries/bulk-import/upload/',
        views.BulkImportUploadView.as_view(),
        name='bulk-import-upload',
    ),
    path(
        'journal-entries/<uuid:entry_id>/',
        views.JournalDetailView.as_view(),
        name='journal-detail',
    ),

    # ── Journal Actions ──
    path(
        'journal-entries/<uuid:entry_id>/post/',
        views.JournalPostView.as_view(),
        name='journal-post',
    ),
    path(
        'journal-entries/<uuid:entry_id>/void/',
        views.JournalVoidView.as_view(),
        name='journal-void',
    ),

    # ── Account Balance (lightweight utility, stays here) ──
    path(
        'accounts/<uuid:account_id>/balance/',
        views.AccountBalanceView.as_view(),
        name='account-balance',
    ),

    # NOTE: Account Ledger has been moved to reports app as
    # "Account Transactions" at:
    #   /api/companies/{id}/reports/account-transactions/?account_id={uuid}
]