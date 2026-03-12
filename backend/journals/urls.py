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

    # ── Account Ledger & Balance ──
    path(
        'accounts/<uuid:account_id>/ledger/',
        views.AccountLedgerView.as_view(),
        name='account-ledger',
    ),
    path(
        'accounts/<uuid:account_id>/balance/',
        views.AccountBalanceView.as_view(),
        name='account-balance',
    ),
]