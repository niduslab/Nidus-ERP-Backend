# backend/reports/tests/test_cash_flow.py
#
# Tests for reports.services.cash_flow — IAS 7 indirect method.
#
# We test the SHAPE and KEY INVARIANTS only, because the full numeric
# verification of cash-flow statements requires complex multi-period
# fixtures (fixed-asset depreciation, working-capital changes, etc.) that
# would balloon Phase 4 beyond the scope of the test suite.
#
# Numeric correctness will be covered when the Fixed Asset / Period-End
# modules are built (Steps 14, 15) — at that point we can test the
# depreciation add-back and FX revaluation.

import pytest
from datetime import date
from decimal import Decimal

from journals.services import post_journal
from reports.services.cash_flow import generate_cash_flow


ZERO = Decimal('0.00')


@pytest.mark.django_db
class TestCashFlowStructure:

    def test_empty_company_yields_zero_cash_flow(self, company):
        """No transactions → all flows = 0, opening = closing = 0."""
        report = generate_cash_flow(
            company, from_date=date(2026, 1, 1), to_date=date(2026, 12, 31),
        )

        summary = report['summary']
        assert Decimal(summary['net_cash_from_operating']) == ZERO
        assert Decimal(summary['net_cash_from_investing']) == ZERO
        assert Decimal(summary['net_cash_from_financing']) == ZERO
        assert Decimal(summary['net_change_in_cash']) == ZERO

    def test_returns_three_activity_sections(self, company):
        """The IAS 7 statement has exactly three activity sections."""
        report = generate_cash_flow(
            company, from_date=date(2026, 1, 1), to_date=date(2026, 12, 31),
        )
        for key in ('operating_activities', 'investing_activities', 'financing_activities'):
            assert key in report, f'Missing required section: {key}'
            assert isinstance(report[key], dict), f'{key} must be a dict'

    def test_cash_reconciliation_balances_after_journal_post(
        self, journal_factory, company, verified_user,
    ):
        """
        IAS 7 RECONCILIATION INVARIANT:
            opening_cash + net_change_in_cash == closing_cash

        This must hold whether the period had activity or not. The whole
        point of the cash-flow statement is to RECONCILE the change in
        the cash balance against the operating/investing/financing flows.
        """
        # Post one cash → equity journal in the period.
        journal = journal_factory(
            amount=Decimal('800.00'),
            journal_date=date(2026, 6, 15),
        )
        post_journal(journal, posted_by=verified_user)

        report = generate_cash_flow(
            company, from_date=date(2026, 1, 1), to_date=date(2026, 12, 31),
        )

        cr = report['cash_reconciliation']
        opening = Decimal(cr['opening_cash_balance'])
        change = Decimal(cr['net_change_in_cash'])
        closing = Decimal(cr['closing_cash_balance'])

        assert opening + change == closing, (
            f'Cash reconciliation broken: '
            f'{opening} + {change} != {closing}'
        )

    def test_returns_required_top_level_keys(self, company):
        """Stable contract for renderers and API consumers."""
        report = generate_cash_flow(
            company, from_date=date(2026, 1, 1), to_date=date(2026, 12, 31),
        )
        required = {
            'operating_activities',
            'investing_activities',
            'financing_activities',
            'cash_reconciliation',
            'summary',
        }
        assert required.issubset(set(report.keys()))