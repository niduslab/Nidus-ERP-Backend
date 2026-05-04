# backend/companies/views.py

from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Company, CompanyUser, PendingInvitation, RoleChoices
from .serializers import (
    CompanyCreateSerializer,
    CompanyUpdateSerializer,
    CompanyListSerializer,
    CompanyDetailSerializer,
    CompanyUserSerializer,
    InviteMemberSerializer,
    PendingInvitationSerializer,
    TransferOwnershipSerializer,
)

import zoneinfo                              # For listing all IANA time zones
from .models import (
    CurrencyChoices,
    IndustryChoices,
    CompanySizeChoices,
    InventoryMethodChoices,
    DateFormatChoices,
)

User = get_user_model()

class CompanyChoicesView(APIView):
    """
    Expose every dropdown option used in company creation/settings forms.

    DESIGN:
        Returns ALL choice lists in a single response so the frontend
        can fetch once at app startup and never refetch (these values
        change only when we deploy new model code).

        Each choice is a `{ value, label }` pair so the frontend
        renderer is uniform across all dropdowns.

    PERMISSIONS:
        IsAuthenticated — these are not secret, but they're internal
        product data, so we require login. No company access check
        needed (these are GLOBAL choices, not company-scoped).

    CACHING:
        Frontend caches indefinitely via TanStack Query staleTime: Infinity.
        If you ever add a new currency or industry, deploying triggers
        a hard reload on clients which clears the cache.

    NOTE on time_zones:
        We expose the standard IANA zoneinfo database (~600 entries).
        These are stable across decades; users want to see their zone
        in the list. We don't filter to "common" zones because what's
        "common" depends on the user's region.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # ── Currencies ──
        # CurrencyChoices.choices is a list of (value, label) tuples.
        # We unpack each into the frontend-friendly { value, label } shape.
        currencies = [
            {'value': value, 'label': label}
            for value, label in CurrencyChoices.choices
        ]

        # ── Industries ──
        industries = [
            {'value': value, 'label': label}
            for value, label in IndustryChoices.choices
        ]

        # ── Company sizes ──
        company_sizes = [
            {'value': value, 'label': label}
            for value, label in CompanySizeChoices.choices
        ]

        # ── Inventory valuation methods ──
        inventory_methods = [
            {'value': value, 'label': label}
            for value, label in InventoryMethodChoices.choices
        ]

        # ── Date formats ──
        date_formats = [
            {'value': value, 'label': label}
            for value, label in DateFormatChoices.choices
        ]

        # ── Fiscal year start months ──
        # The Company model stores this as IntegerField with choices=[(1,1),(2,2)...].
        # The labels in models.py are integers — not user-friendly. We
        # expose proper month names here instead. This is fine because
        # the validation on the backend just checks 1..12 range.
        fiscal_year_months = [
            {'value': 1, 'label': 'January'},
            {'value': 2, 'label': 'February'},
            {'value': 3, 'label': 'March'},
            {'value': 4, 'label': 'April'},
            {'value': 5, 'label': 'May'},
            {'value': 6, 'label': 'June'},
            {'value': 7, 'label': 'July'},
            {'value': 8, 'label': 'August'},
            {'value': 9, 'label': 'September'},
            {'value': 10, 'label': 'October'},
            {'value': 11, 'label': 'November'},
            {'value': 12, 'label': 'December'},
        ]

        # ── Time zones ──
        # zoneinfo.available_timezones() returns a set of IANA zone names.
        # We sort alphabetically for stable, predictable order. The result
        # is ~600 entries on most systems — frontend can use a searchable
        # combobox to make selection ergonomic.
        time_zones = [
            {'value': tz, 'label': tz}
            for tz in sorted(zoneinfo.available_timezones())
        ]

        # ── Reporting methods ──
        # Hardcoded in the model (not a TextChoices class), so we mirror
        # them here. Order matches the model's choices list.
        reporting_methods = [
            {'value': 'ACCRUAL', 'label': 'Accrual'},
            {'value': 'CASH',    'label': 'Cash'},
            {'value': 'BOTH',    'label': 'Both'},
        ]

        return Response(
            {
                'success': True,
                'data': {
                    'currencies':         currencies,
                    'industries':         industries,
                    'company_sizes':      company_sizes,
                    'inventory_methods':  inventory_methods,
                    'date_formats':       date_formats,
                    'fiscal_year_months': fiscal_year_months,
                    'time_zones':         time_zones,
                    'reporting_methods':  reporting_methods,
                },
            },
            status=status.HTTP_200_OK,
        )

def get_user_membership(user, company):
    """
    Returns the active CompanyUser membership for a user in a company.
    Uses select_related to avoid extra queries when accessing user/company fields.
    Returns None if no active membership exists.
    """
    try:
        return CompanyUser.objects.select_related('user').get(
            user=user,
            company=company,
            is_active=True,
        )
    except CompanyUser.DoesNotExist:
        return None



class CompanyListCreateView(APIView):
    # ─────────────────────────────────────────────────────────────
    # parser_classes tells DRF which content types this view accepts.
    #
    # Without this, DRF defaults to JSONParser only, meaning file
    # uploads via multipart/form-data are silently ignored — the
    # coa_file field would always be None even when a file is sent.
    #
    # MultiPartParser: handles multipart/form-data (file uploads)
    # FormParser:      handles application/x-www-form-urlencoded
    # JSONParser:      handles application/json (existing behaviour)
    #
    # The POST method needs MultiPartParser for custom CoA uploads.
    # The GET method doesn't care about parsers (no request body),
    # so adding these has zero impact on the list endpoint.
    # ─────────────────────────────────────────────────────────────
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        """
        List all companies the logged-in user is a member of.
        
        N+1 FIX: Instead of using SerializerMethodField (which queries per company),
        we fetch all memberships in ONE query and inject the role into each company
        object before serialization. This means 1 query instead of N+1.
        """
        memberships = CompanyUser.objects.filter(
            user=request.user,
            is_active=True,
        ).select_related('company')

        # Build a list of companies with their roles attached
        companies = []
        for m in memberships:
            if m.company.is_active:
                # Temporarily attach the role to the company object
                # This avoids a separate query per company in the serializer
                m.company.my_role = m.role
                companies.append(m.company)

        serializer = CompanyListSerializer(
            companies,
            many=True,
            context={'request': request},
        )

        return Response(
            {
                'success': True,
                'count': len(companies),
                'data': serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = CompanyCreateSerializer(
            data=request.data,
            context={'request': request},
        )

        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Company creation failed. Please check your input.',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        company = serializer.save()

        detail_serializer = CompanyDetailSerializer(
            company,
            context={'request': request},
        )

        return Response(
            {
                'success': True,
                'message': f'Company "{company.name}" created successfully! You are the owner.',
                'data': detail_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class CompanyDetailView(APIView):
    def get(self, request, company_id):
        company = get_object_or_404(
            Company.objects.select_related('owner'),     # Join owner in one query
            id=company_id,
            is_active=True,
        )

        membership = get_user_membership(request.user, company)
        if not membership:
            return Response(
                {
                    'success': False,
                    'message': 'You do not have access to this company.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CompanyDetailSerializer(
            company,
            context={'request': request},
        )

        return Response(
            {
                'success': True,
                'data': serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def put(self, request, company_id):
        company = get_object_or_404(Company, id=company_id, is_active=True)

        membership = get_user_membership(request.user, company)
        if not membership or membership.role not in [RoleChoices.OWNER, RoleChoices.ADMIN]:
            return Response(
                {
                    'success': False,
                    'message': 'Only the Owner or Admin can update company settings.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CompanyUpdateSerializer(
            company,
            data=request.data,
            context={'request': request},
        )

        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Update failed. Please check your input.',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()

        detail_serializer = CompanyDetailSerializer(
            company,
            context={'request': request},
        )

        return Response(
            {
                'success': True,
                'message': 'Company settings updated successfully.',
                'data': detail_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, company_id):
        company = get_object_or_404(Company, id=company_id, is_active=True)

        membership = get_user_membership(request.user, company)
        if not membership or membership.role not in [RoleChoices.OWNER, RoleChoices.ADMIN]:
            return Response(
                {
                    'success': False,
                    'message': 'Only the Owner or Admin can update company settings.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CompanyUpdateSerializer(
            company,
            data=request.data,
            partial=True,
            context={'request': request},
        )

        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Update failed. Please check your input.',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()

        detail_serializer = CompanyDetailSerializer(
            company,
            context={'request': request},
        )

        return Response(
            {
                'success': True,
                'message': 'Company settings updated successfully.',
                'data': detail_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, company_id):
        """
        Soft-delete a company. OWNER only.
        Sets is_active=False — preserves all data but hides the company.
        """
        company = get_object_or_404(Company, id=company_id, is_active=True)

        membership = get_user_membership(request.user, company)
        if not membership or membership.role != RoleChoices.OWNER:
            return Response(
                {
                    'success': False,
                    'message': 'Only the Owner can delete a company.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Soft delete — deactivate company and all memberships
        with transaction.atomic():
            company.is_active = False
            company.save(update_fields=['is_active', 'updated_at'])

            # Deactivate all memberships for this company
            CompanyUser.objects.filter(company=company, is_active=True).update(is_active=False)

            # Cancel all pending invitations
            PendingInvitation.objects.filter(company=company, is_accepted=False).update(is_accepted=True)

        

        return Response(
            {
                'success': True,
                'message': f'Company "{company.name}" has been deleted.',
            },
            status=status.HTTP_200_OK,
        )


class TransferOwnershipView(APIView):
    def post(self, request, company_id):
        company = get_object_or_404(Company, id=company_id, is_active=True)

        # Only current OWNER can transfer
        membership = get_user_membership(request.user, company)
        if not membership or membership.role != RoleChoices.OWNER:
            return Response(
                {
                    'success': False,
                    'message': 'Only the current Owner can transfer ownership.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = TransferOwnershipSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Invalid input.',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify current owner's password
        password = serializer.validated_data['password']
        if not request.user.check_password(password):
            return Response(
                {
                    'success': False,
                    'message': 'Incorrect password. Ownership transfer denied.',
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Find the new owner
        new_owner_email = serializer.validated_data['new_owner_email']
        new_role_for_self = serializer.validated_data['new_role_for_self']

        try:
            new_owner_user = User.objects.get(email=new_owner_email)
        except User.DoesNotExist:
            return Response(
                {
                    'success': False,
                    'message': f'No user found with email "{new_owner_email}".',
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # New owner must be an active member of this company
        new_owner_membership = get_user_membership(new_owner_user, company)
        if not new_owner_membership:
            return Response(
                {
                    'success': False,
                    'message': f'{new_owner_user.full_name} is not an active member of this company.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cannot transfer to yourself
        if new_owner_user == request.user:
            return Response(
                {
                    'success': False,
                    'message': 'You are already the owner.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Execute the transfer atomically
        with transaction.atomic():
            # 1. Make the new person OWNER
            new_owner_membership.role = RoleChoices.OWNER
            new_owner_membership.save(update_fields=['role', 'updated_at'])

            # 2. Update the Company.owner field
            company.owner = new_owner_user
            company.save(update_fields=['owner', 'updated_at'])

            # 3. Handle the old owner's role
            if new_role_for_self == 'LEAVE':
                # Soft-delete the old owner's membership
                membership.is_active = False
                membership.save(update_fields=['is_active', 'updated_at'])
                old_owner_status = 'You have left the company.'
            else:
                # Change old owner to their chosen role
                membership.role = new_role_for_self
                membership.save(update_fields=['role', 'updated_at'])
                old_owner_status = f'Your role is now {new_role_for_self}.'

        # Send email notification to the new owner (outside transaction)
        from nidus_erp.email_service import send_ownership_received_email
        send_ownership_received_email(
            user=new_owner_user,
            company_name=company.name,
            previous_owner_name=request.user.full_name,
        )

        # Send confirmation email to the previous owner
        from nidus_erp.email_service import send_ownership_transferred_email
        send_ownership_transferred_email(
            user=request.user,
            company_name=company.name,
            new_owner_name=new_owner_user.full_name,
            new_role_for_self=new_role_for_self,
        )

        return Response(
            {
                'success': True,
                'message': f'Ownership transferred to {new_owner_user.full_name}. {old_owner_status}',
            },
            status=status.HTTP_200_OK,
        )



class CompanyMemberListView(APIView):

    def get(self, request, company_id):
        """List all active members and pending invitations."""
        company = get_object_or_404(Company, id=company_id, is_active=True)

        membership = get_user_membership(request.user, company)
        if not membership:
            return Response(
                {
                    'success': False,
                    'message': 'You do not have access to this company.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        
        members = CompanyUser.objects.filter(
            company=company,
            is_active=True,
        ).select_related('user', 'invited_by')

        # Fetch pending invitations (only visible to OWNER/ADMIN)
        pending = []
        if membership.role in [RoleChoices.OWNER, RoleChoices.ADMIN]:
            pending_qs = PendingInvitation.objects.filter(
                company=company,
                is_accepted=False,
            ).select_related('invited_by')
            pending = PendingInvitationSerializer(pending_qs, many=True).data

        serializer = CompanyUserSerializer(members, many=True)

        return Response(
            {
                'success': True,
                'count': len(serializer.data),     # ← Uses already-loaded data, no extra query
                'data': serializer.data,
                'pending_invitations': pending,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, company_id):
        company = get_object_or_404(Company, id=company_id, is_active=True)

        membership = get_user_membership(request.user, company)
        if not membership or membership.role not in [RoleChoices.OWNER, RoleChoices.ADMIN]:
            return Response(
                {
                    'success': False,
                    'message': 'Only the Owner or Admin can invite members.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = InviteMemberSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Invalid input.',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data['email']
        role = serializer.validated_data['role']

        # Try to find the user
        try:
            invite_user = User.objects.get(email=email)
        except User.DoesNotExist:
            invite_user = None

        if invite_user:
            # ── User EXISTS → Add them directly ──

            existing = CompanyUser.objects.filter(
                user=invite_user,
                company=company,
            ).first()

            if existing:
                if existing.is_active:
                    return Response(
                        {
                            'success': False,
                            'message': f'{invite_user.full_name} is already a member of this company.',
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                else:
                    # Reactivate previously removed member
                    existing.role = role
                    existing.is_active = True
                    existing.invited_by = request.user
                    existing.save(update_fields=['role', 'is_active', 'invited_by', 'updated_at'])

                    from nidus_erp.email_service import send_member_added_email
                    send_member_added_email(
                        user=invite_user,
                        company_name=company.name,
                        role=role,
                        invited_by_name=request.user.full_name,
                    )

                    return Response(
                        {
                            'success': True,
                            'message': f'{invite_user.full_name} has been re-added as {role}.',
                            'data': CompanyUserSerializer(existing).data,
                        },
                        status=status.HTTP_200_OK,
                    )

            new_member = CompanyUser.objects.create(
                user=invite_user,
                company=company,
                role=role,
                invited_by=request.user,
            )

            # Send email notification
            from nidus_erp.email_service import send_member_added_email
            send_member_added_email(
                user=invite_user,
                company_name=company.name,
                role=role,
                invited_by_name=request.user.full_name,
            )

            return Response(
                {
                    'success': True,
                    'message': f'{invite_user.full_name} has been added as {role}.',
                    'data': CompanyUserSerializer(new_member).data,
                },
                status=status.HTTP_201_CREATED,
            )

        else:
            # ── User DOES NOT EXIST → Create PendingInvitation ──

            existing_invite = PendingInvitation.objects.filter(
                email=email,
                company=company,
                is_accepted=False,
            ).first()

            if existing_invite:
                # Update existing pending invitation with new role
                existing_invite.role = role
                existing_invite.invited_by = request.user
                existing_invite.save(update_fields=['role', 'invited_by'])

                # Re-send invitation email with updated role
                from nidus_erp.email_service import send_pending_invitation_email
                send_pending_invitation_email(
                    email=email,
                    company_name=company.name,
                    role=role,
                    invited_by_name=request.user.full_name,
                )

                return Response(
                    {
                        'success': True,
                        'message': f'Pending invitation for {email} updated to {role}.',
                        'data': PendingInvitationSerializer(existing_invite).data,
                    },
                    status=status.HTTP_200_OK,
                )

            pending = PendingInvitation.objects.create(
                email=email,
                company=company,
                role=role,
                invited_by=request.user,
            )

            # Send invitation email
            from nidus_erp.email_service import send_pending_invitation_email
            send_pending_invitation_email(
                email=email,
                company_name=company.name,
                role=role,
                invited_by_name=request.user.full_name,
            )

            return Response(
                {
                    'success': True,
                    'message': f'{email} does not have an account yet. A pending invitation has been created. They will be automatically added when they register.',
                    'data': PendingInvitationSerializer(pending).data,
                },
                status=status.HTTP_201_CREATED,
            )


class CompanyMemberDetailView(APIView):
    def patch(self, request, company_id, member_id):
        """Update a member's role. OWNER or ADMIN only."""
        company = get_object_or_404(Company, id=company_id, is_active=True)

        requester_membership = get_user_membership(request.user, company)
        if not requester_membership or requester_membership.role not in [RoleChoices.OWNER, RoleChoices.ADMIN]:
            return Response(
                {
                    'success': False,
                    'message': 'Only the Owner or Admin can update member roles.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        target_member = get_object_or_404(CompanyUser, id=member_id, company=company, is_active=True)

        # Protect the owner
        if target_member.role == RoleChoices.OWNER:
            return Response(
                {
                    'success': False,
                    'message': 'The Owner\'s role cannot be changed. Use the transfer ownership endpoint instead.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_role = request.data.get('role')
        if not new_role:
            return Response(
                {
                    'success': False,
                    'message': 'Please provide a new role.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate role choice
        valid_roles = [choice[0] for choice in RoleChoices.choices if choice[0] != RoleChoices.OWNER]
        if new_role not in valid_roles:
            return Response(
                {
                    'success': False,
                    'message': f'Invalid role. Choose from: {", ".join(valid_roles)}',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ADMIN cannot change another ADMIN's role (only OWNER can)
        if target_member.role == RoleChoices.ADMIN and requester_membership.role != RoleChoices.OWNER:
            return Response(
                {
                    'success': False,
                    'message': 'Only the Owner can change an Admin\'s role.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        old_role = target_member.role              # Save old role before overwriting
        target_member.role = new_role
        target_member.save(update_fields=['role', 'updated_at'])

        # Send email notification about role change
        from nidus_erp.email_service import send_role_changed_email
        send_role_changed_email(
            user=target_member.user,
            company_name=company.name,
            old_role=old_role,
            new_role=new_role,
        )

        return Response(
            {
                'success': True,
                'message': f'{target_member.user.full_name}\'s role updated to {new_role}.',
                'data': CompanyUserSerializer(target_member).data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, company_id, member_id):
        """Remove a member from the company (soft delete). OWNER or ADMIN only."""
        company = get_object_or_404(Company, id=company_id, is_active=True)

        requester_membership = get_user_membership(request.user, company)
        if not requester_membership or requester_membership.role not in [RoleChoices.OWNER, RoleChoices.ADMIN]:
            return Response(
                {
                    'success': False,
                    'message': 'Only the Owner or Admin can remove members.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        target_member = get_object_or_404(CompanyUser, id=member_id, company=company, is_active=True)

        if target_member.role == RoleChoices.OWNER:
            return Response(
                {
                    'success': False,
                    'message': 'The Owner cannot be removed. Transfer ownership first.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if target_member.role == RoleChoices.ADMIN and requester_membership.role != RoleChoices.OWNER:
            return Response(
                {
                    'success': False,
                    'message': 'Only the Owner can remove an Admin.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        target_member.is_active = False
        target_member.save(update_fields=['is_active', 'updated_at'])

        # Send email notification about removal
        from nidus_erp.email_service import send_member_removed_email
        send_member_removed_email(
            user=target_member.user,
            company_name=company.name,
        )

        return Response(
            {
                'success': True,
                'message': f'{target_member.user.full_name} has been removed from {company.name}.',
            },
            status=status.HTTP_200_OK,
        )