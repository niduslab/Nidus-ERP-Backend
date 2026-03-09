# backend/companies/serializers.py

from rest_framework import serializers
from django.db import transaction
from django.contrib.auth import get_user_model
from .models import Company, CompanyUser, PendingInvitation, RoleChoices

User = get_user_model()


class CompanyCreateSerializer(serializers.ModelSerializer):
    # ─────────────────────────────────────────────────────────────
    # CUSTOM FIELDS (not on the Company model)
    #
    # These must be declared as CLASS-LEVEL ATTRIBUTES on the serializer,
    # NOT inside Meta.fields. Meta.fields only takes string references.
    #
    # write_only=True means: accept these in input, but do NOT include
    # them in the serialized output (they're not real model fields).
    # ─────────────────────────────────────────────────────────────
    coa_type = serializers.ChoiceField(
        choices=['DEFAULT', 'CUSTOM'],
        default='DEFAULT',
        write_only=True,
        help_text='Choose "DEFAULT" for the pre-built CoA, or "CUSTOM" to upload your own.',
    )

    coa_file = serializers.FileField(
        required=False,
        allow_null=True,
        write_only=True,
        help_text='Excel file (.xlsx) with your custom CoA. Required when coa_type is "CUSTOM".',
    )

    class Meta:
        model = Company
        fields = [
            'id',
            'name',
            'trade_name',
            'industry',
            'tax_id',
            'base_currency',
            'company_size',
            'fiscal_year_start_month',
            'inventory_valuation_method',
            'date_format',
            'coa_type',
            'coa_file',
            'is_vds_withholding_entity',
            'address',
            'city',
            'postal_code',
            'country',
            'phone',
            'website',
            'time_zone',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate(self, data):
        coa_type = data.get('coa_type', 'DEFAULT')
        coa_file = data.get('coa_file')

        if coa_type == 'CUSTOM':
            if not coa_file:
                raise serializers.ValidationError({
                    'coa_file': 'An Excel file is required when using a custom CoA. '
                                'Download the template from '
                                'GET /api/companies/custom-coa-template/download/'
                })

            if not coa_file.name.lower().endswith('.xlsx'):
                raise serializers.ValidationError({
                    'coa_file': 'Only .xlsx files are accepted. '
                                'Please use the provided template.'
                })

            if coa_file.size > 5 * 1024 * 1024:
                raise serializers.ValidationError({
                    'coa_file': f'File is too large ({coa_file.size / 1024 / 1024:.1f} MB). '
                                f'Maximum size is 5 MB.'
                })

            # ── IMPORT PATH: chartofaccounts.custom_coa_validator ──
            # Previously: from accounts.coa_validator import validate_coa_file
            # Changed because:
            #   1. App renamed: accounts → chartofaccounts
            #   2. File renamed: coa_validator.py → custom_coa_validator.py
            from chartofaccounts.custom_coa_validator import validate_coa_file
            validation_result = validate_coa_file(coa_file)

            if not validation_result['valid']:
                raise serializers.ValidationError({
                    'coa_file': {
                        'message': f'The uploaded CoA file has '
                                   f'{validation_result["error_count"]} error(s). '
                                   f'Please fix them and try again.',
                        'errors': validation_result['errors'],
                    }
                })

            data['_coa_validated_data'] = validation_result

        return data

    def create(self, validated_data):
        user = self.context['request'].user

        # Pop non-model fields BEFORE passing to Company.objects.create().
        # These are serializer-only fields that don't exist on the Company model.
        # If we don't pop them, Django will raise:
        #   TypeError: Company() got an unexpected keyword argument 'coa_type'
        coa_type = validated_data.pop('coa_type', 'DEFAULT')
        validated_data.pop('coa_file', None)
        coa_validated_data = validated_data.pop('_coa_validated_data', None)

        # ── IMPORT PATH: chartofaccounts.services ──
        # Previously: from accounts.services import ...
        from chartofaccounts.services import generate_default_coa, generate_custom_coa

        with transaction.atomic():
            company = Company.objects.create(
                owner=user,
                **validated_data,
            )

            CompanyUser.objects.create(
                user=user,
                company=company,
                role=RoleChoices.OWNER,
                invited_by=None,
            )

            if coa_type == 'CUSTOM' and coa_validated_data:
                generate_custom_coa(
                    company=company,
                    created_by=user,
                    validated_data=coa_validated_data,
                )
            else:
                generate_default_coa(
                    company=company,
                    created_by=user,
                )

        return company


class CompanyUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            'id',
            'name',
            'trade_name',
            'industry',
            'tax_id',
            'base_currency',
            'company_size',
            'fiscal_year_start_month',
            'inventory_valuation_method',
            'date_format',
            'is_vds_withholding_entity',
            'address',
            'city',
            'postal_code',
            'country',
            'phone',
            'website',
            'time_zone',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'is_vds_withholding_entity',
            'created_at',
            'updated_at',
        ]

    def validate_base_currency(self, value):
        if self.instance and self.instance.base_currency != value:
            if self.instance.has_financial_records():
                raise serializers.ValidationError(
                    'Base currency cannot be changed after financial transactions have been recorded.'
                )
        return value


class CompanyListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing companies.
    The my_role field is injected from the view (not queried per-item)
    to avoid the N+1 query problem.
    """
    my_role = serializers.CharField(read_only=True, default=None)

    class Meta:
        model = Company
        fields = [
            'id',
            'name',
            'trade_name',
            'industry',
            'base_currency',
            'subscription_plan',
            'is_active',
            'my_role',
            'created_at',
        ]


class CompanyDetailSerializer(serializers.ModelSerializer):
    """Full company details for the detail/retrieve view."""
    owner_name = serializers.CharField(source='owner.full_name', read_only=True)
    owner_email = serializers.CharField(source='owner.email', read_only=True)
    my_role = serializers.SerializerMethodField()
    can_change_currency = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            'id',
            'owner',
            'owner_name',
            'owner_email',
            'name',
            'trade_name',
            'industry',
            'tax_id',
            'base_currency',
            'can_change_currency',
            'company_size',
            'fiscal_year_start_month',
            'inventory_valuation_method',
            'date_format',
            'is_vds_withholding_entity',
            'address',
            'city',
            'postal_code',
            'country',
            'phone',
            'website',
            'time_zone',
            'subscription_plan',
            'is_active',
            'my_role',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_my_role(self, obj):
        """Single object — one extra query is acceptable here."""
        request = self.context.get('request')
        if not request or not request.user:
            return None
        try:
            membership = CompanyUser.objects.get(
                user=request.user,
                company=obj,
                is_active=True,
            )
            return membership.role
        except CompanyUser.DoesNotExist:
            return None

    def get_can_change_currency(self, obj):
        return not obj.has_financial_records()


class CompanyUserSerializer(serializers.ModelSerializer):
    """Displays a member's details within a company."""
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_full_name = serializers.CharField(source='user.full_name', read_only=True)
    invited_by_name = serializers.CharField(source='invited_by.full_name', read_only=True, default=None)

    class Meta:
        model = CompanyUser
        fields = [
            'id',
            'user',
            'user_email',
            'user_full_name',
            'role',
            'is_active',
            'invited_by',
            'invited_by_name',
            'created_at',
        ]
        read_only_fields = ['id', 'user', 'user_email', 'user_full_name', 'invited_by', 'invited_by_name', 'created_at']


class InviteMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=RoleChoices.choices)

    def validate_role(self, value):
        if value == RoleChoices.OWNER:
            raise serializers.ValidationError(
                'Cannot invite someone as Owner. Use the ownership transfer endpoint instead.'
            )
        return value

    def validate_email(self, value):
        return value.lower().strip()


class PendingInvitationSerializer(serializers.ModelSerializer):
    invited_by_name = serializers.CharField(source='invited_by.full_name', read_only=True, default=None)
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = PendingInvitation
        fields = [
            'id',
            'email',
            'company',
            'company_name',
            'role',
            'is_accepted',
            'invited_by',
            'invited_by_name',
            'created_at',
        ]
        read_only_fields = fields


class TransferOwnershipSerializer(serializers.Serializer):
    """
    Handles ownership transfer.
    Requires current owner's password for security verification.
    """
    new_owner_email = serializers.EmailField(
        help_text='Email of the member who will become the new owner.',
    )
    password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text='Your current password for verification.',
    )
    new_role_for_self = serializers.ChoiceField(
        choices=[
            ('ADMIN', 'Admin'),
            ('ACCOUNTANT', 'Accountant'),
            ('AUDITOR', 'Auditor'),
            ('SALES', 'Sales'),
            ('INVENTORY', 'Inventory'),
            ('LEAVE', 'Leave the company'),
        ],
        help_text='Your new role after transferring ownership, or LEAVE to exit.',
    )

    def validate_new_owner_email(self, value):
        return value.lower().strip()