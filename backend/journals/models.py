# backend/journals/models.py

"""
Step 4 — Manual Journal Entries

Models:
    - ManualJournal         — Journal entry header
    - ManualJournalLine     — User-facing debit/credit lines
    - LedgerEntry           — Universal ledger (all modules post here)

ARCHITECTURE — THE THREE-TABLE PATTERN:
    ManualJournal → ManualJournalLine → LedgerEntry

    ManualJournal/ManualJournalLine = "What happened and why"
    LedgerEntry = "What accounts were affected and by how much"

    A single ManualJournalLine can generate MULTIPLE LedgerEntries
    when a tax profile is applied (one for the principal, one per
    tax layer).

    The LedgerEntry table is the SINGLE SOURCE OF TRUTH for all
    account balances. Every future module (invoices, bills, expenses)
    will also post to this same table via GenericFK.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models


# ══════════════════════════════════════════════════
# CHOICE ENUMS
# ══════════════════════════════════════════════════

class JournalTypeChoices(models.TextChoices):
    """
    Categorises journal entries by their business purpose.
    Applied at the journal header level — all lines in a journal
    share the same type. Nullable — user can leave it blank.
    """
    ADJUSTMENT        = 'ADJUSTMENT', 'Adjustment'
    PURCHASE          = 'PURCHASE', 'Purchase'
    SALES             = 'SALES', 'Sales'
    PAYROLL           = 'PAYROLL', 'Payroll'
    DEPRECIATION      = 'DEPRECIATION', 'Depreciation'
    INVESTMENT        = 'INVESTMENT', 'Investment'
    DIVIDEND          = 'DIVIDEND', 'Dividend'
    TAX               = 'TAX', 'Tax'
    OPENING_BALANCE   = 'OPENING_BALANCE', 'Opening Balance'
    TRANSFER          = 'TRANSFER', 'Transfer'
    CURRENCY_EXCHANGE = 'CURRENCY_EXCHANGE', 'Currency Exchange'
    OTHER             = 'OTHER', 'Other'


class JournalStatusChoices(models.TextChoices):
    """
    Status lifecycle: DRAFT → POSTED → VOID

    DRAFT:  Work in progress. Editable, deletable. Does NOT affect balances.
    POSTED: Official. Frozen. DOES affect balances. Can only be voided.
    VOID:   Cancelled. A reversing entry is auto-created. Read-only forever.
    """
    DRAFT  = 'DRAFT', 'Draft'
    POSTED = 'POSTED', 'Posted'
    VOID   = 'VOID', 'Void'


class EntryTypeChoices(models.TextChoices):
    """Debit or Credit — used on ManualJournalLine and LedgerEntry."""
    DEBIT  = 'DEBIT', 'Debit'
    CREDIT = 'CREDIT', 'Credit'


class SourceModuleChoices(models.TextChoices):
    """
    Identifies which module created a LedgerEntry.
    Used as a quick filter — faster than joining ContentType.
    """
    MANUAL_JOURNAL = 'MANUAL_JOURNAL', 'Manual Journal'
    SALES_INVOICE  = 'SALES_INVOICE', 'Sales Invoice'
    PURCHASE_BILL  = 'PURCHASE_BILL', 'Purchase Bill'
    PAYMENT        = 'PAYMENT', 'Payment'
    EXPENSE        = 'EXPENSE', 'Expense'
    SYSTEM         = 'SYSTEM', 'System (auto-generated)'


# ══════════════════════════════════════════════════
# MANUAL JOURNAL (HEADER)
# ══════════════════════════════════════════════════

class ManualJournal(models.Model):
    """
    The header of a manual journal entry.

    This is the "business document" — it records WHY the transaction
    happened, WHEN, and WHO created it. The actual accounting impact
    (which accounts, how much) lives in ManualJournalLine and LedgerEntry.

    Status lifecycle:
        DRAFT  → can be edited, deleted, or posted
        POSTED → frozen, affects balances, can only be voided
        VOID   → cancelled, reversing entry auto-created, read-only forever

    The entry_number is auto-generated from DocumentSequence and is
    unique per company. It's the user-facing reference (JE-0001).

    VOID MECHANISM — TWO LINKS:
        voided_by_entry: "I was voided, here's the reversing entry"
        reversal_of:     "I exist to cancel this original entry"

        Example:
            JE-0001.voided_by_entry → JE-0015
            JE-0015.reversal_of     → JE-0001

        OneToOneField ensures each entry can only be voided once,
        and each reversal points to exactly one original.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='manual_journals',
    )

    entry_number = models.CharField(
        max_length=20,
        verbose_name='entry number',
        help_text='Auto-generated. e.g., "JE-0001".',
    )

    date = models.DateField(
        verbose_name='transaction date',
        help_text='The date the transaction financially occurred.',
    )

    description = models.TextField(
        verbose_name='description',
        help_text='What is this journal entry for?',
    )

    reference = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='reference',
        help_text='Optional external reference (invoice #, receipt #, etc.).',
    )

    journal_type = models.CharField(
        max_length=20,
        choices=JournalTypeChoices.choices,
        null=True,
        blank=True,
        default=None,
        verbose_name='journal type',
    )

    status = models.CharField(
        max_length=10,
        choices=JournalStatusChoices.choices,
        default=JournalStatusChoices.DRAFT,
        verbose_name='status',
    )

    currency = models.CharField(
        max_length=3,
        verbose_name='primary currency',
        help_text='The main transaction currency. Defaults to company base currency.',
    )

    exchange_rate = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal('1.000000'),
        verbose_name='exchange rate',
        help_text='Rate to convert journal currency to base currency.',
    )

    # ── Void / Reversal links ──
    voided_by_entry = models.OneToOneField(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='original_voided_entry',
        verbose_name='voided by entry',
        help_text='If voided, points to the reversing entry.',
    )

    reversal_of = models.OneToOneField(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reversal_entry',
        verbose_name='reversal of',
        help_text='If this IS a reversing entry, points to the original.',
    )

    # ── Timestamps & Users ──
    posted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='posted at',
    )

    voided_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='voided at',
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_journals',
        verbose_name='created by',
    )

    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='voided_journals',
        verbose_name='voided by',
        help_text='The user who voided this entry.',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'manual journal'
        verbose_name_plural = 'manual journals'
        ordering = ['-date', '-created_at']

        constraints = [
            models.UniqueConstraint(
                fields=['company', 'entry_number'],
                name='unique_entry_number_per_company',
            ),
        ]

        indexes = [
            models.Index(
                fields=['company', 'status'],
                name='idx_journal_company_status',
            ),
            models.Index(
                fields=['company', 'date'],
                name='idx_journal_company_date',
            ),
            models.Index(
                fields=['company', 'journal_type'],
                name='idx_journal_company_type',
            ),
        ]

    def __str__(self):
        return f"{self.entry_number} — {self.description[:50]}"


