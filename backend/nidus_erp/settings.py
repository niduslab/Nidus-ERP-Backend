# backend/nidus_erp/settings.py

import os 
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv 

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'fallback-insecure-key-for-dev-only')
# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'jazzmin',  
    'django.contrib.admin',

    'django_extensions',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # ── humanize: built-in Django app (no pip install required). ──
    # Provides template filters like {{ n|intcomma }} → "1,234,567"
    # Used in Jazzmin admin list displays and email templates for
    # readable money/date/relative-time formatting.
    'django.contrib.humanize',

    'rest_framework',
    'rest_framework_simplejwt', 
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders', 
    
    'authentication',
    'companies',
    'chartofaccounts',
    'journals',
    'reports',

    # ── drf-spectacular (Phase 3) ──
    # Generates an OpenAPI 3.0 schema automatically from DRF views/serializers.
    # Exposed at:
    #   GET /api/schema/      → raw OpenAPI JSON (consumed by clients/code-gens)
    #   GET /api/docs/        → Swagger UI (human-browsable interactive docs)
    # The frontend will pull /api/schema/ through openapi-typescript-codegen
    # to generate fully-typed TypeScript API clients.
    'drf_spectacular',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware', 
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
   
]


CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',        
    'http://127.0.0.1:3000',        
    'http://localhost:5173',        
    'http://127.0.0.1:5173',        
]


CORS_ALLOW_CREDENTIALS = True

ROOT_URLCONF = 'nidus_erp.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'nidus_erp.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE ='Asia/Dhaka'   

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CUSTOM USER MODEL

AUTH_USER_MODEL = 'authentication.User'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'nidus_erp.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 20,

    # ── OpenAPI schema class (Phase 3) ──
    # drf-spectacular inspects views and serializers to auto-generate
    # OpenAPI 3.0 descriptions. Setting it as the default schema class
    # replaces DRF's built-in (inferior) schema generator.
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',

    # ──────────────────────────────────────────────
    # THROTTLING — per-endpoint rate limits
    # ──────────────────────────────────────────────
    # DRF's ScopedRateThrottle lets each view pick a named scope via
    # `throttle_scope = '...'`. Anonymous users are keyed by IP address;
    # authenticated users are keyed by user ID. The rates below target
    # unauthenticated abuse vectors: brute-force logins and email flooding.
    #
    # HOW DRF STORES THIS: in the default cache (LocMemCache in dev).
    # In production, point CACHES to Redis so counters are shared across
    # Gunicorn workers — otherwise each worker enforces its own counter
    # and the real limit becomes `rate × worker_count`.
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        # Login: 10 attempts per minute per IP.
        # Tight enough to stop credential-stuffing, loose enough that a
        # legitimate user who mistypes a few times is not locked out.
        'anon_login': '10/min',

        # Resend OTP: 5 per hour per IP.
        # This endpoint sends an email on every successful hit, so we
        # protect against (a) email-flood harassment of a known address
        # and (b) SMTP cost abuse. 5/hour still lets a real user recover
        # from a typo'd email without waiting.
        'anon_resend_otp': '5/hour',

        # Forgot password: 5 per hour per IP.
        # Same reasoning as resend-otp — it sends an email and must be
        # rate limited to prevent enumeration + flooding.
        'anon_forgot_password': '5/hour',

        # Reset password: 10 per hour per IP.
        # Not email-sending, but limit OTP-guessing attempts against the
        # password-reset code (6 digits = 1M combinations; 10/hr means
        # realistic brute-force would need ~100k hours).
        'anon_reset_password': '10/hour',
    },
}


SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=1440),    
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),       
    'ROTATE_REFRESH_TOKENS': True,                     
    'BLACKLIST_AFTER_ROTATION': True,                 
    'AUTH_HEADER_TYPES': ('Bearer',),                  
    'USER_ID_FIELD': 'id',                            
    'USER_ID_CLAIM': 'user_id',                       
}

EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend'    # Prints to terminal in dev
)

# Production SMTP settings (uncomment and configure when ready):

EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')

DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'Nidus ERP <noreply@niduserp.com>')

OTP_EXPIRY_MINUTES = int(os.getenv('OTP_EXPIRY_MINUTES', '10'))


# Frontend URL — used in email templates for links (e.g., "Create Account" button)
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
# ──────────────────────────────────────────────
# JAZZMIN ADMIN PANEL CONFIGURATION
# ──────────────────────────────────────────────

