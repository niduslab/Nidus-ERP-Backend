# backend/chartofaccounts/migrations/0005_accountclassification_cash_flow_category.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chartofaccounts', '0004_remove_account_unique_active_account_name_per_classification_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='accountclassification',
            name='cash_flow_category',
            field=models.CharField(
                blank=True,
                choices=[
                    ('OPERATING', 'Operating Activities'),
                    ('INVESTING', 'Investing Activities'),
                    ('FINANCING', 'Financing Activities'),
                    ('CASH', 'Cash & Cash Equivalents'),
                ],
                default=None,
                help_text=(
                    'Which section of the Cash Flow Statement accounts '
                    'under this classification appear in. '
                    'Only applicable to Layer 3 classifications.'
                ),
                max_length=10,
                null=True,
                verbose_name='cash flow category',
            ),
        ),
    ]
