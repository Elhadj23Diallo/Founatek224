from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("iot", "0013_seed_platform_modules_dashboard"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AcademyPackAccess",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("pack_slug", models.SlugField(max_length=120)),
                ("provider", models.CharField(choices=[("stripe", "Stripe"), ("paypal", "PayPal"), ("admin", "Attribution administrative")], max_length=20)),
                ("payment_reference", models.CharField(blank=True, max_length=255)),
                ("amount_eur", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("active", models.BooleanField(default=False)),
                ("granted_at", models.DateTimeField(auto_now_add=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="academy_pack_accesses", to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints": [
                models.UniqueConstraint(fields=("user", "pack_slug"), name="unique_academy_pack_access")
            ]},
        ),
    ]
