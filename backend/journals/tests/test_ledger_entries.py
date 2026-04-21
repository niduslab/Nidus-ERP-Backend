# backend/journals/tests/test_ledger_entries.py
#
# Tests the LEDGER ENTRY creation and the VOID REVERSAL invariant.
#
# These are the most important tests in the entire project. If any of these
# fail in production, financial reports will be wrong.

import pytest
from datetime import date
from decimal import Decimal

from journals.models import LedgerEntry, EntryTypeChoices
from journals.services import post_journal, void_journal


ZERO = Decimal('0.00')


@pytest.mark.django_db
class TestLedgerEntryCreation:
    """
    Posting a journal must create exactly one LedgerEntry per
    ManualJournalLine (assuming no tax_profile). This relationship is
    1:1 and forms the backbone of every financial report.
    """

    def test_draft_journal_creates_no_ledger_entries(self, journal_factory, company):
        """DRAFT lines do NOT touch the ledger. Verifying this prevents a
        regression where someone would accidentally post on create()."""
        journal_factory()   # Created but NOT posted
        assert LedgerEntry.objects.filter(company=company).count() == 0

    def test_post_creates_one_ledger_entry_per_line(
        self, journal_factory, company, verified_user,
    ):
        """
        2-line journal → 2 LedgerEntry rows. Each carries:
          - same date as the journal
          - same entry_type as the line (DEBIT or CREDIT)
          - amount equal to the line amount
          - base_amount = amount × exchange_rate (1.0 for base-currency journals)
        """
        journal = journal_factory(amount=Decimal('500.00'))
        post_journal(journal, posted_by=verified_user)

        entries = LedgerEntry.objects.filter(company=company).order_by('entry_type')
        assert entries.count() == 2

        # CREDIT and DEBIT each appear once.
        debit_entry = entries.get(entry_type=EntryTypeChoices.DEBIT)
        credit_entry = entries.get(entry_type=EntryTypeChoices.CREDIT)

        assert debit_entry.amount == Decimal('500.00')
        assert debit_entry.base_amount == Decimal('500.00')   # Rate is 1.0
        assert credit_entry.amount == Decimal('500.00')
        assert credit_entry.base_amount == Decimal('500.00')

    def test_balance_invariant_sum_of_debits_equals_credits(
        self, journal_factory, company, verified_user,
    ):
        """
        DOUBLE-ENTRY INVARIANT: For every posted journal, the sum of its
        DEBIT base_amounts must equal the sum of its CREDIT base_amounts.

        This is THE foundational accounting law. If this ever breaks, the
        Trial Balance won't balance and the Balance Sheet equation
        (Assets = Liabilities + Equity) will fail.
        """
        journal = journal_factory(amount=Decimal('1234.56'))
        post_journal(journal, posted_by=verified_user)

        entries = LedgerEntry.objects.filter(company=company)
        total_debit = sum(
            (e.base_amount for e in entries if e.entry_type == 'DEBIT'),
            ZERO,
        )
        total_credit = sum(
            (e.base_amount for e in entries if e.entry_type == 'CREDIT'),
            ZERO,
        )
        assert total_debit == total_credit, (
            f'Double-entry violation! '
            f'Debits={total_debit}, Credits={total_credit}'
        )

    def test_ledger_entry_links_back_to_journal_line_via_generic_fk(
        self, journal_factory, company, verified_user,
    ):
        """
        LedgerEntry.source_line (GenericFK) must resolve back to the
        ManualJournalLine that created it. Without this, drill-down from
        the General Ledger report to the source document would be impossible.
        """
        journal = journal_factory()
        post_journal(journal, posted_by=verified_user)

        entry = LedgerEntry.objects.filter(company=company).first()
        # source_line resolves the (content_type, object_id) pair to the
        # actual ManualJournalLine instance.
        source_line = entry.source_line
        assert source_line is not None
        assert source_line.journal_id == journal.id

    def test_ledger_entry_carries_company_and_account_correctly(
        self, journal_factory, company, verified_user, account_picker,
    ):
        """The company and ledger_account FKs on every entry must point to
        the company that owns the journal and the account that the line
        targeted — multi-tenant isolation depends on this."""
        cash = account_picker(company, '1.10.1010')
        journal = journal_factory()
        post_journal(journal, posted_by=verified_user)

        # Every entry must belong to `company`, none to anyone else.
        for entry in LedgerEntry.objects.all():
            assert entry.company_id == company.id
            assert entry.ledger_account.company_id == company.id


@pytest.mark.django_db
class TestVoidReversalInvariant:
    """
    THE most critical invariant in the system.

    When a journal is voided, the system creates a REVERSAL journal whose
    ledger entries swap DEBIT↔CREDIT for every original line. After void,
    the NET balance impact across (original + reversal) must be exactly 0.

    If this invariant ever breaks:
      - Voided invoices still inflate revenue
      - Voided expenses still eat into profit
      - Balance sheet stops balancing
      - Reports become unreliable

    This is the second-most-important test in the project (only behind
    the double-entry balance test above).
    """

    def test_void_zeros_out_net_balance_per_account(
        self, journal_factory, company, verified_user, account_picker,
    ):
        """
        After original is posted then voided, every account that the
        journal touched must have net base_amount = 0
        (sum of debits − sum of credits across both original and reversal).
        """
        journal = journal_factory(amount=Decimal('750.00'))
        post_journal(journal, posted_by=verified_user)
        void_journal(journal, voided_by=verified_user)

        cash = account_picker(company, '1.10.1010')
        equity = account_picker(company, '3.30.3010')

        for account in (cash, equity):
            entries = LedgerEntry.objects.filter(
                company=company, ledger_account=account,
            )
            net = sum(
                (e.base_amount if e.entry_type == 'DEBIT' else -e.base_amount
                 for e in entries),
                ZERO,
            )
            assert net == ZERO, (
                f'VOID reversal failed to zero out account {account.code}: '
                f'net = {net}. Original journal = {journal.entry_number}.'
            )

    def test_void_doubles_total_ledger_entry_count(
        self, journal_factory, company, verified_user,
    ):
        """
        Voiding a 2-line journal creates 2 reversal lines → 4 total
        LedgerEntry rows for that journal pair. The reversal does NOT
        delete the original entries (audit trail is preserved).
        """
        journal = journal_factory()
        post_journal(journal, posted_by=verified_user)
        # Sanity: 2 entries from the original posting.
        assert LedgerEntry.objects.filter(company=company).count() == 2

        void_journal(journal, voided_by=verified_user)
        # Now 4: 2 original (still there) + 2 reversal.
        assert LedgerEntry.objects.filter(company=company).count() == 4

    def test_void_reversal_swaps_debit_and_credit(
        self, journal_factory, company, verified_user, account_picker,
    ):
        """
        Each reversal line must have the OPPOSITE entry_type of the
        original line on the same account. That's why the net is zero.
        """
        cash = account_picker(company, '1.10.1010')

        journal = journal_factory(amount=Decimal('300.00'))
        post_journal(journal, posted_by=verified_user)
        # Originally: DEBIT cash 300
        original_cash_entry = LedgerEntry.objects.get(
            company=company, ledger_account=cash,
        )
        assert original_cash_entry.entry_type == 'DEBIT'

        void_journal(journal, voided_by=verified_user)
        # Now there should be a CREDIT cash 300 reversal entry.
        cash_entries = LedgerEntry.objects.filter(
            company=company, ledger_account=cash,
        )
        assert cash_entries.count() == 2
        entry_types = {e.entry_type for e in cash_entries}
        assert entry_types == {'DEBIT', 'CREDIT'}