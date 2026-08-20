"""
Cree/actualise une fiche de tracabilite (avec QR code) dans product_transparency
pour chaque produit publie dans la boutique founatekapp, afin que les acheteurs
puissent verifier n'importe quel produit du catalogue avant achat.

Idempotent : rejoue sans creer de doublons (le SKU encode le slug du produit
boutique, donc relancer la commande met juste a jour les fiches existantes).

Usage :
    python manage.py sync_boutique_products
    python manage.py sync_boutique_products --username elhadj
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.text import slugify


class Command(BaseCommand):
    help = "Synchronise les produits de la boutique (founatekapp) vers la tracabilite (product_transparency)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username", default="elhadj",
            help="Compte formateur/admin auquel rattacher l'entreprise de tracabilite (defaut: elhadj)",
        )

    def handle(self, *args, **options):
        from founatekapp.models import Product as ShopProduct
        from product_transparency.models import Company, Product as TraceProduct, ProductPricing, ProductPriceHistory

        username = options["username"]
        user = User.objects.filter(username=username).first()
        if not user:
            raise CommandError(f"Utilisateur '{username}' introuvable.")

        company = Company.objects.filter(user=user).first()
        if not company:
            base_slug = slugify(f"{user.username}-boutique") or "boutique-founatek"
            slug = base_slug
            n = 1
            while Company.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{n}"
                n += 1
            company = Company.objects.create(user=user, name="Founatek Boutique", slug=slug, currency="GNF")
            self.stdout.write(self.style.WARNING(f"Entreprise de traçabilité créée : {company.name} ({company.slug})"))
        else:
            self.stdout.write(f"Entreprise utilisée : {company.name} ({company.slug})")

        shop_products = ShopProduct.objects.filter(is_active=True)
        if not shop_products.exists():
            self.stdout.write(self.style.WARNING("Aucun produit actif trouvé dans la boutique — rien à synchroniser."))
            return

        today = timezone.now().date()
        created, updated = 0, 0

        for sp in shop_products:
            sku = f"SHOP-{sp.slug}"[:100]

            trace_product, is_new = TraceProduct.objects.get_or_create(
                sku=sku,
                defaults={"company": company, "name": sp.name},
            )

            if not is_new:
                # Reassigne au cas où la fiche existait déjà (ex: créée manuellement) et met le nom à jour.
                trace_product.company = company
                trace_product.name = sp.name
                trace_product.save(update_fields=["company", "name"])

            # Copie la photo principale du produit boutique si la fiche n'en a pas encore.
            if sp.image and not trace_product.image:
                try:
                    sp.image.open("rb")
                    trace_product.image.save(
                        sp.image.name.split("/")[-1], ContentFile(sp.image.read()), save=True
                    )
                except Exception:
                    pass
                finally:
                    try:
                        sp.image.close()
                    except Exception:
                        pass

            # Prix + dates : la boutique ne suit ni date de production ni date de péremption
            # (produits électroniques/IoT, pas périssables) — placeholder large (10 ans),
            # à ajuster manuellement depuis le tableau de bord traçabilité si besoin.
            pricing = getattr(trace_product, "pricing", None)
            price_changed = pricing is None or pricing.price != sp.price
            if pricing is None:
                pricing = ProductPricing.objects.create(
                    product=trace_product, price=sp.price,
                    production_date=today, expiry_date=today + timedelta(days=3650),
                )
            elif price_changed:
                pricing.price = sp.price
                pricing.save(update_fields=["price"])

            if price_changed:
                ProductPriceHistory.objects.create(
                    product=trace_product, price=sp.price,
                    production_date=pricing.production_date, expiry_date=pricing.expiry_date,
                    changed_by=user, reason="Synchronisation depuis la boutique",
                )

            if is_new:
                created += 1
                self.stdout.write(f"  + Créé : {sp.name} (SKU {sku})")
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nTerminé : {created} fiche(s) créée(s), {updated} déjà à jour/mise(s) à jour, "
            f"sur {shop_products.count()} produit(s) boutique."
        ))
        self.stdout.write(
            "Chaque fiche a son QR code généré automatiquement, consultable depuis le tableau "
            "de bord traçabilité. Pense à ajuster les dates de production/péremption si pertinent."
        )
