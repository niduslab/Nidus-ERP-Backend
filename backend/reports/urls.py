# backend/reports/urls.py

"""
Company-scoped URL routes for financial reports.

All URLs here are included under:
    api/companies/<uuid:company_id>/

So every view automatically receives company_id from the URL.
"""

from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [

    # ── Trial Balance ──
    path(
        'reports/trial-balance/',
        views.TrialBalanceView.as_view(),
        name='trial-balance',
    ),

    # ── Balance Sheet ──
    path(
        'reports/balance-sheet/',
        views.BalanceSheetView.as_view(),
        name='balance-sheet',
    ),

    # ── Income Statement (P&L) ──
    path(
        'reports/income-statement/',
        views.IncomeStatementView.as_view(),
        name='income-statement',
    ),

    # ── General Ledger ──
    path(
        'reports/general-ledger/',
        views.GeneralLedgerView.as_view(),
        name='general-ledger',
    ),

    # ── Account Transactions (Drill-Down) ──
    path(
        'reports/account-transactions/',
        views.AccountTransactionsView.as_view(),
        name='account-transactions',
    ),

    # ── Future report endpoints (uncomment as built) ──
    # path('reports/cash-flow/',
    #      views.CashFlowView.as_view(), name='cash-flow'),
]