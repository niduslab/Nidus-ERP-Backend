# backend/chartofaccounts/services.py

"""
Business logic for the Chart of Accounts.

Contains two main functions:
1. generate_default_coa() — Creates the pre-built 104-account CoA
2. generate_custom_coa()  — Creates a custom CoA from an uploaded file

Both functions are called during company creation from
companies/serializers.py → CompanyCreateSerializer.create()

Both run inside transaction.atomic() to guarantee that a company
never ends up with a half-built Chart of Accounts.
"""

from django.db import transaction

from .models import AccountClassification, Account, SystemAccountMapping
from .seed import CLASSIFICATIONS, DEFAULT_ACCOUNTS


def generate_default_coa(company, created_by):

    with transaction.atomic():

        classification_map = {}

        for internal_path, name in CLASSIFICATIONS:
            if '.' in internal_path:
                parent_path = internal_path.rsplit('.', 1)[0]
                parent = classification_map[parent_path]
            else:
                parent = None

            classification = AccountClassification.objects.create(
                company=company,
                parent=parent,
                name=name,
                internal_path=internal_path,
            )

            # Store in our lookup dictionary for later use
            classification_map[internal_path] = classification


        account_counter = {}
        system_accounts = {}

        for (
            classification_path,
            account_code,
            name,
            normal_balance,
            is_system,
            is_deletable,
            system_code,
        ) in DEFAULT_ACCOUNTS:

            classification = classification_map[classification_path]

            if classification_path not in account_counter:
                account_counter[classification_path] = 0
            account_counter[classification_path] += 1

            sequence = str(account_counter[classification_path]).zfill(4)

            account_internal_path = f"{classification_path}.{sequence}"

            account = Account.objects.create(
                company=company,
                classification=classification,
                parent_account=None,          
                name=name,
                code=account_code,
                internal_path=account_internal_path,
                normal_balance=normal_balance,
                currency=company.base_currency,  
                is_system_account=is_system,
                is_deletable=is_deletable,
                is_active=True,
                created_by=created_by,
            )

            if system_code:
                system_accounts[system_code] = account


        for system_code, account in system_accounts.items():
            SystemAccountMapping.objects.create(
                company=company,
                system_code=system_code,
                account=account,
            )
        from companies.models import DocumentSequence

        DocumentSequence.objects.create(
            company=company,
            module='MANUAL_JOURNAL',
            prefix='JE-',
            next_number=1,
            padding=4,
        )


def generate_custom_coa(company, created_by, validated_data):
    """
    Create a custom Chart of Accounts from validated upload data.

    This function is called AFTER the uploaded file passes validation
    (custom_coa_validator.py). It receives the parsed classifications and
    accounts from the validator and creates the actual database rows.
    """
    custom_classifications = validated_data.get('classifications', [])
    accounts_data = validated_data.get('accounts', [])

    with transaction.atomic():

        # ──────────────────────────────────────
        # STEP 1: Create all standard Layer 1-3 classifications
        # ──────────────────────────────────────
        classification_map = {}
        name_to_classification = {}

        for internal_path, name in CLASSIFICATIONS:
            if '.' in internal_path:
                parent_path = internal_path.rsplit('.', 1)[0]
                parent = classification_map[parent_path]
            else:
                parent = None

            classification = AccountClassification.objects.create(
                company=company,
                parent=parent,
                name=name,
                internal_path=internal_path,
            )

            classification_map[internal_path] = classification


            if internal_path.count('.') == 2:
                name_to_classification[name] = classification

        # ──────────────────────────────────────
        # STEP 2: Create custom Layer 3 classifications
        # ──────────────────────────────────────

        layer2_name_to_classification = {}
        for internal_path, name in CLASSIFICATIONS:
            if internal_path.count('.') == 1:
                layer2_name_to_classification[name] = classification_map[internal_path]

        for custom_class in custom_classifications:
            parent_l2_name = custom_class['parent_layer2_name']
            class_name = custom_class['name']

            parent = layer2_name_to_classification[parent_l2_name]

            # Generate internal path for the new classification.
            # We reuse the same helper that the API views use.
            from .views import generate_next_internal_path

            new_path = generate_next_internal_path(company, parent.internal_path)

            classification = AccountClassification.objects.create(
                company=company,
                parent=parent,
                name=class_name,
                internal_path=new_path,
            )

            name_to_classification[class_name] = classification

        # ──────────────────────────────────────
        # STEP 3: Create accounts
        # ──────────────────────────────────────
        system_accounts = {}
        account_counter = {}

        for acct_data in accounts_data:
            classification_name = acct_data['classification_name']
            classification = name_to_classification[classification_name]

            # Build internal path
            class_path = classification.internal_path
            if class_path not in account_counter:
                account_counter[class_path] = 0
            account_counter[class_path] += 1
            sequence = str(account_counter[class_path]).zfill(4)
            account_internal_path = f"{class_path}.{sequence}"

            # Use provided currency or fall back to company default
            currency = acct_data['currency'] if acct_data['currency'] else company.base_currency

            account = Account.objects.create(
                company=company,
                classification=classification,
                parent_account=None,
                name=acct_data['name'],
                code=acct_data['code'],
                internal_path=account_internal_path,
                normal_balance=acct_data['normal_balance'],
                currency=currency,
                is_system_account=acct_data['is_system'],
                is_deletable=not acct_data['is_system'],
                is_active=True,
                description=acct_data.get('description', ''),
                created_by=created_by,
            )

            if acct_data['system_code']:
                system_accounts[acct_data['system_code']] = account

        # ──────────────────────────────────────
        # STEP 4: Create system account mappings
        # ──────────────────────────────────────

        for system_code, account in system_accounts.items():
            SystemAccountMapping.objects.create(
                company=company,
                system_code=system_code,
                account=account,
            )

        
        from companies.models import DocumentSequence

        DocumentSequence.objects.create(
            company=company,
            module='MANUAL_JOURNAL',
            prefix='JE-',
            next_number=1,
            padding=4,
        )