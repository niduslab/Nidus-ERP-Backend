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

BALANCE FORMULA:
    net = SUM(base_amount WHERE entry_type=DEBIT)
        - SUM(base_amount WHERE entry_type=CREDIT)

    If net > 0 → debit balance
    If net < 0 → credit balance (show abs value)
    If net = 0 → zero balance

    This is purely arithmetic. A Liability account CAN have a debit
    balance (e.g., overpayment). The Trial Balance reflects reality,
    not expectations. The normal_balance field is included in the
    response for the frontend to flag unusual balances if desired.

CALLED BY:
    reports/services/trial_balance.py
    reports/services/balance_sheet.py
    reports/services/income_statement.py
    reports/services/account_statement.py
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

    Performance:
        Single query with GROUP BY. Returns one row per account.
        Typically executes in <50ms for 10,000+ ledger entries.
    """
    # ── Single aggregation query ──
    # Uses conditional SUM to get debit and credit totals in one pass.
    # Django ORM translates this to:
    #   SELECT ledger_account_id,
    #          SUM(CASE WHEN entry_type='DEBIT' THEN base_amount ELSE 0 END),
    #          SUM(CASE WHEN entry_type='CREDIT' THEN base_amount ELSE 0 END)
    #   FROM journals_ledgerentry
    #   WHERE company_id = %s AND date <= %s
    #   GROUP BY ledger_account_id
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

    # ── Build result dict ──
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
    have been used, even if their balance is zero (e.g., an account
    where debits and credits cancel out).

    Args:
        company: Company instance
        as_of_date: datetime.date

    Returns:
        set: set of account_id UUIDs
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