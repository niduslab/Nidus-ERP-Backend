# backend/companies/tests/test_choices.py

"""
Tests for GET /api/companies/choices/

Smoke tests covering:
  - 401 when unauthenticated
  - 200 with the correct shape when authenticated
  - All required choice categories present
  - Each entry has { value, label } shape
"""

import pytest
from django.urls import reverse


pytestmark = pytest.mark.django_db


URL = reverse('companies:company-choices')


def test_unauthenticated_request_is_rejected(api_client):
    """No JWT → 401."""
    response = api_client.get(URL)
    assert response.status_code == 401


def test_authenticated_request_returns_choices(authed_client):
    """A logged-in user gets the full choice payload."""
    response = authed_client.get(URL)

    assert response.status_code == 200
    body = response.data
    assert body['success'] is True

    data = body['data']

    # All categories present
    expected_keys = {
        'currencies', 'industries', 'company_sizes',
        'inventory_methods', 'date_formats',
        'fiscal_year_months', 'time_zones', 'reporting_methods',
    }
    assert set(data.keys()) == expected_keys

    # Each entry has { value, label }
    for category in expected_keys:
        entries = data[category]
        assert isinstance(entries, list), f'{category} should be a list'
        assert len(entries) > 0, f'{category} should not be empty'
        for entry in entries:
            assert 'value' in entry, f'{category} entry missing "value"'
            assert 'label' in entry, f'{category} entry missing "label"'


def test_currencies_contain_bdt_and_usd(authed_client):
    """Spot-check that the most relevant currencies are exposed."""
    response = authed_client.get(URL)
    currencies = response.data['data']['currencies']
    codes = {c['value'] for c in currencies}
    assert 'BDT' in codes
    assert 'USD' in codes


def test_fiscal_year_months_are_integers_1_to_12(authed_client):
    """Backend stores fiscal_year_start_month as int — frontend gets int."""
    response = authed_client.get(URL)
    months = response.data['data']['fiscal_year_months']

    assert len(months) == 12
    for i, month in enumerate(months, start=1):
        assert month['value'] == i