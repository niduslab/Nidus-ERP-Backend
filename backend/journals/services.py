# backend/journals/services.py

"""
Business logic for Manual Journal Entries.

SERVICES:
    generate_entry_number()   — Atomic sequential number generation
    calculate_tax()           — Multi-layer tax calculation (independent + compound)
    create_journal()          — Create a draft journal with lines
    post_journal()            — Post a draft (creates ledger entries)
    void_journal()            — Void a posted entry (creates reversing entry)
    delete_journal()          — Delete a draft entry
    update_journal()          — Edit a draft entry
    get_account_balance()     — Calculate account balance from ledger

DESIGN PRINCIPLES:
    1. All state changes happen inside transaction.atomic()
    2. Validation happens BEFORE any database writes
    3. Ledger entries are only created at posting time, not draft time
    4. Voiding never deletes — it creates a reversing entry
    5. Balance is always calculated, never stored
"""

from decimal import Decimal, ROUND_HALF_UP

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Sum, Case, When, DecimalField, Q, F
from django.utils import timezone

from .models import (
    ManualJournal,
    ManualJournalLine,
    LedgerEntry,
    JournalStatusChoices,
    EntryTypeChoices,
    SourceModuleChoices,
)
from companies.models import DocumentSequence


# ══════════════════════════════════════════════════
# SEQUENTIAL NUMBER GENERATION
# ══════════════════════════════════════════════════

def generate_entry_number(company):
    """
    Atomically generates the next journal entry number for a company.

    Uses select_for_update() to lock the DocumentSequence row during
    the increment. This prevents two concurrent requests from getting
    the same number — a classic race condition in multi-user systems.

    Returns:
        str: The formatted entry number, e.g., "JE-0001"

    Must be called inside a transaction.atomic() block.
    """
    seq = DocumentSequence.objects.select_for_update().get(
        company=company,
        module='MANUAL_JOURNAL',
    )

    number = seq.next_number
    entry_number = f"{seq.prefix}{str(number).zfill(seq.padding)}"

    seq.next_number = F('next_number') + 1
    seq.save(update_fields=['next_number', 'updated_at'])

    return entry_number


# ══════════════════════════════════════════════════
# TAX CALCULATION
# ══════════════════════════════════════════════════

