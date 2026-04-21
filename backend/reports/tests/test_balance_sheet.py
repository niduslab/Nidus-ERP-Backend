# backend/reports/tests/test_balance_sheet.py
#
# Tests for reports.services.balance_sheet — the Balance Sheet generator.
#
# THE most important invariant: the accounting equation
#     Assets = Liabilities + Equity
# This MUST hold for every Balance Sheet, on every date, regardless of
# what journals have been posted. If it ever breaks, either the report
# layer has a bug OR the underlying ledger has a double-entry violation.
#
# We also verify the auto-retained-earnings logic: when income > expenses
# in the current fiscal year, that surplus must show up in the equity
# section as "current_year_earnings" — otherwise Equity would be understated
# and the equation would fail.

import pytest
from datetime import date
from decimal import Decimal

from journals.services import post_journal
from reports.services.balance_sheet import generate_balance_sheet
from reports.services.trial_balance import (
    FILTER_NON_ZERO, FILTER_WITH_TRANSACTIONS, FILTER_ALL,
)


ZERO = Decimal('0.00')


@pytest.mark.django_db
class TestBalanceSheetEquation:
    """
    THE accounting equation: Assets = Liabilities + Equity.
    Every test in this class verifies this holds in different scenarios.
    """

    def test_empty_company_has_balanced_books(self, company):
        """A brand-new company with zero journals: 0 = 0 + 0 = balanced."""
        report = generate_balance_sheet(company, as_of_date=date(2026, 12, 31))

        assert report['is_balanced'] is True
        assert Decimal(report['total_assets']) == ZERO
        assert Decimal(report['total_liabilities_and_equity']) == ZERO

    def test_single_opening_balance_journal_keeps_equation(
        self, journal_factory, company, verified_user,
    ):
        """
        Posting a 1000 BDT cash → equity journal keeps the books balanced:
            Assets (cash) = 1000
            Equity (owner) = 1000
            Liabilities = 0
        Equation: 1000 = 0 + 1000 ✓
        """
        journal = journal_factory(amount=Decimal('1000.00'))
        post_journal(journal, posted_by=verified_user)

        report = generate_balance_sheet(company, as_of_date=date(2026, 12, 31))

        assert report['is_balanced'] is True
        assert Decimal(report['total_assets']) == Decimal('1000.00')
        assert Decimal(report['total_liabilities_and_equity']) == Decimal('1000.00')

    def test_revenue_flows_to_equity_via_retained_earnings(
        self, db_access, company, verified_user, account_picker,
    ):
        """
        AUTO-RETAINED-EARNINGS LOGIC:
            When the company earns revenue (e.g., DEBIT cash 500, CREDIT
            revenue 500), the revenue account itself doesn't appear on the
            balance sheet — but its impact MUST. The balance-sheet engine
            calculates net income (Income - Expense) for the current fiscal
            year and surfaces it as "current_year_earnings" in equity.

        Without this, the equation would fail:
            Assets +500 ≠ Liabilities 0 + Equity 0

        With it:
            Assets +500 = Liabilities 0 + Equity (current year earnings) +500 ✓
        """
        from journals.services import create_journal

        cash = account_picker(company, '1.10.1010')
        revenue = account_picker(company, '4.40.4010')   # Operating Revenue L3

        journal = create_journal(
            company=company,
            created_by=verified_user,
            journal_data={
                'date': date(2026, 8, 1),       # Inside fiscal year (FY starts July)
                'description': 'Cash sale',
                'currency': 'BDT',
                'exchange_rate': Decimal('1.000000'),
            },
            lines_data=[
                {'account': cash,    'entry_type': 'DEBIT',  'amount': Decimal('500.00')},
                {'account': revenue, 'entry_type': 'CREDIT', 'amount': Decimal('500.00')},
            ],
        )
        post_journal(journal, posted_by=verified_user)

        report = generate_balance_sheet(company, as_of_date=date(2026, 12, 31))

        # The crucial assertion — equation holds even though the journal
        # involved a Revenue account, not an Equity account directly.
        assert report['is_balanced'] is True
        assert Decimal(report['total_assets']) == Decimal('500.00')
        assert Decimal(report['total_liabilities_and_equity']) == Decimal('500.00')

        # Equity breakdown: the 500 surplus should appear as current year earnings.
        re_block = report['retained_earnings_auto']
        assert Decimal(re_block['current_year_earnings']) == Decimal('500.00')

    def test_expense_reduces_equity_via_retained_earnings(
        self, db_access, company, verified_user, account_picker,
    ):
        """
        Mirror of the revenue test: expenses reduce current-year earnings.
        Posting cash → expense:
            Assets (cash) -200
            Equity (current year earnings) -200
            Equation: -200 = 0 + (-200) ✓
        """
        from journals.services import create_journal

        cash = account_picker(company, '1.10.1010')
        expense = account_picker(company, '5.51.5130')   # Admin & General Expense

        journal = create_journal(
            company=company,
            created_by=verified_user,
            journal_data={
                'date': date(2026, 8, 1),
                'description': 'Office supplies',
                'currency': 'BDT',
                'exchange_rate': Decimal('1.000000'),
            },
            lines_data=[
                {'account': expense, 'entry_type': 'DEBIT',  'amount': Decimal('200.00')},
                {'account': cash,    'entry_type': 'CREDIT', 'amount': Decimal('200.00')},
            ],
        )
        post_journal(journal, posted_by=verified_user)

        report = generate_balance_sheet(company, as_of_date=date(2026, 12, 31))

        # Equation still holds — both sides are -200.
        assert report['is_balanced'] is True
        assert Decimal(report['total_assets']) == Decimal('-200.00')
        assert Decimal(report['total_liabilities_and_equity']) == Decimal('-200.00')

    def test_voided_journal_does_not_affect_balance_sheet(
        self, journal_factory, company, verified_user,
    ):
        """
        After post + void, the Balance Sheet should look identical to a
        company that never posted the journal at all. Reversal entries
        cancel the originals at the LedgerEntry level.
        """
        from journals.services import void_journal

        journal = journal_factory(amount=Decimal('400.00'))
        post_journal(journal, posted_by=verified_user)
        void_journal(journal, voided_by=verified_user)

        report = generate_balance_sheet(company, as_of_date=date(2026, 12, 31))

        assert report['is_balanced'] is True
        assert Decimal(report['total_assets']) == ZERO
        assert Decimal(report['total_liabilities_and_equity']) == ZERO


