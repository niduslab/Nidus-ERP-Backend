# backend/companies/admin.py

from django.contrib import admin
from .models import Company, CompanyUser, PendingInvitation


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
        'name',
        'owner',
        'industry',
        'base_currency',
        'subscription_plan',
        'is_active',
        'created_at',
    )

    list_filter = (
        'industry',
        'base_currency',
        'subscription_plan',
        'is_active',
        'country',
    )

    search_fields = ('name', 'trade_name', 'tax_id', 'owner__email')

    ordering = ('-created_at',)

    readonly_fields = ('id', 'created_at', 'updated_at')

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'owner', 'name', 'trade_name', 'industry', 'tax_id'),
        }),
        ('Financial Settings', {
            'fields': ('base_currency', 'fiscal_year_start_month', 'inventory_valuation_method', 'date_format', 'is_vds_withholding_entity'),
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