JAZZMIN_SETTINGS = {
    # ── Branding ──
    'site_title': 'Nidus ERP',
    'site_header': 'Nidus ERP Admin',
    'site_brand': 'Nidus ERP',
    'welcome_sign': 'Welcome to Nidus ERP Admin Panel',
    'copyright': 'Nidus ERP',

    # ── Search bar at the top ──
    'search_model': ['chartofaccounts.Account', 'companies.Company', 'authentication.User', 'journals.ManualJournal','journals.LedgerEntry',],

    # ── Top menu links ──
    'topmenu_links': [
        {'name': 'Home', 'url': 'admin:index', 'permissions': ['auth.view_user']},
    ],

    # ── Side menu configuration ──
    'show_sidebar': True,
    'navigation_expanded': True,

    # ── Organize models into groups in the sidebar ──
    'order_with_respect_to': [
        'authentication',
        'companies',
        'chartofaccounts',
        'journals',
    ],

    # ── Icons for each app and model ──
    'icons': {
        'authentication.User': 'fas fa-user',
        'companies.Company': 'fas fa-building',
        'companies.CompanyUser': 'fas fa-user-tie',
        'companies.PendingInvitation': 'fas fa-envelope-open',
        'chartofaccounts.AccountClassification': 'fas fa-folder-tree',
        'chartofaccounts.Account': 'fas fa-book',
        'chartofaccounts.SystemAccountMapping': 'fas fa-link',
        'journals.ManualJournal': 'fas fa-file-invoice',
        'journals.ManualJournalLine': 'fas fa-list',
        'journals.LedgerEntry': 'fas fa-table',
        'auth.Group': 'fas fa-users',
        'token_blacklist.BlacklistedToken': 'fas fa-ban',
        'token_blacklist.OutstandingToken': 'fas fa-key',

        'companies.TaxProfile': 'fas fa-percent',
        'companies.TaxProfileLayer': 'fas fa-layer-group',
        'companies.DocumentSequence': 'fas fa-hashtag',
        'companies.CurrencyExchangeRate': 'fas fa-exchange-alt',
    },

    # Default icon for models not listed above
    'default_icon_parents': 'fas fa-folder',
    'default_icon_children': 'fas fa-circle',

    # ── Misc ──
    'related_modal_active': True,
    'use_google_fonts_cdn': True,
    'show_ui_builder': False,
}

# ── Theme settings ──
JAZZMIN_UI_TWEAKS = {
    'navbar_small_text': False,
    'footer_small_text': False,
    'body_small_text': False,
    'brand_small_text': False,
    'brand_colour': 'navbar-dark',
    'accent': 'accent-primary',
    'navbar': 'navbar-dark navbar-primary',
    'no_navbar_border': False,
    'navbar_fixed': True,
    'layout_boxed': False,
    'footer_fixed': False,
    'sidebar_fixed': True,
    'sidebar': 'sidebar-dark-primary',
    'sidebar_nav_small_text': False,
    'sidebar_disable_expand': False,
    'sidebar_nav_child_indent': True,
    'sidebar_nav_compact_style': False,
    'sidebar_nav_legacy_style': False,
    'sidebar_nav_flat_style': False,
    'theme': 'default',
    'default_theme_mode': 'light',   # ← replaces deprecated dark_mode_theme
    'button_classes': {
        'primary': 'btn-primary',
        'secondary': 'btn-secondary',
        'info': 'btn-info',
        'warning': 'btn-warning',
        'danger': 'btn-danger',
        'success': 'btn-success',
    },
}


# ──────────────────────────────────────────────
# DRF-SPECTACULAR — OpenAPI 3.0 config (Phase 3)
# ──────────────────────────────────────────────
# Every setting is scoped under the SPECTACULAR_SETTINGS key (convention
# enforced by drf-spectacular — do not inline these into REST_FRAMEWORK).
SPECTACULAR_SETTINGS = {
    # ── Document identity ──
    # These appear as the title, version, and description at the top of
    # Swagger UI and inside the generated OpenAPI JSON.
    'TITLE': 'Nidus ERP API',
    'DESCRIPTION': (
        'Internal REST API for Nidus ERP — a multi-tenant financial ERP '
        'backend. Authentication uses JWT (access + refresh token rotation). '
        'All /api/companies/<id>/... endpoints are scoped to the company '
        'identified by <id>; the caller must be an active CompanyUser member.'
    ),
    'VERSION': '0.5.0',     # Semantic: Step 5 (Reports) complete, Step 6 frontend in progress

    # ── Schema routing ──
    # When True, the /api/schema/ endpoint includes the outer Django URL
    # routes (like /admin/, /static/). We only want the API surface.
    'SERVE_INCLUDE_SCHEMA': False,

    # Only routes under /api/ appear in the schema. Exclude /admin/,
    # /static/, and root-level paths — those are Django internals, not API.
    'SCHEMA_PATH_PREFIX': r'/api',

    # ── Authorisation display ──
    # Tells Swagger UI that endpoints default to requiring a Bearer JWT,
    # and renders the "Authorize" button correctly.
    'SECURITY': [{'BearerAuth': []}],

    # ── Renderer defaults ──
    # 'deepLinking' lets users share URLs to specific operations in Swagger UI.
    # 'persistAuthorization' keeps the token in the UI across page reloads,
    # which saves retyping during development.
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayRequestDuration': True,
    },

    # ── Schema hygiene ──
    # COMPONENT_SPLIT_REQUEST=True generates separate schemas for request
    # vs response bodies when they differ (e.g., write-only `password` field
    # on RegisterSerializer). Produces more accurate client types.
    'COMPONENT_SPLIT_REQUEST': True,

    # Keep enum names derived from the field name, not auto-generated
    # 'EnumEnum3' noise. Improves generated client type names.
    'ENUM_NAME_OVERRIDES': {},

    # When a view has no schema annotations at all, generate a best-effort
    # schema rather than omitting it. We'll progressively annotate views
    # later with @extend_schema decorators for precision.
    'GENERIC_ADDITIONAL_PROPERTIES': 'bool',
}