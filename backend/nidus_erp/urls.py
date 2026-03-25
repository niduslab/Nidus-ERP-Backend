# backend/nidus_erp/urls.py

from django.contrib import admin
from django.urls import path, include  

from .admin_api import company_options_api

urlpatterns = [
    # Admin API for dynamic FK filtering (must be before admin/)
    path('admin/api/company-options/<uuid:company_id>/', company_options_api,name='admin-company-options',),

    path('admin/', admin.site.urls),
    path('api/auth/', include('authentication.urls')),
    path('api/companies/', include('companies.urls')),
    path('api/companies/<uuid:company_id>/', include('chartofaccounts.urls')),
    path('api/companies/<uuid:company_id>/', include('journals.urls')),
]
