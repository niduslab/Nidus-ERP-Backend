# backend/chartofaccounts/admin.py

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import AccountClassification, Account, SystemAccountMapping


@admin.register(AccountClassification)
class AccountClassificationAdmin(admin.ModelAdmin):
    # Added cash_flow_category to list_display
    list_display = ['internal_path', 'name', 'layer', 'cash_flow_category', 'parent', 'company']
    list_filter = ['company', 'cash_flow_category', 'name']
    search_fields = ['name', 'internal_path', 'company__name']
    ordering = ['company', 'internal_path']
    readonly_fields = ['id', 'internal_path', 'created_at'] 

    class Media:
        js = ('admin/js/company_scoped_filter.js',)

    fieldsets = (
        ('Classification', {
            'fields': (
                'id', 'company', 'parent', 'name', 'internal_path',
                'cash_flow_category',
            ),
        }),
        ('Audit', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Restrict parent dropdown to Layer 2 only.
        Users can only create Layer 3 classifications (under Layer 2 parents).
        Layer 1 and Layer 2 are system-generated during CoA creation.
        """
        if db_field.name == 'parent':
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
        if db_field.name == 'classification':
            kwargs['queryset'] = AccountClassification.objects.filter(
                internal_path__regex=r'^[^.]+\.[^.]+\.[^.]+$'
            )
        if db_field.name == 'parent_account':
            kwargs['queryset'] = Account.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        """Auto-generate internal_path when creating accounts from admin."""
        if not change:
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

        # Build table rows using .format() to avoid f-string nested quote issues
        rows = []
        for e in entries:
            url = reverse('admin:journals_ledgerentry_change', args=[e.pk])
            rows.append(
                '<tr>'
                '<td style="padding:3px 6px">{date}</td>'
                '<td style="padding:3px 6px">{etype}</td>'
                '<td style="padding:3px 6px">{amt} {cur}</td>'
                '<td style="padding:3px 6px">{base}</td>'
                '<td style="padding:3px 6px"><a href="{url}">{note}</a></td>'
                '</tr>'.format(
                    date=e.date,
                    etype=e.entry_type,
                    amt=e.amount,
                    cur=e.currency,
                    base=e.base_amount,
                    url=url,
                    note=e.note or '—',
                )
            )

        # Build the foreign balance display string
        foreign_info = ''
        if balance['foreign_balance'] is not None:
            foreign_info = ' ({fb} {fc})'.format(
                fb=balance['foreign_balance'],
                fc=balance['currency'],
            )

        balance_line = (
            '<div style="margin-bottom:8px;font-weight:bold">'
            '{foreign}'
            ' Debits: {td} | Credits: {tc}'
            '<div>Balance: {bal} {bc}</div>'
            '</div>'
        ).format(
            foreign=foreign_info,
            td=balance['total_debit'],
            tc=balance['total_credit'],
            bal=balance['balance'],
            bc=balance['base_currency'],
        )

        table = (
            balance_line
            + '<table style="border-collapse:collapse;width:100%;font-size:12px">'
              '<tr style="font-weight:bold">'
              '<td style="padding:3px 6px">Date</td>'
              '<td style="padding:3px 6px">Dr/Cr</td>'
              '<td style="padding:3px 6px">Amount</td>'
              '<td style="padding:3px 6px">Base</td>'
              '<td style="padding:3px 6px">Note</td>'
              '</tr>'
            + ''.join(rows)
            + '</table>'
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