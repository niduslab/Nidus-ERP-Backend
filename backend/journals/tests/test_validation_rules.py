# backend/journals/tests/test_validation_rules.py
#
# Tests that the service-level _validate_journal_data enforces the
# accounting and business rules:
#   - Minimum 2 lines
#   - Debits must equal credits
#   - All accounts must belong to the company
#   - Account must be active
#   - Lock-date enforcement
#   - Positive amounts only

import pytest
from datetime import date
from decimal import Decimal

from journals.services import create_journal


@pytest.mark.django_db
class TestJournalValidation:

    def test_rejects_single_line_journal(
        self, company, verified_user, account_picker,
    ):
        """
        DOUBLE-ENTRY INVARIANT: a journal must have ≥ 2 lines (one debit,
        one credit). A single line cannot balance and breaks the equation.
        """
        cash = account_picker(company, '1.10.1010')
        with pytest.raises(ValueError, match='at least 2 lines'):
            create_journal(
                company=company,
                created_by=verified_user,
                journal_data={
                    'date': date(2026, 4, 1),
                    'description': 'Should fail',
                    'currency': 'BDT',
                    'exchange_rate': Decimal('1.000000'),
                },
                lines_data=[
                    {'account': cash, 'entry_type': 'DEBIT', 'amount': Decimal('100.00')},
                ],
            )

    def test_rejects_unbalanced_journal(
        self, company, verified_user, account_picker,
    ):
        """
        DOUBLE-ENTRY INVARIANT: total debits must equal total credits in
        the journal currency. 100 DEBIT vs 99 CREDIT is rejected.
        """
        cash = account_picker(company, '1.10.1010')
        equity = account_picker(company, '3.30.3010')
        with pytest.raises(ValueError, match='not balanced'):
            create_journal(
                company=company,
                created_by=verified_user,
                journal_data={
                    'date': date(2026, 4, 1),
                    'description': 'Off by 1',
                    'currency': 'BDT',
                    'exchange_rate': Decimal('1.000000'),
                },
                lines_data=[
                    {'account': cash,   'entry_type': 'DEBIT',  'amount': Decimal('100.00')},
                    {'account': equity, 'entry_type': 'CREDIT', 'amount': Decimal('99.00')},
                ],
            )

    def test_rejects_zero_amount_line(
        self, company, verified_user, account_picker,
    ):
        """Zero-amount lines pollute the ledger with no information value."""
        cash = account_picker(company, '1.10.1010')
        equity = account_picker(company, '3.30.3010')
        with pytest.raises(ValueError, match='greater than zero'):
            create_journal(
                company=company,
                created_by=verified_user,
                journal_data={
                    'date': date(2026, 4, 1),
                    'description': 'Zero amount',
                    'currency': 'BDT',
                    'exchange_rate': Decimal('1.000000'),
                },
                lines_data=[
                    {'account': cash,   'entry_type': 'DEBIT',  'amount': Decimal('0.00')},
                    {'account': equity, 'entry_type': 'CREDIT', 'amount': Decimal('0.00')},
                ],
            )

    def test_rejects_inactive_account(
        self, company, verified_user, account_picker,
    ):
        """Inactive accounts must not accept new entries (they may still
        hold historical balances, but cannot receive NEW posts)."""
        cash = account_picker(company, '1.10.1010')
        equity = account_picker(company, '3.30.3010')

        # Deactivate one of the accounts.
        equity.is_active = False
        equity.save(update_fields=['is_active'])

        with pytest.raises(ValueError, match='inactive'):
            create_journal(
                company=company,
                created_by=verified_user,
                journal_data={
                    'date': date(2026, 4, 1),
                    'description': 'Inactive target',
                    'currency': 'BDT',
                    'exchange_rate': Decimal('1.000000'),
                },
                lines_data=[
                    {'account': cash,   'entry_type': 'DEBIT',  'amount': Decimal('100.00')},
                    {'account': equity, 'entry_type': 'CREDIT', 'amount': Decimal('100.00')},
                ],
            )


@pytest.mark.django_db
class TestLockDateEnforcement:
    """
    The lock_date on Company freezes historical periods. Once set, NO
    journal can be created or voided with a date <= lock_date.
    Critical for period-end controls and audit integrity.
    """

    def test_rejects_journal_on_lock_date(
        self, company, verified_user, account_picker,
    ):
        """A journal dated EXACTLY on the lock date is rejected (the
        condition is `date <= lock_date`, inclusive of the lock day)."""
        cash = account_picker(company, '1.10.1010')
        equity = account_picker(company, '3.30.3010')

        # Lock the books at March 31, 2026.
        company.lock_date = date(2026, 3, 31)
        company.save(update_fields=['lock_date'])

        with pytest.raises(ValueError, match='lock date'):
            create_journal(
                company=company,
                created_by=verified_user,
                journal_data={
                    'date': date(2026, 3, 31),    # On the lock date
                    'description': 'Locked period',
                    'currency': 'BDT',
                    'exchange_rate': Decimal('1.000000'),
                },
                lines_data=[
                    {'account': cash,   'entry_type': 'DEBIT',  'amount': Decimal('100.00')},
                    {'account': equity, 'entry_type': 'CREDIT', 'amount': Decimal('100.00')},
                ],
            )

    def test_allows_journal_after_lock_date(
        self, company, verified_user, account_picker,
    ):
        """Posts after the lock date are unaffected — current period
        bookings continue to work."""
        cash = account_picker(company, '1.10.1010')
        equity = account_picker(company, '3.30.3010')

        company.lock_date = date(2026, 3, 31)
        company.save(update_fields=['lock_date'])

        # A journal dated AFTER the lock date should succeed.
        journal = create_journal(
            company=company,
            created_by=verified_user,
            journal_data={
                'date': date(2026, 4, 1),         # After lock
                'description': 'New period',
                'currency': 'BDT',
                'exchange_rate': Decimal('1.000000'),
            },
            lines_data=[
                {'account': cash,   'entry_type': 'DEBIT',  'amount': Decimal('100.00')},
                {'account': equity, 'entry_type': 'CREDIT', 'amount': Decimal('100.00')},
            ],
        )
        assert journal.id is not None