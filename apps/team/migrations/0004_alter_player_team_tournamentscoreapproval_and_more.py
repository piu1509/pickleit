# Generated by Django 5.1 on 2025-01-10 10:40

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team', '0003_alter_player_player_phone_number'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='player',
            name='team',
            field=models.ManyToManyField(blank=True, to='team.team'),
        ),
        migrations.CreateModel(
            name='TournamentScoreApproval',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('team1_approval', models.BooleanField(default=False)),
                ('team2_approval', models.BooleanField(default=False)),
                ('tournament', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='approved_match', to='team.tournament')),
            ],
        ),
        migrations.CreateModel(
            name='TournamentScoreReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField(blank=True, null=True)),
                ('status', models.CharField(choices=[('Pending', 'Pending'), ('Resolved', 'Resolved')], max_length=10)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reporting_user', to=settings.AUTH_USER_MODEL)),
                ('tournament', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reported_match', to='team.tournament')),
            ],
        ),
    ]
