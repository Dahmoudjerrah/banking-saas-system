# Generated by Django 5.1.1 on 2025-06-19 11:13

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0002_initial'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('transactions', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='passwordresetotp',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='password_reset_otps', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='paymentrequest',
            name='merchant',
            field=models.ForeignKey(limit_choices_to={'type_account': 'business'}, on_delete=django.db.models.deletion.CASCADE, to='accounts.businessaccount'),
        ),
        migrations.AddField(
            model_name='pretransaction',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pretransactions', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='transaction',
            name='destination_account_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='destination_transactions', to='contenttypes.contenttype'),
        ),
        migrations.AddField(
            model_name='transaction',
            name='source_account_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='source_transactions', to='contenttypes.contenttype'),
        ),
        migrations.AddField(
            model_name='fee',
            name='transaction',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='fee', to='transactions.transaction'),
        ),
        migrations.AddIndex(
            model_name='passwordresetotp',
            index=models.Index(fields=['phone_number'], name='password_re_phone_n_6bfc22_idx'),
        ),
        migrations.AddIndex(
            model_name='passwordresetotp',
            index=models.Index(fields=['otp_code'], name='password_re_otp_cod_3b18b3_idx'),
        ),
        migrations.AddIndex(
            model_name='passwordresetotp',
            index=models.Index(fields=['reset_token'], name='password_re_reset_t_3f19ef_idx'),
        ),
        migrations.AddIndex(
            model_name='passwordresetotp',
            index=models.Index(fields=['created_at'], name='password_re_created_4ee1aa_idx'),
        ),
    ]
