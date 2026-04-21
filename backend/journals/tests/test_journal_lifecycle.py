# backend/journals/tests/test_journal_lifecycle.py
#
# Tests the DRAFT → POSTED → VOID state machine.
#
# Critical invariants verified here:
#   - Only DRAFT can be posted
#   - Only POSTED can be voided
#   - Only DRAFT can be deleted (POSTED must be voided)
#   - Status transitions are one-way (no POSTED → DRAFT)
#   - Update is allowed only on DRAFT

import pytest
from datetime import date
from decimal import Decimal

from journals.models import ManualJournal, JournalStatusChoices
from journals.services import (
    post_journal, void_journal, delete_journal, update_journal,
)


@pytest.mark.django_db
class TestJournalCreation:

    def test_create_journal_starts_as_draft(self, journal_factory):
        """A newly-created journal must have status=DRAFT and no posted_at timestamp."""
        journal = journal_factory()
        assert journal.status == JournalStatusChoices.DRAFT
        assert journal.posted_at is None
        assert journal.voided_at is None

    def test_create_journal_assigns_sequential_entry_number(
        self, journal_factory,
    ):
        """
        Entry numbers come from the company's MANUAL_JOURNAL DocumentSequence,
        seeded in generate_default_coa(). First journal in a fresh company
        should be JE-0001, second JE-0002.

        Why this matters: gaps in entry-number sequences are a red flag for
        auditors. The atomic increment must produce monotonic numbers.
        """
        first = journal_factory()
        second = journal_factory()

        # Format: JE-NNNN (4-digit zero-padded). Concrete values rather than
        # regex so a misconfigured prefix or padding fails loudly.
        assert first.entry_number == 'JE-0001'
        assert second.entry_number == 'JE-0002'


@pytest.mark.django_db
class TestPostJournal:

    def test_post_transitions_draft_to_posted(self, journal_factory, verified_user):
        """post_journal flips status, sets posted_at, returns the same instance."""
        journal = journal_factory()
        result = post_journal(journal, posted_by=verified_user)

        assert result.id == journal.id   # Same row, mutated in place
        assert result.status == JournalStatusChoices.POSTED
        assert result.posted_at is not None

    def test_cannot_post_already_posted_journal(
        self, journal_factory, verified_user,
    ):
        """
        STATE-MACHINE INVARIANT: POSTED is a terminal forward state.
        Re-posting must raise — otherwise a double-click on the UI would
        create duplicate ledger entries.
        """
        journal = journal_factory()
        post_journal(journal, posted_by=verified_user)

        with pytest.raises(ValueError, match='Only draft'):
            post_journal(journal, posted_by=verified_user)


@pytest.mark.django_db
class TestVoidJournal:

    def test_void_transitions_posted_to_void_and_creates_reversal(
        self, posted_journal, verified_user,
    ):
        """
        Void produces a SECOND ManualJournal (the reversal) and links them
        bidirectionally:
          original.voided_by_entry  → reversal
          reversal.reversal_of      → original
        """
        reversal = void_journal(posted_journal, voided_by=verified_user)

        # Refresh original from DB — void_journal mutates fields.
        posted_journal.refresh_from_db()
        assert posted_journal.status == JournalStatusChoices.VOID
        assert posted_journal.voided_at is not None
        assert posted_journal.voided_by_entry == reversal

        # Reversal is a separate ManualJournal with REVERSAL status.
        assert reversal.status == JournalStatusChoices.REVERSAL
        assert reversal.reversal_of == posted_journal

    def test_cannot_void_a_draft(self, journal_factory, verified_user):
        """A DRAFT has no ledger entries to reverse — voiding makes no sense."""
        draft = journal_factory()
        with pytest.raises(ValueError, match='Only posted'):
            void_journal(draft, voided_by=verified_user)

    def test_cannot_void_an_already_voided_journal(
        self, posted_journal, verified_user,
    ):
        """
        STATE-MACHINE INVARIANT: VOID is terminal. A voided journal cannot
        be re-voided — that would create a second reversal and inflate the
        ledger by 2x the original amount.
        """
        void_journal(posted_journal, voided_by=verified_user)
        with pytest.raises(ValueError, match='Only posted'):
            void_journal(posted_journal, voided_by=verified_user)


@pytest.mark.django_db
class TestDeleteJournal:

    def test_can_delete_draft(self, journal_factory):
        """DRAFT has no ledger impact, so deleting is safe."""
        journal = journal_factory()
        journal_id = journal.id
        delete_journal(journal)
        assert not ManualJournal.objects.filter(id=journal_id).exists()

    def test_cannot_delete_posted_journal(
        self, journal_factory, verified_user,
    ):
        """
        AUDIT-INTEGRITY INVARIANT: Posted entries must be voided, not
        deleted. Deletion would erase the ledger entries and the audit
        trail, breaking traceability — a regulator's worst nightmare.
        """
        journal = journal_factory()
        post_journal(journal, posted_by=verified_user)
        with pytest.raises(ValueError, match='Only draft'):
            delete_journal(journal)


@pytest.mark.django_db
class TestUpdateJournal:

    def test_can_update_draft_description(self, journal_factory):
        """Editing a draft's description is allowed."""
        journal = journal_factory()
        update_journal(journal, journal_data={'description': 'Updated text'})
        journal.refresh_from_db()
        assert journal.description == 'Updated text'

    def test_cannot_update_posted_journal(
        self, journal_factory, verified_user,
    ):
        """
        AUDIT-INTEGRITY INVARIANT: Posted journals are immutable. Edits
        would silently change historical financial records — only voiding
        is permitted.
        """
        journal = journal_factory()
        post_journal(journal, posted_by=verified_user)
        with pytest.raises(ValueError, match='Only draft'):
            update_journal(journal, journal_data={'description': 'Try edit'})