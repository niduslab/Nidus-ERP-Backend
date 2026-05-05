# backend/companies/urls.py
#
# Add a new path for the choices endpoint.

from django.urls import path
from . import views
from chartofaccounts.custom_coa_views import CoATemplateDownloadView


app_name = 'companies'

urlpatterns = [

    path(
        'custom-coa-template/download/',
        CoATemplateDownloadView.as_view(),
        name='coa-template-download',
    ),

    # ── NEW: choices endpoint ──
    # Sits at /api/companies/choices/ — listed BEFORE the <uuid> patterns
    # so Django's URL resolver doesn't try to match "choices" as a UUID.
    path(
        'choices/',
        views.CompanyChoicesView.as_view(),
        name='company-choices',
    ),

    path(
    'validate-coa-file/',
    views.ValidateCoaFileView.as_view(),
    name='validate-coa-file',
    ),

    path('', views.CompanyListCreateView.as_view(), name='company-list-create'),
    path('<uuid:company_id>/', views.CompanyDetailView.as_view(), name='company-detail'),
    path('<uuid:company_id>/transfer-ownership/', views.TransferOwnershipView.as_view(), name='transfer-ownership'),
    path('<uuid:company_id>/members/', views.CompanyMemberListView.as_view(), name='member-list'),
    path('<uuid:company_id>/members/<uuid:member_id>/', views.CompanyMemberDetailView.as_view(), name='member-detail'),
]