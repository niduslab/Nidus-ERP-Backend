# backend/chartofaccounts/serializers.py


from rest_framework import serializers
from .models import AccountClassification, Account, SystemAccountMapping


class AccountClassificationSerializer(serializers.ModelSerializer):
    

    # This is a custom field that doesn't exist on the model as a database column.
    # It calls the @property method we defined on the model.
    # SerializerMethodField tells DRF: "Don't look for this in the database.
    # Instead, call my get_<fieldname> method to get the value."
    layer = serializers.SerializerMethodField()

    # read_only=True means: include this in the response, but if the
    # frontend sends it in a request, ignore it completely.
    children_count = serializers.SerializerMethodField()
    accounts_count = serializers.SerializerMethodField()

    class Meta:
        model = AccountClassification
        fields = [
            'id',
            'name',
            'internal_path',
            'layer',
            'parent',
            'children_count',
            'accounts_count',
            'created_at',
        ]
        # All fields are read-only because users don't directly create
        # classifications through this serializer. They're either
        # auto-generated or created through the "add Layer 3" endpoint.
        read_only_fields = fields

    def get_layer(self, obj):
        return obj.layer

    def get_children_count(self, obj):
        """
        How many direct children does this classification have?
        For Layer 1 (Asset): how many Layer 2 groups under it.
        For Layer 3 (Cash): always 0 (no classification children).
        """
        return obj.children.count()

    def get_accounts_count(self, obj):
        return obj.get_all_accounts().count()


class CreateClassificationSerializer(serializers.Serializer):
    """
    We use serializers.Serializer instead of serializers.ModelSerializer here.
    The difference:
    - ModelSerializer: auto-generates fields from a model. Great for simple CRUD.
    - Serializer: you define every field manually. Better when you need full
      control over what the frontend sends, especially when it doesn't map
      directly to a model.

    Here, the frontend sends a parent Layer 2 path and a name. We do a lot
    of custom work (generate internal_path, validate the parent, etc.) that
    doesn't map cleanly to the model fields.
    """

    # CharField: expects a string value from the frontend.
    # help_text: appears in the auto-generated API documentation.
    name = serializers.CharField(
        max_length=200,
        help_text='Name for the new Layer 3 group (e.g., "Digital Wallets")',
    )

    parent_path = serializers.CharField(
        max_length=500,
        help_text='Internal path of the Layer 2 parent (e.g., "1.10" for Current Asset)',
    )

    def validate_parent_path(self, value):
        """
        Custom validation for the parent_path field.

        DRF calls this automatically because the method name follows
        the pattern validate_<fieldname>. It receives the value the
        frontend sent for parent_path, and we must either:
        - Return the value (meaning it's valid)
        - Raise ValidationError (meaning it's invalid)
        """
        # self.context is a dictionary that the VIEW passes to the serializer.
        # It contains the request object and any extra data the view wants
        # to share. We put the company object in context from the view.
        company = self.context['company']

        # Check if this path actually exists and is a Layer 2 classification
        try:
            parent = AccountClassification.objects.get(
                company=company,
                internal_path=value,
            )
        except AccountClassification.DoesNotExist:
            raise serializers.ValidationError(
                f'No classification found with path "{value}".'
            )

        # Verify it's Layer 2 (new groups can only be added under Layer 2)
        if parent.layer != 2:
            raise serializers.ValidationError(
                f'New classification groups can only be added under Layer 2. '
                f'"{parent.name}" is Layer {parent.layer}.'
            )

        return value



class AccountListSerializer(serializers.ModelSerializer):

    # These fields pull data from related objects.
    # source='classification.name' means: go to this account's
    # classification object, and get its "name" field.
    # Without this, the frontend would only get the classification UUID
    # and would need a separate API call to get the name.
    classification_name = serializers.CharField(
        source='classification.name',
        read_only=True,
    )

    parent_account_name = serializers.CharField(
        source='parent_account.name',
        read_only=True,
        default=None,
    )

    is_sub_account = serializers.BooleanField(read_only=True)

    class Meta:
        model = Account
        fields = [
            'id',
            'name',
            'code',
            'internal_path',
            'normal_balance',
            'currency',
            'classification',
            'classification_name',
            'parent_account',
            'parent_account_name',
            'is_sub_account',
            'is_system_account',
            'is_deletable',
            'is_active',
        ]
        read_only_fields = fields


