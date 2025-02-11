# Generated by Django 5.1 on 2024-08-20 06:29

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Advertisement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4)),
                ('secret_key', models.CharField(max_length=250, unique=True)),
                ('name', models.CharField(blank=True, max_length=250, null=True)),
                ('image', models.ImageField(blank=True, null=True, upload_to='advertisement_image/')),
                ('script_text', models.TextField(blank=True, null=True)),
                ('url', models.TextField(blank=True, null=True)),
                ('approved_by_admin', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('start_date', models.DateTimeField(blank=True, null=True)),
                ('end_date', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='advertisementCreatedBy', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='AdvertiserFacility',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4)),
                ('secret_key', models.CharField(blank=True, max_length=250, null=True, unique=True)),
                ('facility_name', models.CharField(blank=True, max_length=200, null=True)),
                ('facility_type', models.CharField(blank=True, choices=[('Pickleball Facility', 'Pickleball Facility'), ('Sports Facility', 'Sports Facility'), ('Country Club', 'Country Club'), ('Neighborhood Courts', 'Neighborhood Courts'), ('Public Area', 'Public Area'), ('Other', 'Other')], max_length=200, null=True)),
                ('court_type', models.CharField(blank=True, choices=[('Outdoor Court Only', 'Outdoor Court Only'), ('Indoor Court Only', 'Indoor Court Only'), ('Both Outdoor and Indoor', 'Both Outdoor and Indoor')], max_length=200, null=True)),
                ('membership_type', models.CharField(blank=True, choices=[('Open to Public', 'Open to Public'), ('Members only', 'Members only'), ('Pay to Play', 'Pay to Play')], max_length=200, null=True)),
                ('complete_address', models.TextField(blank=True, help_text='street, city, state, country, PIN-postal_code', null=True)),
                ('latitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('number_of_courts', models.PositiveIntegerField()),
                ('response', models.JSONField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('acknowledgement', models.BooleanField(default=False)),
                ('is_view', models.BooleanField(default=False)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='facilityCreatedBy', to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='facilityUpdatedBy', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='AmbassadorsDetails',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ambassador', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ambassador', to=settings.AUTH_USER_MODEL)),
                ('follower', models.ManyToManyField(related_name='ambassador_follower', to=settings.AUTH_USER_MODEL)),
                ('following', models.ManyToManyField(related_name='ambassador_following', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='AmbassadorsPost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4)),
                ('secret_key', models.CharField(blank=True, max_length=250, null=True, unique=True)),
                ('file', models.URLField(blank=True, null=True)),
                ('thumbnail', models.URLField(blank=True, null=True)),
                ('post_text', models.TextField(blank=True, null=True)),
                ('approved_by_admin', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='postby', to=settings.AUTH_USER_MODEL)),
                ('likes', models.ManyToManyField(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ChargeAmount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4)),
                ('secret_key', models.CharField(max_length=250, unique=True)),
                ('charge_for', models.CharField(blank=True, choices=[('Organizer', 'To Become an Organizer'), ('Sponsors', 'To Become a Sponsors'), ('Ambassador', 'To Become a Ambassador')], max_length=250, null=True, unique=True)),
                ('charge_amount', models.PositiveIntegerField(blank=True, help_text='subscription amount ($)', null=True)),
                ('effective_time', models.DurationField(blank=True, help_text='subscription duration of month number,i.e. [days hours:minutes:seconds], for 1 month [30 00:00:00]', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='chargeAmountCreatedBy', to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='chargeAmountUpdatedBy', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Notifications',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField()),
                ('screen', models.CharField(blank=True, choices=[('Player List', 'Player List'), ('User Team List', 'User Team List'), ('Leauge List', 'Leauge List'), ('Home', 'Home'), ('stats', 'Stats'), ('sponsor_view', 'Sponsor View'), ('sponsor_add', 'Sponsor Add')], max_length=250, null=True)),
                ('url', models.TextField(blank=True, null=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('is_read', models.BooleanField(default=False)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
