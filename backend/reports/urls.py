# backend/reports/urls.py

"""
Company-scoped URL routes for financial reports.

All URLs here are included under:
    api/companies/<uuid:company_id>/

So every view automatically receives company_id from the URL.

As new reports are added, their URLs go here. The pattern:
    reports/<report-name>/
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

    # ── Future report endpoints (uncomment as built) ──
    # path('reports/balance-sheet/',
    #      views.BalanceSheetView.as_view(), name='balance-sheet'),
    # path('reports/income-statement/',
    #      views.IncomeStatementView.as_view(), name='income-statement'),
    # path('reports/general-ledger/',
    #      views.GeneralLedgerView.as_view(), name='general-ledger'),
    # path('reports/account-statement/',
    #      views.AccountStatementView.as_view(), name='account-statement'),
    # path('reports/cash-flow/',
    #      views.CashFlowView.as_view(), name='cash-flow'),
]