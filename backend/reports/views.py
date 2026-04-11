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
    the 'format' parameter for content negotiation.
"""

from datetime import date, datetime
from uuid import UUID

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from companies.models import Company, CompanyUser

from .services.trial_balance import (
    generate_trial_balance,
    VALID_FILTER_MODES,
    FILTER_NON_ZERO,
)
from .services.balance_sheet import generate_balance_sheet
from .services.income_statement import generate_income_statement
from .services.general_ledger import generate_general_ledger
from .services.account_transactions import generate_account_transactions
from .services.cash_flow import generate_cash_flow

from .exporters import maybe_export

from chartofaccounts.models import Account
from journals.models import JournalTypeChoices


# ══════════════════════════════════════════════════
# SHARED HELPERS
# ══════════════════════════════════════════════════

def _get_company_and_check_access(request, company_id):
    """
    Validate company exists and user is a member.
    Returns (company, error_response) — one will be None.
    """
    try:
        company = Company.objects.get(id=company_id)
    except Company.DoesNotExist:
        return None, Response(
            {'success': False, 'message': 'Company not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

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
    Parse a YYYY-MM-DD date string from query parameters.
    Returns (date_obj, error_message) — one will be None.
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


def _validate_filter_mode(filter_mode):
    """Validate and return filter_mode, or return error response."""
    if filter_mode not in VALID_FILTER_MODES:
        return None, Response(
            {
                'success': False,
                'message': (
                    f'Invalid filter_mode: "{filter_mode}". '
                    f'Valid options: {", ".join(sorted(VALID_FILTER_MODES))}.'
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    return filter_mode, None


def _validate_layout(layout):
    """Validate and return layout parameter."""
    if layout not in ('nested', 'flat'):
        return None, Response(
            {
                'success': False,
                'message': (
                    f'Invalid layout: "{layout}". '
                    f'Valid options: nested, flat.'
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    return layout, None


def _get_fiscal_year_start(company, reference_date):
    """
    Calculate the start date of the fiscal year containing reference_date.

    Used by IncomeStatementView to default from_date to fiscal year start
    when no from_date is provided (standard YTD behaviour).

    Example: fiscal_year_start_month=7, reference_date=2026-03-31
        → Returns 2025-07-01 (FY runs Jul 2025 – Jun 2026)
    """
    fy_month = company.fiscal_year_start_month or 1
    year = reference_date.year

    # If the fiscal year starts in a month after the current month,
    # the fiscal year actually began in the previous calendar year.
    if fy_month > reference_date.month:
        year -= 1

    return date(year, fy_month, 1)


# ══════════════════════════════════════════════════
# TRIAL BALANCE
# ══════════════════════════════════════════════════

class TrialBalanceView(APIView):
    """
    GET /api/companies/{company_id}/reports/trial-balance/

    Query Parameters:
        as_of_date      YYYY-MM-DD (default: today)
        filter_mode     'all' | 'with_transactions' | 'non_zero' (default)
        compare_date    YYYY-MM-DD (optional comparison column)
        layout          'nested' (default) | 'flat'
    """

    def get(self, request, company_id):
        company, error = _get_company_and_check_access(request, company_id)
        if error:
            return error

        # ── Parse as_of_date ──
        as_of_date_str = request.query_params.get('as_of_date')
        if as_of_date_str:
            as_of_date, err = _parse_date_param(as_of_date_str, 'as_of_date')
            if err:
                return Response({'success': False, 'message': err}, status=status.HTTP_400_BAD_REQUEST)
        else:
            as_of_date = date.today()

        # ── Parse filter_mode ──
        filter_mode = request.query_params.get('filter_mode', FILTER_NON_ZERO)
        filter_mode, err = _validate_filter_mode(filter_mode)
        if err:
            return err

        # ── Parse compare_date ──
        compare_date = None
        compare_str = request.query_params.get('compare_date')
        if compare_str:
            compare_date, err = _parse_date_param(compare_str, 'compare_date')
            if err:
                return Response({'success': False, 'message': err}, status=status.HTTP_400_BAD_REQUEST)

        # ── Parse layout ──
        response_layout = request.query_params.get('layout', 'nested')
        response_layout, err = _validate_layout(response_layout)
        if err:
            return err

        # ── Generate report ──
        report = generate_trial_balance(
            company=company,
            as_of_date=as_of_date,
            filter_mode=filter_mode,
            compare_date=compare_date,
        )

        # ── Export if requested ──
        export_format = request.query_params.get('export')
        if export_format:
            return maybe_export(export_format, 'trial_balance', report, company.name)

        # ── Build response ──
        data = {
            'report_title': report['report_title'],
            'company_name': report['company_name'],
            'base_currency': report['base_currency'],
            'as_of_date': report['as_of_date'],
            'compare_date': report['compare_date'],
            'filter_mode': report['filter_mode'],
            'account_count': report['account_count'],
            'generated_at': datetime.now().isoformat(),
            'grand_total_debit': report['grand_total_debit'],
            'grand_total_credit': report['grand_total_credit'],
            'is_balanced': report['is_balanced'],
        }

        if compare_date:
            data['compare_grand_total_debit'] = report['compare_grand_total_debit']
            data['compare_grand_total_credit'] = report['compare_grand_total_credit']

        if response_layout == 'nested':
            data['groups'] = report['groups']
        else:
            data['accounts'] = report['flat_accounts']

        return Response({'success': True, 'data': data}, status=status.HTTP_200_OK)


# ══════════════════════════════════════════════════
# BALANCE SHEET
# ══════════════════════════════════════════════════

class BalanceSheetView(APIView):
    """
    GET /api/companies/{company_id}/reports/balance-sheet/

    Generates a Balance Sheet (Statement of Financial Position).
    Shows Assets = Liabilities + Equity at a specific date.

    Automatically calculates retained earnings from Income − Expense
    accounts. Supports both auto-calculation and manual closing journals
    without double-counting.

    Query Parameters:
        as_of_date      YYYY-MM-DD (default: today)
        filter_mode     'all' | 'with_transactions' | 'non_zero' (default)
        compare_date    YYYY-MM-DD (optional comparison column)
    """

    def get(self, request, company_id):
        company, error = _get_company_and_check_access(request, company_id)
        if error:
            return error

        # ── Parse as_of_date ──
        as_of_date_str = request.query_params.get('as_of_date')
        if as_of_date_str:
            as_of_date, err = _parse_date_param(as_of_date_str, 'as_of_date')
            if err:
                return Response({'success': False, 'message': err}, status=status.HTTP_400_BAD_REQUEST)
        else:
            as_of_date = date.today()

        # ── Parse filter_mode ──
        filter_mode = request.query_params.get('filter_mode', FILTER_NON_ZERO)
        filter_mode, err = _validate_filter_mode(filter_mode)
        if err:
            return err

        # ── Parse compare_date ──
        compare_date = None
        compare_str = request.query_params.get('compare_date')
        if compare_str:
            compare_date, err = _parse_date_param(compare_str, 'compare_date')
            if err:
                return Response({'success': False, 'message': err}, status=status.HTTP_400_BAD_REQUEST)

        # ── Generate report ──
        report = generate_balance_sheet(
            company=company,
            as_of_date=as_of_date,
            filter_mode=filter_mode,
            compare_date=compare_date,
        )

        # ── Export if requested ──
        export_format = request.query_params.get('export')
        if export_format:
            return maybe_export(export_format, 'balance_sheet', report, company.name)

        # ── Build response ──
        data = {
            'report_title': report['report_title'],
            'company_name': report['company_name'],
            'base_currency': report['base_currency'],
            'as_of_date': report['as_of_date'],
            'compare_date': report['compare_date'],
            'filter_mode': report['filter_mode'],
            'account_count': report['account_count'],
            'generated_at': datetime.now().isoformat(),

            # Three sections with account trees
            'assets': report['assets'],
            'liabilities': report['liabilities'],
            'equity': report['equity'],

            # Auto-calculated earnings
            'retained_earnings_auto': report['retained_earnings_auto'],

            # Totals
            'total_assets': report['total_assets'],
            'total_liabilities': report['total_liabilities'],
            'total_equity_accounts': report['total_equity_accounts'],
            'total_equity': report['total_equity'],
            'total_liabilities_and_equity': report['total_liabilities_and_equity'],

            # Equation check
            'is_balanced': report['is_balanced'],
        }

        # Add comparison totals if applicable
        if compare_date:
            data['compare_total_assets'] = report['compare_total_assets']
            data['compare_total_liabilities_and_equity'] = report['compare_total_liabilities_and_equity']
            data['change_total_assets'] = report['change_total_assets']
            data['change_total_le'] = report['change_total_le']

        return Response({'success': True, 'data': data}, status=status.HTTP_200_OK)


# ══════════════════════════════════════════════════
# INCOME STATEMENT (P&L)
# ══════════════════════════════════════════════════

class IncomeStatementView(APIView):
    """
    GET /api/companies/{company_id}/reports/income-statement/

    Generates an Income Statement (Profit & Loss).
    Shows Revenue − Expenses = Net Income for a specific PERIOD.

    Unlike the Balance Sheet (point-in-time), this is period-based.
    Default period: fiscal year start → today (Year-to-Date).

    Query Parameters:
        from_date           YYYY-MM-DD (default: fiscal year start)
        to_date             YYYY-MM-DD (default: today)
        filter_mode         'all' | 'with_transactions' | 'non_zero' (default)
        compare_from_date   YYYY-MM-DD (optional comparison period start)
        compare_to_date     YYYY-MM-DD (optional comparison period end)

    COMPARISON NOTES:
        Both compare_from_date and compare_to_date must be provided
        together. Typical use cases:
        - This month vs last month
        - This quarter vs same quarter last year
        - YTD this year vs YTD last year
    """

    def get(self, request, company_id):
        company, error = _get_company_and_check_access(request, company_id)
        if error:
            return error

        # ── Parse to_date (parse first — needed for from_date default) ──
        to_date_str = request.query_params.get('to_date')
        if to_date_str:
            to_date, err = _parse_date_param(to_date_str, 'to_date')
            if err:
                return Response(
                    {'success': False, 'message': err},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            to_date = date.today()

        # ── Parse from_date (default: fiscal year start of to_date) ──
        from_date_str = request.query_params.get('from_date')
        if from_date_str:
            from_date, err = _parse_date_param(from_date_str, 'from_date')
            if err:
                return Response(
                    {'success': False, 'message': err},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            # Default to Year-to-Date: fiscal year start → to_date
            from_date = _get_fiscal_year_start(company, to_date)

        # ── Validate date range ──
        if from_date > to_date:
            return Response(
                {
                    'success': False,
                    'message': (
                        f'from_date ({from_date}) cannot be after '
                        f'to_date ({to_date}).'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Parse filter_mode ──
        filter_mode = request.query_params.get('filter_mode', FILTER_NON_ZERO)
        filter_mode, err = _validate_filter_mode(filter_mode)
        if err:
            return err

        # ── Parse comparison period ──
        compare_from_date = None
        compare_to_date = None
        compare_from_str = request.query_params.get('compare_from_date')
        compare_to_str = request.query_params.get('compare_to_date')

        # Both must be provided, or neither
        if compare_from_str or compare_to_str:
            if not compare_from_str or not compare_to_str:
                return Response(
                    {
                        'success': False,
                        'message': (
                            'Both compare_from_date and compare_to_date '
                            'must be provided together.'
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            compare_from_date, err = _parse_date_param(
                compare_from_str, 'compare_from_date',
            )
            if err:
                return Response(
                    {'success': False, 'message': err},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            compare_to_date, err = _parse_date_param(
                compare_to_str, 'compare_to_date',
            )
            if err:
                return Response(
                    {'success': False, 'message': err},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate comparison date range
            if compare_from_date > compare_to_date:
                return Response(
                    {
                        'success': False,
                        'message': (
                            f'compare_from_date ({compare_from_date}) cannot '
                            f'be after compare_to_date ({compare_to_date}).'
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ── Generate report ──
        report = generate_income_statement(
            company=company,
            from_date=from_date,
            to_date=to_date,
            filter_mode=filter_mode,
            compare_from_date=compare_from_date,
            compare_to_date=compare_to_date,
        )

        # ── Export if requested ──
        export_format = request.query_params.get('export')
        if export_format:
            return maybe_export(export_format, 'income_statement', report, company.name)

        # ── Build response ──
        has_compare = compare_from_date is not None

        data = {
            'report_title': report['report_title'],
            'company_name': report['company_name'],
            'base_currency': report['base_currency'],
            'from_date': report['from_date'],
            'to_date': report['to_date'],
            'filter_mode': report['filter_mode'],
            'account_count': report['account_count'],
            'generated_at': datetime.now().isoformat(),

            # Two sections with account trees
            'revenue': report['revenue'],
            'expenses': report['expenses'],

            # Summary totals
            'total_revenue': report['total_revenue'],
            'total_expenses': report['total_expenses'],
            'net_income': report['net_income'],

            # Profitability indicator
            'is_net_profit': report['is_net_profit'],
        }

        # Add comparison data if applicable
        if has_compare:
            data['compare_from_date'] = report['compare_from_date']
            data['compare_to_date'] = report['compare_to_date']
            data['compare_total_revenue'] = report['compare_total_revenue']
            data['compare_total_expenses'] = report['compare_total_expenses']
            data['compare_net_income'] = report['compare_net_income']
            data['change_revenue'] = report['change_revenue']
            data['change_expenses'] = report['change_expenses']
            data['change_net_income'] = report['change_net_income']
            data['change_revenue_pct'] = report['change_revenue_pct']
            data['change_expenses_pct'] = report['change_expenses_pct']
            data['change_net_income_pct'] = report['change_net_income_pct']

        return Response({'success': True, 'data': data}, status=status.HTTP_200_OK)


# ══════════════════════════════════════════════════
# GENERAL LEDGER
# ══════════════════════════════════════════════════

# Valid journal type values for the filter parameter
VALID_JOURNAL_TYPES = {choice.value for choice in JournalTypeChoices}


class GeneralLedgerView(APIView):
    """
    GET /api/companies/{company_id}/reports/general-ledger/

    Generates a detailed General Ledger showing every transaction
    per account with opening balance, running balance, and closing
    balance. This is the transaction-level detail report.

    Unlike the summary reports (Trial Balance, Balance Sheet, Income
    Statement), this shows individual LedgerEntry rows.

    Query Parameters:
        from_date       YYYY-MM-DD (default: fiscal year start)
        to_date         YYYY-MM-DD (default: today)
        account_id      UUID (optional — filter to a single account)
        journal_type    str (optional — filter by type: SALES, PURCHASE, etc.)

    PAGINATION:
        Paginated at the account level — each page contains N complete
        accounts with all their transactions. Default page_size=20 accounts.
        Use ?page=2&page_size=10 to control.
    """

    def get(self, request, company_id):
        company, error = _get_company_and_check_access(request, company_id)
        if error:
            return error

        # ── Parse to_date (parse first — needed for from_date default) ──
        to_date_str = request.query_params.get('to_date')
        if to_date_str:
            to_date, err = _parse_date_param(to_date_str, 'to_date')
            if err:
                return Response(
                    {'success': False, 'message': err},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            to_date = date.today()

        # ── Parse from_date (default: fiscal year start of to_date) ──
        from_date_str = request.query_params.get('from_date')
        if from_date_str:
            from_date, err = _parse_date_param(from_date_str, 'from_date')
            if err:
                return Response(
                    {'success': False, 'message': err},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            from_date = _get_fiscal_year_start(company, to_date)

        # ── Validate date range ──
        if from_date > to_date:
            return Response(
                {
                    'success': False,
                    'message': (
                        f'from_date ({from_date}) cannot be after '
                        f'to_date ({to_date}).'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Parse optional account_id filter ──
        account_id = None
        account_id_str = request.query_params.get('account_id')
        if account_id_str:
            try:
                account_id = UUID(account_id_str)
            except (ValueError, AttributeError):
                return Response(
                    {
                        'success': False,
                        'message': (
                            f'Invalid account_id: "{account_id_str}". '
                            f'Must be a valid UUID.'
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ── Parse optional journal_type filter ──
        journal_type = None
        journal_type_str = request.query_params.get('journal_type')
        if journal_type_str:
            journal_type = journal_type_str.upper()
            if journal_type not in VALID_JOURNAL_TYPES:
                return Response(
                    {
                        'success': False,
                        'message': (
                            f'Invalid journal_type: "{journal_type_str}". '
                            f'Valid options: {", ".join(sorted(VALID_JOURNAL_TYPES))}.'
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ── Generate full report ──
        report = generate_general_ledger(
            company=company,
            from_date=from_date,
            to_date=to_date,
            account_id=account_id,
            journal_type=journal_type,
        )

        # ── Export if requested (before pagination — exports ALL accounts) ──
        export_format = request.query_params.get('export')
        if export_format:
            return maybe_export(export_format, 'general_ledger', report, company.name)

        # ── Paginate at the account level ──
        # Each page contains N complete accounts with all their transactions.
        all_accounts = report['accounts']
        page_size = min(
            int(request.query_params.get('page_size', 20)),
            100,   # Hard cap — matches StandardResultsSetPagination.max_page_size
        )
        page_num = int(request.query_params.get('page', 1))
        total_accounts = len(all_accounts)
        total_pages = max(1, -(-total_accounts // page_size))  # Ceiling division

        # Validate page number
        if page_num < 1 or (page_num > total_pages and total_accounts > 0):
            return Response(
                {
                    'success': False,
                    'message': (
                        f'Invalid page: {page_num}. '
                        f'Total pages: {total_pages}.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Slice the accounts for this page
        start_idx = (page_num - 1) * page_size
        end_idx = start_idx + page_size
        page_accounts = all_accounts[start_idx:end_idx]

        # Count transactions on this page only
        page_transaction_count = sum(
            a['transaction_count'] for a in page_accounts
        )

        # ── Build response ──
        data = {
            'report_title': report['report_title'],
            'company_name': report['company_name'],
            'base_currency': report['base_currency'],
            'from_date': report['from_date'],
            'to_date': report['to_date'],
            'filters': report['filters'],
            'generated_at': datetime.now().isoformat(),

            # Grand totals (across ALL accounts, not just this page)
            'account_count': report['account_count'],
            'transaction_count': report['transaction_count'],
            'grand_total_debit': report['grand_total_debit'],
            'grand_total_credit': report['grand_total_credit'],

            # Paginated account data
            'accounts': page_accounts,
        }

        return Response(
            {
                'success': True,
                'data': data,
                'pagination': {
                    'total_count': total_accounts,
                    'page': page_num,
                    'page_size': page_size,
                    'total_pages': total_pages,
                    'page_transaction_count': page_transaction_count,
                },
            },
            status=status.HTTP_200_OK,
        )


# ══════════════════════════════════════════════════
# ACCOUNT TRANSACTIONS (Drill-Down Report)
# ══════════════════════════════════════════════════

class AccountTransactionsView(APIView):
    """
    GET /api/companies/{company_id}/reports/account-transactions/

    Generates a detailed Account Transactions report for a single
    account. This is the drill-down view — when a user clicks an
    account name in Trial Balance, Balance Sheet, P&L, or General
    Ledger, they land here.

    Shows every ledger entry with opening balance, running balance,
    closing balance, and source journal references (entry_number,
    description, reference).

    NO PAGINATION — all entries in the date range are returned.
    Date range filtering naturally bounds the data volume.

    Query Parameters:
        account_id      UUID (REQUIRED — the account to show)
        from_date       YYYY-MM-DD (default: fiscal year start)
        to_date         YYYY-MM-DD (default: today)
    """

    def get(self, request, company_id):
        company, error = _get_company_and_check_access(request, company_id)
        if error:
            return error

        # ── Parse account_id (REQUIRED) ──
        account_id_str = request.query_params.get('account_id')
        if not account_id_str:
            return Response(
                {
                    'success': False,
                    'message': (
                        'account_id is required. '
                        'Provide the UUID of the account to view.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            account_id = UUID(account_id_str)
        except (ValueError, AttributeError):
            return Response(
                {
                    'success': False,
                    'message': (
                        f'Invalid account_id: "{account_id_str}". '
                        f'Must be a valid UUID.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Validate account exists and belongs to this company ──
        try:
            account = (
                Account.objects
                .select_related('classification', 'parent_account')
                .get(id=account_id, company=company)
            )
        except Account.DoesNotExist:
            return Response(
                {
                    'success': False,
                    'message': (
                        f'Account not found. No account with ID '
                        f'"{account_id}" exists in this company.'
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Parse to_date (parse first — needed for from_date default) ──
        to_date_str = request.query_params.get('to_date')
        if to_date_str:
            to_date, err = _parse_date_param(to_date_str, 'to_date')
            if err:
                return Response(
                    {'success': False, 'message': err},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            to_date = date.today()

        # ── Parse from_date (default: fiscal year start of to_date) ──
        from_date_str = request.query_params.get('from_date')
        if from_date_str:
            from_date, err = _parse_date_param(from_date_str, 'from_date')
            if err:
                return Response(
                    {'success': False, 'message': err},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            from_date = _get_fiscal_year_start(company, to_date)

        # ── Validate date range ──
        if from_date > to_date:
            return Response(
                {
                    'success': False,
                    'message': (
                        f'from_date ({from_date}) cannot be after '
                        f'to_date ({to_date}).'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Generate report ──
        report = generate_account_transactions(
            company=company,
            account=account,
            from_date=from_date,
            to_date=to_date,
        )

        # ── Export if requested ──
        export_format = request.query_params.get('export')
        if export_format:
            return maybe_export(export_format, 'account_transactions', report, company.name)

        # ── Build response ──
        data = {
            'report_title': report['report_title'],
            'company_name': report['company_name'],
            'base_currency': report['base_currency'],
            'from_date': report['from_date'],
            'to_date': report['to_date'],
            'generated_at': datetime.now().isoformat(),

            # Account info
            'account': report['account'],

            # Opening balance
            'opening_balance': report['opening_balance'],
            'opening_balance_type': report['opening_balance_type'],

            # Transactions (no pagination)
            'transactions': report['transactions'],
            'transaction_count': report['transaction_count'],

            # Period totals
            'total_debit': report['total_debit'],
            'total_credit': report['total_credit'],
            'net_movement': report['net_movement'],

            # Closing balance
            'closing_balance': report['closing_balance'],
            'closing_balance_type': report['closing_balance_type'],
        }

        return Response({'success': True, 'data': data}, status=status.HTTP_200_OK)


# ══════════════════════════════════════════════════
# CASH FLOW STATEMENT
# ══════════════════════════════════════════════════

class CashFlowView(APIView):
    """
    GET /api/companies/{company_id}/reports/cash-flow/

    Generates a Cash Flow Statement.
    Shows where cash came from and where it went during a period,
    split into Operating, Investing, and Financing activities.

    Period-based report (like Income Statement).
    Default period: fiscal year start → today.

    Query Parameters:
        method              'indirect' (default) | 'direct'
        from_date           YYYY-MM-DD (default: fiscal year start)
        to_date             YYYY-MM-DD (default: today)
        compare_from_date   YYYY-MM-DD (optional comparison period start)
        compare_to_date     YYYY-MM-DD (optional comparison period end)
    """

    def get(self, request, company_id):
        company, error = _get_company_and_check_access(request, company_id)
        if error:
            return error

        # ── Parse method (default: indirect) ──
        method = request.query_params.get('method', 'indirect').lower()

        if method not in ('indirect', 'direct'):
            return Response(
                {
                    'success': False,
                    'message': (
                        f'Invalid method: "{method}". '
                        f'Valid options: indirect, direct.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Direct method: not yet available ──
        if method == 'direct':
            return Response(
                {
                    'success': False,
                    'message': (
                        'The Direct Method for Cash Flow Statement is coming soon. '
                        'This method requires transaction-level cash classification '
                        'from modules like Sales, Purchase, Expense, and Payroll, '
                        'which are not yet available. '
                        'Please use method=indirect (the default) for now.'
                    ),
                },
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        # ── Parse to_date (parse first — needed for from_date default) ──
        to_date_str = request.query_params.get('to_date')
        if to_date_str:
            to_date, err = _parse_date_param(to_date_str, 'to_date')
            if err:
                return Response(
                    {'success': False, 'message': err},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            to_date = date.today()

        # ── Parse from_date (default: fiscal year start of to_date) ──
        from_date_str = request.query_params.get('from_date')
        if from_date_str:
            from_date, err = _parse_date_param(from_date_str, 'from_date')
            if err:
                return Response(
                    {'success': False, 'message': err},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            from_date = _get_fiscal_year_start(company, to_date)

        # ── Validate date range ──
        if from_date > to_date:
            return Response(
                {
                    'success': False,
                    'message': (
                        f'from_date ({from_date}) cannot be after '
                        f'to_date ({to_date}).'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Parse comparison period ──
        compare_from_date = None
        compare_to_date = None
        compare_from_str = request.query_params.get('compare_from_date')
        compare_to_str = request.query_params.get('compare_to_date')

        if compare_from_str or compare_to_str:
            if not compare_from_str or not compare_to_str:
                return Response(
                    {
                        'success': False,
                        'message': (
                            'Both compare_from_date and compare_to_date '
                            'must be provided together.'
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            compare_from_date, err = _parse_date_param(
                compare_from_str, 'compare_from_date',
            )
            if err:
                return Response(
                    {'success': False, 'message': err},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            compare_to_date, err = _parse_date_param(
                compare_to_str, 'compare_to_date',
            )
            if err:
                return Response(
                    {'success': False, 'message': err},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if compare_from_date > compare_to_date:
                return Response(
                    {
                        'success': False,
                        'message': (
                            f'compare_from_date ({compare_from_date}) cannot '
                            f'be after compare_to_date ({compare_to_date}).'
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ── Generate report ──
        report = generate_cash_flow(
            company=company,
            from_date=from_date,
            to_date=to_date,
            compare_from_date=compare_from_date,
            compare_to_date=compare_to_date,
        )

        # ── Export if requested ──
        export_format = request.query_params.get('export')
        if export_format:
            return maybe_export(export_format, 'cash_flow', report, company.name)

        # ── Build response ──
        has_compare = compare_from_date is not None

        data = {
            'report_title': report['report_title'],
            'method': report['method'],
            'company_name': report['company_name'],
            'base_currency': report['base_currency'],
            'from_date': report['from_date'],
            'to_date': report['to_date'],
            'generated_at': datetime.now().isoformat(),

            # Three activity sections
            'operating_activities': report['operating_activities'],
            'investing_activities': report['investing_activities'],
            'financing_activities': report['financing_activities'],

            # Cash reconciliation with verification
            'cash_reconciliation': report['cash_reconciliation'],

            # Summary totals
            'summary': report['summary'],
        }

        # Add comparison data if applicable
        if has_compare:
            data['compare_from_date'] = report['compare_from_date']
            data['compare_to_date'] = report['compare_to_date']
            data['compare_operating_activities'] = report['compare_operating_activities']
            data['compare_investing_activities'] = report['compare_investing_activities']
            data['compare_financing_activities'] = report['compare_financing_activities']
            data['compare_cash_reconciliation'] = report['compare_cash_reconciliation']
            data['compare_summary'] = report['compare_summary']
            data['changes'] = report['changes']

        return Response({'success': True, 'data': data}, status=status.HTTP_200_OK)