def calculate_tax(tax_profile, base_amount):
    
    layers = tax_profile.layers.order_by('apply_order')
    results = []
    running_total = base_amount

    for layer in layers:
        if layer.calculation_type == 'INDEPENDENT':
            # Calculate on the ORIGINAL base amount, not the running total
            taxable_amount = base_amount
        else:
            # COMPOUND — calculate on the running total (base + all previous taxes)
            taxable_amount = running_total

        tax_amount = (taxable_amount * layer.rate / Decimal('100')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        results.append({
            'layer': layer,
            'tax_amount': tax_amount,
            'taxable_amount': taxable_amount,
        })

        # Always add to running total regardless of type,
        # because a later COMPOUND layer needs to include this
        running_total += tax_amount

    return results


# ══════════════════════════════════════════════════
# CREATE JOURNAL (DRAFT)
# ══════════════════════════════════════════════════

def create_journal(company, created_by, journal_data, lines_data):
    """
    Create a new manual journal entry as DRAFT.

    Drafts do NOT create ledger entries — they're just saved for review.
    Ledger entries are created only when the journal is posted.

    Args:
        company: Company instance
        created_by: User instance
        journal_data: dict with header fields:
            {
                'date': date,
                'description': str,
                'reference': str (optional),
                'journal_type': str (optional),
                'currency': str,
                'exchange_rate': Decimal,
            }
        lines_data: list of dicts:
            [
                {
                    'account': Account instance,
                    'entry_type': 'DEBIT' or 'CREDIT',
                    'amount': Decimal,
                    'description': str (optional),
                    'tax_profile': TaxProfile instance or None,
                },
                ...
            ]

    Returns:
        ManualJournal instance

    Raises:
        ValueError: If validation fails
    """
    # ── Validation ──
    _validate_journal_data(company, journal_data, lines_data)

    with transaction.atomic():
        entry_number = generate_entry_number(company)

        journal = ManualJournal.objects.create(
            company=company,
            entry_number=entry_number,
            date=journal_data['date'],
            description=journal_data['description'],
            reference=journal_data.get('reference'),
            journal_type=journal_data.get('journal_type'),
            status=JournalStatusChoices.DRAFT,
            currency=journal_data.get('currency', company.base_currency),
            exchange_rate=journal_data.get('exchange_rate', Decimal('1.000000')),
            created_by=created_by,
        )

        for line_data in lines_data:
            ManualJournalLine.objects.create(
                journal=journal,
                account=line_data['account'],
                entry_type=line_data['entry_type'],
                amount=line_data['amount'],
                description=line_data.get('description'),
                tax_profile=line_data.get('tax_profile'),
            )

    return journal


# ══════════════════════════════════════════════════
# POST JOURNAL (DRAFT → POSTED)
# ══════════════════════════════════════════════════

def post_journal(journal, posted_by):
    """
    Post a draft journal — changes status to POSTED and creates
    ledger entries for every line (including tax-expanded lines).

    This is the moment the journal affects account balances.

    For each ManualJournalLine:
        1. Create a LedgerEntry for the principal amount
        2. If tax_profile is set, calculate tax per layer and
           create additional LedgerEntries for each tax account

    Args:
        journal: ManualJournal instance (must be DRAFT)
        posted_by: User instance

    Returns:
        ManualJournal instance (now POSTED)

    Raises:
        ValueError: If journal is not DRAFT or validation fails
    """
    if journal.status != JournalStatusChoices.DRAFT:
        raise ValueError(
            f'Only DRAFT journals can be posted. '
            f'This journal is {journal.status}.'
        )

    

    # Re-validate everything before posting
    lines_data = []
    for line in journal.lines.select_related('account', 'tax_profile'):
        lines_data.append({
            'account': line.account,
            'entry_type': line.entry_type,
            'amount': line.amount,
            'tax_profile': line.tax_profile,
        })

    journal_data = {
        'date': journal.date,
        'description': journal.description,
        'currency': journal.currency,
        'exchange_rate': journal.exchange_rate,
    }
    _validate_journal_data(journal.company, journal_data, lines_data)

    with transaction.atomic():
        journal_line_ct = ContentType.objects.get_for_model(ManualJournalLine)

        for line in journal.lines.select_related('account', 'tax_profile'):
            # ── Principal ledger entry ──
            _create_ledger_entry(
                company=journal.company,
                account=line.account,
                date=journal.date,
                entry_type=line.entry_type,
                amount=line.amount,
                currency=line.account.currency,
                exchange_rate=journal.exchange_rate,
                note=line.description or journal.description,
                journal_type=journal.journal_type,
                source_module=SourceModuleChoices.MANUAL_JOURNAL,
                content_type=journal_line_ct,
                object_id=line.id,
            )

            # ── Tax ledger entries (one per tax layer) ──
            if line.tax_profile:
                tax_results = calculate_tax(line.tax_profile, line.amount)

                for tax_result in tax_results:
                    layer = tax_result['layer']
                    tax_account = layer.default_tax_account

                    _create_ledger_entry(
                        company=journal.company,
                        account=tax_account,
                        date=journal.date,
                        entry_type=line.entry_type,
                        amount=tax_result['tax_amount'],
                        currency=tax_account.currency,
                        exchange_rate=journal.exchange_rate,
                        note=f"{layer.name} ({layer.rate}%) on {line.account.name}",
                        journal_type=journal.journal_type,
                        source_module=SourceModuleChoices.MANUAL_JOURNAL,
                        content_type=journal_line_ct,
                        object_id=line.id,
                    )

        # Update journal status
        journal.status = JournalStatusChoices.POSTED
        journal.posted_at = timezone.now()
        journal.save(update_fields=['status', 'posted_at', 'updated_at'])

    return journal


# ══════════════════════════════════════════════════
# VOID JOURNAL (POSTED → VOID)
# ══════════════════════════════════════════════════

def void_journal(journal, voided_by, void_date=None):
    """
    Void a posted journal — creates an automatic reversing entry
    that cancels out the original.

    The original entry's status changes to VOID.
    A new POSTED entry is created with all debits/credits swapped.
    Both entries are linked for audit trail.

    Args:
        journal: ManualJournal instance (must be POSTED)
        voided_by: User instance
        void_date: date for the reversing entry (defaults to today)

    Returns:
        ManualJournal: The reversing entry (POSTED)

    Raises:
        ValueError: If journal is not POSTED or date is before lock date
    """
    if journal.status != JournalStatusChoices.POSTED:
        raise ValueError(
            f'Only POSTED journals can be voided. '
            f'This journal is {journal.status}.'
        )

    # Check lock date on the ORIGINAL entry's date
    if journal.company.lock_date and journal.date <= journal.company.lock_date:
        raise ValueError(
            f'Cannot void this entry. Its transaction date ({journal.date}) '
            f'is on or before the lock date ({journal.company.lock_date}).'
        )

    if void_date is None:
        void_date = timezone.now().date()

    # Check lock date on the void date too
    if journal.company.lock_date and void_date <= journal.company.lock_date:
        raise ValueError(
            f'Cannot create a reversing entry on {void_date}. '
            f'This date is on or before the lock date ({journal.company.lock_date}).'
        )

    with transaction.atomic():
        # ── Create the reversing journal ──
        reversal_number = generate_entry_number(journal.company)

        reversal = ManualJournal.objects.create(
            company=journal.company,
            entry_number=reversal_number,
            date=void_date,
            description=f"Reversal of {journal.entry_number}",
            reference=journal.reference,
            journal_type=journal.journal_type,
            status=JournalStatusChoices.POSTED,
            currency=journal.currency,
            exchange_rate=journal.exchange_rate,
            reversal_of=journal,
            posted_at=timezone.now(),
            created_by=voided_by,
        )

        # ── Create reversed lines (swap debit ↔ credit) ──
        for original_line in journal.lines.select_related('account', 'tax_profile'):
            reversed_type = (
                EntryTypeChoices.CREDIT
                if original_line.entry_type == EntryTypeChoices.DEBIT
                else EntryTypeChoices.DEBIT
            )

            ManualJournalLine.objects.create(
                journal=reversal,
                account=original_line.account,
                entry_type=reversed_type,
                amount=original_line.amount,
                description=f"Reversal: {original_line.description or ''}".strip(),
                tax_profile=original_line.tax_profile,
            )

        # ── Post the reversal (creates ledger entries) ──
        # We call the internal posting logic directly since the
        # reversal is already marked as POSTED
        journal_line_ct = ContentType.objects.get_for_model(ManualJournalLine)

        for line in reversal.lines.select_related('account', 'tax_profile'):
            _create_ledger_entry(
                company=reversal.company,
                account=line.account,
                date=reversal.date,
                entry_type=line.entry_type,
                amount=line.amount,
                currency=line.account.currency,
                exchange_rate=reversal.exchange_rate,
                note=line.description or reversal.description,
                journal_type=reversal.journal_type,
                source_module=SourceModuleChoices.MANUAL_JOURNAL,
                content_type=journal_line_ct,
                object_id=line.id,
            )

            if line.tax_profile:
                tax_results = calculate_tax(line.tax_profile, line.amount)
                for tax_result in tax_results:
                    layer = tax_result['layer']
                    _create_ledger_entry(
                        company=reversal.company,
                        account=layer.default_tax_account,
                        date=reversal.date,
                        entry_type=line.entry_type,
                        amount=tax_result['tax_amount'],
                        currency=layer.default_tax_account.currency,
                        exchange_rate=reversal.exchange_rate,
                        note=f"Reversal: {layer.name} ({layer.rate}%)",
                        journal_type=reversal.journal_type,
                        source_module=SourceModuleChoices.MANUAL_JOURNAL,
                        content_type=journal_line_ct,
                        object_id=line.id,
                    )

        # ── Mark original as VOID and link to reversal ──
        journal.status = JournalStatusChoices.VOID
        journal.voided_at = timezone.now()
        journal.voided_by = voided_by
        journal.voided_by_entry = reversal
        journal.save(update_fields=[
            'status', 'voided_at', 'voided_by',
            'voided_by_entry', 'updated_at',
        ])

    return reversal


# ══════════════════════════════════════════════════
# DELETE JOURNAL (DRAFT ONLY)
# ══════════════════════════════════════════════════

def delete_journal(journal):
    """
    Permanently delete a draft journal and all its lines.

    Only DRAFT entries can be deleted. POSTED and VOID entries
    must be preserved for audit trail.

    Args:
        journal: ManualJournal instance (must be DRAFT)

    Raises:
        ValueError: If journal is not DRAFT
    """
    if journal.status != JournalStatusChoices.DRAFT:
        raise ValueError(
            f'Only DRAFT journals can be deleted. '
            f'This journal is {journal.status}. '
            f'Posted entries must be voided instead.'
        )

    # CASCADE on the FK handles deleting all lines automatically
    journal.delete()


# ══════════════════════════════════════════════════
# UPDATE JOURNAL (DRAFT ONLY)
# ══════════════════════════════════════════════════

def update_journal(journal, journal_data=None, lines_data=None):
    """
    Update a draft journal's header and/or replace its lines.

    Only DRAFT entries can be edited. When lines_data is provided,
    ALL existing lines are deleted and replaced with the new ones
    (full replacement, not partial update — simpler and less error-prone).

    Args:
        journal: ManualJournal instance (must be DRAFT)
        journal_data: dict with header fields to update (optional)
        lines_data: list of line dicts (optional, replaces all lines)

    Returns:
        ManualJournal instance (updated)

    Raises:
        ValueError: If journal is not DRAFT or validation fails
    """
    if journal.status != JournalStatusChoices.DRAFT:
        raise ValueError(
            f'Only DRAFT journals can be edited. '
            f'This journal is {journal.status}.'
        )

    with transaction.atomic():
        # ── Update header fields ──
        if journal_data:
            update_fields = ['updated_at']
            for field in ['date', 'description', 'reference', 'journal_type',
                          'currency', 'exchange_rate']:
                if field in journal_data:
                    setattr(journal, field, journal_data[field])
                    update_fields.append(field)
            journal.save(update_fields=update_fields)

        # ── Replace lines (full replacement) ──
        if lines_data is not None:
            # Validate before deleting old lines
            j_data = {
                'date': journal.date,
                'description': journal.description,
                'currency': journal.currency,
                'exchange_rate': journal.exchange_rate,
            }
            _validate_journal_data(journal.company, j_data, lines_data)

            # Delete all existing lines and recreate
            journal.lines.all().delete()

            for line_data in lines_data:
                ManualJournalLine.objects.create(
                    journal=journal,
                    account=line_data['account'],
                    entry_type=line_data['entry_type'],
                    amount=line_data['amount'],
                    description=line_data.get('description'),
                    tax_profile=line_data.get('tax_profile'),
                )

    return journal


# ══════════════════════════════════════════════════
# ACCOUNT BALANCE CALCULATION
# ══════════════════════════════════════════════════

def get_account_balance(account, as_of_date=None, include_sub_accounts=True):
    """
    Calculate the balance of an account from posted ledger entries.

    For DEBIT-normal accounts (assets, expenses):
        balance = total debits − total credits
        Positive = normal, Negative = unusual

    For CREDIT-normal accounts (liabilities, equity, income):
        balance = total credits − total debits
        Positive = normal, Negative = unusual

    Args:
        account: Account instance
        as_of_date: date (optional) — only include entries on or before this date
        include_sub_accounts: bool — if True, includes all Layer 5+ descendants

    Returns:
        dict: {
            'balance': Decimal (in base currency, signed),
            'foreign_balance': Decimal or None (in account currency, if non-base),
            'total_debit': Decimal (base currency),
            'total_credit': Decimal (base currency),
            'currency': str,
            'base_currency': str,
        }
    """
    filters = Q(company=account.company)

    if include_sub_accounts:
        # Include this account AND all sub-accounts beneath it
        filters &= Q(
            ledger_account__internal_path__startswith=account.internal_path
        )
    else:
        filters &= Q(ledger_account=account)

    if as_of_date:
        filters &= Q(date__lte=as_of_date)

    aggregation = LedgerEntry.objects.filter(filters).aggregate(
        total_debit=Sum(
            Case(
                When(entry_type=EntryTypeChoices.DEBIT, then='base_amount'),
                default=Decimal('0.00'),
                output_field=DecimalField(max_digits=18, decimal_places=2),
            )
        ),
        total_credit=Sum(
            Case(
                When(entry_type=EntryTypeChoices.CREDIT, then='base_amount'),
                default=Decimal('0.00'),
                output_field=DecimalField(max_digits=18, decimal_places=2),
            )
        ),
    )

    total_debit = aggregation['total_debit'] or Decimal('0.00')
    total_credit = aggregation['total_credit'] or Decimal('0.00')

    # Calculate signed balance based on normal balance direction
    if account.normal_balance == 'DEBIT':
        balance = total_debit - total_credit
    else:
        balance = total_credit - total_debit

    # Foreign currency balance (only for non-base-currency accounts)
    foreign_balance = None
    if account.currency != account.company.base_currency:
        foreign_agg = LedgerEntry.objects.filter(
            filters & Q(ledger_account=account)  # Only this account, not subs
        ).aggregate(
            foreign_debit=Sum(
                Case(
                    When(entry_type=EntryTypeChoices.DEBIT, then='amount'),
                    default=Decimal('0.00'),
                    output_field=DecimalField(max_digits=18, decimal_places=2),
                )
            ),
            foreign_credit=Sum(
                Case(
                    When(entry_type=EntryTypeChoices.CREDIT, then='amount'),
                    default=Decimal('0.00'),
                    output_field=DecimalField(max_digits=18, decimal_places=2),
                )
            ),
        )
        fd = foreign_agg['foreign_debit'] or Decimal('0.00')
        fc = foreign_agg['foreign_credit'] or Decimal('0.00')

        if account.normal_balance == 'DEBIT':
            foreign_balance = fd - fc
        else:
            foreign_balance = fc - fd

    return {
        'balance': balance,
        'foreign_balance': foreign_balance,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'currency': account.currency,
        'base_currency': account.company.base_currency,
    }


# ══════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════

def _create_ledger_entry(
    company, account, date, entry_type, amount,
    currency, exchange_rate, note, journal_type,
    source_module, content_type, object_id,
):
    """
    Create a single LedgerEntry with auto-calculated base_amount.

    This is the ONLY function that creates LedgerEntry rows.
    Having a single creation point ensures base_amount is always
    calculated consistently (amount × exchange_rate).
    """
    # If the account currency matches the company base currency,
    # the exchange rate is always 1.0 regardless of what was passed
    if currency == company.base_currency:
        exchange_rate = Decimal('1.000000')

    base_amount = (amount * exchange_rate).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )

    return LedgerEntry.objects.create(
        company=company,
        ledger_account=account,
        date=date,
        entry_type=entry_type,
        amount=amount,
        currency=currency,
        exchange_rate=exchange_rate,
        base_amount=base_amount,
        note=note,
        journal_type=journal_type,
        source_module=source_module,
        content_type=content_type,
        object_id=object_id,
    )


