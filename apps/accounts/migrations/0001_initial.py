# Generated by Django 5.1.1 on 2025-06-19 11:13

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AgencyAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account_number', models.CharField(max_length=30, unique=True)),
                ('balance', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('status', models.CharField(choices=[('ACTIVE', 'Actif'), ('PENDING', 'En attente'), ('BLOCKED', 'Bloqué'), ('CLOSED', 'Fermé')], default='ACTIVE', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('registration_number', models.CharField(blank=True, max_length=50, null=True)),
                ('tax_id', models.CharField(blank=True, max_length=50, null=True)),
                ('code', models.CharField(blank=True, max_length=6, null=True, unique=True)),
                ('deposit_porcentage', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('retrai_percentage', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='BusinessAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account_number', models.CharField(max_length=30, unique=True)),
                ('balance', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('status', models.CharField(choices=[('ACTIVE', 'Actif'), ('PENDING', 'En attente'), ('BLOCKED', 'Bloqué'), ('CLOSED', 'Fermé')], default='ACTIVE', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('registration_number', models.CharField(blank=True, max_length=50, null=True)),
                ('tax_id', models.CharField(blank=True, max_length=50, null=True)),
                ('code', models.CharField(blank=True, max_length=6, null=True, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='InternAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account_number', models.CharField(max_length=30, unique=True)),
                ('balance', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('status', models.CharField(choices=[('ACTIVE', 'Actif'), ('PENDING', 'En attente'), ('BLOCKED', 'Bloqué'), ('CLOSED', 'Fermé')], default='ACTIVE', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('purpose', models.CharField(blank=True, choices=[('commission', 'Commission'), ('frais', 'Frais'), ('taxe', 'Taxe'), ('reserve', 'Reserve')], max_length=50, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='PersonalAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account_number', models.CharField(max_length=30, unique=True)),
                ('balance', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('status', models.CharField(choices=[('ACTIVE', 'Actif'), ('PENDING', 'En attente'), ('BLOCKED', 'Bloqué'), ('CLOSED', 'Fermé')], default='ACTIVE', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
