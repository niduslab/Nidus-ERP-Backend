# backend/journals/tests/test_account_balance_utility.py
#
# Tests for journals.services.get_account_balance — the per-account balance
# utility that powers GET /api/companies/<id>/accounts/<aid>/balance/
#
# This is a different function from balance_engine.get_account_balances:
#   balance_engine.get_account_balances → bulk, all accounts at once
#   journals.get_account_balance        → one account, with foreign-currency
#                                         decomposition and sub-account roll-up

import pytest
from datetime import date
from decimal import Decimal

from journals.services import get_account_balance, post_journal


ZERO = Decimal('0.00')


@pytest.mark.django_db
class TestGetAccountBalance:

    def test_zero_balance_when_no_entries(self, company, account_picker):
        """An account with no ledger entries → balance is 0, not None."""
        cash = account_picker(company, '1.10.1010')
        result = get_account_balance(cash)

        assert result['balance'] == ZERO
        assert result['total_debit'] == ZERO
        assert result['total_credit'] == ZERO
        # Cash is in BDT (base currency) so foreign_balance must be None.
        assert result['foreign_balance'] is None

    def test_debit_normal_account_shows_positive_for_debit_balance(
        self, journal_factory, company, verified_user, account_picker,
    ):
        """
        Cash is a DEBIT-normal account. After a 500 DEBIT, its balance
        should be +500 (not -500). The function flips signs based on
        normal_balance so the displayed value matches accounting intuition.
        """
        cash = account_picker(company, '1.10.1010')
        j = journal_factory(amount=Decimal('500.00'))
        post_journal(j, posted_by=verified_user)

        result = get_account_balance(cash)
        assert result['balance'] == Decimal('500.00')
        assert result['total_debit'] == Decimal('500.00')
        assert result['total_credit'] == ZERO

    def test_credit_normal_account_shows_positive_for_credit_balance(
        self, journal_factory, company, verified_user, account_picker,
    ):
        """
        Equity is a CREDIT-normal account. After a 500 CREDIT, its balance
        should be displayed as +500 (intuitive — equity went up by 500),
        not -500.

        This is the function's whole point: a balance sheet showing equity
        as -500 would be unreadable. The view-side sign flip happens here.
        """
        equity = account_picker(company, '3.30.3010')
        j = journal_factory(amount=Decimal('500.00'))
        post_journal(j, posted_by=verified_user)

        result = get_account_balance(equity)
        assert result['balance'] == Decimal('500.00')   # NOT -500
        assert result['total_credit'] == Decimal('500.00')

    def test_excludes_entries_after_as_of_date(
        self, journal_factory, company, verified_user, account_picker,
    ):
        """as_of_date kwarg must filter out later entries."""
        cash = account_picker(company, '1.10.1010')

        j1 = journal_factory(
            amount=Decimal('100.00'), journal_date=date(2026, 1, 1),
        )
        post_journal(j1, posted_by=verified_user)
        j2 = journal_factory(
            amount=Decimal('200.00'), journal_date=date(2026, 6, 1),
        )
        post_journal(j2, posted_by=verified_user)

        # Only j1 should count "as of March 1".
        result = get_account_balance(cash, as_of_date=date(2026, 3, 1))
        assert result['balance'] == Decimal('100.00')

    def test_balance_zero_after_post_and_void(
        self, journal_factory, company, verified_user, account_picker,
    ):
        """
        Confirms void integrates correctly with the per-account balance
        utility — the API endpoint /api/.../balance/ correctly hides
        voided activity (because the reversal entries cancel it).
        """
        from journals.services import void_journal

        cash = account_picker(company, '1.10.1010')
        j = journal_factory(amount=Decimal('400.00'))
        post_journal(j, posted_by=verified_user)
        void_journal(j, voided_by=verified_user)

        result = get_account_balance(cash)
        assert result['balance'] == ZERO