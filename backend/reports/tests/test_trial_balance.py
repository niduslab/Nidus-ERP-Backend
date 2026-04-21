# backend/reports/tests/test_trial_balance.py
#
# Tests the Trial Balance generator. The Trial Balance is the simplest
# report — one row per account with debit/credit columns. Its central
# invariant: total debits = total credits (the "trial" verifies the
# books balance).

import pytest
from datetime import date
from decimal import Decimal

from journals.services import post_journal
from reports.services.trial_balance import generate_trial_balance


ZERO = Decimal('0.00')


@pytest.mark.django_db
class TestTrialBalance:

    def test_empty_company_yields_balanced_zero_totals(self, company):
        report = generate_trial_balance(company, as_of_date=date(2026, 12, 31))
        assert Decimal(report['grand_total_debit']) == ZERO
        assert Decimal(report['grand_total_credit']) == ZERO
        assert report['is_balanced'] is True

    def test_single_journal_appears_with_balanced_totals(
        self, journal_factory, company, verified_user,
    ):
        """
        TRIAL BALANCE INVARIANT: After any balanced journal, the grand
        totals must be equal. This is the most direct verification that
        the double-entry bookkeeping system is intact.
        """
        journal = journal_factory(amount=Decimal('750.00'))
        post_journal(journal, posted_by=verified_user)

        report = generate_trial_balance(company, as_of_date=date(2026, 12, 31))

        assert Decimal(report['grand_total_debit']) == Decimal('750.00')
        assert Decimal(report['grand_total_credit']) == Decimal('750.00')
        assert report['is_balanced'] is True

    def test_voided_journal_zeros_out_trial_balance(
        self, journal_factory, company, verified_user,
    ):
        """Post + void → grand totals back to 0, still balanced."""
        from journals.services import void_journal
        journal = journal_factory(amount=Decimal('500.00'))
        post_journal(journal, posted_by=verified_user)
        void_journal(journal, voided_by=verified_user)

        report = generate_trial_balance(company, as_of_date=date(2026, 12, 31))
        assert Decimal(report['grand_total_debit']) == ZERO
        assert Decimal(report['grand_total_credit']) == ZERO
        assert report['is_balanced'] is True

    def test_returns_required_keys(self, company):
        """Stable response contract for the renderer + API consumers."""
        report = generate_trial_balance(company, as_of_date=date(2026, 12, 31))
        required_keys = {
            'report_title', 'company_name', 'base_currency', 'as_of_date',
            'groups', 'flat_accounts',
            'grand_total_debit', 'grand_total_credit', 'is_balanced',
        }
        assert required_keys.issubset(set(report.keys()))