# backend/reports/views.py

"""
API views for financial reports.

All report views follow the same pattern:
    1. Validate query parameters
    2. Check company membership and permissions
    3. Call the appropriate service function
    4. Return the formatted response

PERMISSIONS:
    All roles can view reports. Reports are read-only.

NOTE ON QUERY PARAMETERS:
    We use 'layout' instead of 'format' because DRF reserves
    the 'format' parameter for content negotiation (e.g.,
    ?format=json, ?format=api). Using ?format=flat causes a 404
    because DRF tries to find a renderer for the 'flat' format.
"""

from datetime import date, datetime

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from companies.models import Company, CompanyUser

from .services.trial_balance import (
    generate_trial_balance,
    VALID_FILTER_MODES,
    FILTER_NON_ZERO,
)


def _get_company_and_check_access(request, company_id):
    """
    Shared helper: validate company exists and user is a member.

    Returns:
        (company, error_response) — one of them will be None.
    """
    try:
        company = Company.objects.get(id=company_id)
    except Company.DoesNotExist:
        return None, Response(
            {'success': False, 'message': 'Company not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # ── User is a member? ──
    membership = CompanyUser.objects.filter(
        company=company,
        user=request.user,
        is_active=True,
    ).first()

    if not membership:
        return None, Response(
            {'success': False, 'message': 'You do not have access to this company.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    return company, None


def _parse_date_param(value, param_name):
    """
    Parse a date string from query parameters.

    Returns:
        (date_obj, error_message) — one will be None
    """
    if not value:
        return None, None

    try:
        return datetime.strptime(value, '%Y-%m-%d').date(), None
    except (ValueError, TypeError):
        return None, (
            f'Invalid {param_name}: "{value}". '
            f'Use YYYY-MM-DD format (e.g., 2026-03-31).'
        )


class TrialBalanceView(APIView):
    """
    GET /api/companies/{company_id}/reports/trial-balance/

    Generate a Trial Balance report.

    Query Parameters:
        as_of_date      (str, optional)  YYYY-MM-DD. Default: today.
        filter_mode     (str, optional)  'all', 'with_transactions',
                                         or 'non_zero'. Default: 'non_zero'.
        compare_date    (str, optional)  YYYY-MM-DD for comparison column.
        layout          (str, optional)  'nested' or 'flat'. Default: 'nested'.
                        NOTE: We use 'layout' not 'format' because
                        DRF reserves 'format' for content negotiation.

    Returns:
        Nested: groups → L1 → L2 → L3 → accounts (with infinite
                sub-account depth). Each account shows own balance
                plus subtotal including all children.
        Flat: flat_accounts → simple list with depth and parent info.
        Both include grand totals and is_balanced flag.
    """

    def get(self, request, company_id):

        # ── Access check ──
        company, error = _get_company_and_check_access(request, company_id)
        if error:
            return error

        # ── Parse as_of_date (default: today) ──
        as_of_date_str = request.query_params.get('as_of_date')
        if as_of_date_str:
            as_of_date, date_error = _parse_date_param(as_of_date_str, 'as_of_date')
            if date_error:
                return Response(
                    {'success': False, 'message': date_error},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            as_of_date = date.today()

        # ── Parse filter_mode (default: non_zero) ──
        filter_mode = request.query_params.get('filter_mode', FILTER_NON_ZERO)
        if filter_mode not in VALID_FILTER_MODES:
            return Response(
                {
                    'success': False,
                    'message': (
                        f'Invalid filter_mode: "{filter_mode}". '
                        f'Valid options: {", ".join(sorted(VALID_FILTER_MODES))}.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Parse compare_date (optional) ──
        compare_date = None
        compare_date_str = request.query_params.get('compare_date')
        if compare_date_str:
            compare_date, date_error = _parse_date_param(
                compare_date_str, 'compare_date',
            )
            if date_error:
                return Response(
                    {'success': False, 'message': date_error},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ── Parse layout (default: nested) ──
        # NOTE: 'format' is reserved by DRF for content negotiation.
        # Using 'layout' avoids the ?format=flat → 404 issue.
        response_layout = request.query_params.get('layout', 'nested')
        if response_layout not in ('nested', 'flat'):
            return Response(
                {
                    'success': False,
                    'message': (
                        f'Invalid layout: "{response_layout}". '
                        f'Valid options: nested, flat.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Generate the report ──
        report_data = generate_trial_balance(
            company=company,
            as_of_date=as_of_date,
            filter_mode=filter_mode,
            compare_date=compare_date,
        )

        # ── Build response ──
        response = {
            'success': True,
            'data': {
                'report_title': report_data['report_title'],
                'company_name': report_data['company_name'],
                'base_currency': report_data['base_currency'],
                'as_of_date': report_data['as_of_date'],
                'compare_date': report_data['compare_date'],
                'filter_mode': report_data['filter_mode'],
                'account_count': report_data['account_count'],
                'generated_at': datetime.now().isoformat(),
                # Grand totals
                'grand_total_debit': report_data['grand_total_debit'],
                'grand_total_credit': report_data['grand_total_credit'],
                'is_balanced': report_data['is_balanced'],
            },
        }

        # Add comparison grand totals if applicable
        if compare_date:
            response['data']['compare_grand_total_debit'] = report_data['compare_grand_total_debit']
            response['data']['compare_grand_total_credit'] = report_data['compare_grand_total_credit']

        # Add grouped or flat data based on layout
        if response_layout == 'nested':
            response['data']['groups'] = report_data['groups']
        else:
            response['data']['accounts'] = report_data['flat_accounts']

        return Response(response, status=status.HTTP_200_OK)