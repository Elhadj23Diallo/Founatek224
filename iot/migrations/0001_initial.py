# Generated by Django 5.2 on 2025-05-04 14:25

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Chapitre',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titre', models.CharField(max_length=200)),
                ('contenu', models.TextField()),
                ('ordre', models.PositiveIntegerField(default=0)),
                ('image', models.ImageField(blank=True, null=True, upload_to='chapitres/')),
                ('date_ajout', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['ordre'],
            },
        ),
    ]
