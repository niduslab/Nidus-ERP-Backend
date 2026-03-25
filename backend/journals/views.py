# backend/journals/views.py

"""
API views for Manual Journal Entries.

ENDPOINTS:
    POST   /api/companies/<id>/journal-entries/                 Create (DRAFT)
    GET    /api/companies/<id>/journal-entries/                  List (with filters)
    GET    /api/companies/<id>/journal-entries/<entry_id>/       Detail
    PATCH  /api/companies/<id>/journal-entries/<entry_id>/       Edit (DRAFT only)
    DELETE /api/companies/<id>/journal-entries/<entry_id>/       Delete (DRAFT only)
    POST   /api/companies/<id>/journal-entries/<entry_id>/post/  Post a draft
    POST   /api/companies/<id>/journal-entries/<entry_id>/void/  Void a posted entry

    GET    /api/companies/<id>/accounts/<account_id>/ledger/     Account ledger
    GET    /api/companies/<id>/accounts/<account_id>/balance/    Account balance

DESIGN:
    Views handle HTTP concerns (request parsing, response formatting,
    permissions). Business logic lives in services.py. Views never
    contain financial calculations or state transitions directly.
"""

from django.http import HttpResponse
from rest_framework.parsers import MultiPartParser, FormParser
from .bulk_import_template import generate_bulk_import_template
from .bulk_import_validator import validate_bulk_import
from .services import bulk_create_journals

from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from companies.models import Company, CompanyUser, RoleChoices
from chartofaccounts.models import Account

from .models import ManualJournal, LedgerEntry
from .serializers import (
    CreateManualJournalSerializer,
    UpdateManualJournalSerializer,
    ManualJournalListSerializer,
    ManualJournalDetailSerializer,
    LedgerEntrySerializer,
    VoidJournalSerializer,
)
from .services import (
    create_journal,
    post_journal,
    void_journal,
    delete_journal,
    update_journal,
    get_account_balance,
)


# ──────────────────────────────────────────────
# ROLE GROUPS
# ──────────────────────────────────────────────

JOURNAL_WRITE_ROLES = [RoleChoices.OWNER, RoleChoices.ADMIN, RoleChoices.ACCOUNTANT]
JOURNAL_VIEW_ROLES = [RoleChoices.OWNER, RoleChoices.ADMIN, RoleChoices.ACCOUNTANT, RoleChoices.AUDITOR]


# ──────────────────────────────────────────────
# HELPER
# ──────────────────────────────────────────────

def get_company_and_membership(request, company_id):
    company = get_object_or_404(Company, id=company_id, is_active=True)
    try:
        membership = CompanyUser.objects.get(
            user=request.user, company=company, is_active=True,
        )
    except CompanyUser.DoesNotExist:
        return company, None
    return company, membership


# ══════════════════════════════════════════════════
# JOURNAL LIST & CREATE
# ══════════════════════════════════════════════════

