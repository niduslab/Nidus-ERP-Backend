# backend/chartofaccounts/views.py

from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from companies.models import Company, CompanyUser, RoleChoices
from .models import AccountClassification, Account, SystemAccountMapping
from .serializers import (
    AccountClassificationSerializer,
    CreateClassificationSerializer,
    AccountListSerializer,
    AccountDetailSerializer,
    CreateAccountSerializer,
    UpdateAccountSerializer,
    SystemAccountMappingSerializer,
)


# ──────────────────────────────────────────────
# ROLE GROUPS
# ──────────────────────────────────────────────
# Instead of repeating role lists in every view, we define them once.
# If the role requirements change later, we update one place.

COA_WRITE_ROLES = [RoleChoices.OWNER, RoleChoices.ADMIN, RoleChoices.ACCOUNTANT]
COA_DELETE_ROLES = [RoleChoices.OWNER, RoleChoices.ADMIN, RoleChoices.ACCOUNTANT]


# ──────────────────────────────────────────────
# HELPER FUNCTIONS
# ──────────────────────────────────────────────

def get_company_and_membership(request, company_id):
    """
    Finds the company and checks if the user is an active member.
    Returns (company, membership) tuple.
    membership is None if user has no access.
    """
    company = get_object_or_404(Company, id=company_id, is_active=True)

    try:
        membership = CompanyUser.objects.get(
            user=request.user,
            company=company,
            is_active=True,
        )
    except CompanyUser.DoesNotExist:
        return company, None

    return company, membership


def generate_next_internal_path(company, parent_path):

    prefix = parent_path + '.'

    existing_account_paths = list(
        Account.objects.filter(
            company=company,
            internal_path__startswith=prefix,
        ).values_list('internal_path', flat=True)
    )

    existing_classification_paths = list(
        AccountClassification.objects.filter(
            company=company,
            internal_path__startswith=prefix,
        ).values_list('internal_path', flat=True)
    )

    all_paths = existing_account_paths + existing_classification_paths

    direct_children = []
    for path in all_paths:
        remainder = path[len(prefix):]
        if '.' not in remainder:
            direct_children.append(remainder)

    if direct_children:
        highest = max(int(segment) for segment in direct_children)
        next_number = highest + 1
    else:
        next_number = 1

    next_segment = str(next_number).zfill(4)
    return f"{parent_path}.{next_segment}"


# ──────────────────────────────────────────────
# CLASSIFICATION VIEWS
# ──────────────────────────────────────────────

