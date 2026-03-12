# backend/companies/serializers.py

from rest_framework import serializers
from django.db import transaction
from django.contrib.auth import get_user_model
from .models import Company, CompanyUser, PendingInvitation, RoleChoices, TaxProfile,TaxProfileLayer,DocumentSequence,CurrencyExchangeRate,TaxCalculationTypeChoices
 
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
    

class TaxProfileLayerSerializer(serializers.ModelSerializer):
    """Display a single tax layer within a profile."""
    default_tax_account_name = serializers.CharField(
        source='default_tax_account.name',
        read_only=True,
    )
    default_tax_account_code = serializers.CharField(
        source='default_tax_account.code',
        read_only=True,
    )

    class Meta:
        model = TaxProfileLayer
        fields = [
            'id',
            'name',
            'rate',
            'calculation_type',
            'apply_order',
            'default_tax_account',
            'default_tax_account_name',
            'default_tax_account_code',
        ]
        read_only_fields = ['id']


class TaxProfileListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing tax profiles."""
    layer_count = serializers.SerializerMethodField()

    class Meta:
        model = TaxProfile
        fields = [
            'id',
            'name',
            'combined_rate',
            'is_active',
            'layer_count',
        ]

    def get_layer_count(self, obj):
        return obj.layers.count()


class TaxProfileDetailSerializer(serializers.ModelSerializer):
    """Full tax profile with nested layers."""
    layers = TaxProfileLayerSerializer(many=True, read_only=True)

    class Meta:
        model = TaxProfile
        fields = [
            'id',
            'name',
            'combined_rate',
            'is_active',
            'layers',
            'created_at',
            'updated_at',
        ]


class CreateTaxProfileLayerSerializer(serializers.Serializer):
    """Input serializer for a single layer during profile creation."""
    name = serializers.CharField(max_length=100)
    rate = serializers.DecimalField(max_digits=7, decimal_places=4)
    calculation_type = serializers.ChoiceField(
        choices=TaxCalculationTypeChoices.choices,
        default=TaxCalculationTypeChoices.INDEPENDENT,
    )
    apply_order = serializers.IntegerField(min_value=1)
    default_tax_account_id = serializers.UUIDField()


class CreateTaxProfileSerializer(serializers.Serializer):
    """
    Create a tax profile with nested layers in one request.

    Example payload:
    {
        "name": "SD 5% + VAT 15%",
        "layers": [
            {
                "name": "Supplementary Duty",
                "rate": "5.0000",
                "calculation_type": "INDEPENDENT",
                "apply_order": 1,
                "default_tax_account_id": "<uuid>"
            },
            {
                "name": "VAT",
                "rate": "15.0000",
                "calculation_type": "COMPOUND",
                "apply_order": 2,
                "default_tax_account_id": "<uuid>"
            }
        ]
    }

    The combined_rate is auto-calculated from the layers using the
    same tax calculation engine that journal posting uses.
    """
    name = serializers.CharField(max_length=100)
    layers = CreateTaxProfileLayerSerializer(many=True)

    def validate_name(self, value):
        company = self.context['company']
        if TaxProfile.objects.filter(company=company, name=value).exists():
            raise serializers.ValidationError(
                f'A tax profile named "{value}" already exists in this company.'
            )
        return value

    def validate_layers(self, value):
        if len(value) < 1:
            raise serializers.ValidationError(
                'A tax profile must have at least one layer.'
            )

        # Check apply_order uniqueness
        orders = [layer['apply_order'] for layer in value]
        if len(orders) != len(set(orders)):
            raise serializers.ValidationError(
                'Each layer must have a unique apply_order.'
            )

        # Validate all tax account IDs exist and belong to this company
        from chartofaccounts.models import Account
        company = self.context['company']

        for i, layer in enumerate(value, start=1):
            try:
                account = Account.objects.get(
                    id=layer['default_tax_account_id'],
                    company=company,
                )
                if not account.is_active:
                    raise serializers.ValidationError(
                        f'Layer {i}: Tax account "{account.name}" is inactive.'
                    )
                # Store the resolved account for use in create()
                layer['_account'] = account
            except Account.DoesNotExist:
                raise serializers.ValidationError(
                    f'Layer {i}: Tax account not found in this company.'
                )

        return value


# ══════════════════════════════════════════════════
# DOCUMENT SEQUENCE SERIALIZERS
# ══════════════════════════════════════════════════

class DocumentSequenceSerializer(serializers.ModelSerializer):
    """Display and update document sequences."""
    current_format = serializers.SerializerMethodField()

    class Meta:
        model = DocumentSequence
        fields = [
            'id',
            'module',
            'prefix',
            'next_number',
            'padding',
            'current_format',
        ]
        read_only_fields = ['id', 'module', 'next_number', 'current_format']

    def get_current_format(self, obj):
        """Show what the next number will look like."""
        return f"{obj.prefix}{str(obj.next_number).zfill(obj.padding)}"


class UpdateDocumentSequenceSerializer(serializers.Serializer):
    """Update prefix and/or padding of a document sequence."""
    prefix = serializers.CharField(max_length=10, required=False)
    padding = serializers.IntegerField(min_value=1, max_value=10, required=False)


# ══════════════════════════════════════════════════
# CURRENCY EXCHANGE RATE SERIALIZERS
# ══════════════════════════════════════════════════

class CurrencyExchangeRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CurrencyExchangeRate
        fields = [
            'id',
            'currency_code',
            'rate_to_base',
            'effective_date',
            'source',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class CreateCurrencyExchangeRateSerializer(serializers.Serializer):
    """
    Create or update an exchange rate.

    If a rate already exists for this company + currency + date,
    it gets updated. Otherwise, a new record is created.
    """
    currency_code = serializers.CharField(max_length=3)
    rate_to_base = serializers.DecimalField(max_digits=18, decimal_places=6)
    effective_date = serializers.DateField()
    source = serializers.CharField(max_length=30, default='MANUAL')

    def validate_currency_code(self, value):
        value = value.upper().strip()
        if len(value) != 3:
            raise serializers.ValidationError(
                'Currency code must be exactly 3 characters (ISO 4217).'
            )
        company = self.context['company']
        if value == company.base_currency:
            raise serializers.ValidationError(
                f'Cannot set exchange rate for the base currency ({value}). '
                f'The base currency always has a rate of 1.0.'
            )
        return value

    def validate_rate_to_base(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                'Exchange rate must be greater than zero.'
            )
        return value


# ══════════════════════════════════════════════════
# LOCK DATE SERIALIZER
# ══════════════════════════════════════════════════

class LockDateSerializer(serializers.Serializer):
    """Set or clear the company lock date."""
    lock_date = serializers.DateField(
        required=False,
        allow_null=True,
        help_text='Set to a date to freeze transactions before it. '
                  'Set to null to remove the lock.',
    )