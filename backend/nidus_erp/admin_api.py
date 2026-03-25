# backend/nidus_erp/admin_api.py

"""
Admin API endpoints for dynamic FK filtering.

When creating records in Django admin, FK dropdowns show ALL records
from ALL companies. This endpoint returns filtered options scoped to
a specific company, which the admin JavaScript uses to dynamically
update dropdown options when the user selects a company.

ENDPOINTS:
    GET /admin/api/company-options/<company_id>/

RETURNS:
    {
        "classifications_layer2": [{"id": "...", "label": "1.10 — Current Asset"}, ...],
        "classifications_layer3": [{"id": "...", "label": "1.10.1010 — Cash"}, ...],
        "accounts": [{"id": "...", "label": "10101 — Petty Cash"}, ...],
    }

SECURITY:
    Only accessible to staff users (admin panel users).
"""

import json

from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404

from companies.models import Company
from chartofaccounts.models import AccountClassification, Account


@staff_member_required
def company_options_api(request, company_id):
    """
    Return all classifications and accounts for a specific company.
    Used by admin JavaScript to filter FK dropdowns dynamically.
    """
    company = get_object_or_404(Company, id=company_id)

    # Layer 2 classifications (for parent dropdown in ClassificationAdmin)
    classifications_layer2 = []
    for c in AccountClassification.objects.filter(
        company=company,
    ).order_by('internal_path'):
        if c.layer == 2:
            classifications_layer2.append({
                'id': str(c.id),
                'label': f"{c.internal_path} — {c.name}",
            })

    # Layer 3 classifications (for classification dropdown in AccountAdmin)
    classifications_layer3 = []
    for c in AccountClassification.objects.filter(
        company=company,
    ).order_by('internal_path'):
        if c.layer == 3:
            classifications_layer3.append({
                'id': str(c.id),
                'label': f"{c.internal_path} — {c.name}",
            })

    # Active accounts (for parent_account and account dropdowns)
    accounts = []
    for a in Account.objects.filter(
        company=company,
        is_active=True,
    ).order_by('internal_path'):
        accounts.append({
            'id': str(a.id),
            'label': f"{a.code} — {a.name}",
        })

    return JsonResponse({
        'company_id': str(company.id),
        'company_name': company.name,
        'classifications_layer2': classifications_layer2,
        'classifications_layer3': classifications_layer3,
        'accounts': accounts,
    })