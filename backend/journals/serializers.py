# backend/journals/serializers.py

"""
Serializers for Manual Journal Entries.

KEY DESIGN:
    Journal creation uses a NESTED serializer — the user sends the
    header + all lines in one POST request, not separate requests.
    This matches how Zoho Books works and is the standard pattern
    for header-detail financial documents.

    {
        "date": "2026-03-10",
        "description": "Office rent for March",
        "currency": "BDT",
        "lines": [
            {"account_id": "...", "entry_type": "DEBIT", "amount": "25000.00"},
            {"account_id": "...", "entry_type": "CREDIT", "amount": "25000.00"}
        ]
    }

    The serializer validates the structure, then hands off to the
    service layer (services.py) for business logic and database writes.
"""

from decimal import Decimal

from rest_framework import serializers
from django.db.models import Sum

from chartofaccounts.models import Account
from companies.models import TaxProfile
from .models import (
    ManualJournal,
    ManualJournalLine,
    LedgerEntry,
    JournalTypeChoices,
    EntryTypeChoices,
    SourceModuleChoices,
)


# ══════════════════════════════════════════════════
# JOURNAL LINE SERIALIZERS
# ══════════════════════════════════════════════════

class ManualJournalLineOutputSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for displaying journal lines.
    Used inside ManualJournalDetailSerializer.
    """
    account_id = serializers.UUIDField(source='account.id')
    account_code = serializers.CharField(source='account.code', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)
    tax_profile_id = serializers.UUIDField(source='tax_profile.id', allow_null=True, read_only=True)
    tax_profile_name = serializers.CharField(source='tax_profile.name', default=None, read_only=True)

    class Meta:
        model = ManualJournalLine
        fields = [
            'id',
            'account_id',
            'account_code',
            'account_name',
            'entry_type',
            'amount',
            'description',
            'tax_profile_id',
            'tax_profile_name',
        ]


class ManualJournalLineInputSerializer(serializers.Serializer):
    """
    Input serializer for a single journal line.
    Used inside CreateManualJournalSerializer and UpdateManualJournalSerializer.

    The account_id is a UUID that gets resolved to an Account instance
    during validation. The resolved instance is stored in _account for
    use by the service layer.
    """
    account_id = serializers.UUIDField()
    entry_type = serializers.ChoiceField(choices=EntryTypeChoices.choices)
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    tax_profile_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Amount must be greater than zero.')
        if value > Decimal('999999999999.99'):
            raise serializers.ValidationError(
                'Amount cannot exceed 999,999,999,999.99 (approximately 1 trillion).'
            )
        return value


# ══════════════════════════════════════════════════
# JOURNAL HEADER SERIALIZERS
# ══════════════════════════════════════════════════

class CreateManualJournalSerializer(serializers.Serializer):
    """
    Create a manual journal entry (DRAFT) with nested lines.

    Validates structure and resolves foreign keys, then hands
    the clean data to services.create_journal().
    """
    date = serializers.DateField()
    description = serializers.CharField()
    reference = serializers.CharField(max_length=200, required=False, allow_blank=True)
    journal_type = serializers.ChoiceField(
        choices=JournalTypeChoices.choices,
        required=False,
        allow_null=True,
    )
    currency = serializers.CharField(max_length=3, required=False)
    exchange_rate = serializers.DecimalField(
        max_digits=18,
        decimal_places=6,
        required=False,
    )
    lines = ManualJournalLineInputSerializer(many=True)

    def validate_currency(self, value):
        if value:
            value = value.upper().strip()
            if len(value) != 3:
                raise serializers.ValidationError(
                    'Currency code must be exactly 3 characters (ISO 4217).'
                )
        return value

    def validate_exchange_rate(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                'Exchange rate must be greater than zero.'
            )
        return value

    def validate_lines(self, value):
        if len(value) < 2:
            raise serializers.ValidationError(
                'A journal entry must have at least 2 lines.'
            )
        return value

    def validate(self, data):
        """
        Cross-field validation:
        - Resolve account_id → Account instance
        - Resolve tax_profile_id → TaxProfile instance
        - Check all accounts belong to this company and are active
        - Check debits equal credits
        """
        company = self.context['company']
        lines = data.get('lines', [])
        errors = []

        currency = data.get('currency', company.base_currency)
        exchange_rate = data.get('exchange_rate', Decimal('1.000000'))

        # If currency is the base currency, force exchange rate to 1
        if currency == company.base_currency:
            data['exchange_rate'] = Decimal('1.000000')
            exchange_rate = Decimal('1.000000')

        total_debit = Decimal('0.00')
        total_credit = Decimal('0.00')

        for i, line in enumerate(lines, start=1):
            # Resolve account
            try:
                account = Account.objects.select_related('company').get(
                    id=line['account_id'],
                    company=company,
                )
                if not account.is_active:
                    errors.append(
                        f'Line {i}: Account "{account.name}" is inactive.'
                    )
                line['_account'] = account
            except Account.DoesNotExist:
                errors.append(
                    f'Line {i}: Account not found in this company.'
                )
                continue

            # Resolve tax profile (optional)
            tax_profile_id = line.get('tax_profile_id')
            if tax_profile_id:
                try:
                    tax_profile = TaxProfile.objects.get(
                        id=tax_profile_id,
                        company=company,
                        is_active=True,
                    )
                    line['_tax_profile'] = tax_profile
                except TaxProfile.DoesNotExist:
                    errors.append(
                        f'Line {i}: Tax profile not found or inactive.'
                    )
            else:
                line['_tax_profile'] = None

            # Accumulate for balance check
            line_base = line['amount'] * exchange_rate
            if line['entry_type'] == 'DEBIT':
                total_debit += line_base
            else:
                total_credit += line_base

        if errors:
            raise serializers.ValidationError({'lines': errors})

        # Balance check
        total_debit = total_debit.quantize(Decimal('0.01'))
        total_credit = total_credit.quantize(Decimal('0.01'))

        if total_debit != total_credit:
            diff = abs(total_debit - total_credit)
            raise serializers.ValidationError({
                'lines': (
                    f'Journal is not balanced. '
                    f'Total debits: {total_debit}, Total credits: {total_credit}. '
                    f'Difference: {diff}.'
                )
            })

        return data


class UpdateManualJournalSerializer(serializers.Serializer):
    """
    Update a draft journal entry. All fields are optional.
    If lines are provided, ALL existing lines are replaced.
    """
    date = serializers.DateField(required=False)
    description = serializers.CharField(required=False)
    reference = serializers.CharField(max_length=200, required=False, allow_blank=True, allow_null=True)
    journal_type = serializers.ChoiceField(
        choices=JournalTypeChoices.choices,
        required=False,
        allow_null=True,
    )
    currency = serializers.CharField(max_length=3, required=False)
    exchange_rate = serializers.DecimalField(
        max_digits=18,
        decimal_places=6,
        required=False,
    )
    lines = ManualJournalLineInputSerializer(many=True, required=False)

    def validate_currency(self, value):
        if value:
            value = value.upper().strip()
            if len(value) != 3:
                raise serializers.ValidationError(
                    'Currency code must be exactly 3 characters (ISO 4217).'
                )
        return value

    def validate_exchange_rate(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                'Exchange rate must be greater than zero.'
            )
        return value

    def validate(self, data):
        """If lines are provided, resolve and validate them."""
        lines = data.get('lines')
        if lines is None:
            return data

        if len(lines) < 2:
            raise serializers.ValidationError({
                'lines': 'A journal entry must have at least 2 lines.'
            })

        company = self.context['company']
        journal = self.context['journal']

        currency = data.get('currency', journal.currency)
        exchange_rate = data.get('exchange_rate', journal.exchange_rate)

        if currency == company.base_currency:
            data['exchange_rate'] = Decimal('1.000000')
            exchange_rate = Decimal('1.000000')

        errors = []
        total_debit = Decimal('0.00')
        total_credit = Decimal('0.00')

        for i, line in enumerate(lines, start=1):
            try:
                account = Account.objects.get(
                    id=line['account_id'],
                    company=company,
                )
                if not account.is_active:
                    errors.append(f'Line {i}: Account "{account.name}" is inactive.')
                line['_account'] = account
            except Account.DoesNotExist:
                errors.append(f'Line {i}: Account not found in this company.')
                continue

            tax_profile_id = line.get('tax_profile_id')
            if tax_profile_id:
                try:
                    line['_tax_profile'] = TaxProfile.objects.get(
                        id=tax_profile_id, company=company, is_active=True,
                    )
                except TaxProfile.DoesNotExist:
                    errors.append(f'Line {i}: Tax profile not found or inactive.')
            else:
                line['_tax_profile'] = None

            line_base = line['amount'] * exchange_rate
            if line['entry_type'] == 'DEBIT':
                total_debit += line_base
            else:
                total_credit += line_base

        if errors:
            raise serializers.ValidationError({'lines': errors})

        total_debit = total_debit.quantize(Decimal('0.01'))
        total_credit = total_credit.quantize(Decimal('0.01'))

        if total_debit != total_credit:
            diff = abs(total_debit - total_credit)
            raise serializers.ValidationError({
                'lines': (
                    f'Journal is not balanced. '
                    f'Total debits: {total_debit}, Total credits: {total_credit}. '
                    f'Difference: {diff}.'
                )
            })

        return data


# ══════════════════════════════════════════════════
# JOURNAL OUTPUT SERIALIZERS
# ══════════════════════════════════════════════════

class ManualJournalListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing journals.

    PERFORMANCE CONTRACT (read carefully):
        This serializer EXPECTS the input queryset to carry two annotations:
            - total_amount : Sum of DEBIT line amounts  (Decimal, may be None)
            - line_count   : Count of lines             (int)
        These are added in JournalListCreateView.get() via .annotate(...).

    WHY THIS MATTERS:
        The previous implementation used SerializerMethodField with
        obj.lines.filter(...).aggregate(Sum) and obj.lines.count(). Each call
        ran a fresh SQL query — 2 extra queries per journal. For a page of 20,
        that is 40 wasted round trips. The .filter().aggregate() pattern also
        BYPASSES prefetch_related() caches, so the earlier prefetch was useless.

        The fix moves both computations into the original SELECT using GROUP BY,
        so N journals → 1 query instead of 1 + 2N queries.
    """
    created_by_name = serializers.CharField(
        source='created_by.full_name',
        read_only=True,
    )

    # Read directly from the queryset annotation via SerializerMethodField only
    # to stringify the Decimal consistently (and handle None for empty journals).
    total_amount = serializers.SerializerMethodField()

    # line_count is read directly from the annotation — Django's IntegerField
    # will pick up obj.line_count without any method call.
    line_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ManualJournal
        fields = [
            'id',
            'entry_number',
            'date',
            'description',
            'reference',
            'journal_type',
            'status',
            'currency',
            'exchange_rate',
            'total_amount',
            'line_count',
            'created_by_name',
            'created_at',
        ]

    def get_total_amount(self, obj):
        """
        Return the annotated DEBIT total as a string.

        Falls back to '0.00' when the annotation is missing (journal has no
        lines yet, so SUM() returned NULL → None in Python) or when the
        caller forgot to annotate (defensive — bug should surface loudly in
        tests, but we never want to crash a list response).
        """
        total = getattr(obj, 'total_amount', None)
        return str(total) if total is not None else '0.00'


