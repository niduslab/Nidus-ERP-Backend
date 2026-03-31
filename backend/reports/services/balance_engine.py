# backend/reports/services/balance_engine.py
"""
Shared balance calculation engine for all financial reports.

THIS IS THE SINGLE SOURCE OF TRUTH for account balance calculations.
Every report (Trial Balance, Balance Sheet, Income Statement, General
Ledger, Account Statement, Cash Flow) calls this module.

DESIGN PRINCIPLES:
    1. One SQL query per date — no N+1 queries regardless of account count.
    2. Always uses base_amount — multi-currency is already converted.
    3. Returns raw data — formatting/grouping is the caller's job.
    4. Stateless — no caching, no side effects, pure functions.
    5. NEVER filters by is_active — inactive accounts may hold balances
       that are critical for accurate financial reporting. Deactivation
       only prevents NEW journal entries; it must never hide existing
       balances from reports.

BALANCE FORMULA:
    net = SUM(base_amount WHERE entry_type=DEBIT)
        - SUM(base_amount WHERE entry_type=CREDIT)

    If net > 0 → debit balance
    If net < 0 → credit balance (show abs value)
    If net = 0 → zero balance

CALLED BY:
    reports/services/trial_balance.py
    reports/services/balance_sheet.py
    reports/services/income_statement.py
    (future) reports/services/account_statement.py
"""

from decimal import Decimal

from django.db.models import Sum, Case, When, Value, DecimalField

from journals.models import LedgerEntry


def get_account_balances(company, as_of_date):
    """
    Calculate the net balance for every account that has ledger entries
    on or before as_of_date.

    Args:
        company: Company instance
        as_of_date: datetime.date — include all entries up to and
                    including this date

    Returns:
        dict: {account_id (UUID): {
            'total_debit': Decimal,
            'total_credit': Decimal,
            'net': Decimal,   # positive = debit balance, negative = credit balance
        }}

    """
    # ── Single aggregation query ──
    aggregated = (
        LedgerEntry.objects
        .filter(
            company=company,
            date__lte=as_of_date,
        )
        .values('ledger_account_id')
        .annotate(
            total_debit=Sum(
                Case(
                    When(entry_type='DEBIT', then='base_amount'),
                    default=Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                )
            ),
            total_credit=Sum(
                Case(
                    When(entry_type='CREDIT', then='base_amount'),
                    default=Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                )
            ),
        )
    )

    balances = {}
    for row in aggregated:
        total_debit = row['total_debit'] or Decimal('0.00')
        total_credit = row['total_credit'] or Decimal('0.00')
        net = total_debit - total_credit

        balances[row['ledger_account_id']] = {
            'total_debit': total_debit,
            'total_credit': total_credit,
            'net': net,
        }

    return balances


def get_accounts_with_transactions(company, as_of_date):
    """
    Return the set of account IDs that have at least one ledger entry
    on or before as_of_date.

    Used by the 'with_transactions' filter mode — show accounts that
    have been used, even if their balance is zero (e.g., voided).
    """
    return set(
        LedgerEntry.objects
        .filter(
            company=company,
            date__lte=as_of_date,
        )
        .values_list('ledger_account_id', flat=True)
        .distinct()
    )


# ══════════════════════════════════════════════════
# PERIOD-BASED FUNCTIONS 
# ══════════════════════════════════════════════════

def get_period_balances(company, from_date, to_date):
    """
    Calculate the net activity for every account WITHIN a date range.

    Unlike get_account_balances() which is cumulative (inception to date),
    this returns only the movement during [from_date, to_date].

    This is critical for the Income Statement (P&L), which reports
    revenue earned and expenses incurred during a specific period —
    not cumulative from inception.

    IMPLEMENTATION:
        Single SQL query with a date range filter. This is more
        efficient than the subtraction approach (cumulative_to - cumulative_before)
        used in balance_sheet._calculate_net_income(), because:
        1. One query instead of two
        2. The DB handles the date filtering natively
        3. Result dict is identical in shape to get_account_balances()

    Args:
        company: Company instance
        from_date: datetime.date — start of period (inclusive)
        to_date: datetime.date — end of period (inclusive)

    Returns:
        dict: {account_id (UUID): {
            'total_debit': Decimal,
            'total_credit': Decimal,
            'net': Decimal,  # positive = net debit, negative = net credit
        }}
    """
    # ── Single aggregation query scoped to the period ──
    aggregated = (
        LedgerEntry.objects
        .filter(
            company=company,
            date__gte=from_date,
            date__lte=to_date,
        )
        .values('ledger_account_id')
        .annotate(
            total_debit=Sum(
                Case(
                    When(entry_type='DEBIT', then='base_amount'),
                    default=Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                )
            ),
            total_credit=Sum(
                Case(
                    When(entry_type='CREDIT', then='base_amount'),
                    default=Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                )
            ),
        )
    )

    balances = {}
    for row in aggregated:
        total_debit = row['total_debit'] or Decimal('0.00')
        total_credit = row['total_credit'] or Decimal('0.00')
        net = total_debit - total_credit

        balances[row['ledger_account_id']] = {
            'total_debit': total_debit,
            'total_credit': total_credit,
            'net': net,
        }

    return balances


def get_accounts_with_transactions_in_period(company, from_date, to_date):
    """
    Return the set of account IDs that have at least one ledger entry
    within [from_date, to_date].
 
    Period-scoped counterpart of get_accounts_with_transactions().
    Used by Income Statement's 'with_transactions' filter mode.
    """
    return set(
        LedgerEntry.objects
        .filter(
            company=company,
            date__gte=from_date,
            date__lte=to_date,
        )
        .values_list('ledger_account_id', flat=True)
        .distinct()
    )
 