class ClassificationListCreateView(APIView):
    """
    GET  /api/companies/<id>/classifications/
        → List all classifications

    POST /api/companies/<id>/classifications/
        → Create classification 
    """

    def get(self, request, company_id):
        company, membership = get_company_and_membership(request, company_id)

        if not membership:
            return Response(
                {
                    'success': False,
                    'message': 'You do not have access to this company.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        classifications = AccountClassification.objects.filter(
            company=company,
        )

        serializer = AccountClassificationSerializer(
            classifications,
            many=True,
        )

        return Response(
            {
                'success': True,
                'count': len(serializer.data),
                'data': serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, company_id):

        company, membership = get_company_and_membership(request, company_id)

        if not membership:
            return Response(
                {
                    'success': False,
                    'message': 'You do not have access to this company.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if membership.role not in COA_WRITE_ROLES:
            return Response(
                {
                    'success': False,
                    'message': 'Only Owner, Admin, or Accountant can create classification groups.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CreateClassificationSerializer(
            data=request.data,
            context={'company': company},
        )

        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Invalid input.',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        parent_path = serializer.validated_data['parent_path']
        name = serializer.validated_data['name']
        # ── NEW: Extract cash flow category (defaults to OPERATING) ──
        cash_flow_category = serializer.validated_data.get('cash_flow_category', 'OPERATING')

        parent = AccountClassification.objects.get(
            company=company,
            internal_path=parent_path,
        )

        new_path = generate_next_internal_path(company, parent_path)

        classification = AccountClassification.objects.create(
            company=company,
            parent=parent,
            name=name,
            internal_path=new_path,
            cash_flow_category=cash_flow_category,
        )

        return Response(
            {
                'success': True,
                'message': f'Classification group "{name}" created successfully.',
                'data': AccountClassificationSerializer(classification).data,
            },
            status=status.HTTP_201_CREATED,
        )



class AccountListCreateView(APIView):
    """
    GET  /api/companies/<id>/accounts/
        → List all accounts with optional filtering

    POST /api/companies/<id>/accounts/
        → Create a new account
    """

    def get(self, request, company_id):

        company, membership = get_company_and_membership(request, company_id)

        if not membership:
            return Response(
                {
                    'success': False,
                    'message': 'You do not have access to this company.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # By default, only show active accounts.
        # If include_inactive=true, show all accounts.
        include_inactive = request.query_params.get('include_inactive')
        if include_inactive and include_inactive.lower() == 'true':
            accounts = Account.objects.filter(company=company)
        else:
            accounts = Account.objects.filter(company=company, is_active=True)

        # ── Optional filters ──

        classification_path = request.query_params.get('classification_path')
        if classification_path:
            accounts = accounts.filter(
                classification__internal_path__startswith=classification_path,
            )

        normal_balance = request.query_params.get('normal_balance')
        if normal_balance:
            accounts = accounts.filter(normal_balance=normal_balance.upper())

        system_only = request.query_params.get('system_only')
        if system_only and system_only.lower() == 'true':
            accounts = accounts.filter(is_system_account=True)

        parent_account_id = request.query_params.get('parent_account')
        if parent_account_id:
            accounts = accounts.filter(parent_account_id=parent_account_id)

        layer4_only = request.query_params.get('layer4_only')
        if layer4_only and layer4_only.lower() == 'true':
            accounts = accounts.filter(parent_account__isnull=True)

        currency = request.query_params.get('currency')
        if currency:
            accounts = accounts.filter(currency=currency.upper())

        search = request.query_params.get('search')
        if search:
            from django.db.models import Q
            accounts = accounts.filter(
                Q(name__icontains=search) | Q(code__icontains=search)
            )

        accounts = accounts.select_related(
            'classification',
            'parent_account',
        )

        serializer = AccountListSerializer(accounts, many=True)

        return Response(
            {
                'success': True,
                'count': len(serializer.data),
                'data': serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, company_id):
     
        company, membership = get_company_and_membership(request, company_id)

        if not membership:
            return Response(
                {
                    'success': False,
                    'message': 'You do not have access to this company.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if membership.role not in COA_WRITE_ROLES:
            return Response(
                {
                    'success': False,
                    'message': 'Only Owner, Admin, or Accountant can create accounts.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CreateAccountSerializer(
            data=request.data,
            context={'company': company},
        )

        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Invalid input.',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        classification = data['_classification']
        parent_account = data['_parent_account']

        if parent_account:
            parent_path = parent_account.internal_path
        else:
            parent_path = classification.internal_path

        internal_path = generate_next_internal_path(company, parent_path)

        account = Account.objects.create(
            company=company,
            classification=classification,
            parent_account=parent_account,
            name=data['name'],
            code=data['code'],
            internal_path=internal_path,
            normal_balance=data['normal_balance'],
            currency=data.get('currency', company.base_currency),
            is_system_account=False,
            is_deletable=True,
            is_active=True,
            description=data.get('description', ''),
            created_by=request.user,
        )

        return Response(
            {
                'success': True,
                'message': f'Account "{account.name}" created successfully.',
                'data': AccountDetailSerializer(account).data,
            },
            status=status.HTTP_201_CREATED,
        )



class AccountDetailView(APIView):
    """
    GET   /api/companies/<id>/accounts/<account_id>/
    PATCH /api/companies/<id>/accounts/<account_id>/
    """

    def get(self, request, company_id, account_id):
 
        company, membership = get_company_and_membership(request, company_id)

        if not membership:
            return Response(
                {
                    'success': False,
                    'message': 'You do not have access to this company.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        account = get_object_or_404(
            Account.objects.select_related(
                'classification',
                'parent_account',
                'created_by',
            ),
            id=account_id,
            company=company,
        )

        serializer = AccountDetailSerializer(account)

        return Response(
            {
                'success': True,
                'data': serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, company_id, account_id):

        company, membership = get_company_and_membership(request, company_id)

        if not membership:
            return Response(
                {
                    'success': False,
                    'message': 'You do not have access to this company.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if membership.role not in COA_WRITE_ROLES:
            return Response(
                {
                    'success': False,
                    'message': 'Only Owner, Admin, or Accountant can edit accounts.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        account = get_object_or_404(
            Account,
            id=account_id,
            company=company,
        )

        serializer = UpdateAccountSerializer(
            data=request.data,
            context={
                'company': company,
                'account': account,
            },
        )

        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Invalid input.',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated_fields = []

        if 'name' in serializer.validated_data:
            account.name = serializer.validated_data['name']
            updated_fields.append('name')

        if 'code' in serializer.validated_data:
            account.code = serializer.validated_data['code']
            updated_fields.append('code')

        if 'description' in serializer.validated_data:
            account.description = serializer.validated_data['description']
            updated_fields.append('description')

        if updated_fields:
            updated_fields.append('updated_at')
            account.save(update_fields=updated_fields)

        return Response(
            {
                'success': True,
                'message': f'Account "{account.name}" updated successfully.',
                'data': AccountDetailSerializer(account).data,
            },
            status=status.HTTP_200_OK,
        )


class AccountDeleteView(APIView):
    """
    WHY A SEPARATE URL?
    We use /delete/ instead of just DELETE on /accounts/<id>/ because
    delete is a destructive, permanent action. Having a separate URL
    makes it harder to accidentally trigger from the frontend. The
    detail endpoint (PATCH) and the delete endpoint are separated.
    """

    def delete(self, request, company_id, account_id):

        company, membership = get_company_and_membership(request, company_id)

        if not membership:
            return Response(
                {
                    'success': False,
                    'message': 'You do not have access to this company.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if membership.role not in COA_DELETE_ROLES:
            return Response(
                {
                    'success': False,
                    'message': 'Only Owner, Admin, or Accountant can delete accounts.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        account = get_object_or_404(
            Account,
            id=account_id,
            company=company,
        )

        if account.is_system_account:
            return Response(
                {
                    'success': False,
                    'message': f'"{account.name}" is a system account used by ERP modules '
                               f'and cannot be deleted.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not account.is_deletable:
            return Response(
                {
                    'success': False,
                    'message': f'"{account.name}" is a protected account and cannot be deleted.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


        has_children = Account.objects.filter(
            parent_account=account,
        ).exists()

        if has_children:
            return Response(
                {
                    'success': False,
                    'message': f'"{account.name}" has sub-accounts. '
                               f'Delete all sub-accounts first.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Rule 4: Cannot delete accounts with journal entries ──
        # TODO: Add this check in Step 4 when JournalEntryLine model exists.
        # Example:
        # has_entries = JournalEntryLine.objects.filter(account=account).exists()
        # if has_entries:
        #     return Response({...}, status=400)

        # ── All checks passed — permanently delete ──
        # account.delete() removes the row from the database entirely.
        # This is different from setting is_active=False (deactivation).
        account_name = account.name
        account.delete()

        return Response(
            {
                'success': True,
                'message': f'Account "{account_name}" has been permanently deleted.',
            },
            status=status.HTTP_200_OK,
        )



class AccountDeactivateView(APIView):
    """
    POST /api/companies/<id>/accounts/<account_id>/deactivate/
    """

    def post(self, request, company_id, account_id):
        company, membership = get_company_and_membership(request, company_id)

        if not membership:
            return Response(
                {
                    'success': False,
                    'message': 'You do not have access to this company.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if membership.role not in COA_WRITE_ROLES:
            return Response(
                {
                    'success': False,
                    'message': 'Only Owner, Admin, or Accountant can deactivate accounts.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        account = get_object_or_404(
            Account,
            id=account_id,
            company=company,
        )

        # ── Already inactive ──
        if not account.is_active:
            return Response(
                {
                    'success': False,
                    'message': f'"{account.name}" is already inactive.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Cannot deactivate if assigned as a system account ──
        # We check the SystemAccountMapping table to see if any
        # module currently depends on this account.
        # .exists() is efficient — it doesn't load the actual rows,
        # just checks if at least one exists.
        is_mapped = SystemAccountMapping.objects.filter(
            company=company,
            account=account,
        ).exists()

        if is_mapped:
            mapped_codes = list(
                SystemAccountMapping.objects.filter(
                    company=company,
                    account=account,
                ).values_list('system_code', flat=True)
            )

            codes_display = ', '.join(mapped_codes)

            return Response(
                {
                    'success': False,
                    'message': f'"{account.name}" is assigned as a system account '
                               f'({codes_display}). Reassign the system account '
                               f'mapping to a different account before deactivating.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        account.is_active = False
        account.save(update_fields=['is_active', 'updated_at'])

        return Response(
            {
                'success': True,
                'message': f'"{account.name}" has been deactivated. '
                           f'It will no longer accept new journal entries.',
                'data': AccountDetailSerializer(account).data,
            },
            status=status.HTTP_200_OK,
        )


class AccountActivateView(APIView):
    """
    POST /api/companies/<id>/accounts/<account_id>/activate/
    """

    def post(self, request, company_id, account_id):
        company, membership = get_company_and_membership(request, company_id)

        if not membership:
            return Response(
                {
                    'success': False,
                    'message': 'You do not have access to this company.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if membership.role not in COA_WRITE_ROLES:
            return Response(
                {
                    'success': False,
                    'message': 'Only Owner, Admin, or Accountant can activate accounts.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        account = get_object_or_404(
            Account,
            id=account_id,
            company=company,
        )

        if account.is_active:
            return Response(
                {
                    'success': False,
                    'message': f'"{account.name}" is already active.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        account.is_active = True
        account.save(update_fields=['is_active', 'updated_at'])

        return Response(
            {
                'success': True,
                'message': f'"{account.name}" has been reactivated.',
                'data': AccountDetailSerializer(account).data,
            },
            status=status.HTTP_200_OK,
        )



class SystemAccountMappingListView(APIView):
    """
    GET /api/companies/<id>/system-accounts/
    """

    def get(self, request, company_id):
        company, membership = get_company_and_membership(request, company_id)

        if not membership:
            return Response(
                {
                    'success': False,
                    'message': 'You do not have access to this company.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        mappings = SystemAccountMapping.objects.filter(
            company=company,
        ).select_related('account').order_by('system_code')

        serializer = SystemAccountMappingSerializer(mappings, many=True)

        return Response(
            {
                'success': True,
                'count': len(serializer.data),
                'data': serializer.data,
            },
            status=status.HTTP_200_OK,
        )



class ChartOfAccountsTreeView(APIView):
    """
    GET /api/companies/<id>/chart-of-accounts/
    """

    def get(self, request, company_id):
        company, membership = get_company_and_membership(request, company_id)

        if not membership:
            return Response(
                {
                    'success': False,
                    'message': 'You do not have access to this company.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        classifications = AccountClassification.objects.filter(
            company=company,
        ).order_by('internal_path')

        
        include_inactive = request.query_params.get('include_inactive')
        account_filter = {'company': company}
        if not (include_inactive and include_inactive.lower() == 'true'):
            account_filter['is_active'] = True

        accounts = Account.objects.filter(
            **account_filter,
        ).select_related(
            'classification',
            'parent_account',
        ).order_by('internal_path')

        # ── Build classification tree ──
        classification_dict = {}
        for c in classifications:
            classification_dict[c.internal_path] = {
                'id': str(c.id),
                'name': c.name,
                'internal_path': c.internal_path,
                'layer': c.layer,
                'cash_flow_category': c.cash_flow_category,
                'children': [],
                'accounts': [],
            }

        roots = []
        for c in classifications:
            node = classification_dict[c.internal_path]

            if c.parent_id:
                parent_path = c.internal_path.rsplit('.', 1)[0]
                parent_node = classification_dict.get(parent_path)
                if parent_node:
                    parent_node['children'].append(node)
            else:
                roots.append(node)

        # ── Build account tree ──
        account_nodes = {}
        for a in accounts:
            account_nodes[a.internal_path] = {
                'id': str(a.id),
                'name': a.name,
                'code': a.code,
                'internal_path': a.internal_path,
                'normal_balance': a.normal_balance,
                'currency': a.currency,
                'is_system_account': a.is_system_account,
                'is_deletable': a.is_deletable,
                'is_active': a.is_active,
                'is_sub_account': a.is_sub_account,
                'sub_accounts': [],
            }

        for a in accounts:
            node = account_nodes[a.internal_path]

            if a.parent_account_id:
                parent_node = account_nodes.get(a.parent_account.internal_path)
                if parent_node:
                    parent_node['sub_accounts'].append(node)
            else:
                class_node = classification_dict.get(a.classification.internal_path)
                if class_node:
                    class_node['accounts'].append(node)

        return Response(
            {
                'success': True,
                'data': roots,
            },
            status=status.HTTP_200_OK,
        )