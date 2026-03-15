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
    """
    Calculate tax for each layer in a tax profile.
    Supports mixed INDEPENDENT and COMPOUND layers in any order.

    Args:
        tax_profile: TaxProfile instance (with .layers prefetched)
        base_amount: Decimal — the pre-tax amount

    Returns:
        list of dicts, one per layer:
        [{'layer': TaxProfileLayer, 'tax_amount': Decimal, 'taxable_amount': Decimal}]
    """
    layers = tax_profile.layers.order_by('apply_order')
    results = []
    running_total = base_amount

    for layer in layers:
        if layer.calculation_type == 'INDEPENDENT':
            taxable_amount = base_amount
        else:
            taxable_amount = running_total

        tax_amount = (taxable_amount * layer.rate / Decimal('100')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        results.append({
            'layer': layer,
            'tax_amount': tax_amount,
            'taxable_amount': taxable_amount,
        })

        running_total += tax_amount

    return results


# ══════════════════════════════════════════════════
# CREATE JOURNAL (DRAFT)
# ══════════════════════════════════════════════════

def create_journal(company, created_by, journal_data, lines_data):
    """
    Create a new manual journal entry as DRAFT.
    Drafts do NOT create ledger entries.
    """
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
    """
    if journal.status != JournalStatusChoices.DRAFT:
        raise ValueError(
            f'Only draft journal entries can be posted. '
            f'This entry ({journal.entry_number}) has status: {journal.get_status_display()}.'
        )

    # Re-validate before posting
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
            # FIX: Pass journal.currency, not line.account.currency.
            # The ledger entry stores the amount in the journal's currency
            # and converts to base currency using the journal's exchange rate.
            _create_ledger_entry(
                company=journal.company,
                account=line.account,
                date=journal.date,
                entry_type=line.entry_type,
                amount=line.amount,
                currency=journal.currency,
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

                    _create_ledger_entry(
                        company=journal.company,
                        account=layer.default_tax_account,
                        date=journal.date,
                        entry_type=line.entry_type,
                        amount=tax_result['tax_amount'],
                        currency=journal.currency,
                        exchange_rate=journal.exchange_rate,
                        note=f"{layer.name} ({layer.rate}%) on {line.account.name}",
                        journal_type=journal.journal_type,
                        source_module=SourceModuleChoices.MANUAL_JOURNAL,
                        content_type=journal_line_ct,
                        object_id=line.id,
                    )

        journal.status = JournalStatusChoices.POSTED
        journal.posted_at = timezone.now()
        journal.save(update_fields=['status', 'posted_at', 'updated_at'])

    return journal


# ══════════════════════════════════════════════════
# VOID JOURNAL (POSTED → VOID)
# ══════════════════════════════════════════════════

def void_journal(journal, voided_by, void_date=None):
    """
    Void a posted journal — creates an automatic reversing entry.
    The reversing entry gets status REVERSAL (not POSTED) so users
    can identify system-generated entries.
    """
    if journal.status != JournalStatusChoices.POSTED:
        raise ValueError(
            f'Only posted journal entries can be voided. '
            f'This entry ({journal.entry_number}) has status: {journal.get_status_display()}.'
        )

    if journal.company.lock_date and journal.date <= journal.company.lock_date:
        raise ValueError(
            f'This journal entry cannot be voided because the company lock date is {journal.company.lock_date}. '
            f'Void operations are not allowed on or before the lock date.'
            f'Or the transaction date ({journal.date} is on or before the lock date ({journal.company.lock_date}).) '
            f'Transactions before the lock date are frozen.'
        )

    if void_date is None:
        void_date = timezone.now().date()

    if journal.company.lock_date and void_date <= journal.company.lock_date:
        raise ValueError(
            f'Cannot create a reversing entry on {void_date}. '
            f'This date is on or before the lock date ({journal.company.lock_date}). '
            f'Choose a date after {journal.company.lock_date}.'
        )

    with transaction.atomic():
        reversal_number = generate_entry_number(journal.company)

        # Reversing entry gets REVERSAL status — not POSTED.
        # This lets users filter out system-generated entries.
        reversal = ManualJournal.objects.create(
            company=journal.company,
            entry_number=reversal_number,
            date=void_date,
            description=f"Reversal of {journal.entry_number}",
            reference=journal.reference,
            journal_type=journal.journal_type,
            status=JournalStatusChoices.REVERSAL,
            currency=journal.currency,
            exchange_rate=journal.exchange_rate,
            reversal_of=journal,
            posted_at=timezone.now(),
            created_by=voided_by,
        )

        # Create reversed lines (swap debit ↔ credit)
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

        # Post the reversal's ledger entries
        journal_line_ct = ContentType.objects.get_for_model(ManualJournalLine)

        for line in reversal.lines.select_related('account', 'tax_profile'):
            _create_ledger_entry(
                company=reversal.company,
                account=line.account,
                date=reversal.date,
                entry_type=line.entry_type,
                amount=line.amount,
                currency=reversal.currency,
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
                        currency=reversal.currency,
                        exchange_rate=reversal.exchange_rate,
                        note=f"Reversal: {layer.name} ({layer.rate}%)",
                        journal_type=reversal.journal_type,
                        source_module=SourceModuleChoices.MANUAL_JOURNAL,
                        content_type=journal_line_ct,
                        object_id=line.id,
                    )

        # Mark original as VOID
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
    if journal.status != JournalStatusChoices.DRAFT:
        raise ValueError(
            f'Only draft journal entries can be deleted. '
            f'This entry ({journal.entry_number}) has status: {journal.get_status_display()}. '
            f'Posted entries must be voided, not deleted.'
        )
    journal.delete()


# ══════════════════════════════════════════════════
# UPDATE JOURNAL (DRAFT ONLY)
# ══════════════════════════════════════════════════

def update_journal(journal, journal_data=None, lines_data=None):
    if journal.status != JournalStatusChoices.DRAFT:
        raise ValueError(
            f'Only draft journal entries can be edited. '
            f'This entry ({journal.entry_number}) has status: {journal.get_status_display()}.'
        )

    with transaction.atomic():
        if journal_data:
            update_fields = ['updated_at']
            for field in ['date', 'description', 'reference', 'journal_type',
                          'currency', 'exchange_rate']:
                if field in journal_data:
                    setattr(journal, field, journal_data[field])
                    update_fields.append(field)
            journal.save(update_fields=update_fields)

        if lines_data is not None:
            j_data = {
                'date': journal.date,
                'description': journal.description,
                'currency': journal.currency,
                'exchange_rate': journal.exchange_rate,
            }
            _validate_journal_data(journal.company, j_data, lines_data)

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
    """
    filters = Q(company=account.company)

    if include_sub_accounts:
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

    if account.normal_balance == 'DEBIT':
        balance = total_debit - total_credit
    else:
        balance = total_credit - total_debit

    # Foreign currency balance (only for non-base-currency accounts)
    foreign_balance = None
    if account.currency != account.company.base_currency:
        foreign_agg = LedgerEntry.objects.filter(
            filters & Q(ledger_account=account)
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

    CURRENCY LOGIC:
        The 'currency' parameter is the JOURNAL's currency — what the
        amount is denominated in. The exchange_rate converts from this
        currency to the company's base currency.

        - Journal in BDT (base): currency=BDT, rate=1.0, base_amount=amount
        - Journal in USD:        currency=USD, rate=120, base_amount=amount×120
    """
    # If the journal currency IS the base currency, rate is always 1.0
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
    """
    errors = []

    if len(lines_data) < 2:
        errors.append('A journal entry requires at least 2 lines.')

    if company.lock_date and journal_data['date'] <= company.lock_date:
        errors.append(
            f'Transaction date {journal_data["date"]} is on or before '
            f'the lock date ({company.lock_date}). '
            f'Transactions before the lock date are frozen.'
        )

    exchange_rate = journal_data.get('exchange_rate', Decimal('1.000000'))
    if exchange_rate is not None and exchange_rate <= 0:
        errors.append('Exchange rate must be greater than zero.')

    total_debit = Decimal('0.00')
    total_credit = Decimal('0.00')

    for i, line in enumerate(lines_data, start=1):
        if line['amount'] <= 0:
            errors.append(f'Line {i}: Amount must be greater than zero.')

        if line['entry_type'] not in ('DEBIT', 'CREDIT'):
            errors.append(f'Line {i}: Entry type must be "DEBIT" or "CREDIT".')

        account = line['account']
        if account.company_id != company.id:
            errors.append(
                f'Line {i}: Account "{account.name}" does not belong to this company.'
            )

        if not account.is_active:
            errors.append(
                f'Line {i}: Account "{account.name}" is inactive. '
                f'Reactivate it first or choose an active account.'
            )

        if exchange_rate and exchange_rate > 0:
            line_base = (line['amount'] * exchange_rate).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            if line['entry_type'] == 'DEBIT':
                total_debit += line_base
            else:
                total_credit += line_base

    if total_debit != total_credit and not errors:
        diff = abs(total_debit - total_credit)
        errors.append(
            f'Journal is not balanced. '
            f'Total debits: {total_debit}, Total credits: {total_credit}. '
            f'Difference: {diff}.'
        )

    if errors:
        raise ValueError(' | '.join(errors))