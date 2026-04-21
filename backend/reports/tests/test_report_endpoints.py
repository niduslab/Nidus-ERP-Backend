# backend/reports/tests/test_report_endpoints.py
#
# Tests the HTTP layer for the reports app.
# Service-layer correctness is covered in the other test files; here we
# just verify that the endpoints are wired correctly, return JSON,
# enforce auth, and respect company-membership permissions.

import pytest
from datetime import date
from django.urls import reverse


def _balance_sheet_url(company_id):
    return reverse('reports:balance-sheet', args=[company_id])


def _trial_balance_url(company_id):
    return reverse('reports:trial-balance', args=[company_id])


def _income_statement_url(company_id):
    return reverse('reports:income-statement', args=[company_id])


@pytest.mark.django_db
class TestReportEndpointsAuth:

    def test_anonymous_request_is_rejected(self, api_client, company):
        """All report endpoints require auth — no anonymous reads."""
        response = api_client.get(_balance_sheet_url(company.id))
        assert response.status_code == 401

    def test_non_member_is_rejected(
        self, authed_client_for, other_user, company,
    ):
        """A verified user who isn't a member of `company` must get 403."""
        client = authed_client_for(other_user)
        response = client.get(
            _balance_sheet_url(company.id),
            {'as_of_date': '2026-12-31'},
        )
        assert response.status_code == 403


@pytest.mark.django_db
class TestReportEndpointsHappyPath:

    def test_balance_sheet_returns_json_with_required_keys(
        self, authed_client, company,
    ):
        """The balance sheet endpoint returns JSON in the expected shape."""
        response = authed_client.get(
            _balance_sheet_url(company.id),
            {'as_of_date': '2026-12-31'},
        )
        assert response.status_code == 200
        # The response is wrapped in {'success': True, 'data': {...}} per
        # the views' standard envelope. Find the report payload.
        payload = response.data.get('data') or response.data
        assert 'total_assets' in payload
        assert 'is_balanced' in payload