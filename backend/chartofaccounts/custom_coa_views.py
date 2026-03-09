# backend/chartofaccounts/custom_coa_views.py

"""
Views for the Custom CoA feature.

This file is separate from views.py because these views don't operate
on a specific company's data. The template download is a generic endpoint
(not scoped to a company), and the upload happens during company creation
(which is in the companies app).

ENDPOINTS:
    GET /api/companies/custom-coa-template/download/
        → Download the CoA template Excel file.
        → Requires authentication (user must be logged in).
        → Returns an .xlsx file as a download.

URL ROUTING:
    This view is wired in companies/urls.py (not chartofaccounts/urls.py)
    because the template download is part of the company creation flow
    and doesn't require a company_id. The chartofaccounts/urls.py is
    included under api/companies/<uuid:company_id>/, so all its URLs
    require a company_id — which wouldn't work here since the template
    is downloaded BEFORE a company exists.
"""

from django.http import HttpResponse

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .custom_coa_template import generate_coa_template


class CoATemplateDownloadView(APIView):
    """
    GET /api/companies/custom-coa-template/download/

    Returns a downloadable Excel template for custom Chart of Accounts.

    The template has 4 sheets:
    - Instructions: Rules, field reference, and the list of 43 system accounts
    - Default CoA Tree: Complete visual tree of the 104-account default CoA
    - Classifications: Layer 3 groups (system + custom)
    - Accounts: Layer 4 accounts (system + custom)

    The user fills in the template and uploads it during company creation.

    WHY HttpResponse INSTEAD OF Response?
        DRF's Response is designed for JSON data. For file downloads,
        we use Django's HttpResponse directly because it lets us set
        the content_type to the Excel MIME type and add the
        Content-Disposition header that triggers a download in the browser.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        file_bytes = generate_coa_template()

        response = HttpResponse(
            file_bytes,
            content_type=(
                'application/vnd.openxmlformats-officedocument'
                '.spreadsheetml.sheet'
            ),
        )
        response['Content-Disposition'] = (
            'attachment; filename="NidusERP_Custom_CoA_Template.xlsx"'
        )

        return response