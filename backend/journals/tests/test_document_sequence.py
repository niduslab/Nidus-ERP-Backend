# backend/journals/tests/test_document_sequence.py
#
# Tests for the DocumentSequence atomic-increment behaviour.
#
# The entry_number generator (generate_entry_number in services.py) uses
# select_for_update + F() to guarantee monotonic, gap-free numbers even
# under concurrent writes. We can't easily simulate true concurrency in
# SQLite, but we can verify the sequential behaviour and the F() correctness.

import pytest
from decimal import Decimal

from companies.models import DocumentSequence
from journals.services import generate_entry_number, create_journal


@pytest.mark.django_db
class TestDocumentSequence:

    def test_sequence_starts_at_one(self, company):
        """Fresh CoA generation seeds next_number=1."""
        seq = DocumentSequence.objects.get(
            company=company, module='MANUAL_JOURNAL',
        )
        assert seq.next_number == 1
        assert seq.prefix == 'JE-'
        assert seq.padding == 4

    def test_generate_entry_number_returns_padded_format(self, company):
        """
        The format is "{prefix}{number padded to {padding} digits}".
        Run inside a transaction so select_for_update doesn't choke.
        """
        from django.db import transaction
        with transaction.atomic():
            number = generate_entry_number(company)
        assert number == 'JE-0001'

    def test_generate_entry_number_increments_atomically(self, company):
        """
        Calling generate_entry_number twice produces JE-0001 then JE-0002,
        and DocumentSequence.next_number is 3 after both calls. Verifies
        the F('next_number') + 1 expression isn't mis-evaluated.
        """
        from django.db import transaction

        with transaction.atomic():
            n1 = generate_entry_number(company)
        with transaction.atomic():
            n2 = generate_entry_number(company)

        assert n1 == 'JE-0001'
        assert n2 == 'JE-0002'

        seq = DocumentSequence.objects.get(
            company=company, module='MANUAL_JOURNAL',
        )
        assert seq.next_number == 3

    def test_two_companies_have_independent_sequences(
        self, db_access, verified_user, other_user,
    ):
        """
        Each company has its own DocumentSequence — Rahim Trading's JE-0001
        and Karim Industries' JE-0001 must coexist without colliding.
        Tests the (company, module) unique constraint behaves correctly.
        """
        from companies.models import Company, CompanyUser, RoleChoices
        from chartofaccounts.services import generate_default_coa
        from django.db import transaction

        # Build two independent companies, each with their own seeded CoA.
        company_a = Company.objects.create(
            owner=verified_user, name='Company A', industry='SERVICES',
            base_currency='BDT', company_size='1-10', fiscal_year_start_month=7,
        )
        CompanyUser.objects.create(user=verified_user, company=company_a, role=RoleChoices.OWNER)
        generate_default_coa(company=company_a, created_by=verified_user)

        company_b = Company.objects.create(
            owner=other_user, name='Company B', industry='SERVICES',
            base_currency='BDT', company_size='1-10', fiscal_year_start_month=7,
        )
        CompanyUser.objects.create(user=other_user, company=company_b, role=RoleChoices.OWNER)
        generate_default_coa(company=company_b, created_by=other_user)

        with transaction.atomic():
            n_a = generate_entry_number(company_a)
        with transaction.atomic():
            n_b = generate_entry_number(company_b)

        # Both companies start at 0001 — independent counters.
        assert n_a == 'JE-0001'
        assert n_b == 'JE-0001'