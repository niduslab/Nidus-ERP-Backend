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
    # Registered before the <uuid:entry_id> detail URL so the more specific
    # 'bulk-import/*' routes win the match (Django's URL resolver is first-hit).
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

    # ── Export (Phase 3) ──
    # Also registered before the detail URL for the same reason:
    # 'journal-entries/export/' must not be interpreted as entry_id='export'.
    # UUID converter would actually prevent the collision, but listing it
    # here explicitly keeps the ordering intention clear to future readers.
    path(
        'journal-entries/export/',
        views.JournalExportView.as_view(),
        name='journal-export',
    ),

    # ── Journal Detail (must come AFTER the specific paths above) ──
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