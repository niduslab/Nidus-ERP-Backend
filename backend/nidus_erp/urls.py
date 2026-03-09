# backend/nidus_erp/urls.py

from django.contrib import admin
from django.urls import path, include  

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('authentication.urls')),
    path('api/companies/', include('companies.urls')),
    path('api/companies/<uuid:company_id>/', include('chartofaccounts.urls')),
]