class AccountDetailSerializer(serializers.ModelSerializer):
    """
    Full detail serializer for a single account.
    Includes everything from the list serializer plus additional info.
    Used when viewing one specific account's full details.
    """

    classification_name = serializers.CharField(
        source='classification.name',
        read_only=True,
    )

    parent_account_name = serializers.CharField(
        source='parent_account.name',
        read_only=True,
        default=None,
    )

    is_sub_account = serializers.BooleanField(read_only=True)
    sub_accounts_count = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(
        source='created_by.full_name',
        read_only=True,
        default=None,
    )

    class Meta:
        model = Account
        fields = [
            'id',
            'name',
            'code',
            'internal_path',
            'normal_balance',
            'currency',
            'classification',
            'classification_name',
            'parent_account',
            'parent_account_name',
            'is_sub_account',
            'is_system_account',
            'is_deletable',
            'is_active',
            'description',
            'sub_accounts_count',
            'created_by',
            'created_by_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_sub_accounts_count(self, obj):
        """Count how many active sub-accounts exist directly under this account."""
        return obj.sub_accounts.filter(is_active=True).count()


class CreateAccountSerializer(serializers.Serializer):
    """
    Validates and processes data for creating a new account.
    We use serializers.Serializer (not ModelSerializer) because the creation
    process involves a lot of custom logic: generating internal_path,
    inheriting currency, validating parent relationships, etc.
    """

    name = serializers.CharField(
        max_length=200,
        help_text='Account name (e.g., "Petty Cash - Dhaka")',
    )

    code = serializers.CharField(
        max_length=30,
        help_text='User-visible account code (must be unique within the company)',
    )

    # UUIDField: expects a UUID string from the frontend.
    # required=False: this field is optional. When creating a sub-account,
    # the user sends parent_account_id instead.
    classification_id = serializers.UUIDField(
        required=False,
        help_text='Layer 3 classification ID. Required when creating a Layer 4 account.',
    )

    parent_account_id = serializers.UUIDField(
        required=False,
        help_text='Parent account ID. Required when creating a sub-account (Layer 5+).',
    )

    normal_balance = serializers.ChoiceField(
        choices=['DEBIT', 'CREDIT'],
        help_text='DEBIT or CREDIT. Determines how the balance is calculated.',
    )

    currency = serializers.CharField(
        max_length=3,
        required=False,
        help_text='Currency code (e.g., "BDT", "USD"). Defaults to company base currency.',
    )

    description = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        help_text='Optional description of the account.',
    )

    def validate_name(self, value):
        company = self.context['company']
        # Check company-wide uniqueness (not just within classification)
        if Account.objects.filter(
            company=company,
            name=value,
            is_active=True,
        ).exists():
            raise serializers.ValidationError(
                f'An active account named "{value}" already exists in this company. '
                f'Account names must be unique across the entire Chart of Accounts.'
            )
        return value

    def validate_code(self, value):
        """
        Account codes cannot contain spaces and must be unique
        within the company.

        NOTE: This method ONLY validates the 'code' field.
        Name uniqueness is checked in validate() because it needs
        access to the classification, which is resolved there.
        """
        if ' ' in value:
            raise serializers.ValidationError(
                'Account code cannot contain spaces.'
            )

        company = self.context['company']
        if Account.objects.filter(company=company, code=value, is_active=True).exists():
            raise serializers.ValidationError(
                f'Account code "{value}" is already in use.'
            )

        return value

    def validate(self, data):
        """
        Cross-field validation. This runs AFTER all individual field
        validations pass. Here we check rules that involve multiple fields.

        DRF calls this automatically. The "data" parameter is a dictionary
        containing all the validated field values.
        """
        company = self.context['company']
        classification_id = data.get('classification_id')
        parent_account_id = data.get('parent_account_id')

        # ── Rule 1: Must provide exactly one of classification_id or parent_account_id ──
        if classification_id and parent_account_id:
            raise serializers.ValidationError(
                'Provide either classification_id (for Layer 4) or '
                'parent_account_id (for sub-accounts), not both.'
            )

        if not classification_id and not parent_account_id:
            raise serializers.ValidationError(
                'Provide either classification_id (for Layer 4) or '
                'parent_account_id (for sub-accounts).'
            )

        # ── Scenario A: Creating a Layer 4 account under a classification ──
        if classification_id:
            try:
                classification = AccountClassification.objects.get(
                    id=classification_id,
                    company=company,
                )
            except AccountClassification.DoesNotExist:
                raise serializers.ValidationError(
                    {'classification_id': 'Classification not found.'}
                )

            if classification.layer != 3:
                raise serializers.ValidationError(
                    {'classification_id': f'Accounts can only be created under Layer 3 classifications. '
                                          f'"{classification.name}" is Layer {classification.layer}.'}
                )

            # Store the classification object for use in the view's create logic
            data['_classification'] = classification
            data['_parent_account'] = None

        # ── Scenario B: Creating a sub-account under an existing account ──
        if parent_account_id:
            try:
                parent_account = Account.objects.get(
                    id=parent_account_id,
                    company=company,
                    is_active=True,
                )
            except Account.DoesNotExist:
                raise serializers.ValidationError(
                    {'parent_account_id': 'Parent account not found.'}
                )

            # Sub-accounts inherit their parent's classification
            data['_classification'] = parent_account.classification
            data['_parent_account'] = parent_account

            # ── Rule: Sub-account currency must match the Layer 4 ancestor ──
            # Walk up to find the Layer 4 ancestor
            ancestor = parent_account
            while ancestor.parent_account is not None:
                ancestor = ancestor.parent_account

            user_currency = data.get('currency')
            if user_currency and user_currency != ancestor.currency:
                raise serializers.ValidationError(
                    {'currency': f'Sub-accounts must use the same currency as their '
                                 f'Layer 4 ancestor ({ancestor.currency}).'}
                )

            # Force the currency to match the ancestor
            data['currency'] = ancestor.currency

        # ── Default currency to company base currency if not provided ──
        if not data.get('currency'):
            data['currency'] = company.base_currency

        # ────────────────────────────────────────────────
        # DUPLICATE NAME CHECK
        # ────────────────────────────────────────────────
        # Enforced at the classification level: no two active accounts
        # under the same Layer 3 group can share a name.
        #
        # WHY HERE AND NOT IN validate_name()?
        #   Because we need the resolved classification object, which is
        #   only available after the classification_id / parent_account_id
        #   logic above runs. Field-level validators (validate_name) execute
        #   before cross-field validate(), so they don't have access to
        #   _classification yet.
        #
        # This is the serializer-level check. The database constraint
        # (unique_active_account_name_per_classification) is the safety net.
        # ────────────────────────────────────────────────
        classification = data['_classification']
        name = data['name']

        if Account.objects.filter(
            company=company,
            classification=classification,
            name=name,
            is_active=True,
        ).exists():
            raise serializers.ValidationError({
                'name': (
                    f'An active account named "{name}" already exists '
                    f'under the "{classification.name}" classification.'
                ),
            })

        return data


