# Generated by Django 5.1 on 2024-12-24 06:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0003_user_latitude_user_longitude'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='full_location',
            field=models.TextField(blank=True, null=True),
        ),
    ]
