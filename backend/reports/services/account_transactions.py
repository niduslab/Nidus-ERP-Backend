# backend/reports/services/account_transactions.py

"""
Account Transactions report generation.

THIS IS THE DRILL-DOWN REPORT. When a user clicks an account name in
Trial Balance, Balance Sheet, P&L, or General Ledger, they land here.
Zoho Books calls it "Account Transactions".

HOW IT DIFFERS FROM OTHER REPORTS:
    General Ledger:       ALL accounts, grouped, paginated at account level
    Account Transactions: ONE account, all entries, no pagination, richer data

    This report is specifically designed for viewing a single account's
    complete transaction history within a date range. It includes source
    journal references (entry_number, description, reference) which the
    General Ledger omits for performance (it loads all accounts at once).

STRUCTURE:
    {
        account: { id, code, name, normal_balance, ... },
        opening_balance, opening_balance_type,
        transactions: [
            {
                date, entry_type, amount, base_amount,
                running_balance,
                source_number, source_description, source_reference, source_id,
                journal_type, source_module, note,
            },
            ...
        ],
        total_debit, total_credit, net_movement,
        closing_balance, closing_balance_type,
        transaction_count,
    }

NO PAGINATION:
    All entries within the date range are returned in a single response.
    This matches Zoho Books' behaviour. With date range filtering, the
    data volume is naturally bounded. Even 10,000 entries (~1.5 MB JSON)
    is handled comfortably by modern clients.

    Pagination would break the running balance chain — each page would
    need a "page opening balance" workaround, adding complexity for no
    real user benefit.

SOURCE DOCUMENT REFERENCES:
    Each LedgerEntry traces back to its source document line via
    GenericFK (content_type + object_id). Currently all entries come
    from ManualJournalLine. We batch-fetch the source lines and their
    parent documents in 1 extra query to get:
        - source_number (e.g., "JE-0001", "INV-0001")
        - source_description (header-level description)
        - source_reference (external ref like invoice number)
        - source_id (UUID of the source document header)

    The source_module field on LedgerEntry tells the frontend what
    type of document it is (MANUAL_JOURNAL, SALES_INVOICE, etc.),
    so the frontend can build the correct drill-down URL from
    source_module + source_id.

    When future modules (Sales, Purchase, Expense) are added, their
    source document lines will also be traced here using the same
    GenericFK pattern — just add their ContentType to the lookup.

QUERY COUNT: 3 total (regardless of transaction count)
    1. get_account_balances() for opening balance
    2. LedgerEntry.objects.filter() for period transactions
    3. ManualJournalLine.objects.filter() for source document references

CALLED FROM:
    reports/views.py → AccountTransactionsView
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType

from chartofaccounts.models import Account
from journals.models import LedgerEntry, ManualJournalLine

from .balance_engine import get_account_balances


ZERO = Decimal('0.00')


def generate_account_transactions(company, account, from_date, to_date):
    """
    Generate a complete Account Transactions report for a single account.

    Args:
        company: Company instance
        account: Account instance (already validated and fetched by the view)
        from_date: datetime.date — start of reporting period (inclusive)
        to_date: datetime.date — end of reporting period (inclusive)

    Returns:
        dict: Complete Account Transactions data ready for API response
    """

    # ── Step 1: Opening balance (inception → day before from_date) ──
    # One SQL query — returns {account_id: {total_debit, total_credit, net}}
    opening_date = from_date - timedelta(days=1)
    opening_balances = get_account_balances(company, opening_date)

    ob = opening_balances.get(account.id)
    opening_net = ob['net'] if ob else ZERO

    # ── Step 2: Fetch ALL period transactions for this account ──
    # One SQL query with select_related for the account FK.
    # No pagination — all entries returned (matches Zoho Books behaviour).
    entries = list(
        LedgerEntry.objects
        .filter(
            company=company,
            ledger_account=account,
            date__gte=from_date,
            date__lte=to_date,
        )
        .order_by('date', 'created_at')
    )

    # ── Step 3: Batch-fetch source journal references ──
    # Each LedgerEntry has a GenericFK (content_type + object_id)
    # pointing to ManualJournalLine. We batch-fetch the lines and
    # their parent journals to get entry_number, description, reference.
    #
    # This is 1 extra query instead of N queries (one per entry).
    source_map = _build_source_journal_map(entries)

    # ── Step 4: Build transaction rows with running balance ──
    running = opening_net
    period_debit = ZERO
    period_credit = ZERO
    transaction_rows = []

    for entry in entries:
        # Update running balance
        if entry.entry_type == 'DEBIT':
            running += entry.base_amount
            period_debit += entry.base_amount
        else:
            running -= entry.base_amount
            period_credit += entry.base_amount

        # Lookup source journal info
        source = source_map.get(entry.object_id, {})

        transaction_rows.append({
            'entry_id': str(entry.id),
            'date': str(entry.date),
            'entry_type': entry.entry_type,
            'debit': str(entry.base_amount) if entry.entry_type == 'DEBIT' else None,
            'credit': str(entry.base_amount) if entry.entry_type == 'CREDIT' else None,
            'amount': str(entry.amount),
            'currency': entry.currency,
            'exchange_rate': str(entry.exchange_rate),
            'base_amount': str(entry.base_amount),
            'running_balance': str(running),
            'note': entry.note or '',

            # Source document references
            'source_number': source.get('entry_number', ''),
            'source_description': source.get('description', ''),
            'source_reference': source.get('reference', ''),
            'source_id': source.get('source_id', ''),

            # Classification fields
            'journal_type': entry.journal_type or '',
            'source_module': entry.source_module,
        })

    # ── Step 5: Calculate closing balance ──
    closing_net = opening_net + period_debit - period_credit
    net_movement = period_debit - period_credit

    return {
        'report_title': 'Account Transactions',
        'company_name': company.name,
        'base_currency': company.base_currency,
        'from_date': str(from_date),
        'to_date': str(to_date),

        # ── Account info ──
        'account': {
            'id': str(account.id),
            'code': account.code,
            'name': account.name,
            'normal_balance': account.normal_balance,
            'currency': account.currency,
            'is_active': account.is_active,
            'is_sub_account': account.is_sub_account,
            'classification_path': account.classification.internal_path,
            'classification_name': account.classification.name,
        },

        # ── Opening balance ──
        'opening_balance': str(opening_net),
        'opening_balance_type': (
            'DEBIT' if opening_net > ZERO
            else 'CREDIT' if opening_net < ZERO
            else 'ZERO'
        ),

        # ── Transactions (no pagination) ──
        'transactions': transaction_rows,
        'transaction_count': len(transaction_rows),

        # ── Period totals ──
        'total_debit': str(period_debit),
        'total_credit': str(period_credit),
        'net_movement': str(net_movement),

        # ── Closing balance ──
        'closing_balance': str(closing_net),
        'closing_balance_type': (
            'DEBIT' if closing_net > ZERO
            else 'CREDIT' if closing_net < ZERO
            else 'ZERO'
        ),
    }


# ══════════════════════════════════════════════════
# SOURCE JOURNAL REFERENCE LOOKUP
# ══════════════════════════════════════════════════

def _build_source_journal_map(entries):
    """
    Batch-fetch source journal header info for a list of LedgerEntries.

    Currently all LedgerEntries originate from ManualJournalLine.
    We collect the object_ids (ManualJournalLine PKs), fetch them
    with select_related('journal'), and build a lookup dict.

    When future modules (Sales Invoice, Purchase Bill, etc.) are added,
    each will have its own ContentType. We'll extend this function to
    handle multiple content types by grouping entries by content_type_id
    and fetching each source model separately.

    Args:
        entries: list of LedgerEntry instances

    Returns:
        dict: {object_id (UUID): {
            'entry_number': str,
            'description': str,
            'reference': str or '',
            'source_id': str,
        }}
    """
    if not entries:
        return {}

    # ── Collect ManualJournalLine IDs ──
    # Group by content_type to be future-proof.
    # Currently only MANUAL_JOURNAL exists, but this pattern scales.
    manual_journal_ct = ContentType.objects.get_for_model(ManualJournalLine)

    manual_line_ids = [
        entry.object_id
        for entry in entries
        if entry.content_type_id == manual_journal_ct.id
    ]

    source_map = {}

    if manual_line_ids:
        # ── One query: fetch lines + their parent journals ──
        lines = (
            ManualJournalLine.objects
            .filter(id__in=manual_line_ids)
            .select_related('journal')
            .only(
                'id',
                'journal__id',
                'journal__entry_number',
                'journal__description',
                'journal__reference',
            )
        )

        for line in lines:
            source_map[line.id] = {
                'entry_number': line.journal.entry_number,
                'description': line.journal.description,
                'reference': line.journal.reference or '',
                'source_id': str(line.journal.id),
            }

    # ── Future: Add similar blocks for InvoiceLine, BillLine, etc. ──
    # invoice_ct = ContentType.objects.get_for_model(InvoiceLine)
    # invoice_line_ids = [e.object_id for e in entries if e.content_type_id == invoice_ct.id]
    # ...

    return source_map