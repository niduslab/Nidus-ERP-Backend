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

    GET    /api/companies/<id>/accounts/<account_id>/balance/    Account balance

    GET    /api/companies/<id>/journal-entries/bulk-import/template/  Download template
    POST   /api/companies/<id>/journal-entries/bulk-import/upload/    Upload entries

NOTE:
    The Account Ledger view (previously at accounts/<id>/ledger/) has been
    moved to the reports app as Account Transactions. This keeps all
    read-only financial reporting in one app and all write operations here.

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
        """
        List journal entries with optional filters.

        PERFORMANCE:
            The queryset carries two annotations (`total_amount`, `line_count`)
            consumed by ManualJournalListSerializer. This replaces an older
            implementation that computed these via SerializerMethodField per
            row, causing a 2×N N+1 query pattern. See the serializer docstring
            for details.

            We also drop prefetch_related('lines') from the list path: the list
            serializer no longer reads line rows directly — only the aggregated
            annotations — so prefetching lines would be wasted work and memory.
        """
        # ── Imports (local to avoid polluting the module top-level namespace) ──
        from django.db.models import Sum, Count, Q
        from nidus_erp.pagination import StandardResultsSetPagination

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

        # ── Base queryset with performance annotations ──
        # total_amount: SUM of DEBIT line amounts — reported to the client as the
        #               journal "size" (equals total credit when balanced).
        # line_count : Count of all lines (debit + credit). distinct=True guards
        #              against row multiplication when combined with the Sum JOIN.
        # Both aggregations share a single LEFT JOIN on manual_journal_line and
        # execute as one SQL query with GROUP BY manual_journal.id.
        journals = (
            ManualJournal.objects
            .filter(company=company)
            .select_related('created_by')
            .annotate(
                total_amount=Sum(
                    'lines__amount',
                    filter=Q(lines__entry_type='DEBIT'),
                ),
                line_count=Count('lines', distinct=True),
            )
        )

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
            journals = journals.filter(
                Q(entry_number__icontains=search) |
                Q(description__icontains=search) |
                Q(reference__icontains=search)
            )

        # ── Ordering ──
        # Accepts a comma-separated `ordering` query param, DRF-style:
        #     ?ordering=-created_at            → newest created first
        #     ?ordering=-status,-date          → primary by status, secondary by date
        #     ?ordering=date                   → oldest date first
        #
        # We whitelist the allowed fields to:
        #   (a) prevent ORDER BY on unindexed columns (e.g., `description`),
        #       which would trigger a full table scan on the 7k+ row dataset;
        #   (b) avoid leaking fields that aren't in the response payload;
        #   (c) keep the public API surface tight and documented.
        #
        # `total_amount` is valid because we added it as a SQL annotation at
        # the top of this method — the database can ORDER BY it natively.
        #
        # When the param is absent, we fall through to the model's Meta
        # ordering (['-date', '-created_at']) — the existing behaviour.
        ALLOWED_ORDERING = {
            'date', '-date',
            'created_at', '-created_at',
            'entry_number', '-entry_number',
            'status', '-status',
            'journal_type', '-journal_type',
            'total_amount', '-total_amount',
        }

        ordering_param = request.query_params.get('ordering')
        if ordering_param:
            # Split, strip blanks, drop empty tokens from a trailing comma
            requested_fields = [f.strip() for f in ordering_param.split(',') if f.strip()]
            invalid_fields = [f for f in requested_fields if f not in ALLOWED_ORDERING]

            if invalid_fields:
                # Return 400 rather than silently ignore — clearer for API clients
                # and surfaces typos (e.g., `?ordering=-created` instead of `-created_at`).
                return Response(
                    {
                        'success': False,
                        'message': (
                            f'Invalid ordering field(s): {invalid_fields}. '
                            f'Allowed fields: {sorted(ALLOWED_ORDERING)}'
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # *requested_fields unpacks the list into order_by() positional args
            journals = journals.order_by(*requested_fields)

        # ── Pagination ──
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(journals, request)

        if page is not None:
            serializer = ManualJournalListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        # Fallback (shouldn't happen with DRF's default paginator, but safe)
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
# ACCOUNT BALANCE (remains here — lightweight utility, not a report)
# ══════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════
# BULK IMPORT
# ══════════════════════════════════════════════════

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
                    'accepted_entries': result['accepted_entries'],
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




# ══════════════════════════════════════════════════
# JOURNAL ENTRIES EXPORT (Phase 3)
# ══════════════════════════════════════════════════

class JournalExportView(APIView):
    """
    GET /api/companies/<company_id>/journal-entries/export/

    Export all journal entries matching the filters as xlsx / csv / pdf / docx.

    QUERY PARAMS:
        export        — xlsx | csv | pdf | docx       REQUIRED
        status        — DRAFT | POSTED | VOID         optional
        journal_type  — ADJUSTMENT | SALES | ...      optional
        date_from     — YYYY-MM-DD                    optional
        date_to       — YYYY-MM-DD                    optional
        search        — free text                     optional

    WHY A DEDICATED VIEW (instead of ?export= on the list endpoint):
        - Cleaner OpenAPI schema (the list endpoint stays strictly JSON).
        - No pagination ambiguity — export always returns everything matching
          the filter, pagination only applies to the human-facing list UI.
        - Shares the same filter surface as the list endpoint, so there is
          no new vocabulary for users to learn.

    PERMISSIONS:
        Same as list: any JOURNAL_VIEW_ROLES member (OWNER, ADMIN,
        ACCOUNTANT, AUDITOR). Export is a read operation.

    RATE LIMIT:
        Not throttled at the per-endpoint level yet. If abuse emerges,
        add a scoped throttle keyed by user_id (authenticated users only —
        this endpoint is not AllowAny).
    """

    def get(self, request, company_id):
        # ── Imports local to this method to mirror existing style in this file ──
        from reports.exporters import maybe_export
        from .export import build_export_payload

        # ── Permission check (same pattern as JournalListCreateView.get) ──
        company, membership = get_company_and_membership(request, company_id)
        if not membership:
            return Response(
                {'success': False, 'message': 'You do not have access to this company.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if membership.role not in JOURNAL_VIEW_ROLES:
            return Response(
                {'success': False, 'message': 'Your role does not have permission to export journal entries.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # ── Required param: export format ──
        # We accept 'export' (matches the reports app's convention) and
        # deliberately do NOT accept 'format' — DRF reserves that name for
        # its internal content-negotiation mechanism.
        export_format = request.query_params.get('export')
        if not export_format:
            return Response(
                {
                    'success': False,
                    'message': (
                        "Missing required query parameter: 'export'. "
                        "Use ?export=xlsx | csv | pdf | docx."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Collect & normalise optional filters ──
        # We upper-case status and journal_type so users can pass 'posted'
        # or 'POSTED' interchangeably, matching the list endpoint's behaviour.
        filters = {}

        status_filter = request.query_params.get('status')
        if status_filter:
            filters['status'] = status_filter.upper()

        journal_type = request.query_params.get('journal_type')
        if journal_type:
            filters['journal_type'] = journal_type.upper()

        date_from = request.query_params.get('date_from')
        if date_from:
            filters['date_from'] = date_from

        date_to = request.query_params.get('date_to')
        if date_to:
            filters['date_to'] = date_to

        search = request.query_params.get('search')
        if search:
            filters['search'] = search

        # ── Assemble the payload ──
        # build_export_payload raises ValueError if the result set exceeds
        # MAX_EXPORT_JOURNALS. Translate that into an HTTP 400 — the user's
        # filter was too broad, it's their responsibility to narrow it.
        try:
            payload, _ = build_export_payload(company, filters=filters)
        except ValueError as exc:
            return Response(
                {'success': False, 'message': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Delegate to the existing renderer dispatch ──
        # maybe_export handles:
        #   - Format validation (xlsx/csv/pdf/docx only)
        #   - Per-report format allow-list (journal_entries supports all 4)
        #   - Filename generation (NidusERP_<company>_Journal_Entries.<ext>)
        #   - HttpResponse wrapping with correct Content-Type + Content-Disposition
        # It returns an HttpResponse on success or a DRF Response (HTTP 400)
        # on format-validation failure — either way we just return it.
        return maybe_export(
            export_format=export_format,
            report_type='journal_entries',
            report_data=payload,
            company_name=company.name,
        )