class JournalListCreateView(APIView):
    """
    GET  → List journal entries with optional filters
    POST → Create a new journal entry (DRAFT)
    """

    def get(self, request, company_id):
        company, membership = get_company_and_membership(request, company_id)
        if not membership:
            return Response(
                {'success': False, 'message': 'You do not have access to this company.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if membership.role not in JOURNAL_VIEW_ROLES:
            return Response(
                {'success': False, 'message': 'Your role does not have permission to view journal entries.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        journals = ManualJournal.objects.filter(
            company=company,
        ).select_related('created_by').prefetch_related('lines')

        # ── Optional filters ──
        status_filter = request.query_params.get('status')
        if status_filter:
            journals = journals.filter(status=status_filter.upper())

        journal_type = request.query_params.get('journal_type')
        if journal_type:
            journals = journals.filter(journal_type=journal_type.upper())

        date_from = request.query_params.get('date_from')
        if date_from:
            journals = journals.filter(date__gte=date_from)

        date_to = request.query_params.get('date_to')
        if date_to:
            journals = journals.filter(date__lte=date_to)

        search = request.query_params.get('search')
        if search:
            from django.db.models import Q
            journals = journals.filter(
                Q(entry_number__icontains=search) |
                Q(description__icontains=search) |
                Q(reference__icontains=search)
            )

        # ── Pagination ──
        from nidus_erp.pagination import StandardResultsSetPagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(journals, request)

        if page is not None:
            serializer = ManualJournalListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        # Fallback (shouldn't happen, but safe)
        serializer = ManualJournalListSerializer(journals, many=True)
        return Response(
            {'success': True, 'count': len(serializer.data), 'data': serializer.data},
            status=status.HTTP_200_OK,
        )

    def post(self, request, company_id):
        company, membership = get_company_and_membership(request, company_id)
        if not membership:
            return Response(
                {'success': False, 'message': 'You do not have access to this company.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if membership.role not in JOURNAL_WRITE_ROLES:
            return Response(
                {'success': False, 'message': 'Only Owner, Admin, or Accountant can create journal entries.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CreateManualJournalSerializer(
            data=request.data,
            context={'company': company},
        )

        if not serializer.is_valid():
            return Response(
                {'success': False, 'message': 'Invalid input.', 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data

        # Build service-layer data structures
        journal_data = {
            'date': data['date'],
            'description': data['description'],
            'reference': data.get('reference'),
            'journal_type': data.get('journal_type'),
            'currency': data.get('currency', company.base_currency),
            'exchange_rate': data.get('exchange_rate'),
        }

        lines_data = []
        for line in data['lines']:
            lines_data.append({
                'account': line['_account'],
                'entry_type': line['entry_type'],
                'amount': line['amount'],
                'description': line.get('description'),
                'tax_profile': line.get('_tax_profile'),
            })

        try:
            journal = create_journal(company, request.user, journal_data, lines_data)
        except ValueError as e:
            return Response(
                {'success': False, 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        output = ManualJournalDetailSerializer(journal).data

        return Response(
            {
                'success': True,
                'message': f'Journal {journal.entry_number} created as DRAFT.',
                'data': output,
            },
            status=status.HTTP_201_CREATED,
        )


# ══════════════════════════════════════════════════
# JOURNAL DETAIL, UPDATE, DELETE
# ══════════════════════════════════════════════════

class JournalDetailView(APIView):
    """
    GET    → View journal details with all lines
    PATCH  → Edit a draft journal
    DELETE → Delete a draft journal
    """

    def get(self, request, company_id, entry_id):
        company, membership = get_company_and_membership(request, company_id)
        if not membership:
            return Response(
                {'success': False, 'message': 'You do not have access to this company.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if membership.role not in JOURNAL_VIEW_ROLES:
            return Response(
                {'success': False, 'message': 'Your role does not have permission to view journal entries.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        journal = get_object_or_404(
            ManualJournal.objects.select_related(
                'created_by', 'voided_by', 'voided_by_entry', 'reversal_of',
            ).prefetch_related('lines__account', 'lines__tax_profile'),
            id=entry_id,
            company=company,
        )

        serializer = ManualJournalDetailSerializer(journal)

        return Response(
            {'success': True, 'data': serializer.data},
            status=status.HTTP_200_OK,
        )

    def patch(self, request, company_id, entry_id):
        company, membership = get_company_and_membership(request, company_id)
        if not membership:
            return Response(
                {'success': False, 'message': 'You do not have access to this company.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if membership.role not in JOURNAL_WRITE_ROLES:
            return Response(
                {'success': False, 'message': 'Only Owner, Admin, or Accountant can create journal entries.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        journal = get_object_or_404(ManualJournal, id=entry_id, company=company)

        serializer = UpdateManualJournalSerializer(
            data=request.data,
            context={'company': company, 'journal': journal},
        )

        if not serializer.is_valid():
            return Response(
                {'success': False, 'message': 'Invalid input.', 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data

        # Build service-layer structures
        journal_data = {}
        for field in ['date', 'description', 'reference', 'journal_type', 'currency', 'exchange_rate']:
            if field in data:
                journal_data[field] = data[field]

        lines_data = None
        if 'lines' in data:
            lines_data = []
            for line in data['lines']:
                lines_data.append({
                    'account': line['_account'],
                    'entry_type': line['entry_type'],
                    'amount': line['amount'],
                    'description': line.get('description'),
                    'tax_profile': line.get('_tax_profile'),
                })

        try:
            journal = update_journal(
                journal,
                journal_data=journal_data if journal_data else None,
                lines_data=lines_data,
            )
        except ValueError as e:
            return Response(
                {'success': False, 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        output = ManualJournalDetailSerializer(journal).data

        return Response(
            {'success': True, 'message': 'Journal updated.', 'data': output},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, company_id, entry_id):
        company, membership = get_company_and_membership(request, company_id)
        if not membership:
            return Response(
                {'success': False, 'message': 'You do not have access to this company.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if membership.role not in JOURNAL_WRITE_ROLES:
            return Response(
                {'success': False, 'message': 'Only Owner, Admin, or Accountant can create journal entries.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        journal = get_object_or_404(ManualJournal, id=entry_id, company=company)

        try:
            delete_journal(journal)
        except ValueError as e:
            return Response(
                {'success': False, 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {'success': True, 'message': f'Journal {journal.entry_number} deleted.'},
            status=status.HTTP_200_OK,
        )


# ══════════════════════════════════════════════════
# POST & VOID ACTIONS
# ══════════════════════════════════════════════════

class JournalPostView(APIView):
    """POST → Post a draft journal entry (DRAFT → POSTED)."""

    def post(self, request, company_id, entry_id):
        company, membership = get_company_and_membership(request, company_id)
        if not membership:
            return Response(
                {'success': False, 'message': 'You do not have access to this company.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if membership.role not in JOURNAL_WRITE_ROLES:
            return Response(
                {'success': False, 'message': 'Only Owner, Admin, or Accountant can create journal entries.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        journal = get_object_or_404(ManualJournal, id=entry_id, company=company)

        try:
            journal = post_journal(journal, request.user)
        except ValueError as e:
            return Response(
                {'success': False, 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        output = ManualJournalDetailSerializer(journal).data

        return Response(
            {
                'success': True,
                'message': f'Journal {journal.entry_number} has been posted.',
                'data': output,
            },
            status=status.HTTP_200_OK,
        )


class JournalVoidView(APIView):
    """POST → Void a posted journal entry (POSTED → VOID)."""

    def post(self, request, company_id, entry_id):
        company, membership = get_company_and_membership(request, company_id)
        if not membership:
            return Response(
                {'success': False, 'message': 'You do not have access to this company.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if membership.role not in JOURNAL_WRITE_ROLES:
            return Response(
                {'success': False, 'message': 'Only Owner, Admin, or Accountant can create journal entries.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        journal = get_object_or_404(ManualJournal, id=entry_id, company=company)

        serializer = VoidJournalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        void_date = serializer.validated_data.get('void_date')

        try:
            reversal = void_journal(journal, request.user, void_date)
        except ValueError as e:
            return Response(
                {'success': False, 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                'success': True,
                'message': (
                    f'Journal {journal.entry_number} has been voided. '
                    f'Reversing entry {reversal.entry_number} created.'
                ),
                'data': {
                    'voided_journal': ManualJournalDetailSerializer(journal).data,
                    'reversing_entry': ManualJournalDetailSerializer(reversal).data,
                },
            },
            status=status.HTTP_200_OK,
        )


# ══════════════════════════════════════════════════
# ACCOUNT LEDGER & BALANCE
# ══════════════════════════════════════════════════

class AccountLedgerView(APIView):
    """
    GET → List all ledger entries for a specific account.
    Shows the transaction history of an account.
    """
    def get(self, request, company_id,account_id):
        company, membership = get_company_and_membership(request, company_id)
        if not membership:
            return Response(
                {'success': False, 'message': 'You do not have access to this company.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if membership.role not in JOURNAL_VIEW_ROLES:
            return Response(
                {'success': False, 'message': 'Your role does not have permission to view journal entries.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        account = get_object_or_404(Account, id=account_id, company=company)

        entries = LedgerEntry.objects.filter(
            company=company,
            ledger_account=account,
        ).select_related('ledger_account').order_by('date', 'created_at')

        # Optional date filters
        date_from = request.query_params.get('date_from')
        if date_from:
            entries = entries.filter(date__gte=date_from)

        date_to = request.query_params.get('date_to')
        if date_to:
            entries = entries.filter(date__lte=date_to)

        # ── Pagination ──
        from nidus_erp.pagination import StandardResultsSetPagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(entries, request)

        if page is not None:
            serializer = LedgerEntrySerializer(page, many=True)
            # Build custom response that includes account info + pagination
            response = paginator.get_paginated_response(serializer.data)
            response.data['account'] = {
                'id': str(account.id),
                'code': account.code,
                'name': account.name,
                'normal_balance': account.normal_balance,
                'currency': account.currency,
            }
            return response

        # Fallback
        serializer = LedgerEntrySerializer(entries, many=True)
        return Response(
            {
                'success': True,
                'account': {
                    'id': str(account.id),
                    'code': account.code,
                    'name': account.name,
                    'normal_balance': account.normal_balance,
                    'currency': account.currency,
                },
                'data': serializer.data,
            },
            status=status.HTTP_200_OK,
        )
    

class AccountBalanceView(APIView):
    """
    GET → Calculate and return the current balance of an account.
    Supports ?as_of_date=YYYY-MM-DD and ?include_sub_accounts=true/false.
    """

    def get(self, request, company_id, account_id):
        company, membership = get_company_and_membership(request, company_id)
        if not membership:
            return Response(
                {'success': False, 'message': 'You do not have access to this company.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if membership.role not in JOURNAL_VIEW_ROLES:
            return Response(
                {'success': False, 'message': 'Your role does not have permission to view journal entries.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        account = get_object_or_404(Account, id=account_id, company=company)

        as_of_date = request.query_params.get('as_of_date')
        include_subs = request.query_params.get('include_sub_accounts', 'true').lower() == 'true'

        balance_data = get_account_balance(
            account=account,
            as_of_date=as_of_date,
            include_sub_accounts=include_subs,
        )

        return Response(
            {
                'success': True,
                'account': {
                    'id': str(account.id),
                    'code': account.code,
                    'name': account.name,
                    'normal_balance': account.normal_balance,
                },
                'data': {
                    'balance': str(balance_data['balance']),
                    'foreign_balance': str(balance_data['foreign_balance']) if balance_data['foreign_balance'] is not None else None,
                    'total_debit': str(balance_data['total_debit']),
                    'total_credit': str(balance_data['total_credit']),
                    'currency': balance_data['currency'],
                    'base_currency': balance_data['base_currency'],
                    'include_sub_accounts': include_subs,
                    'as_of_date': as_of_date,
                },
            },
            status=status.HTTP_200_OK,
        )
    


class BulkImportTemplateDownloadView(APIView):
    """
    GET /api/companies/<id>/journal-entries/bulk-import/template/
 
    Download the bulk import Excel template, pre-populated with
    this company's account reference sheet.
    """
 
    def get(self, request, company_id):
        company, membership = get_company_and_membership(request, company_id)
 
        if not membership:
            return Response(
                {'success': False, 'message': 'You do not have access to this company.'},
                status=status.HTTP_403_FORBIDDEN,
            )
 
        if membership.role not in JOURNAL_WRITE_ROLES:
            return Response(
                {'success': False, 'message': 'Only Owner, Admin, or Accountant can download the import template.'},
                status=status.HTTP_403_FORBIDDEN,
            )
 
        from .bulk_import_template import generate_bulk_import_template
 
        file_bytes = generate_bulk_import_template(company)
 
        response = HttpResponse(
            file_bytes,
            content_type=(
                'application/vnd.openxmlformats-officedocument'
                '.spreadsheetml.sheet'
            ),
        )
        safe_name = company.name.replace('"', '').replace(' ', '_')[:30]
        response['Content-Disposition'] = (
            f'attachment; filename="NidusERP_Bulk_Journal_Import_{safe_name}.xlsx"'
        )
 
        return response
 
 
class BulkImportUploadView(APIView):
    """
    POST /api/companies/<id>/journal-entries/bulk-import/upload/
 
    Upload a filled bulk import file (.xlsx or .csv).
 
    Form data:
        file: The uploaded file
        save_mode: "valid_only" or "all_or_none" (default: "all_or_none")
 
    "valid_only":  Save accepted entries, return rejected with errors.
    "all_or_none": If ANY entry fails, save nothing, return all errors.
 
    All imported entries are created as DRAFT.
    """
    parser_classes = [MultiPartParser, FormParser]
 
    def post(self, request, company_id):
        company, membership = get_company_and_membership(request, company_id)
 
        if not membership:
            return Response(
                {'success': False, 'message': 'You do not have access to this company.'},
                status=status.HTTP_403_FORBIDDEN,
            )
 
        if membership.role not in JOURNAL_WRITE_ROLES:
            return Response(
                {'success': False, 'message': 'Only Owner, Admin, or Accountant can import journal entries.'},
                status=status.HTTP_403_FORBIDDEN,
            )
 
        # ── Get the uploaded file ──
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response(
                {'success': False, 'message': 'No file uploaded. Please attach an .xlsx or .csv file.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
 
        save_mode = request.data.get('save_mode', 'all_or_none')
        if save_mode not in ('valid_only', 'all_or_none'):
            return Response(
                {
                    'success': False,
                    'message': 'Invalid save_mode. Must be "valid_only" or "all_or_none".',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
 
        # ── Validate the file ──
        from .bulk_import_validator import validate_bulk_import
 
        result = validate_bulk_import(
            file_obj=uploaded_file,
            file_name=uploaded_file.name,
            company=company,
        )
 
        # ── File-level error (can't even parse) ──
        if result.get('file_error'):
            return Response(
                {
                    'success': False,
                    'message': result['file_error'],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
 
        # ── All-or-none mode: reject everything if any errors ──
        if save_mode == 'all_or_none' and not result['valid']:
            return Response(
                {
                    'success': False,
                    'message': (
                        f'Import rejected. {result["summary"]["rejected"]} of '
                        f'{result["summary"]["total_groups"]} entries have errors. '
                        f'Fix all errors and re-upload, or use save_mode="valid_only" '
                        f'to save only the valid entries.'
                    ),
                    'summary': result['summary'],
                    'accepted_entries': result['accepted_entries'],   # ← ADD THIS LINE
                    'rejected_entries': result['rejected_entries'],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
 
        # ── No valid entries to save ──
        if not result['parsed_data']:
            return Response(
                {
                    'success': False,
                    'message': 'No valid entries found in the file.',
                    'summary': result['summary'],
                    'rejected_entries': result['rejected_entries'],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
 
        # ── Save valid entries ──
        from .services import bulk_create_journals
 
        try:
            created = bulk_create_journals(
                company=company,
                created_by=request.user,
                parsed_entries=result['parsed_data'],
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'Import failed during save: {str(e)}',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
 
        # ── Build response ──
        accepted_summary = [
            {
                'entry_number': j.entry_number,
                'date': str(j.date),
                'description': j.description,
                'status': j.status,
                'lines': j.lines.count(),
            }
            for j in created
        ]
 
        response_data = {
            'success': True,
            'message': (
                f'Successfully imported {len(created)} journal entries as DRAFT. '
                f'{result["summary"]["rejected"]} entries were rejected.'
                if result['summary']['rejected'] > 0
                else f'Successfully imported {len(created)} journal entries as DRAFT.'
            ),
            'summary': {
                'total_groups': result['summary']['total_groups'],
                'accepted': len(created),
                'rejected': result['summary']['rejected'],
                'total_rows': result['summary']['total_rows'],
            },
            'accepted_entries': accepted_summary,
        }
 
        if result['rejected_entries']:
            response_data['rejected_entries'] = result['rejected_entries']
 
        return Response(response_data, status=status.HTTP_201_CREATED)
 