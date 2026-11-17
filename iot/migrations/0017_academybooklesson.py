from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("iot", "0016_academypackpayment")]

    operations = [
        migrations.CreateModel(
            name="AcademyBookLesson",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("chapter_number", models.CharField(max_length=2)),
                ("published", models.BooleanField(default=False)),
                ("lecon", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="academy_book_entry", to="iot.lecon")),
            ],
        ),
    ]
