from founatekapp.models import Category, Product, ProductImage
from django.utils.text import slugify
import os
from django.conf import settings

# =====================================
# CATEGORIES
# =====================================

categories = [
    "Sneakers Homme",
    "Sneakers Femme",
    "Chaussures Ville Homme",
    "Chaussures Ville Femme",
    "Sandales Homme",
    "Sandales Femme",
    "Claquettes",
    "Bottes",
    "Chaussures Football",
    "Chaussures Enfants",
]


category_objects = {}

for name in categories:
    category, _ = Category.objects.get_or_create(
        name=name,
        defaults={
            "description": f"Découvrez notre sélection {name} chez FOUNATEK SHOP."
        }
    )

    category_objects[name] = category



# =====================================
# CATALOGUE CHAUSSURES
# =====================================

catalogue = [

("Nike Air Force 1 Blanc","Sneakers Homme",650000),
("Nike Air Max 90","Sneakers Homme",700000),
("Nike Dunk Low","Sneakers Homme",750000),
("Nike Revolution 6","Sneakers Homme",400000),
("Jordan 1 Retro","Sneakers Homme",900000),

("Adidas Superstar Blanc Noir","Sneakers Homme",550000),
("Adidas Stan Smith","Sneakers Homme",500000),
("Adidas Samba Classic","Sneakers Homme",600000),
("Adidas Gazelle","Sneakers Femme",520000),

("Puma Smash V2 Blanc","Sneakers Homme",350000),
("Puma RS-X","Sneakers Homme",650000),
("Puma Cali Femme","Sneakers Femme",450000),

("New Balance 574 Classic","Sneakers Homme",450000),
("New Balance 530","Sneakers Femme",500000),

("Converse Chuck Taylor","Sneakers Homme",300000),
("Vans Old Skool","Sneakers Homme",350000),

("Mocassin Cuir Homme Noir","Chaussures Ville Homme",300000),
("Derby Cuir Homme Marron","Chaussures Ville Homme",350000),
("Chaussure Oxford Homme","Chaussures Ville Homme",450000),

("Escarpin Femme Noir","Chaussures Ville Femme",250000),
("Ballerine Femme Classique","Chaussures Ville Femme",180000),

("Sandale Cuir Homme Premium","Sandales Homme",150000),
("Sandale Homme Casual","Sandales Homme",120000),

("Sandale Femme Élégante","Sandales Femme",180000),
("Mule Femme Moderne","Sandales Femme",220000),

("Claquette Nike Style Sport","Claquettes",150000),
("Claquette Adidas Confort","Claquettes",140000),

("Botte Chelsea Homme","Bottes",500000),
("Botte Cuir Femme","Bottes",450000),

("Nike Mercurial Football","Chaussures Football",800000),
("Adidas Predator Football","Chaussures Football",750000),

("Basket Enfant Nike","Chaussures Enfants",250000),
("Basket Enfant Adidas","Chaussures Enfants",230000),

]



# =====================================
# CREATION PRODUITS
# =====================================

for name, category_name, price in catalogue:

    category = category_objects[category_name]

    slug = slugify(name)

    product, created = Product.objects.get_or_create(
        slug=slug,
        defaults={

            "category": category,

            "name": name,

            "description": f"""
{name} disponible chez FOUNATEK SHOP.

Chaussure confortable adaptée au quotidien.
Design moderne, finition soignée et excellent rapport qualité prix.
""",

            "specifications": f"""
Produit : {name}
Catégorie : {category_name}
Couleur : Selon disponibilité
Matière : Synthétique premium
Semelle : Caoutchouc antidérapant
Fermeture : Lacets ou fermeture classique
Pointures : 39 à 45
Origine : Importation
""",

            "price": price,

            "stock": 20,

            "image": f"products/{slug}.jpg",

            "is_active": True,

        }
    )


    if created:
        print("✅ Créé :", name)
    else:
        print("ℹ️ Existe :", name)



    # Galerie automatique

    for i in range(1, 5):

        gallery_path = f"products/gallery/{slug}-{i}.jpg"

        full_path = os.path.join(
            settings.MEDIA_ROOT,
            gallery_path
        )

        if os.path.exists(full_path):

            ProductImage.objects.get_or_create(
                product=product,
                image=gallery_path,
                defaults={
                    "alt": f"{name} vue {i}",
                    "order": i
                }
            )


print("\n================================")
print("🎉 CATALOGUE CHAUSSURES AJOUTÉ")
print("================================")