def _validate_journal_data(company, journal_data, lines_data):
    """  
    Validates journal header and lines before creation or posting.

    All validation rules in one place:
        1. Minimum 2 lines required
        2. Each line must have positive amount
        3. Each line must be DEBIT or CREDIT
        4. All accounts must belong to this company
        5. All accounts must be active
        6. Total debits must equal total credits (balanced in base currency)
        7. Transaction date must not be before lock date
        8. Exchange rate must be positive

    Raises:
        ValueError with descriptive message if any rule is violated.
    """
    errors = []

    # Rule 1: Minimum 2 lines
    if len(lines_data) < 2:
        errors.append('A journal entry must have at least 2 lines.')

    # Rule 7: Lock date check
    if company.lock_date and journal_data['date'] <= company.lock_date:
        errors.append(
            f'Transaction date {journal_data["date"]} is on or before '
            f'the lock date ({company.lock_date}). '
            f'Transactions before the lock date are frozen.'
        )

    # Rule 8: Exchange rate must be positive
    exchange_rate = journal_data.get('exchange_rate') or Decimal('1.000000')
    if exchange_rate <= 0:
        errors.append('Exchange rate must be greater than zero.')

    total_debit = Decimal('0.00')
    total_credit = Decimal('0.00')

    for i, line in enumerate(lines_data, start=1):
        # Rule 2: Positive amount
        if line['amount'] <= 0:
            errors.append(f'Line {i}: Amount must be greater than zero.')

        # Rule 3: Valid entry type
        if line['entry_type'] not in ('DEBIT', 'CREDIT'):
            errors.append(f'Line {i}: Entry type must be "DEBIT" or "CREDIT".')

        # Rule 4: Account belongs to this company
        account = line['account']
        if account.company_id != company.id:
            errors.append(
                f'Line {i}: Account "{account.name}" does not belong to this company.'
            )

        # Rule 5: Account must be active
        if not account.is_active:
            errors.append(
                f'Line {i}: Account "{account.name}" is inactive and cannot '
                f'receive new entries. Reactivate it first.'
            )

        # Accumulate totals for balance check (Rule 6)
        line_base = (line['amount'] * exchange_rate).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        if line['entry_type'] == 'DEBIT':
            total_debit += line_base
        else:
            total_credit += line_base

    # Rule 6: Debits must equal credits
    if total_debit != total_credit and not errors:
        diff = abs(total_debit - total_credit)
        errors.append(
            f'Journal is not balanced. '
            f'Total debits: {total_debit}, Total credits: {total_credit}. '
            f'Difference: {diff}.'
        )

    if errors:
        raise ValueError(' | '.join(errors))