class ManualJournalDetailSerializer(serializers.ModelSerializer):
    """
    Full journal details with nested lines and audit info.

    PERFORMANCE CONTRACT:
        Caller should prefetch related lines to keep total queries flat:
            ManualJournal.objects
              .select_related('created_by', 'voided_by',
                              'voided_by_entry', 'reversal_of')
              .prefetch_related('lines__account', 'lines__tax_profile')

        JournalDetailView.get() already does this correctly.

    PERFORMANCE NOTE on total_debit / total_credit:
        These now iterate obj.lines.all() in Python using the prefetched
        queryset — NOT .filter().aggregate(), which would bypass the prefetch
        cache and hit the DB again. With prefetch in place, 0 extra queries.
    """
    lines = ManualJournalLineOutputSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(
        source='created_by.full_name', read_only=True,
    )
    voided_by_name = serializers.CharField(
        source='voided_by.full_name', default=None, read_only=True,
    )
    voided_by_entry_number = serializers.CharField(
        source='voided_by_entry.entry_number', default=None, read_only=True,
    )
    reversal_of_entry_number = serializers.CharField(
        source='reversal_of.entry_number', default=None, read_only=True,
    )
    total_debit = serializers.SerializerMethodField()
    total_credit = serializers.SerializerMethodField()

    class Meta:
        model = ManualJournal
        fields = [
            'id',
            'entry_number',
            'date',
            'description',
            'reference',
            'journal_type',
            'status',
            'currency',
            'exchange_rate',
            'total_debit',
            'total_credit',
            'lines',
            'voided_by_entry',
            'voided_by_entry_number',
            'reversal_of',
            'reversal_of_entry_number',
            'posted_at',
            'voided_at',
            'voided_by_name',
            'created_by',
            'created_by_name',
            'created_at',
            'updated_at',
        ]

    def get_total_debit(self, obj):
        """
        Sum the amounts of all DEBIT lines using the prefetched queryset.

        Iterates obj.lines.all() in Python — with prefetch_related('lines') in
        the view, this triggers ZERO additional DB queries. Decimal addition
        starts from Decimal('0.00') to preserve precision even for empty lists.
        """
        total = sum(
            (line.amount for line in obj.lines.all()
             if line.entry_type == EntryTypeChoices.DEBIT),
            Decimal('0.00'),
        )
        return str(total)

    def get_total_credit(self, obj):
        """Mirror of get_total_debit for the CREDIT side. Same zero-extra-query contract."""
        total = sum(
            (line.amount for line in obj.lines.all()
             if line.entry_type == EntryTypeChoices.CREDIT),
            Decimal('0.00'),
        )
        return str(total)
# ══════════════════════════════════════════════════
# LEDGER ENTRY SERIALIZER
# ══════════════════════════════════════════════════

class LedgerEntrySerializer(serializers.ModelSerializer):
    """
    Read-only serializer for displaying ledger entries.
    Used in the account ledger view.
    """
    account_code = serializers.CharField(
        source='ledger_account.code', read_only=True,
    )
    account_name = serializers.CharField(
        source='ledger_account.name', read_only=True,
    )

    class Meta:
        model = LedgerEntry
        fields = [
            'id',
            'date',
            'ledger_account',
            'account_code',
            'account_name',
            'entry_type',
            'amount',
            'currency',
            'exchange_rate',
            'base_amount',
            'note',
            'journal_type',
            'source_module',
            'created_at',
        ]


# ══════════════════════════════════════════════════
# VOID SERIALIZER
# ══════════════════════════════════════════════════

class VoidJournalSerializer(serializers.Serializer):
    """Input for voiding a journal. Only void_date is needed (optional)."""
    void_date = serializers.DateField(
        required=False,
        help_text='Date for the reversing entry. Defaults to today.',
    )