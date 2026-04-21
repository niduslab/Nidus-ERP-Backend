# backend/journals/tests/test_balance_engine.py
#
# Tests for reports.services.balance_engine — the SQL aggregation function
# that powers ALL six financial reports (Trial Balance, Balance Sheet,
# Income Statement, General Ledger, Account Transactions, Cash Flow).
#
# A bug here = wrong numbers in every report. So we test it heavily and
# in isolation from the report-rendering layers.

import pytest
from datetime import date, timedelta
from decimal import Decimal

from journals.models import LedgerEntry
from journals.services import post_journal, void_journal
from reports.services.balance_engine import (
    get_account_balances,
    get_period_balances,
    get_accounts_with_transactions,
)


ZERO = Decimal('0.00')


@pytest.mark.django_db
class TestGetAccountBalances:
    """
    get_account_balances(company, as_of_date) → cumulative net balance
    per account from inception through as_of_date (inclusive).
    """

    def test_returns_empty_dict_when_no_entries(self, company):
        """No ledger entries → empty dict (NOT a dict of zeros)."""
        result = get_account_balances(company, date(2026, 12, 31))
        assert result == {}

    def test_single_journal_appears_correctly(
        self, journal_factory, company, verified_user, account_picker,
    ):
        """
        After posting one balanced journal, both involved accounts should
        appear in the result with net values that mirror each other
        (positive on the debit side, negative on the credit side).
        """
        cash = account_picker(company, '1.10.1010')
        equity = account_picker(company, '3.30.3010')

        journal = journal_factory(amount=Decimal('500.00'))
        post_journal(journal, posted_by=verified_user)

        balances = get_account_balances(company, date(2026, 12, 31))

        assert cash.id in balances
        assert equity.id in balances

        # Cash was DEBITed → net is +500
        assert balances[cash.id]['net'] == Decimal('500.00')
        # Equity was CREDITed → net is -500
        assert balances[equity.id]['net'] == Decimal('-500.00')

    def test_balances_sum_to_zero_across_all_accounts(
        self, journal_factory, company, verified_user,
    ):
        """
        TRIAL-BALANCE INVARIANT: For any company, sum of net balances across
        ALL accounts must equal zero. This is the database expression of
        "total debits = total credits". If it ever fails, the trial
        balance is broken.
        """
        # Post 3 unrelated journals to exercise the sum.
        for amount in [Decimal('100.00'), Decimal('250.00'), Decimal('999.99')]:
            j = journal_factory(amount=amount)
            post_journal(j, posted_by=verified_user)

        balances = get_account_balances(company, date(2026, 12, 31))
        total = sum((b['net'] for b in balances.values()), ZERO)
        assert total == ZERO, (
            f'Trial balance invariant violation: net sum = {total}, '
            f'should be 0. Either a journal posted unbalanced lines, '
            f'or balance_engine has an aggregation bug.'
        )

    def test_excludes_entries_after_as_of_date(
        self, journal_factory, company, verified_user, account_picker,
    ):
        """
        as_of_date is INCLUSIVE on its date but excludes anything after.
        A balance "as of 2026-04-01" must not include a 2026-04-02 entry.
        """
        cash = account_picker(company, '1.10.1010')

        # Two journals: one inside the range, one after.
        j1 = journal_factory(
            amount=Decimal('100.00'),
            journal_date=date(2026, 4, 1),
        )
        post_journal(j1, posted_by=verified_user)

        j2 = journal_factory(
            amount=Decimal('200.00'),
            journal_date=date(2026, 4, 2),
        )
        post_journal(j2, posted_by=verified_user)

        # Query "as of April 1" — should only see j1's 100.
        balances = get_account_balances(company, date(2026, 4, 1))
        assert balances[cash.id]['net'] == Decimal('100.00')

        # Query "as of April 2" — should see both → 300.
        balances = get_account_balances(company, date(2026, 4, 2))
        assert balances[cash.id]['net'] == Decimal('300.00')

    def test_voided_journal_nets_to_zero_in_balances(
        self, journal_factory, company, verified_user, account_picker,
    ):
        """
        After post + void, the affected account's net per balance_engine
        must be 0 — proving the report layer correctly ignores voided
        activity (because the reversal cancels it out at the LedgerEntry
        level, not by filtering).
        """
        cash = account_picker(company, '1.10.1010')

        journal = journal_factory(amount=Decimal('400.00'))
        post_journal(journal, posted_by=verified_user)
        void_journal(journal, voided_by=verified_user)

        balances = get_account_balances(company, date(2026, 12, 31))
        # Account may or may not appear in result depending on whether the
        # zero-net account is included. If absent, treat as 0.
        net = balances.get(cash.id, {'net': ZERO})['net']
        assert net == ZERO


@pytest.mark.django_db
class TestGetPeriodBalances:
    """
    get_period_balances(company, from_date, to_date) → net activity within
    a date range (NOT cumulative). Used by the Income Statement.
    """

    def test_returns_only_period_activity(
        self, journal_factory, company, verified_user, account_picker,
    ):
        """
        Activity outside [from_date, to_date] is excluded. Cumulative-to-
        date balances should NOT bleed into period results.
        """
        cash = account_picker(company, '1.10.1010')

        # Post two journals — only the second one is "in period".
        j1 = journal_factory(
            amount=Decimal('100.00'), journal_date=date(2026, 1, 1),
        )
        post_journal(j1, posted_by=verified_user)

        j2 = journal_factory(
            amount=Decimal('250.00'), journal_date=date(2026, 4, 15),
        )
        post_journal(j2, posted_by=verified_user)

        period = get_period_balances(
            company,
            from_date=date(2026, 4, 1),
            to_date=date(2026, 4, 30),
        )

        # Only j2's activity counts → 250 (the cash side, debit-positive)
        assert period[cash.id]['net'] == Decimal('250.00')


@pytest.mark.django_db
class TestGetAccountsWithTransactions:

    def test_returns_only_accounts_that_were_used(
        self, journal_factory, company, verified_user, account_picker,
    ):
        """
        Accounts that have at least one ledger entry (even a reversed one)
        appear in the set; untouched accounts do not. Used by report
        filter_mode='with_transactions'.
        """
        cash = account_picker(company, '1.10.1010')
        equity = account_picker(company, '3.30.3010')
        # An untouched account — should NOT be in the result.
        receivable = account_picker(company, '1.10.1060')

        j = journal_factory()
        post_journal(j, posted_by=verified_user)

        used = get_accounts_with_transactions(company, date(2026, 12, 31))
        assert cash.id in used
        assert equity.id in used
        assert receivable.id not in used