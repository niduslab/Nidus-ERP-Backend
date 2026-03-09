# backend/accounts/admin.py

from django.contrib import admin
from .models import AccountClassification, Account, SystemAccountMapping


@admin.register(AccountClassification)
class AccountClassificationAdmin(admin.ModelAdmin):

    # By default, Django only shows __str__. We want more detail.
    list_display = [
        'internal_path',
        'name',
        'layer',         # This calls the @property we defined on the model
        'parent',
        'company',
    ]

    list_filter = [
        'company',
    ]


    search_fields = [
        'name',
        'internal_path',
        'company__name',
    ]

    ordering = [
        'company',
        'internal_path',
    ]

    readonly_fields = [
        'id',
        'internal_path',
        'created_at',
    ]



@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    """Configuration for the Account model in admin panel."""

    list_display = [
        'code',
        'name',
        'internal_path',
        'normal_balance',
        'currency',
        'classification',
        'is_system_account',
        'is_deletable',
        'is_active',
        'company',
    ]

    list_filter = [
        'company',
        'normal_balance',
        'is_system_account',
        'is_deletable',
        'is_active',
        'currency',
    ]

    search_fields = [
        'name',
        'code',
        'internal_path',
        'company__name',
    ]

    ordering = [
        'company',
        'internal_path',
    ]

    readonly_fields = [
        'id',
        'internal_path',
        'created_at',
        'updated_at',
    ]



@admin.register(SystemAccountMapping)
class SystemAccountMappingAdmin(admin.ModelAdmin):
    """Configuration for the SystemAccountMapping model in admin panel."""

    list_display = [
        'system_code',
        'account',
        'company',
    ]

    list_filter = [
        'company',
    ]

    search_fields = [
        'system_code',
        'account__name',
        'company__name',
    ]

    ordering = [
        'company',
        'system_code',
    ]

    readonly_fields = [
        'company',
        'id',
        'system_code',

    ]