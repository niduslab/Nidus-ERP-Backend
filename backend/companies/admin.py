# backend/companies/admin.py

from django.contrib import admin
from .models import Company, CompanyUser, PendingInvitation, RoleChoices
from .models import TaxProfile, TaxProfileLayer, DocumentSequence, CurrencyExchangeRate



class CompanyUserInline(admin.TabularInline):
    model = CompanyUser
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('user', 'role', 'is_active', 'invited_by', 'created_at')


class PendingInvitationInline(admin.TabularInline):
    model = PendingInvitation
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('email', 'role', 'is_accepted', 'invited_by', 'created_at')


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'owner', 'industry', 'base_currency',
        'subscription_plan', 'is_active', 'created_at',
    )
    list_filter = (
        'industry', 'base_currency', 'subscription_plan',
        'is_active', 'country',
    )
    search_fields = ('name', 'trade_name', 'tax_id', 'owner__email')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'created_at', 'updated_at')

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'owner', 'name', 'trade_name', 'industry', 'tax_id'),
        }),
        ('Financial Settings', {
            'fields': (
                'base_currency', 'fiscal_year_start_month',
                'inventory_valuation_method', 'reporting_method',
                'lock_date', 'date_format', 'is_vds_withholding_entity',
            ),
        }),
        ('Contact & Address', {
            'fields': ('address', 'city', 'postal_code', 'country', 'phone', 'website'),
        }),
        ('System Settings', {
            'fields': ('company_size', 'time_zone', 'subscription_plan'),
        }),
        ('Status & Timestamps', {
            'fields': ('is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    inlines = [CompanyUserInline, PendingInvitationInline]

    def save_model(self, request, obj, form, change):
        """
        When creating a new company from admin, auto-generate:
        1. OWNER membership for the company owner
        2. Default Chart of Accounts (104 accounts)
        3. DocumentSequence for journal numbering

        This replicates what CompanyCreateSerializer.create() does via the API.
        On update (change=True), just save normally.
        """
        super().save_model(request, obj, form, change)

        if not change:
            # 1. Create OWNER membership
            if not CompanyUser.objects.filter(user=obj.owner, company=obj).exists():
                CompanyUser.objects.create(
                    user=obj.owner,
                    company=obj,
                    role=RoleChoices.OWNER,
                    invited_by=None,
                )

            # 2. Generate default CoA
            from chartofaccounts.services import generate_default_coa
            try:
                generate_default_coa(company=obj, created_by=obj.owner)
            except Exception as e:
                self.message_user(
                    request,
                    f'Company created but CoA generation failed: {e}',
                    level='error',
                )


@admin.register(CompanyUser)
class CompanyUserAdmin(admin.ModelAdmin):

    list_display = (
        'user',
        'company',
        'role',
        'is_active',
        'invited_by',
        'created_at',
    )

    list_filter = (
        'company',
        'role',
        'is_active',
    )

    search_fields = ('user__email', 'user__full_name', 'company__name')

    ordering = ('-created_at',)

    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(PendingInvitation)
class PendingInvitationAdmin(admin.ModelAdmin):

    list_display = (
        'email',
        'company',
        'role',
        'is_accepted',
        'invited_by',
        'created_at',
    )

    list_filter = (
        'is_accepted',
        'role',
    )

    search_fields = ('email', 'company__name')

    ordering = ('-created_at',)

    readonly_fields = ('id', 'created_at')


class TaxProfileLayerInline(admin.TabularInline):
    model = TaxProfileLayer
    extra = 0
    fields = ('name', 'rate', 'calculation_type', 'apply_order', 'default_tax_account')
    class Media:
        js = ('admin/js/company_scoped_filter.js',)


@admin.register(TaxProfile)
class TaxProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'combined_rate', 'is_active')
    list_filter = ('company', 'is_active')
    search_fields = ('name',)
    inlines = [TaxProfileLayerInline]
    class Media:
        js = ('admin/js/company_scoped_filter.js',)

@admin.register(DocumentSequence)
class DocumentSequenceAdmin(admin.ModelAdmin):
    list_display = ('company', 'module', 'prefix', 'next_number', 'padding')
    list_filter = ('module', 'company')


@admin.register(CurrencyExchangeRate)
class CurrencyExchangeRateAdmin(admin.ModelAdmin):
    list_display = ('company', 'currency_code', 'rate_to_base', 'effective_date', 'source')
    list_filter = ('company', 'currency_code', 'source')
    ordering = ('-effective_date',)
    readonly_fields=('id',)  