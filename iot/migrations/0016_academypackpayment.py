from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("iot", "0015_merge_academy_and_bloc_type"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AcademyPackPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("pack_slug", models.SlugField(max_length=120)),
                ("provider", models.CharField(default="stripe", max_length=20)),
                ("checkout_id", models.CharField(max_length=255, unique=True)),
                ("payment_reference", models.CharField(blank=True, max_length=255)),
                ("amount_eur", models.DecimalField(decimal_places=2, max_digits=10)),
                ("status", models.CharField(default="pending", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="academy_pack_payments", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
