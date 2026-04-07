# backend/chartofaccounts/models.py

import uuid
from django.conf import settings
from django.db import models


# ══════════════════════════════════════════════════
# CASH FLOW CATEGORY CHOICES
# ══════════════════════════════════════════════════

class CashFlowCategoryChoices(models.TextChoices):
    """
    Categorises L3 classifications for the Cash Flow Statement.

    The Cash Flow Statement groups all account movements into one of
    these categories. The category is set on the L3 classification
    because that's the layer accounts attach to — so all accounts
    under a given L3 inherit its cash flow category.

    OPERATING:  Day-to-day business activities. Includes working capital
                changes (AR, AP, Inventory) and all P&L items.
    INVESTING:  Purchase/sale of long-term assets (PPE, Investments,
                Intangibles) and their contra accounts (Accumulated Depreciation).
    FINANCING:  Debt and equity transactions (loans, owner capital,
                dividends, drawings).
    CASH:       Cash and cash equivalents (Petty Cash, Bank, etc.).
                These are NOT an activity — they are the RESULT.
                Their opening/closing balances form the verification line.
    """
    OPERATING = 'OPERATING', 'Operating Activities'
    INVESTING = 'INVESTING', 'Investing Activities'
    FINANCING = 'FINANCING', 'Financing Activities'
    CASH = 'CASH', 'Cash & Cash Equivalents'


class AccountClassification(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='classifications',
        verbose_name='company',
    )

    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='parent classification',
    )

    name = models.CharField(
        max_length=200,
        verbose_name='classification name',
    )

    internal_path = models.CharField(
        max_length=500,
        db_index=True,
        verbose_name='internal path',
        help_text='System-generated. Do not edit manually.',
    )

    # ── Cash Flow Category (L3 only) ──
    # Only meaningful for Layer 3 classifications.
    # L1 and L2 classifications have this set to NULL.
    # Determines which section of the Cash Flow Statement
    # accounts under this classification appear in.
    cash_flow_category = models.CharField(
        max_length=10,
        choices=CashFlowCategoryChoices.choices,
        null=True,
        blank=True,
        default=None,
        verbose_name='cash flow category',
        help_text=(
            'Which section of the Cash Flow Statement accounts '
            'under this classification appear in. '
            'Only applicable to Layer 3 classifications.'
        ),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='created at',
    )

    class Meta:
        verbose_name = 'account classification'
        verbose_name_plural = 'account classifications'

        ordering = ['internal_path']

        constraints = [
            models.UniqueConstraint(
                fields=['company', 'internal_path'],
                name='unique_classification_path_per_company',
            ),
        ]

    def __str__(self):
        return f"{self.internal_path} — {self.name}"

    @property
    def layer(self):
        """
        Derive the layer from internal_path instead of storing it.
        """
        return len(self.internal_path.split('.'))

    def get_all_accounts(self):

        if self.layer == 3:
        
            return Account.objects.filter(
                classification=self,
                is_active=True,
            )

        descendant_layer3 = AccountClassification.objects.filter(
            company=self.company,
            internal_path__startswith=self.internal_path + '.',
        ).exclude(
            internal_path__regex=r'^[^.]*(\.[^.]*)?$',
        )

        return Account.objects.filter(
            classification__in=descendant_layer3,
            is_active=True,
        )
    


class NormalBalanceChoices(models.TextChoices):
    DEBIT = 'DEBIT', 'Debit'
    CREDIT = 'CREDIT', 'Credit'



class Account(models.Model):
  
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='accounts',
        verbose_name='company',
    )

    classification = models.ForeignKey(
        AccountClassification,
        on_delete=models.CASCADE,
        related_name='accounts',
        verbose_name='classification (Layer 3)',
        help_text='The Layer 3 classification group this account belongs to.',
    )

    parent_account = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sub_accounts',
        verbose_name='parent account',
    )

    name = models.CharField(
        max_length=200,
        verbose_name='account name',
    )

    code = models.CharField(
        max_length=30,
        verbose_name='account code',
    )

    internal_path = models.CharField(
        max_length=500,
        db_index=True,
        verbose_name='internal path',
        help_text='System-generated. Do not edit manually.',
    )

    normal_balance = models.CharField(
        max_length=6,
        choices=NormalBalanceChoices.choices,
        verbose_name='normal balance',
    )

    currency = models.CharField(
        max_length=3,
        verbose_name='currency',
        help_text='Defaults to company base currency. Cannot change after first transaction.',
    )

    is_system_account = models.BooleanField(
        default=False,
        verbose_name='system account',
    )

    is_deletable = models.BooleanField(
        default=True,
        verbose_name='deletable',
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name='active',
    )

    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='description',
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='created at',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='updated at',
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_accounts',
        verbose_name='created by',
    )

    class Meta:
        verbose_name = 'account'
        verbose_name_plural = 'accounts'
        ordering = ['internal_path']

        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'],
                name='unique_account_code_per_company',
            ),
            models.UniqueConstraint(
                fields=['company', 'internal_path'],
                name='unique_account_path_per_company',
            ),
            # ────────────────────────────────────────────────
            # DUPLICATE NAME PREVENTION (COMPANY-WIDE)
            # ────────────────────────────────────────────────
            models.UniqueConstraint(
                fields=['company', 'name'],
                condition=models.Q(is_active=True),
                name='unique_active_account_name_per_company',
            ),
        ]

        indexes = [
            models.Index(
                fields=['company', 'is_active'],
                name='idx_account_company_active',
            ),
            models.Index(
                fields=['company', 'classification'],
                name='idx_account_company_class',
            ),
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"

    @property
    def is_sub_account(self):
        return self.parent_account_id is not None
    



class SystemAccountMapping(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='system_account_mappings',
        verbose_name='company',
    )
    # which module it is referring to
    system_code = models.CharField(
        max_length=50,
        verbose_name='system code',
        help_text='Internal identifier used by ERP modules.',
    )

    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name='system_mappings',
        verbose_name='mapped account',
    )

    class Meta:
        verbose_name = 'system account mapping'
        verbose_name_plural = 'system account mappings'

        constraints = [
            models.UniqueConstraint(
                fields=['company', 'system_code'],
                name='unique_system_code_per_company',
            ),
        ]

    def __str__(self):
        return f"{self.system_code} → {self.account.name}"