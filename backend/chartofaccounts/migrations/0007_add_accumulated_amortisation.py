# backend/chartofaccounts/migrations/0007_add_accumulated_amortisation.py

"""
DATA MIGRATION: Adds the Accumulated Amortisation L3 classification
and ledger account to all existing companies.

New L3: 1.11.1125 — Accumulated Amortisation (cash_flow_category=INVESTING)
New Account: 11251 — Accumulated Amortisation (CREDIT, system, non-deletable)
New SystemAccountMapping: ACCUMULATED_AMORTISATION → 11251
"""

from django.db import migrations


def add_accumulated_amortisation(apps, schema_editor):
    Company = apps.get_model('companies', 'Company')
    AccountClassification = apps.get_model('chartofaccounts', 'AccountClassification')
    Account = apps.get_model('chartofaccounts', 'Account')
    SystemAccountMapping = apps.get_model('chartofaccounts', 'SystemAccountMapping')

    for company in Company.objects.all():
        # Find the parent L2 (Non-Current Asset = 1.11)
        try:
            parent_l2 = AccountClassification.objects.get(
                company=company, internal_path='1.11',
            )
        except AccountClassification.DoesNotExist:
            continue

        # Check if already exists (idempotent)
        if AccountClassification.objects.filter(
            company=company, internal_path='1.11.1125',
        ).exists():
            continue

        # Create L3 classification
        new_l3 = AccountClassification.objects.create(
            company=company,
            parent=parent_l2,
            name='Accumulated Amortisation',
            internal_path='1.11.1125',
            cash_flow_category='INVESTING',
        )

        # Create the ledger account
        new_account = Account.objects.create(
            company=company,
            classification=new_l3,
            parent_account=None,
            name='Accumulated Amortisation',
            code='11251',
            internal_path='1.11.1125.0001',
            normal_balance='CREDIT',
            currency=company.base_currency,
            is_system_account=True,
            is_deletable=False,
            is_active=True,
        )

        # Create system mapping
        SystemAccountMapping.objects.create(
            company=company,
            system_code='ACCUMULATED_AMORTISATION',
            account=new_account,
        )


def reverse_add(apps, schema_editor):
    SystemAccountMapping = apps.get_model('chartofaccounts', 'SystemAccountMapping')
    Account = apps.get_model('chartofaccounts', 'Account')
    AccountClassification = apps.get_model('chartofaccounts', 'AccountClassification')

    SystemAccountMapping.objects.filter(system_code='ACCUMULATED_AMORTISATION').delete()
    Account.objects.filter(code='11251').delete()
    AccountClassification.objects.filter(internal_path='1.11.1125').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('chartofaccounts', '0006_backfill_cash_flow_category'),
        ('companies', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            add_accumulated_amortisation,
            reverse_code=reverse_add,
        ),
    ]