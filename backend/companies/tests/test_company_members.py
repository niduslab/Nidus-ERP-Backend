# backend/companies/tests/test_company_members.py
#
# Tests for member management:
#   POST   /api/companies/<id>/members/           — invite / add
#   GET    /api/companies/<id>/members/           — list
#   PATCH  /api/companies/<id>/members/<mid>/     — change role
#   DELETE /api/companies/<id>/members/<mid>/     — soft-remove
#
# Critical invariants verified:
#   - Owner's role cannot be changed via PATCH (transfer-ownership only)
#   - Owner cannot be removed via DELETE (transfer-ownership only)
#   - Only OWNER/ADMIN can invite/remove; ACCOUNTANT and AUDITOR cannot
#   - Non-existing emails create PendingInvitation rows, not CompanyUser rows

import pytest
from django.urls import reverse

from companies.models import CompanyUser, PendingInvitation, RoleChoices


def _member_list_url(company_id):
    return reverse('companies:member-list', args=[company_id])


def _member_detail_url(company_id, member_id):
    return reverse('companies:member-detail', args=[company_id, member_id])


@pytest.mark.django_db
class TestMemberInvite:

    def test_owner_can_invite_existing_user_directly(
        self, authed_client, company, other_user,
    ):
        """
        If the email is already a registered User, they're added to
        CompanyUser immediately (no PendingInvitation).
        """
        response = authed_client.post(_member_list_url(company.id), {
            'email': other_user.email,
            'role': 'ACCOUNTANT',
        }, format='json')

        assert response.status_code == 201
        # CompanyUser created, PendingInvitation NOT created.
        assert CompanyUser.objects.filter(
            user=other_user, company=company, role='ACCOUNTANT', is_active=True,
        ).exists()
        assert not PendingInvitation.objects.filter(
            email=other_user.email, company=company,
        ).exists()

    def test_owner_invite_unknown_email_creates_pending_invitation(
        self, authed_client, company,
    ):
        """Unknown email → PendingInvitation row, auto-applied when the user later registers."""
        response = authed_client.post(_member_list_url(company.id), {
            'email': 'notyet@example.com',
            'role': 'AUDITOR',
        }, format='json')

        assert response.status_code == 201
        assert PendingInvitation.objects.filter(
            email='notyet@example.com', company=company, role='AUDITOR',
        ).exists()

    def test_cannot_invite_as_owner_role(self, authed_client, company):
        """
        The OWNER role is reserved for transfer-ownership. The invite
        serializer explicitly rejects it.
        """
        response = authed_client.post(_member_list_url(company.id), {
            'email': 'somebody@example.com',
            'role': 'OWNER',
        }, format='json')
        assert response.status_code == 400

    def test_rejects_duplicate_active_member(
        self, authed_client, company_with_accountant, other_user,
    ):
        """other_user is already ACCOUNTANT → re-inviting them = 400."""
        response = authed_client.post(
            _member_list_url(company_with_accountant.id),
            {'email': other_user.email, 'role': 'AUDITOR'},
            format='json',
        )
        assert response.status_code == 400

    def test_accountant_cannot_invite_members(
        self, authed_client_for, company_with_accountant, other_user,
    ):
        """
        Permission check: only OWNER/ADMIN can invite. An ACCOUNTANT gets 403.
        This is the role-based access enforcement on the invite endpoint.
        """
        client = authed_client_for(other_user)   # other_user is the accountant
        response = client.post(
            _member_list_url(company_with_accountant.id),
            {'email': 'anotherperson@example.com', 'role': 'SALES'},
            format='json',
        )
        assert response.status_code == 403


@pytest.mark.django_db
class TestMemberList:

    def test_lists_active_members(
        self, authed_client, company_with_accountant, verified_user, other_user,
    ):
        response = authed_client.get(_member_list_url(company_with_accountant.id))
        assert response.status_code == 200
        # The owner + accountant = 2 active members.
        assert response.data['count'] == 2

        emails = {m['user_email'] for m in response.data['data']}
        assert verified_user.email in emails
        assert other_user.email in emails

    def test_non_member_gets_403(
        self, authed_client_for, company, other_user,
    ):
        """other_user has no membership in `company` → list should 403."""
        client = authed_client_for(other_user)
        response = client.get(_member_list_url(company.id))
        assert response.status_code == 403


@pytest.mark.django_db
class TestMemberRoleChange:

    def test_owner_can_change_accountants_role(
        self, authed_client, company_with_accountant, other_user,
    ):
        membership = CompanyUser.objects.get(
            user=other_user, company=company_with_accountant,
        )
        response = authed_client.patch(
            _member_detail_url(company_with_accountant.id, membership.id),
            {'role': 'AUDITOR'},
            format='json',
        )
        assert response.status_code == 200
        membership.refresh_from_db()
        assert membership.role == 'AUDITOR'

    def test_cannot_change_owner_role_via_patch(
        self, authed_client, company, verified_user,
    ):
        """
        SECURITY INVARIANT:
            The OWNER's role must never change through the member-detail
            endpoint — only through the dedicated transfer-ownership flow
            (which requires password re-verification). Attempting a PATCH
            on the owner's membership must return 400.
        """
        owner_membership = CompanyUser.objects.get(
            user=verified_user, company=company,
        )
        response = authed_client.patch(
            _member_detail_url(company.id, owner_membership.id),
            {'role': 'ADMIN'},
            format='json',
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestMemberRemove:

    def test_owner_can_soft_remove_accountant(
        self, authed_client, company_with_accountant, other_user,
    ):
        membership = CompanyUser.objects.get(
            user=other_user, company=company_with_accountant,
        )
        response = authed_client.delete(
            _member_detail_url(company_with_accountant.id, membership.id),
        )
        assert response.status_code == 200

        # SOFT DELETE — the row still exists with is_active=False.
        # This preserves audit trails (who posted what journal, etc.) while
        # revoking access. A hard delete would risk orphaning those records.
        membership.refresh_from_db()
        assert membership.is_active is False

    def test_cannot_remove_owner(
        self, authed_client, company, verified_user,
    ):
        """SECURITY INVARIANT: Owner cannot be removed. Transfer first."""
        owner_membership = CompanyUser.objects.get(
            user=verified_user, company=company,
        )
        response = authed_client.delete(
            _member_detail_url(company.id, owner_membership.id),
        )
        assert response.status_code == 400