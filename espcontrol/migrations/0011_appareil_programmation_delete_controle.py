# Generated by Django 5.2 on 2025-04-12 22:15

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('espcontrol', '0010_rename_appareil_controle_app'),
    ]

    operations = [
        migrations.CreateModel(
            name='Appareil',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=100)),
                ('emplacement', models.CharField(max_length=100)),
                ('etat', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='Programmation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('heure_on', models.TimeField()),
                ('heure_off', models.TimeField()),
                ('appareil', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='espcontrol.appareil')),
            ],
        ),
        migrations.DeleteModel(
            name='Controle',
        ),
    ]