# ══════════════════════════════════════════════════
# MANUAL JOURNAL LINE
# ══════════════════════════════════════════════════

class ManualJournalLine(models.Model):
    """
    A single debit or credit line within a ManualJournal.

    This is the USER-FACING line — what the user sees and fills in.
    Each line says: "Debit/Credit this account for this amount."

    When a tax_profile is applied, this single line generates MULTIPLE
    LedgerEntries: one for the principal amount and one per tax layer.

    Example without tax:
        ManualJournalLine: DEBIT Rent Expense 25,000
        → 1 LedgerEntry:  DEBIT Rent Expense 25,000

    Example with tax (VAT 15%):
        ManualJournalLine: DEBIT Rent Expense 25,000, tax_profile: "VAT 15%"
        → LedgerEntry 1:  DEBIT Rent Expense 25,000 (principal)
        → LedgerEntry 2:  DEBIT Input VAT    3,750  (tax, auto-calculated)
        (The offsetting CREDIT line's ledger entry covers the full 28,750)

    GenericRelation:
        The ledger_entries field is NOT a database column. It's a Django
        helper that lets you do: line.ledger_entries.all() to get all
        LedgerEntry records that were generated from this line. It works
        because LedgerEntry has a GenericFK (content_type + object_id)
        that can point back to this model.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    journal = models.ForeignKey(
        ManualJournal,
        on_delete=models.CASCADE,
        related_name='lines',
    )

    account = models.ForeignKey(
        'chartofaccounts.Account',
        on_delete=models.PROTECT,
        related_name='manual_journal_lines',
        verbose_name='ledger account',
    )

    description = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='line description',
        help_text='Optional note for this specific line.',
    )

    entry_type = models.CharField(
        max_length=6,
        choices=EntryTypeChoices.choices,
        verbose_name='debit/credit',
    )

    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        verbose_name='amount',
        help_text='Amount in the journal currency. Always positive.',
    )

    tax_profile = models.ForeignKey(
        'companies.TaxProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journal_lines',
        verbose_name='tax profile',
    )

    # ── Contact (deferred until contacts app is built) ──
    # TODO: Uncomment when contacts app is created
    # contact = models.ForeignKey(
    #     'contacts.Contact',
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='manual_journal_lines',
    #     verbose_name='contact',
    #     help_text='Optional: customer, supplier, or employee.',
    # )

    # Reverse lookup: line.ledger_entries.all()
    # NOT a database column — just a Django accessor.
    ledger_entries = GenericRelation(
        'LedgerEntry',
        content_type_field='content_type',
        object_id_field='object_id',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'manual journal line'
        verbose_name_plural = 'manual journal lines'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.entry_type} {self.account.code} {self.amount}"


# ══════════════════════════════════════════════════
# LEDGER ENTRY (UNIVERSAL GENERAL LEDGER)
# ══════════════════════════════════════════════════

class LedgerEntry(models.Model):
    """
    The SINGLE SOURCE OF TRUTH for all account balances.

    Every financial event in the system — whether from a manual journal,
    sales invoice, purchase bill, expense, or system-generated entry —
    creates rows in this table. Account balances are calculated by
    summing entries in this table.

    GENERIC FOREIGN KEY (content_type + object_id):
        Points back to the source line (ManualJournalLine, future
        InvoiceLine, etc.). Lets you trace any ledger entry to its origin.

        entry.source_line → resolves to the actual model instance

    SOURCE_MODULE (denormalised CharField):
        Fast filter for "show me all manual journal entries" without
        JOINing the django_content_type table. Intentional denormalisation.

        source_module answers "which module?" (for list filtering)
        content_type + object_id answers "which exact record?" (for navigation)

    AMOUNT + ENTRY_TYPE (Approach B):
        Single positive amount with a DEBIT/CREDIT flag. No wasted
        zero-value columns. Aligns with Zoho Books.

        Balance for DEBIT-normal account (e.g., Petty Cash):
            SUM(CASE WHEN type='DEBIT' THEN base_amount ELSE 0 END)
            - SUM(CASE WHEN type='CREDIT' THEN base_amount ELSE 0 END)
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='ledger_entries',
    )

    ledger_account = models.ForeignKey(
        'chartofaccounts.Account',
        on_delete=models.PROTECT,
        related_name='ledger_entries',
        verbose_name='ledger account',
    )

    date = models.DateField(
        verbose_name='transaction date',
    )

    note = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='note',
    )

    journal_type = models.CharField(
        max_length=20,
        choices=JournalTypeChoices.choices,
        null=True,
        blank=True,
        default=None,
        verbose_name='journal type',
        help_text='Inherited from the source document header. Nullable.',
    )

    entry_type = models.CharField(
        max_length=6,
        choices=EntryTypeChoices.choices,
        verbose_name='debit/credit',
    )

    # ── Foreign currency amount ──
    currency = models.CharField(
        max_length=3,
        verbose_name='currency',
        help_text="The ledger account's currency.",
    )

    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        verbose_name='amount (account currency)',
        help_text='Always positive. In the account currency.',
    )

    # ── Base currency equivalent ──
    exchange_rate = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal('1.000000'),
        verbose_name='exchange rate',
        help_text='Rate at posting time. Locked forever after posting.',
    )

    base_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        verbose_name='amount (base currency)',
        help_text='Always positive. amount × exchange_rate. Snapshot at posting time.',
    )

    # ── Source tracing ──
    source_module = models.CharField(
        max_length=20,
        choices=SourceModuleChoices.choices,
        verbose_name='source module',
        help_text='Which module created this entry. For fast filtering.',
    )

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        verbose_name='source type',
        help_text='ContentType of the source line model (for GenericFK).',
    )

    object_id = models.UUIDField(
        verbose_name='source line ID',
        help_text='PK of the source line record (for GenericFK).',
    )

    source_line = GenericForeignKey('content_type', 'object_id')

    # ── Contact (deferred until contacts app is built) ──
    # TODO: Uncomment when contacts app is created
    # contact = models.ForeignKey(
    #     'contacts.Contact',
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='ledger_entries',
    #     verbose_name='contact',
    # )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'ledger entry'
        verbose_name_plural = 'ledger entries'
        ordering = ['date', 'created_at']

        indexes = [
            models.Index(
                fields=['company', 'ledger_account', 'date'],
                name='idx_led_comp_acc_dt',
            ),
            models.Index(
                fields=['company', 'source_module'],
                name='idx_ledger_company_module',
            ),
            models.Index(
                fields=['company', 'journal_type'],
                name='idx_ledger_company_jtype',
            ),
            models.Index(
                fields=['content_type', 'object_id'],
                name='idx_ledger_generic_fk',
            ),
        ]

    def __str__(self):
        return (
            f"{self.date} | {self.entry_type} "
            f"{self.ledger_account.code} {self.amount} {self.currency}"
        )   