# Generated by Django 5.2 on 2025-04-13 12:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('espcontrol', '0014_rename_timestamp_soildata_created_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='Video',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('video', models.FileField(upload_to='videos/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
