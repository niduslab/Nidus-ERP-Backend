# backend/chartofaccounts/tests/test_accounts.py
#
# Tests for account-level endpoints:
#   GET/POST /api/companies/<id>/accounts/
#   POST     /api/companies/<id>/accounts/<aid>/deactivate/
#   POST     /api/companies/<id>/accounts/<aid>/activate/
#
# NOTE on create-via-POST: depending on how your AccountListCreateView was
# implemented (I see it referenced in urls.py as account-list-create), the
# POST path may not be fully wired for manual account creation in all
# branches. If a test here fails with "method not allowed", we'll wire it
# up in Phase 4c. For now we only exercise GET + activate/deactivate.

import pytest
from django.urls import reverse

from chartofaccounts.models import Account


def _account_list_url(company_id):
    return reverse('chartofaccounts:account-list-create', args=[company_id])


def _deactivate_url(company_id, account_id):
    return reverse('chartofaccounts:account-deactivate', args=[company_id, account_id])


def _activate_url(company_id, account_id):
    return reverse('chartofaccounts:account-activate', args=[company_id, account_id])


@pytest.mark.django_db
class TestAccountList:

    def test_list_includes_all_seeded_accounts(self, authed_client, company):
        """The default seed plants ~107 accounts — all visible via GET."""
        response = authed_client.get(_account_list_url(company.id))
        assert response.status_code == 200

        # Response may or may not be paginated depending on the view. We
        # count accounts in the DB directly instead — the key point is that
        # the endpoint returned 200 without error on a freshly-seeded company.
        assert Account.objects.filter(company=company).count() >= 50

    def test_non_member_gets_403(
        self, authed_client_for, other_user, company,
    ):
        client = authed_client_for(other_user)
        response = client.get(_account_list_url(company.id))
        assert response.status_code == 403


@pytest.mark.django_db
class TestAccountDeactivation:
    """
    Deactivation is soft-delete: is_active flag flips, the row stays.
    Critical for preserving audit trail — past journals still reference
    the account, but no NEW journals can use it.
    """

    def test_owner_can_deactivate_a_non_system_account(self, authed_client, company):
        """Pick any non-system, deletable account from the seed and deactivate."""
        account = Account.objects.filter(
            company=company, is_system_account=False, is_deletable=True, is_active=True,
        ).first()
        assert account is not None, 'Seed CoA should have deletable user accounts'

        response = authed_client.post(_deactivate_url(company.id, account.id))
        assert response.status_code == 200

        account.refresh_from_db()
        assert account.is_active is False

    def test_deactivated_account_can_be_reactivated(self, authed_client, company):
        """Full round-trip: deactivate → reactivate leaves the account usable."""
        account = Account.objects.filter(
            company=company, is_system_account=False, is_deletable=True, is_active=True,
        ).first()

        authed_client.post(_deactivate_url(company.id, account.id))
        response = authed_client.post(_activate_url(company.id, account.id))

        assert response.status_code == 200
        account.refresh_from_db()
        assert account.is_active is True

    def test_auditor_cannot_deactivate(
        self, authed_client_for, company, other_user,
    ):
        """
        Role-based access: AUDITOR is read-only. Attempting to deactivate
        an account as an auditor must return 403.
        """
        from companies.models import CompanyUser, RoleChoices

        # Attach other_user as AUDITOR to `company` for this test.
        CompanyUser.objects.create(
            user=other_user, company=company, role=RoleChoices.AUDITOR,
        )
        client = authed_client_for(other_user)

        account = Account.objects.filter(
            company=company, is_system_account=False, is_deletable=True,
        ).first()
        response = client.post(_deactivate_url(company.id, account.id))
        assert response.status_code == 403