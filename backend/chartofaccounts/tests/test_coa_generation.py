# backend/chartofaccounts/tests/test_coa_generation.py
#
# Tests the default Chart of Accounts seed function.
# These tests run generate_default_coa() directly (not via HTTP) — they
# verify the SHAPE of the generated data, not request/response plumbing.

import pytest

from chartofaccounts.models import (
    AccountClassification, Account, SystemAccountMapping,
)
from chartofaccounts.services import generate_default_coa


@pytest.mark.django_db
class TestGenerateDefaultCoA:
    """
    `generate_default_coa(company, created_by)` must produce:
        1. A 3-layer classification tree (L1 → L2 → L3)
        2. ~107 accounts attached to L3 classifications
        3. System account mappings (RETAINED_EARNINGS, etc.)
        4. A MANUAL_JOURNAL DocumentSequence

    These tests use the `bare_company` fixture so we're calling the service
    on a FRESH company — not one that already has a seeded CoA from the
    `company` fixture.
    """

    def test_creates_five_l1_classifications(self, bare_company, verified_user):
        """The standard accounting chart has exactly 5 L1 types:
        Asset (1), Liability (2), Equity (3), Income (4), Expense (5)."""
        generate_default_coa(company=bare_company, created_by=verified_user)

        l1s = AccountClassification.objects.filter(
            company=bare_company, parent__isnull=True,
        )
        assert l1s.count() == 5

        names = set(l1s.values_list('name', flat=True))
        assert {'Asset', 'Liability', 'Equity', 'Income', 'Expense'}.issubset(names)

    def test_classifications_form_three_layer_tree(self, bare_company, verified_user):
        """Every account's classification must be L3 (layer==3). L1/L2
        classifications exist only as grouping containers."""
        generate_default_coa(company=bare_company, created_by=verified_user)

        accounts = Account.objects.filter(company=bare_company)
        for account in accounts:
            # internal_path format: "1.10.1010.0001"
            # The L3 classification has a 3-segment path: "1.10.1010"
            assert account.classification.layer == 3, (
                f'Account {account.code} ({account.name}) is attached to a '
                f'non-L3 classification: {account.classification.internal_path}'
            )

    def test_creates_system_account_mappings(self, bare_company, verified_user):
        """
        After seeding, the system must know which account to use for
        RETAINED_EARNINGS, OWNER_CAPITAL, ACCUMULATED_DEPRECIATION, etc.
        Without these mappings, the Balance Sheet's retained-earnings logic
        and the amortisation journals would have nowhere to post.
        """
        generate_default_coa(company=bare_company, created_by=verified_user)

        mapped_codes = set(
            SystemAccountMapping.objects
            .filter(company=bare_company)
            .values_list('system_code', flat=True)
        )

        # These are the 9 system codes documented in CLAUDE.md. Without them,
        # retained earnings, amortisation, and FX loss journals would fail.
        required = {
            'RETAINED_EARNINGS',
            'ACCUMULATED_DEPRECIATION',
            'ACCUMULATED_AMORTISATION',
            'OWNER_CAPITAL',
            'BANK_FEES',
            'INTEREST_EXPENSE',
            'FX_LOSS',
            'INCOME_TAX_EXPENSE',
            'LOSS_ON_DISPOSAL',
        }
        assert required.issubset(mapped_codes)

    def test_creates_manual_journal_document_sequence(self, bare_company, verified_user):
        """
        Regression test: generate_default_coa() auto-creates the
        MANUAL_JOURNAL sequence so the first journal post doesn't fail.
        This was once a pending item in todo.txt — now verified here.
        """
        from companies.models import DocumentSequence

        generate_default_coa(company=bare_company, created_by=verified_user)

        seq = DocumentSequence.objects.get(
            company=bare_company, module='MANUAL_JOURNAL',
        )
        assert seq.prefix == 'JE-'
        assert seq.next_number == 1
        assert seq.padding == 4

    def test_accounts_inherit_company_base_currency(self, bare_company, verified_user):
        """All accounts are seeded with the company's base_currency by default."""
        generate_default_coa(company=bare_company, created_by=verified_user)

        accounts = Account.objects.filter(company=bare_company)
        assert accounts.exists()
        for a in accounts:
            assert a.currency == bare_company.base_currency   # 'BDT' from fixture