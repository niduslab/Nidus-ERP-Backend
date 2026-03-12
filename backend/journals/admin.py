# backend/journals/admin.py

from django.contrib import admin
from .models import ManualJournal, ManualJournalLine, LedgerEntry


class ManualJournalLineInline(admin.TabularInline):
    model = ManualJournalLine
    extra = 0
    readonly_fields = ('id', 'created_at')
    fields = ('account', 'entry_type', 'amount', 'tax_profile', 'description', 'created_at')


@admin.register(ManualJournal)
class ManualJournalAdmin(admin.ModelAdmin):
    list_display = ('entry_number', 'company', 'date', 'status', 'journal_type', 'currency', 'created_by', 'created_at')
    list_filter = ('status', 'journal_type', 'company')
    search_fields = ('entry_number', 'description', 'reference')
    ordering = ('-date', '-created_at')
    readonly_fields = ('id', 'entry_number', 'posted_at', 'voided_at', 'created_at', 'updated_at')
    inlines = [ManualJournalLineInline]


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ('date', 'ledger_account', 'entry_type', 'amount', 'currency', 'base_amount', 'source_module', 'journal_type')
    list_filter = ('source_module', 'journal_type', 'entry_type', 'company')
    search_fields = ('note', 'ledger_account__name', 'ledger_account__code')
    ordering = ('-date', '-created_at')
    readonly_fields = ('id', 'content_type', 'object_id', 'created_at')