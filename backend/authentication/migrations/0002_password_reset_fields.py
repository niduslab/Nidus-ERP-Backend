# backend/authentication/migrations/0002_password_reset_fields.py
#
# Adds password-reset OTP fields to the User model.
# Two new nullable fields — safe for an online migration, no data backfill needed.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # Depends only on the initial User migration — no cross-app dependencies.
        ('authentication', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='password_reset_code',
            field=models.CharField(
                blank=True,
                help_text='6-digit OTP sent to user email for password reset. Cleared on successful reset.',
                max_length=6,
                null=True,
                verbose_name='password reset code',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='password_reset_code_expires',
            field=models.DateTimeField(
                blank=True,
                help_text='When the password reset OTP expires. Typically now + OTP_EXPIRY_MINUTES.',
                null=True,
                verbose_name='password reset code expiry',
            ),
        ),
    ]