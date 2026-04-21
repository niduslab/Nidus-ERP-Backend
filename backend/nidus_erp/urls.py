# backend/nidus_erp/urls.py

from django.contrib import admin
from django.urls import path, include

from .admin_api import company_options_api

# drf-spectacular views — imported here so they're visible in the urlpatterns
# that follow. These three views give us:
#   SpectacularAPIView          → the raw OpenAPI JSON at /api/schema/
#   SpectacularSwaggerView      → Swagger UI at /api/docs/
#   SpectacularRedocView        → ReDoc alternative at /api/redoc/ (optional)
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    # Admin API for dynamic FK filtering (must be before admin/)
    path(
        'admin/api/company-options/<uuid:company_id>/',
        company_options_api,
        name='admin-company-options',
    ),

    path('admin/', admin.site.urls),

    # ── API routes ──
    path('api/auth/', include('authentication.urls')),
    path('api/companies/', include('companies.urls')),
    path('api/companies/<uuid:company_id>/', include('chartofaccounts.urls')),
    path('api/companies/<uuid:company_id>/', include('journals.urls')),
    path('api/companies/<uuid:company_id>/', include('reports.urls')),

    # ── OpenAPI / Swagger (Phase 3) ──
    # /api/schema/  → machine-readable OpenAPI 3.0 JSON.
    #                 Use this in the frontend to auto-generate a typed API
    #                 client (e.g., `npx openapi-typescript` or `orval`).
    # /api/docs/    → interactive Swagger UI — human-browsable, lets you try
    #                 endpoints in the browser with a Bearer token.
    # /api/redoc/   → alternative ReDoc-rendered view of the same schema.
    #                 Prettier for read-only documentation; keep both as
    #                 team preference varies.
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path(
        'api/docs/',
        SpectacularSwaggerView.as_view(url_name='schema'),
        name='swagger-ui',
    ),
    path(
        'api/redoc/',
        SpectacularRedocView.as_view(url_name='schema'),
        name='redoc',
    ),
]