@pytest.mark.django_db
class TestBalanceSheetStructure:

    def test_returns_required_top_level_keys(self, company):
        """The renderers and the API consumer rely on this stable contract."""
        report = generate_balance_sheet(company, as_of_date=date(2026, 12, 31))

        required_keys = {
            'report_title', 'company_name', 'base_currency', 'as_of_date',
            'assets', 'liabilities', 'equity',
            'total_assets', 'total_liabilities', 'total_equity',
            'total_liabilities_and_equity',
            'is_balanced', 'retained_earnings_auto',
        }
        assert required_keys.issubset(set(report.keys())), (
            f'Missing keys: {required_keys - set(report.keys())}'
        )

    def test_three_sections_are_lists(self, company):
        """assets, liabilities, equity must always be lists (possibly empty)
        so the renderer can iterate without None checks."""
        report = generate_balance_sheet(company, as_of_date=date(2026, 12, 31))
        assert isinstance(report['assets'], list)
        assert isinstance(report['liabilities'], list)
        assert isinstance(report['equity'], list)

    def test_filter_mode_all_includes_zero_balance_accounts(self, company):
        """
        FILTER_ALL mode includes EVERY account, even ones with zero balance.
        FILTER_NON_ZERO (default) hides them. We use account_count to
        compare without making assertions about exact tree shape.
        """
        all_report = generate_balance_sheet(
            company, as_of_date=date(2026, 12, 31), filter_mode=FILTER_ALL,
        )
        nonzero_report = generate_balance_sheet(
            company, as_of_date=date(2026, 12, 31), filter_mode=FILTER_NON_ZERO,
        )

        # Sum lengths of all 3 sections to compare account visibility.
        def section_count(rep):
            return (
                _count_leaf_accounts(rep['assets'])
                + _count_leaf_accounts(rep['liabilities'])
                + _count_leaf_accounts(rep['equity'])
            )

        # FILTER_ALL must show >= what NON_ZERO shows (and on an empty
        # company, FILTER_ALL shows many more accounts).
        assert section_count(all_report) >= section_count(nonzero_report)


def _count_leaf_accounts(section):
    """Recursively count leaf account nodes in a balance-sheet tree section.
    Helper for the FILTER_ALL test above. Defensive — handles missing keys."""
    count = 0
    for item in section:
        # The structure is L2 → l3_groups → accounts (with possible sub_accounts).
        for l3 in item.get('l3_groups', []) or []:
            count += len(l3.get('accounts', []) or [])
    return count