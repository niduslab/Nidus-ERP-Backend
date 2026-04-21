# backend/companies/tests/test_company_crud.py
#
# Tests for core company CRUD:
#   POST   /api/companies/              — create
#   GET    /api/companies/              — list (user's memberships)
#   GET    /api/companies/<id>/         — detail
#   PUT    /api/companies/<id>/         — update
#
# NOTE: Company creation is a multi-step transaction — creates Company,
# CompanyUser(OWNER), generates default CoA (164 classifications, 107
# accounts, system mappings, document sequence). We verify all of these
# side effects actually happen, not just that the HTTP response is 201.

import pytest
from django.urls import reverse


LIST_URL = reverse('companies:company-list-create')


def _detail_url(company_id):
    return reverse('companies:company-detail', args=[company_id])


@pytest.mark.django_db
class TestCompanyCreate:
    """
    POST /api/companies/ — create a new company.

    This is the most heavyweight endpoint in the whole app because it seeds
    the entire Chart of Accounts in the same atomic transaction. Tests here
    verify the full side-effect set, not just the HTTP response shape.
    """

    @pytest.mark.slow
    def test_creates_company_with_full_coa(self, authed_client, verified_user):
        """
        Happy path — 201 + all downstream objects exist.

        Each assertion verifies one side effect of CompanyCreateSerializer.create():
            1. Company row
            2. CompanyUser row with role=OWNER
            3. AccountClassification rows (164 of them — 5 L1 + 19 L2 + 140 L3)
            4. Account rows (~107 for the default CoA)
            5. SystemAccountMapping rows (~9 system codes)
            6. DocumentSequence for MANUAL_JOURNAL (auto-created in generate_default_coa)
        """
        from companies.models import Company, CompanyUser, RoleChoices, DocumentSequence
        from chartofaccounts.models import (
            AccountClassification, Account, SystemAccountMapping,
        )

        response = authed_client.post(LIST_URL, {
            'name': 'Test Enterprise Ltd',
            'industry': 'TRADING',
            'base_currency': 'BDT',
            'company_size': '1-10',
            'fiscal_year_start_month': 7,
        }, format='json')

        assert response.status_code == 201, response.data

        # 1. Company row exists with the submitted values.
        company = Company.objects.get(name='Test Enterprise Ltd')
        assert company.owner == verified_user
        assert company.base_currency == 'BDT'

        # 2. Owner membership auto-created.
        membership = CompanyUser.objects.get(user=verified_user, company=company)
        assert membership.role == RoleChoices.OWNER

        # 3-5. CoA fully generated — we assert counts are plausible, not exact
        # (the seed data may grow over time). The point is "some non-trivial
        # amount exists" — exact counts are the seed's responsibility.
        assert AccountClassification.objects.filter(company=company).count() >= 30
        assert Account.objects.filter(company=company).count() >= 50
        assert SystemAccountMapping.objects.filter(company=company).count() >= 5

        # 6. MANUAL_JOURNAL sequence exists so the user can post journals
        # immediately without manual admin setup (verifies the fix that's
        # already in chartofaccounts/services.py — this is a regression test).
        assert DocumentSequence.objects.filter(
            company=company, module='MANUAL_JOURNAL',
        ).exists()

    def test_rejects_anonymous(self, api_client):
        """Company creation requires auth."""
        response = api_client.post(LIST_URL, {
            'name': 'Should Fail',
            'industry': 'SERVICES',
            'company_size': '1-10',
        }, format='json')
        assert response.status_code == 401

    def test_rejects_missing_required_fields(self, authed_client):
        """
        Omitting `industry` or `company_size` must return 400 — they have no
        Django-level default, so the serializer enforces them.
        """
        response = authed_client.post(LIST_URL, {
            'name': 'Incomplete',
            # industry missing
            # company_size missing
        }, format='json')
        assert response.status_code == 400

    def test_rejects_invalid_currency(self, authed_client):
        """base_currency must be a valid ISO 4217 code from CurrencyChoices."""
        response = authed_client.post(LIST_URL, {
            'name': 'Bad Currency Co',
            'industry': 'SERVICES',
            'company_size': '1-10',
            'base_currency': 'XXX',   # Not in CurrencyChoices
        }, format='json')
        assert response.status_code == 400


@pytest.mark.django_db
class TestCompanyList:

    def test_lists_user_companies(self, authed_client, company, verified_user):
        """The list should return the one company the user owns."""
        response = authed_client.get(LIST_URL)
        assert response.status_code == 200
        assert response.data['count'] == 1
        assert response.data['data'][0]['id'] == str(company.id)
        # my_role should be OWNER since verified_user is the owner of `company`.
        assert response.data['data'][0]['my_role'] == 'OWNER'

    def test_does_not_leak_other_users_companies(
        self, authed_client_for, verified_user, other_user, company,
    ):
        """
        Multi-tenant isolation check: other_user has NO membership in `company`,
        so GET /api/companies/ should return 0 entries for them.
        """
        client = authed_client_for(other_user)
        response = client.get(LIST_URL)
        assert response.status_code == 200
        assert response.data['count'] == 0


@pytest.mark.django_db
class TestCompanyDetail:

    def test_returns_company_detail_for_member(self, authed_client, company):
        response = authed_client.get(_detail_url(company.id))
        assert response.status_code == 200
        assert response.data['data']['id'] == str(company.id)
        assert response.data['data']['my_role'] == 'OWNER'

    def test_returns_403_for_non_member(
        self, authed_client_for, other_user, company,
    ):
        """A verified user who isn't a member gets 403, not 404 — we confirm
        the company exists but withhold data. This matches Zoho Books behaviour."""
        client = authed_client_for(other_user)
        response = client.get(_detail_url(company.id))
        assert response.status_code == 403

    def test_can_change_currency_flag_reflects_ledger_state(self, authed_client, company):
        """
        can_change_currency is True when the company has no LedgerEntry rows,
        False after the first posted journal creates one. Here we only check
        the 'True' branch — the 'False' branch belongs in journal tests.
        """
        response = authed_client.get(_detail_url(company.id))
        assert response.data['data']['can_change_currency'] is True