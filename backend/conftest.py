# backend/conftest.py
#
# Shared pytest fixtures for Nidus ERP.
#
# WHAT GOES HERE vs. in app-specific conftest.py files:
#   - HERE: fixtures used by MULTIPLE apps (users, API clients, JWT helpers)
#   - App conftest.py: fixtures specific to that app (e.g., a posted journal
#     fixture belongs in journals/tests/conftest.py, not here)
#
# Fixtures are loaded lazily — defining 10 here costs nothing if a test uses 2.
# They are cached per-test by default (use scope='session'/'module' to widen).

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


# ══════════════════════════════════════════════════
# DATABASE ACCESS
# ══════════════════════════════════════════════════

@pytest.fixture
def db_access(db):
    """
    Convenience alias for pytest-django's `db` fixture.

    Renamed to make test signatures read naturally: a test that takes
    `db_access` clearly opts into DB access. Using bare `db` in the
    signature works identically but less expressively.

    pytest-django handles transaction rollback automatically — each test
    starts with a clean slate, no manual teardown needed.
    """
    return db


# ══════════════════════════════════════════════════
# API CLIENT FIXTURES
# ══════════════════════════════════════════════════

@pytest.fixture
def api_client():
    """
    An unauthenticated DRF test client.

    Use this for endpoints that allow anonymous access (register, login,
    forgot-password, etc.) and for deliberate 401/403 tests on protected
    endpoints.

    Why APIClient instead of Django's Client:
        - Handles JSON serialization automatically (client.post(url, data=dict))
        - Sets Content-Type correctly
        - Integrates with DRF's JWT authentication via force_authenticate /
          credentials()
    """
    return APIClient()


