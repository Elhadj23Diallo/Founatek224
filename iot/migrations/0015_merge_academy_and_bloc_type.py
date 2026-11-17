"""Fusion des deux migrations 0014 de l'application IoT.

Les deux branches sont indépendantes : l'une change les types de blocs,
l'autre crée la table d'accès au pack Academy. Aucune opération SQL ajoutée.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("iot", "0014_alter_blocpedagogique_type"),
        ("iot", "0014_academypackaccess"),
    ]

    operations = []