class UpdateAccountSerializer(serializers.Serializer):
    """
    Validates PATCH updates to an existing account.

    Only name, code, and description can be changed after creation.
    Normal balance, currency, and classification are immutable once
    the account exists (changing them would invalidate existing
    journal entries).
    """

    # required=False on every field because PATCH requests
    # only send the fields being changed, not all fields.
    name = serializers.CharField(
        max_length=200,
        required=False,
    )

    code = serializers.CharField(
        max_length=30,
        required=False,
    )

    description = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    def validate_name(self, value):
        company = self.context['company']
        account = self.context['account']
        if Account.objects.filter(
            company=company,
            name=value,
            is_active=True,
        ).exclude(id=account.id).exists():
            raise serializers.ValidationError(
                f'An active account named "{value}" already exists in this company. '
                f'Account names must be unique across the entire Chart of Accounts.'
            )
        return value

    def validate_code(self, value):
        if ' ' in value:
            raise serializers.ValidationError(
                'Account code cannot contain spaces.'
            )

        company = self.context['company']

        # self.context['account'] is the existing account being updated.
        # We need to exclude it from the uniqueness check — an account
        # should be allowed to keep its own code.
        account = self.context['account']

        if Account.objects.filter(
            company=company,
            code=value,
            is_active=True,
        ).exclude(id=account.id).exists():
            raise serializers.ValidationError(
                f'Account code "{value}" is already in use.'
            )

        return value

    def validate(self, data):
        """
        Cross-field validation for updates.

        If the user is renaming the account, we check that the new name
        doesn't conflict with another active account in the same
        classification.
        """
        # Only run name uniqueness check if name is actually being changed
        if 'name' not in data:
            return data

        company = self.context['company']
        account = self.context['account']
        new_name = data['name']

        # If the name hasn't actually changed, skip the check
        if new_name == account.name:
            return data

        # Check for duplicates within the same classification
        if Account.objects.filter(
            company=company,
            classification=account.classification,
            name=new_name,
            is_active=True,
        ).exclude(id=account.id).exists():
            raise serializers.ValidationError({
                'name': (
                    f'An active account named "{new_name}" already exists '
                    f'under the "{account.classification.name}" classification.'
                ),
            })

        return data


class SystemAccountMappingSerializer(serializers.ModelSerializer):


    account_name = serializers.CharField(
        source='account.name',
        read_only=True,
    )

    account_code = serializers.CharField(
        source='account.code',
        read_only=True,
    )

    class Meta:
        model = SystemAccountMapping
        fields = [
            'id',
            'system_code',
            'account',
            'account_name',
            'account_code',
        ]
        read_only_fields = fields