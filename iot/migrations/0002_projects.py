# Generated by Django 5.2 on 2025-05-05 12:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('iot', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Projects',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titre', models.CharField(max_length=200)),
                ('contenu', models.TextField()),
                ('ordre', models.PositiveIntegerField(default=0)),
                ('video', models.FileField(blank=True, null=True, upload_to='tutos/')),
                ('date_ajout', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['ordre'],
            },
        ),
    ]
