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
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework_simplejwt', 
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders', 
    
    'authentication',
    'companies',
    'chartofaccounts',
    'journals',
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
}


SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),    
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
    'search_model': ['chartofaccounts.Account', 'companies.Company', 'authentication.User'],

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