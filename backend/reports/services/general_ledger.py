# backend/reports/services/general_ledger.py

"""
General Ledger report generation.

HOW IT DIFFERS FROM OTHER REPORTS:
    Trial Balance:     Summary — one row per account, shows net balance
    Balance Sheet:     Summary — grouped by Asset/Liability/Equity
    Income Statement:  Summary — grouped by Revenue/Expense
    General Ledger:    DETAIL  — every transaction, grouped by account

    This is the only report that queries individual LedgerEntry rows
    rather than aggregating them into a single net figure per account.

STRUCTURE PER ACCOUNT:
    {
        account_id, code, name, normal_balance, ...
        opening_balance:  balance BEFORE from_date
        transactions: [   each LedgerEntry in the period
            { date, entry_type, amount, running_balance, note, ... }
        ]
        total_debit:      sum of DEBIT entries in period
        total_credit:     sum of CREDIT entries in period
        closing_balance:  opening_balance + period_debits − period_credits
    }

RUNNING BALANCE:
    Starts from the opening balance. For each transaction:
        if DEBIT  → running += base_amount
        if CREDIT → running -= base_amount
    The final running balance == closing balance.

    Note: This is a SIGNED running balance (debit − credit perspective).
    A positive value = debit balance, negative = credit balance.
    The view/frontend interprets the sign based on normal_balance.

OPENING BALANCE:
    Uses get_account_balances(company, from_date - 1 day) from
    balance_engine. This gives cumulative (inception → day before period)
    net for each account. One SQL query regardless of account count.

PERIOD TRANSACTIONS:
    Direct query on LedgerEntry filtered by [from_date, to_date].
    Ordered by (date, created_at) for deterministic sort within a day.

OPTIONAL FILTERS:
    - account_id:   Show only one account (useful for drill-down)
    - journal_type: Filter by SALES, PURCHASE, PAYROLL, etc.

PAGINATION:
    The General Ledger can be very large. We paginate at the ACCOUNT
    level — each page contains N complete accounts with all their
    transactions. This keeps the data structure coherent (no account
    split across pages). The view handles pagination using DRF's
    standard paginator on the account list.

CALLED FROM:
    reports/views.py → GeneralLedgerView
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Q

from chartofaccounts.models import Account
from journals.models import LedgerEntry

from .balance_engine import get_account_balances


ZERO = Decimal('0.00')


def generate_general_ledger(company, from_date, to_date,
                             account_id=None, journal_type=None):
    """
    Generate a complete General Ledger report.

    Args:
        company: Company instance
        from_date: datetime.date — start of reporting period (inclusive)
        to_date: datetime.date — end of reporting period (inclusive)
        account_id: UUID or None — filter to a single account
        journal_type: str or None — filter by journal type (e.g. 'SALES')

    Returns:
        dict: {
            'report_title', 'company_name', 'base_currency',
            'from_date', 'to_date',
            'filters': { account_id, journal_type },
            'accounts': [  <-- list of account dicts, ordered by internal_path
                {
                    account_id, code, name, normal_balance, ...,
                    opening_balance, transactions: [...],
                    total_debit, total_credit, closing_balance,
                    net_movement,
                }
            ],
            'account_count',
            'transaction_count',
            'grand_total_debit', 'grand_total_credit',
        }
    """

    # ── Step 1: Determine which accounts to include ──
    # Start with all accounts, optionally filtered to a single account.
    # We'll narrow further based on which accounts have transactions
    # or opening balances in the period.
    account_qs = (
        Account.objects
        .filter(company=company)
        .select_related('classification', 'parent_account')
        .order_by('internal_path')
    )

    if account_id:
        account_qs = account_qs.filter(id=account_id)

    all_accounts = list(account_qs)
    account_map = {a.id: a for a in all_accounts}

    # ── Step 2: Get opening balances (inception → day before from_date) ──
    # One SQL query — returns {account_id: {total_debit, total_credit, net}}
    opening_date = from_date - timedelta(days=1)
    opening_balances = get_account_balances(company, opening_date)

    # ── Step 3: Fetch ALL period transactions ──
    # One query for the entire period. We'll group in Python.
    entry_qs = (
        LedgerEntry.objects
        .filter(
            company=company,
            date__gte=from_date,
            date__lte=to_date,
        )
        .select_related('ledger_account')
        .order_by('date', 'created_at')
    )

    # Apply optional filters
    if account_id:
        entry_qs = entry_qs.filter(ledger_account_id=account_id)

    if journal_type:
        entry_qs = entry_qs.filter(journal_type=journal_type)

    # ── Step 4: Group transactions by account ──
    # {account_id: [LedgerEntry, ...]}
    entries_by_account = {}
    for entry in entry_qs:
        entries_by_account.setdefault(entry.ledger_account_id, []).append(entry)

    # ── Step 5: Determine which accounts appear in the report ──
    # An account appears if it has:
    #   a) At least one transaction in the period, OR
    #   b) A non-zero opening balance (only when no account_id filter)
    #
    # When account_id is specified, always show it even if empty
    # (the user explicitly asked for it).
    accounts_with_transactions = set(entries_by_account.keys())

    if account_id:
        # Always show the requested account
        relevant_account_ids = {a.id for a in all_accounts}
    else:
        # Show accounts that have period transactions
        relevant_account_ids = set(accounts_with_transactions)
        # Also show accounts with non-zero opening balance
        for acct_id, bal in opening_balances.items():
            if bal['net'] != ZERO and acct_id in account_map:
                # Apply journal_type filter consideration:
                # If filtering by journal_type, only show accounts that
                # have matching transactions (opening balance alone isn't enough,
                # since it could come from a different journal type).
                if journal_type:
                    if acct_id in accounts_with_transactions:
                        relevant_account_ids.add(acct_id)
                else:
                    relevant_account_ids.add(acct_id)

    # ── Step 6: Build account detail dicts ──
    account_details = []
    grand_total_debit = ZERO
    grand_total_credit = ZERO
    total_transaction_count = 0

    for account in all_accounts:
        if account.id not in relevant_account_ids:
            continue

        # Opening balance: cumulative net up to (from_date - 1)
        ob = opening_balances.get(account.id)
        opening_net = ob['net'] if ob else ZERO

        # Build transaction rows with running balance
        entries = entries_by_account.get(account.id, [])
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

            transaction_rows.append({
                'entry_id': str(entry.id),
                'date': str(entry.date),
                'entry_type': entry.entry_type,
                'amount': str(entry.amount),
                'currency': entry.currency,
                'exchange_rate': str(entry.exchange_rate),
                'base_amount': str(entry.base_amount),
                'running_balance': str(running),
                'note': entry.note or '',
                'journal_type': entry.journal_type or '',
                'source_module': entry.source_module,
            })

        closing_net = opening_net + period_debit - period_credit
        net_movement = period_debit - period_credit

        # Format opening/closing for display:
        # Positive net = debit balance, negative = credit balance
        account_details.append({
            'account_id': str(account.id),
            'code': account.code,
            'name': account.name,
            'normal_balance': account.normal_balance,
            'currency': account.currency,
            'is_active': account.is_active,
            'is_sub_account': account.is_sub_account,
            'classification_path': account.classification.internal_path,
            'classification_name': account.classification.name,

            # Opening balance (before period)
            'opening_balance': str(opening_net),
            'opening_balance_type': (
                'DEBIT' if opening_net > ZERO
                else 'CREDIT' if opening_net < ZERO
                else 'ZERO'
            ),

            # Period transactions
            'transactions': transaction_rows,
            'transaction_count': len(transaction_rows),

            # Period totals
            'total_debit': str(period_debit),
            'total_credit': str(period_credit),
            'net_movement': str(net_movement),

            # Closing balance (opening + period movement)
            'closing_balance': str(closing_net),
            'closing_balance_type': (
                'DEBIT' if closing_net > ZERO
                else 'CREDIT' if closing_net < ZERO
                else 'ZERO'
            ),
        })

        grand_total_debit += period_debit
        grand_total_credit += period_credit
        total_transaction_count += len(transaction_rows)

    return {
        'report_title': 'General Ledger',
        'company_name': company.name,
        'base_currency': company.base_currency,
        'from_date': str(from_date),
        'to_date': str(to_date),
        'filters': {
            'account_id': str(account_id) if account_id else None,
            'journal_type': journal_type,
        },
        'account_count': len(account_details),
        'transaction_count': total_transaction_count,
        'grand_total_debit': str(grand_total_debit),
        'grand_total_credit': str(grand_total_credit),
        'accounts': account_details,
    }