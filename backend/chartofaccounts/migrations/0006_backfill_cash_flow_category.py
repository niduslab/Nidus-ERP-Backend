# backend/chartofaccounts/migrations/0006_backfill_cash_flow_category.py

"""
DATA MIGRATION: Sets cash_flow_category for all existing L3
classifications based on the mapping from seed.py.

This must run AFTER 0005 (which adds the field).
"""

from django.db import migrations


# ── Mapping: L3 internal_path → cash_flow_category ──
# All companies share the same seed structure, so we can
# map by internal_path reliably for system classifications.
# Custom classifications (not in the map) get OPERATING as default.

L3_PATH_TO_CATEGORY = {
    '1.10.1010': 'CASH',        # Cash
    '1.10.1020': 'CASH',        # Bank
    '1.10.1030': 'OPERATING',   # Inventory
    '1.10.1040': 'OPERATING',   # Tax Receivables
    '1.10.1050': 'OPERATING',   # Advances & Prepayments
    '1.10.1060': 'OPERATING',   # Receivables
    '1.10.1070': 'OPERATING',   # Other Current Asset
    '1.11.1110': 'INVESTING',   # Property Plant & Equipment
    '1.11.1120': 'INVESTING',   # Accumulated Depreciation
    '1.11.1130': 'INVESTING',   # Intangible Assets
    '1.11.1140': 'INVESTING',   # Investments
    '1.11.1150': 'INVESTING',   # Other Non-Current Assets
    '2.20.2010': 'OPERATING',   # Accounts Payables
    '2.20.2020': 'OPERATING',   # Accrued Expense
    '2.20.2030': 'OPERATING',   # Withholding Tax & VAT
    '2.20.2040': 'FINANCING',   # Short-Term Loans
    '2.20.2050': 'OPERATING',   # Unearned Revenue
    '2.20.2060': 'OPERATING',   # Suspense & Clearing
    '2.20.2070': 'OPERATING',   # Other Current Liabilities
    '2.20.2080': 'OPERATING',   # Provisions
    '2.21.2110': 'FINANCING',   # Long-Term Loans
    '2.21.2120': 'FINANCING',   # Other Long-Term Liabilities
    '3.30.3010': 'FINANCING',   # Owner's Equity
    '4.40.4010': 'OPERATING',   # Revenue
    '4.41.4110': 'OPERATING',   # Interest & Investment Income
    '4.41.4120': 'OPERATING',   # Rent Income
    '4.41.4130': 'OPERATING',   # Other Income
    '5.50.5010': 'OPERATING',   # Cost of Goods Sold/Services
    '5.51.5110': 'OPERATING',   # Payroll & Employee Costs
    '5.51.5120': 'OPERATING',   # Premises & Utilities
    '5.51.5130': 'OPERATING',   # Administrative & General
    '5.51.5140': 'OPERATING',   # Depreciation & Amortisation
    '5.51.5150': 'OPERATING',   # Sales & Marketing Expense
    '5.51.5160': 'OPERATING',   # Other Operating Expense
    '5.51.5170': 'OPERATING',   # Research & Development Expense
    '5.52.5210': 'OPERATING',   # Financial Expense
    '5.52.5220': 'OPERATING',   # Tax Expense
    '5.52.5230': 'OPERATING',   # Other Non-Operating Expense
}


def backfill_cash_flow_category(apps, schema_editor):
    """
    Set cash_flow_category for all existing L3 classifications.
    L1 and L2 classifications are left as NULL.
    Custom L3 classifications (not in the map) get OPERATING as default.
    """
    AccountClassification = apps.get_model('chartofaccounts', 'AccountClassification')

    for cls in AccountClassification.objects.all():
        dot_count = cls.internal_path.count('.')
        if dot_count != 2:
            # L1 or L2 — leave as NULL
            continue

        # Look up the category from our mapping
        category = L3_PATH_TO_CATEGORY.get(cls.internal_path, 'OPERATING')
        cls.cash_flow_category = category
        cls.save(update_fields=['cash_flow_category'])


def reverse_backfill(apps, schema_editor):
    """Reverse: set all cash_flow_category back to NULL."""
    AccountClassification = apps.get_model('chartofaccounts', 'AccountClassification')
    AccountClassification.objects.all().update(cash_flow_category=None)


class Migration(migrations.Migration):

    dependencies = [
        ('chartofaccounts', '0005_accountclassification_cash_flow_category'),
    ]

    operations = [
        migrations.RunPython(
            backfill_cash_flow_category,
            reverse_code=reverse_backfill,
        ),
    ]