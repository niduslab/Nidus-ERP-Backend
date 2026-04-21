# backend/chartofaccounts/tests/test_classifications.py
#
# Tests for GET /api/companies/<id>/classifications/ and the tree view.

import pytest
from django.urls import reverse


def _classification_list_url(company_id):
    return reverse('chartofaccounts:classification-list-create', args=[company_id])


def _tree_url(company_id):
    return reverse('chartofaccounts:chart-of-accounts-tree', args=[company_id])


@pytest.mark.django_db
class TestClassificationList:

    def test_lists_all_classifications_for_company(self, authed_client, company):
        response = authed_client.get(_classification_list_url(company.id))
        assert response.status_code == 200
        # The seed creates at least 30 classifications across the 3 layers.
        assert len(response.data['data']) >= 30 or response.data.get('count', 0) >= 30

    def test_non_member_gets_403(
        self, authed_client_for, other_user, company,
    ):
        client = authed_client_for(other_user)
        response = client.get(_classification_list_url(company.id))
        assert response.status_code == 403


@pytest.mark.django_db
class TestChartOfAccountsTree:
    """
    The tree endpoint assembles the full L1→L2→L3→Accounts hierarchy in a
    nested-dict shape for the frontend UI. We smoke-test the shape here.
    """

    def test_tree_shape_has_five_top_level_nodes(self, authed_client, company):
        response = authed_client.get(_tree_url(company.id))
        assert response.status_code == 200
        # Response shape varies — may be {'data': [...]} or {'tree': [...]}
        # or a direct list. Find the top-level list regardless.
        top_level = (
            response.data.get('data')
            or response.data.get('tree')
            or (response.data if isinstance(response.data, list) else None)
        )
        assert top_level is not None, (
            f'Tree endpoint returned unexpected shape: {type(response.data)} — '
            f'keys={list(response.data.keys()) if isinstance(response.data, dict) else "not a dict"}'
        )
        # Five L1 classifications: Asset, Liability, Equity, Income, Expense.
        assert len(top_level) == 5