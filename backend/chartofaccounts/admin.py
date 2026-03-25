# backend/chartofaccounts/admin.py

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import AccountClassification, Account, SystemAccountMapping


@admin.register(AccountClassification)
class AccountClassificationAdmin(admin.ModelAdmin):
    list_display = ['internal_path', 'name', 'layer', 'parent', 'company']
    list_filter = ['company', 'name']
    search_fields = ['name', 'internal_path', 'company__name']
    ordering = ['company', 'internal_path']
    readonly_fields = ['id', 'internal_path', 'created_at'] 

    class Media:
        js = ('admin/js/company_scoped_filter.js',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Restrict parent dropdown to Layer 2 only.
        Users can only create Layer 3 classifications (under Layer 2 parents).
        Layer 1 and Layer 2 are system-generated during CoA creation.
        """
        if db_field.name == 'parent':
            # Layer 2 = exactly 1 dot in internal_path (e.g., "1.10")
            kwargs['queryset'] = AccountClassification.objects.filter(
                internal_path__regex=r'^[^.]+\.[^.]+$'
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        """Auto-generate internal_path for new classifications."""
        if not change and obj.parent:
            from .views import generate_next_internal_path
            obj.internal_path = generate_next_internal_path(
                obj.company, obj.parent.internal_path
            )
        super().save_model(request, obj, form, change)


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'name', 'internal_path', 'normal_balance',
        'currency', 'classification', 'is_system_account',
        'is_active', 'company', 'view_ledger_link',
    ]
    list_filter = [
        'company', 'normal_balance', 'is_system_account',
        'is_deletable', 'is_active', 'currency',
    ]
    search_fields = ['name', 'code', 'internal_path', 'company__name']
    ordering = ['company', 'internal_path']
    readonly_fields = [
        'id', 'internal_path', 'created_at', 'updated_at',
        'ledger_summary',
    ]

    class Media:
        js = ('admin/js/company_scoped_filter.js',)

    fieldsets = (
        ('Account', {
            'fields': (
                'id', 'company', 'classification', 'parent_account',
                'name', 'code', 'internal_path',
                'normal_balance', 'currency',
            ),
        }),
        ('Flags', {
            'fields': ('is_system_account', 'is_deletable', 'is_active'),
        }),
        ('Description', {
            'fields': ('description',),
        }),
        ('Ledger Entries', {
            'fields': ('ledger_summary',),
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Restrict classification dropdown to Layer 3 only.
        Restrict parent_account to Layer 4+ accounts only.
        """
        if db_field.name == 'classification':
            # Only show Layer 3 classifications (internal_path has exactly 2 dots)
            kwargs['queryset'] = AccountClassification.objects.filter(
                internal_path__regex=r'^[^.]+\.[^.]+\.[^.]+$'
            )
        if db_field.name == 'parent_account':
            # Only show Layer 4+ accounts (existing accounts, not classifications)
            kwargs['queryset'] = Account.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        """Auto-generate internal_path when creating accounts from admin."""
        if not change:
            # New account — generate internal_path
            from .views import generate_next_internal_path

            if obj.parent_account:
                parent_path = obj.parent_account.internal_path
            else:
                parent_path = obj.classification.internal_path

            obj.internal_path = generate_next_internal_path(
                obj.company, parent_path
            )

            if not obj.created_by:
                obj.created_by = request.user

        super().save_model(request, obj, form, change)

    def view_ledger_link(self, obj):
        """Link to filtered ledger entries for this account."""
        from journals.models import LedgerEntry
        count = LedgerEntry.objects.filter(ledger_account=obj).count()
        if count > 0:
            url = reverse('admin:journals_ledgerentry_changelist')
            return format_html(
                '<a href="{}?ledger_account__id__exact={}">{} entries</a>',
                url, obj.pk, count,
            )
        return 'No entries'
    view_ledger_link.short_description = 'Ledger'

    def ledger_summary(self, obj):
        """Show recent ledger entries and balance inside the account detail page."""
        from journals.models import LedgerEntry
        from journals.services import get_account_balance

        entries = LedgerEntry.objects.filter(
            ledger_account=obj,
        ).order_by('-date', '-created_at')[:20]

        if not entries.exists():
            return 'No ledger entries for this account.'

        balance = get_account_balance(obj, include_sub_accounts=False)

        rows = []
        for e in entries:
            url = reverse('admin:journals_ledgerentry_change', args=[e.pk])
            rows.append(
                f'<tr>'
                f'<td style="padding:3px 6px">{e.date}</td>'
                f'<td style="padding:3px 6px">{e.entry_type}</td>'
                f'<td style="padding:3px 6px">{e.amount} {e.currency}</td>'
                f'<td style="padding:3px 6px">{e.base_amount}</td>'
                f'<td style="padding:3px 6px"><a href="{url}">{e.note or "—"}</a></td>'
                f'</tr>'
            )

        balance_line = (
            f'<div style="margin-bottom:8px;font-weight:bold">'
            f'{f" ({balance["foreign_balance"]} {balance["currency"]})" if balance["foreign_balance"] is not None else ""}'
            f' Debits: {balance["total_debit"]} | Credits: {balance["total_credit"]}'
            f'<div>Balance: {balance["balance"]} {balance["base_currency"]}</div>'
            f'</div>'
        )

        table = (
            balance_line +
            '<table style="border-collapse:collapse;width:100%;font-size:12px">'
            '<tr style="font-weight:bold">'
            '<td style="padding:3px 6px">Date</td>'
            '<td style="padding:3px 6px">Dr/Cr</td>'
            '<td style="padding:3px 6px">Amount</td>'
            '<td style="padding:3px 6px">Base</td>'
            '<td style="padding:3px 6px">Note</td>'
            '</tr>' + ''.join(rows) +
            '</table>'
            '<div style="margin-top:4px;font-size:11px;color:#666">'
            'Showing latest 20 entries.</div>'
        )
        return mark_safe(table)
    ledger_summary.short_description = 'Ledger entries & balance'


@admin.register(SystemAccountMapping)
class SystemAccountMappingAdmin(admin.ModelAdmin):
    list_display = ['system_code', 'account', 'company']
    list_filter = ['company']
    search_fields = ['system_code', 'account__name', 'company__name']
    ordering = ['company', 'system_code']
    readonly_fields = ['company', 'id', 'system_code']
    
    class Media:
        js = ('admin/js/company_scoped_filter.js',)