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
            'cash_flow_category',   # ← NEW: Cash flow category for L3
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

    # ── NEW: Cash flow category for the Cash Flow Statement ──
    # Optional — defaults to OPERATING, which is the most common category.
    # Users can set this when creating custom L3 classifications to control
    # where accounts under this group appear in the Cash Flow Statement.
    cash_flow_category = serializers.ChoiceField(
        choices=['OPERATING', 'INVESTING', 'FINANCING', 'CASH'],
        default='OPERATING',
        required=False,
        help_text=(
            'Cash Flow Statement category. Determines which section '
            'accounts under this classification appear in. '
            'Options: OPERATING, INVESTING, FINANCING, CASH. '
            'Default: OPERATING.'
        ),
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
        company = self.context['company']
        classification_id = data.get('classification_id')
        parent_account_id = data.get('parent_account_id')

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

            data['_classification'] = classification
            data['_parent_account'] = None

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

            data['_classification'] = parent_account.classification
            data['_parent_account'] = parent_account

            ancestor = parent_account
            while ancestor.parent_account is not None:
                ancestor = ancestor.parent_account

            user_currency = data.get('currency')
            if user_currency and user_currency != ancestor.currency:
                raise serializers.ValidationError(
                    {'currency': f'Sub-accounts must use the same currency as their '
                                 f'Layer 4 ancestor ({ancestor.currency}).'}
                )

            data['currency'] = ancestor.currency

        if not data.get('currency'):
            data['currency'] = company.base_currency

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
        if 'name' not in data:
            return data

        company = self.context['company']
        account = self.context['account']
        new_name = data['name']

        if new_name == account.name:
            return data

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