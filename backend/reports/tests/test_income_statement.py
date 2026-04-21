# backend/reports/tests/test_income_statement.py
#
# Tests for reports.services.income_statement — the P&L generator.
#
# Critical invariants:
#   1. Net Income = Revenue - Expenses (in signed terms after all sections)
#   2. Gross Profit = Operating Income - COGS
#   3. Operating Profit = Gross Profit - Operating Expenses
#   4. Net Income = Operating Profit + Non-Op Income - Non-Op Expenses
#   5. Period filtering: Only entries in [from_date, to_date] count
#   6. Voided journals do not appear in P&L

import pytest
from datetime import date
from decimal import Decimal

from journals.services import create_journal, post_journal, void_journal
from reports.services.income_statement import generate_income_statement


ZERO = Decimal('0.00')


@pytest.mark.django_db
class TestIncomeStatementMath:

    def test_empty_period_yields_zero_net_income(self, company):
        """No journals in the period → all sections are 0."""
        report = generate_income_statement(
            company,
            from_date=date(2026, 1, 1),
            to_date=date(2026, 12, 31),
        )

        assert Decimal(report['total_operating_income']) == ZERO
        assert Decimal(report['total_cogs']) == ZERO
        assert Decimal(report['gross_profit']) == ZERO
        assert Decimal(report['operating_profit']) == ZERO
        assert Decimal(report['net_income']) == ZERO

    def test_revenue_only_journal_increases_operating_income(
        self, db_access, company, verified_user, account_picker,
    ):
        """
        DEBIT cash 500, CREDIT revenue 500 → operating income = 500,
        net income = 500.

        SIGN-CONVENTION CHECK: Revenue is CREDIT-normal. The P&L must
        display it as a POSITIVE number (so users see "Revenue: 500",
        not "Revenue: -500"). This is the income-statement engine's
        responsibility, not the renderer's.
        """
        cash = account_picker(company, '1.10.1010')
        revenue = account_picker(company, '4.40.4010')

        journal = create_journal(
            company=company,
            created_by=verified_user,
            journal_data={
                'date': date(2026, 6, 15),
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

        report = generate_income_statement(
            company, from_date=date(2026, 1, 1), to_date=date(2026, 12, 31),
        )

        assert Decimal(report['total_operating_income']) == Decimal('500.00')
        assert Decimal(report['net_income']) == Decimal('500.00')
        assert report['is_net_profit'] is True

    def test_expense_only_journal_yields_net_loss(
        self, db_access, company, verified_user, account_picker,
    ):
        """
        Expense without revenue → net loss.
            Total Expenses: 200
            Net Income: -200
            is_net_profit: False
        """
        cash = account_picker(company, '1.10.1010')
        expense = account_picker(company, '5.51.5130')   # Admin & General

        journal = create_journal(
            company=company,
            created_by=verified_user,
            journal_data={
                'date': date(2026, 6, 15),
                'description': 'Office expense',
                'currency': 'BDT',
                'exchange_rate': Decimal('1.000000'),
            },
            lines_data=[
                {'account': expense, 'entry_type': 'DEBIT',  'amount': Decimal('200.00')},
                {'account': cash,    'entry_type': 'CREDIT', 'amount': Decimal('200.00')},
            ],
        )
        post_journal(journal, posted_by=verified_user)

        report = generate_income_statement(
            company, from_date=date(2026, 1, 1), to_date=date(2026, 12, 31),
        )

        assert Decimal(report['total_operating_expenses']) == Decimal('200.00')
        assert Decimal(report['net_income']) == Decimal('-200.00')
        assert report['is_net_profit'] is False

    def test_period_filter_excludes_dates_outside_range(
        self, db_access, company, verified_user, account_picker,
    ):
        """
        PERIOD INVARIANT: Income Statement reports ACTIVITY in a window,
        not cumulative balances. A journal dated outside [from_date, to_date]
        must NOT appear.
        """
        cash = account_picker(company, '1.10.1010')
        revenue = account_picker(company, '4.40.4010')

        # Inside the period.
        j1 = create_journal(
            company=company, created_by=verified_user,
            journal_data={
                'date': date(2026, 6, 15),
                'description': 'In period', 'currency': 'BDT',
                'exchange_rate': Decimal('1.000000'),
            },
            lines_data=[
                {'account': cash,    'entry_type': 'DEBIT',  'amount': Decimal('300.00')},
                {'account': revenue, 'entry_type': 'CREDIT', 'amount': Decimal('300.00')},
            ],
        )
        post_journal(j1, posted_by=verified_user)

        # Outside the period (after to_date).
        j2 = create_journal(
            company=company, created_by=verified_user,
            journal_data={
                'date': date(2027, 1, 15),
                'description': 'Out of period', 'currency': 'BDT',
                'exchange_rate': Decimal('1.000000'),
            },
            lines_data=[
                {'account': cash,    'entry_type': 'DEBIT',  'amount': Decimal('999.00')},
                {'account': revenue, 'entry_type': 'CREDIT', 'amount': Decimal('999.00')},
            ],
        )
        post_journal(j2, posted_by=verified_user)

        report = generate_income_statement(
            company, from_date=date(2026, 1, 1), to_date=date(2026, 12, 31),
        )

        # Only the in-period 300 counts; the 999 is hidden.
        assert Decimal(report['total_operating_income']) == Decimal('300.00')
        assert Decimal(report['net_income']) == Decimal('300.00')

    def test_voided_journal_excluded_from_pl(
        self, db_access, company, verified_user, account_picker,
    ):
        """A voided revenue journal must not inflate the P&L."""
        cash = account_picker(company, '1.10.1010')
        revenue = account_picker(company, '4.40.4010')

        journal = create_journal(
            company=company, created_by=verified_user,
            journal_data={
                'date': date(2026, 6, 15),
                'description': 'Voided sale', 'currency': 'BDT',
                'exchange_rate': Decimal('1.000000'),
            },
            lines_data=[
                {'account': cash,    'entry_type': 'DEBIT',  'amount': Decimal('100.00')},
                {'account': revenue, 'entry_type': 'CREDIT', 'amount': Decimal('100.00')},
            ],
        )
        post_journal(journal, posted_by=verified_user)
        void_journal(journal, voided_by=verified_user)

        report = generate_income_statement(
            company, from_date=date(2026, 1, 1), to_date=date(2026, 12, 31),
        )
        # Voided + reversal cancel out → net income = 0.
        assert Decimal(report['net_income']) == ZERO


@pytest.mark.django_db
class TestIncomeStatementStructure:

    def test_returns_five_sections(self, company):
        """The P&L has 5 sections per Zoho Books convention. All must be
        lists, even when empty."""
        report = generate_income_statement(
            company, from_date=date(2026, 1, 1), to_date=date(2026, 12, 31),
        )

        for key in (
            'operating_income', 'cost_of_goods_sold', 'operating_expenses',
            'non_operating_income', 'non_operating_expenses',
        ):
            assert isinstance(report[key], list), f'{key} must be a list'

    def test_intermediate_totals_are_consistent(
        self, db_access, company, verified_user, account_picker,
    ):
        """
        ALGEBRAIC INVARIANTS within the P&L:
            gross_profit       = total_operating_income - total_cogs
            operating_profit   = gross_profit - total_operating_expenses
            net_income         = operating_profit
                                  + total_non_operating_income
                                  - total_non_operating_expenses

        We seed one revenue + one expense and verify the formulas hold.
        """
        cash = account_picker(company, '1.10.1010')
        revenue = account_picker(company, '4.40.4010')
        expense = account_picker(company, '5.51.5130')   # Admin & General Expense

        # 1000 revenue
        j1 = create_journal(
            company=company, created_by=verified_user,
            journal_data={
                'date': date(2026, 6, 1),
                'description': 'Sale', 'currency': 'BDT',
                'exchange_rate': Decimal('1.000000'),
            },
            lines_data=[
                {'account': cash,    'entry_type': 'DEBIT',  'amount': Decimal('1000.00')},
                {'account': revenue, 'entry_type': 'CREDIT', 'amount': Decimal('1000.00')},
            ],
        )
        post_journal(j1, posted_by=verified_user)

        # 300 expense
        j2 = create_journal(
            company=company, created_by=verified_user,
            journal_data={
                'date': date(2026, 6, 15),
                'description': 'Cost', 'currency': 'BDT',
                'exchange_rate': Decimal('1.000000'),
            },
            lines_data=[
                {'account': expense, 'entry_type': 'DEBIT',  'amount': Decimal('300.00')},
                {'account': cash,    'entry_type': 'CREDIT', 'amount': Decimal('300.00')},
            ],
        )
        post_journal(j2, posted_by=verified_user)

        report = generate_income_statement(
            company, from_date=date(2026, 1, 1), to_date=date(2026, 12, 31),
        )

        op_inc = Decimal(report['total_operating_income'])
        cogs = Decimal(report['total_cogs'])
        op_exp = Decimal(report['total_operating_expenses'])
        non_op_inc = Decimal(report['total_non_operating_income'])
        non_op_exp = Decimal(report['total_non_operating_expenses'])
        gross = Decimal(report['gross_profit'])
        op_profit = Decimal(report['operating_profit'])
        net = Decimal(report['net_income'])

        # Verify each formula holds.
        assert gross == op_inc - cogs, 'Gross Profit formula broken'
        assert op_profit == gross - op_exp, 'Operating Profit formula broken'
        assert net == op_profit + non_op_inc - non_op_exp, 'Net Income formula broken'

        # And the concrete values for this scenario.
        assert op_inc == Decimal('1000.00')
        assert op_exp == Decimal('300.00')
        assert net == Decimal('700.00')