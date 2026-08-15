import os
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.core.files import File

from founatekapp.models import Category, Product, ProductImage


class Command(BaseCommand):
    help = "Importe des produits depuis un fichier Excel (.xlsx). Les produits sont créés désactivés (is_active=False) en attente de validation admin."

    def add_arguments(self, parser):
        parser.add_argument('excel_path', type=str, help="Chemin vers le fichier .xlsx")
        parser.add_argument(
            '--images-dir',
            type=str,
            default='/home/Founatek224/Founatek224/media/import/',
            help="Dossier contenant les images référencées dans le fichier Excel"
        )

    def handle(self, *args, **options):
        try:
            import openpyxl
        except ImportError:
            raise CommandError("openpyxl n'est pas installé. Lancez : pip install openpyxl --break-system-packages")

        excel_path = options['excel_path']
        images_dir = options['images_dir']

        if not os.path.exists(excel_path):
            raise CommandError(f"Fichier introuvable : {excel_path}")

        wb = openpyxl.load_workbook(excel_path)
        sheet = wb.active

        headers = [cell.value.strip().lower() if cell.value else '' for cell in sheet[1]]
        required = ['nom', 'categorie', 'prix_gnf', 'stock']
        missing = [r for r in required if r not in headers]
        if missing:
            raise CommandError(f"Colonnes manquantes dans le fichier Excel : {missing}")

        created_count = 0
        error_count = 0

        for row_num, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            row_data = dict(zip(headers, row))

            nom = (row_data.get('nom') or '').strip() if row_data.get('nom') else ''
            if not nom:
                continue  # ligne vide, on saute

            try:
                categorie_nom = (row_data.get('categorie') or 'Divers').strip()
                category, _ = Category.objects.get_or_create(
                    name=categorie_nom,
                    defaults={'slug': categorie_nom.lower().replace(' ', '-')}
                )

                prix_raw = row_data.get('prix_gnf')
                try:
                    prix = Decimal(str(prix_raw))
                except (InvalidOperation, TypeError):
                    self.stdout.write(self.style.ERROR(f"Ligne {row_num}: prix_gnf invalide ({prix_raw}), ligne ignorée"))
                    error_count += 1
                    continue

                stock_raw = row_data.get('stock') or 0
                try:
                    stock = int(stock_raw)
                except (ValueError, TypeError):
                    stock = 0

                description = (row_data.get('description') or '').strip() if row_data.get('description') else ''
                marque = (row_data.get('marque') or '').strip() if row_data.get('marque') else ''
                couleur = (row_data.get('couleur') or '').strip() if row_data.get('couleur') else ''
                taille = (row_data.get('taille') or '').strip() if row_data.get('taille') else ''

                specs_parts = []
                if marque:
                    specs_parts.append(f"Marque : {marque}")
                if couleur:
                    specs_parts.append(f"Couleur : {couleur}")
                if taille:
                    specs_parts.append(f"Taille / modèle : {taille}")
                specifications = "\n".join(specs_parts)

                product = Product(
                    category=category,
                    name=nom,
                    description=description,
                    specifications=specifications,
                    price=prix,
                    stock=stock,
                    is_active=False,  # en attente de validation admin
                )

                image_principale = (row_data.get('image_principale') or '').strip() if row_data.get('image_principale') else ''
                if image_principale:
                    img_path = os.path.join(images_dir, image_principale)
                    if os.path.exists(img_path):
                        with open(img_path, 'rb') as f:
                            product.image.save(image_principale, File(f), save=False)
                    else:
                        self.stdout.write(self.style.WARNING(f"Ligne {row_num}: image principale introuvable ({img_path})"))

                product.save()

                for col in ['image2', 'image3', 'image4']:
                    img_name = (row_data.get(col) or '').strip() if row_data.get(col) else ''
                    if img_name:
                        img_path = os.path.join(images_dir, img_name)
                        if os.path.exists(img_path):
                            with open(img_path, 'rb') as f:
                                gallery_img = ProductImage(product=product, order=int(col[-1]))
                                gallery_img.image.save(img_name, File(f), save=True)
                        else:
                            self.stdout.write(self.style.WARNING(f"Ligne {row_num}: {col} introuvable ({img_path})"))

                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Ligne {row_num}: produit '{nom}' créé (désactivé, en attente de validation)"))

            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f"Ligne {row_num}: erreur - {e}"))

        self.stdout.write(self.style.SUCCESS(f"\nImport terminé : {created_count} produit(s) créé(s), {error_count} erreur(s)."))
        self.stdout.write("Les produits sont désactivés (is_active=False). Validez-les depuis l'admin Django avant qu'ils apparaissent sur la boutique.")