@pytest.fixture
def authed_client(api_client, verified_user):
    """
    A DRF client pre-authenticated as a fresh verified user.

    Uses REAL JWT tokens (not force_authenticate) so the request path
    exercises the actual SimpleJWT middleware — tests catch auth bugs that
    force_authenticate would hide.
    """
    refresh = RefreshToken.for_user(verified_user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


# ══════════════════════════════════════════════════
# USER FIXTURES
# ══════════════════════════════════════════════════
#
# Fixtures below produce User instances at specific lifecycle stages.
# Tests should depend on the EARLIEST stage they need (YAGNI).
#
# IMPORT NOTE:
#   We import from `authentication.factories` — NOT `.authentication.factories`.
#   The `backend/` directory is not a Python package (it has no __init__.py —
#   and intentionally so: Django apps live on sys.path directly via
#   DJANGO_SETTINGS_MODULE). A leading dot triggers relative-import machinery
#   that requires a parent package and raises ImportError at fixture setup.


@pytest.fixture
def unverified_user(db_access):
    """
    A User who has registered but NOT yet verified their email.

    `is_email_verified=False`, no OTP set. Use this in tests that check
    the gating logic for unverified accounts (e.g., login should refuse).
    """
    from authentication.factories import UserFactory
    return UserFactory(is_email_verified=False)


@pytest.fixture
def verified_user(db_access):
    """
    A fully-verified User ready to log in and perform authenticated actions.
    `is_email_verified=True`, password = 'TestPassword123!' (the factory default).
    """
    from authentication.factories import UserFactory
    return UserFactory(is_email_verified=True)


@pytest.fixture
def user_with_otp(db_access):
    """
    An unverified user with a valid email-verification OTP already set.
    Useful for /verify-email/ happy-path tests.
    """
    from authentication.factories import UserFactory
    from django.utils import timezone
    from datetime import timedelta
    from django.conf import settings

    user = UserFactory(is_email_verified=False)
    user.email_verification_code = '123456'
    user.email_verification_code_expires = (
        timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
    )
    user.save(update_fields=[
        'email_verification_code',
        'email_verification_code_expires',
    ])
    return user


@pytest.fixture
def user_with_reset_otp(db_access):
    """
    A verified user with an active password-reset OTP.
    Useful for /reset-password/ happy-path tests.
    """
    from authentication.factories import UserFactory
    from django.utils import timezone
    from datetime import timedelta
    from django.conf import settings

    user = UserFactory(is_email_verified=True)
    user.password_reset_code = '654321'
    user.password_reset_code_expires = (
        timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
    )
    user.save(update_fields=[
        'password_reset_code',
        'password_reset_code_expires',
    ])
    return user


# ══════════════════════════════════════════════════
# THROTTLE ISOLATION
# ══════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def clear_throttle_cache(settings):
    """
    Clears DRF's throttle cache between every test.

    Why autouse=True: throttle state leaks across tests otherwise. A login
    test that fires 10 attempts would poison the next test's single
    legitimate login by keeping the counter at 10.

    The cache is cleared BEFORE each test runs. We use Django's cache
    framework (which DRF uses internally) — safe to call even when the
    cache backend is the dev default (LocMemCache).
    """
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()

# ══════════════════════════════════════════════════
# COMPANY FIXTURES
# ══════════════════════════════════════════════════
#
# IMPORTANT DESIGN CHOICE:
#     `company` creates a real Company with the DEFAULT Chart of Accounts
#     (107 accounts, system mappings, document sequences) via
#     CompanyCreateSerializer's own `.create()` path. This is slower than a
#     bare Company.objects.create() but ensures tests exercise the SAME
#     code path that production hits when an owner signs up.
#
#     For tests that don't need accounts (pure company-model tests), use the
#     `bare_company` fixture instead — it skips CoA generation for speed.
#
# PERFORMANCE:
#     `company` runs generate_default_coa() which does ~140 INSERTs. On SQLite
#     this is ~300ms. Acceptable for correctness tests, but if you're writing
#     a whole test class that only touches Company model fields, switch to
#     `bare_company`.


@pytest.fixture
def bare_company(db_access, verified_user):
    """
    A Company with NO Chart of Accounts, NO members, NO sequences.

    For lightweight tests that only check company-model behaviour
    (e.g., name validation, uniqueness). Avoids the ~300ms CoA seed cost.
    The owner is NOT added as a CompanyUser — do that explicitly in tests
    that need role/permission checks.
    """
    from companies.models import Company
    return Company.objects.create(
        owner=verified_user,
        name='Bare Test Co Ltd',
        industry='SERVICES',
        base_currency='BDT',
        company_size='1-10',
        fiscal_year_start_month=7,
    )


@pytest.fixture
def company(db_access, verified_user):
    """
    A fully-seeded Company:
        - Owner = `verified_user`
        - DEFAULT CoA: 164 classifications + 107 accounts + system mappings
        - DocumentSequence for MANUAL_JOURNAL
        - OWNER membership row in CompanyUser
        - Membership email (send_welcome_email etc.) is suppressed by the
          settings.EMAIL_BACKEND = console default — no SMTP calls happen.

    Goes through the real generate_default_coa() so tests exercise production
    code paths. Use `bare_company` for pure model tests that don't need
    this setup.
    """
    from companies.models import Company, CompanyUser, RoleChoices
    from chartofaccounts.services import generate_default_coa

    company = Company.objects.create(
        owner=verified_user,
        name='Rahim Trading Test Ltd',
        industry='TRADING',
        base_currency='BDT',
        company_size='11-50',
        fiscal_year_start_month=7,
    )
    CompanyUser.objects.create(
        user=verified_user,
        company=company,
        role=RoleChoices.OWNER,
    )
    generate_default_coa(company=company, created_by=verified_user)
    return company


@pytest.fixture
def other_user(db_access):
    """
    A second verified user — useful for 'user A cannot access company B'
    multi-tenant isolation tests, or as the recipient of an invitation.
    """
    from authentication.factories import UserFactory
    return UserFactory(is_email_verified=True)


@pytest.fixture
def company_with_accountant(db_access, company, other_user):
    """
    The `company` fixture, plus `other_user` added as an ACCOUNTANT.

    Returns the Company (the accountant is accessible via
    company.members.get(user=other_user)).
    """
    from companies.models import CompanyUser, RoleChoices

    CompanyUser.objects.create(
        user=other_user,
        company=company,
        role=RoleChoices.ACCOUNTANT,
    )
    return company


@pytest.fixture
def authed_client_for(api_client):
    """
    Factory fixture — returns a callable that produces an authenticated
    APIClient for ANY user. Use this when a single test needs to act as
    multiple users in sequence.

    Usage:
        def test_foo(authed_client_for, verified_user, other_user):
            owner_client = authed_client_for(verified_user)
            member_client = authed_client_for(other_user)
            # ... act as each one
    """
    from rest_framework_simplejwt.tokens import RefreshToken

    def _make(user):
        # Create a FRESH APIClient each time so credentials from one user
        # don't leak into another — self-contained isolation.
        from rest_framework.test import APIClient
        client = APIClient()
        refresh = RefreshToken.for_user(user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        return client

    return _make





# ══════════════════════════════════════════════════
# JOURNAL / ACCOUNT HELPER FIXTURES
# ══════════════════════════════════════════════════
#
# When a test needs "a cash account" or "a revenue account", we look up the
# first matching account from the seeded CoA. This way tests don't break
# when the seed data changes — they ask for what they need by classification
# path, not by hardcoded UUID.


@pytest.fixture
def account_picker(db_access):
    """
    Factory fixture — returns a callable that finds an account by L3
    classification internal_path within a given company.

    Usage:
        def test_x(account_picker, company):
            cash = account_picker(company, '1.10.1010')          # First Cash account
            revenue = account_picker(company, '4.40.4010')        # First Revenue account
            payables = account_picker(company, '2.20.2010')       # First Payables account

    Why a factory: tests typically need 2-4 different accounts, hardcoding
    each as its own fixture would explode conftest.py. The factory lets each
    test name what it needs inline.
    """
    def _pick(company, classification_path):
        from chartofaccounts.models import Account
        account = Account.objects.filter(
            company=company,
            classification__internal_path=classification_path,
            is_active=True,
        ).first()
        if account is None:
            raise LookupError(
                f'No active account found at classification {classification_path} '
                f'in company {company.name}. Check the seed CoA.'
            )
        return account
    return _pick


@pytest.fixture
def journal_factory(db_access, company, verified_user, account_picker):
    """
    Factory fixture — creates a balanced 2-line draft journal in `company`.

    Default behaviour: DEBIT a Cash account, CREDIT an Owner Equity account
    (a typical opening-balance entry shape). Both default to amount=1000.00.
    Override via kwargs:
        journal_factory()                          # 1000 BDT cash → equity
        journal_factory(amount=Decimal('500.00'))  # 500 BDT
        journal_factory(date=date(2025,1,1))       # specific date

    Returns the freshly-created (DRAFT) ManualJournal.

    Tests that need POSTED state should call post_journal() themselves —
    keeping the factory at DRAFT lets tests choose which transitions to
    exercise.
    """
    from datetime import date
    from decimal import Decimal
    from journals.services import create_journal

    def _make(amount=None, journal_date=None, debit_path='1.10.1010', credit_path='3.30.3010'):
        debit_account = account_picker(company, debit_path)
        credit_account = account_picker(company, credit_path)
        amount = amount or Decimal('1000.00')

        return create_journal(
            company=company,
            created_by=verified_user,
            journal_data={
                'date': journal_date or date(2026, 4, 1),
                'description': 'Test journal entry',
                'currency': company.base_currency,
                'exchange_rate': Decimal('1.000000'),
            },
            lines_data=[
                {'account': debit_account, 'entry_type': 'DEBIT',  'amount': amount},
                {'account': credit_account, 'entry_type': 'CREDIT', 'amount': amount},
            ],
        )

    return _make


@pytest.fixture
def posted_journal(journal_factory, verified_user):
    """
    A balanced, POSTED journal — the most common starting point for
    LedgerEntry/balance tests. Returns the journal AFTER post_journal()
    has run, so its associated LedgerEntry rows already exist.
    """
    from journals.services import post_journal
    journal = journal_factory()
    return post_journal(journal, posted_by=verified_user)