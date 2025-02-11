# Generated by Django 5.1 on 2024-08-20 07:58

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pickleitcollection', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentDetails',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField()),
                ('secret_key', models.CharField(max_length=250, unique=True)),
                ('var_chargeamount', models.IntegerField()),
                ('payment_for', models.CharField(blank=True, max_length=250, null=True)),
                ('payment_for_id', models.TextField(blank=True, null=True)),
                ('payment_by', models.CharField(blank=True, max_length=250, null=True)),
                ('payment_amount', models.IntegerField()),
                ('payment_status', models.BooleanField()),
                ('created_at', models.DateTimeField()),
                ('stripe_response', models.JSONField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('chargeamount', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='pickleitcollection.chargeamount')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('payment_for_ad', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='pickleitcollection.advertisement')),
            ],
        ),
    ]
