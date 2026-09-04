"""
Attache le schema "broche flottante vs pull-down" a la Lecon 4 du parcours
"Initiation a l'Electronique de base avec Arduino", juste apres le texte qui
explique pourquoi la resistance de pull-down est indispensable.

Meme idiome que attach_arduino_lecon3_media : la nouvelle image s'intercale
entre des blocs texte/code deja existants, donc toute la lecon est recreee
(contenu texte/code copie verbatim depuis seed_arduino_debutant) plutot que
de ne toucher qu'un sous-type de bloc. L'emplacement reserve d'origine (photo
reelle du montage sur breadboard) reste en attente : aucune photo du montage
physique n'a ete fournie cette fois-ci.

Usage : python manage.py attach_arduino_lecon4_media
"""
import os
from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from iot.models import Parcours, BlocPedagogique

ASSETS_DIR = os.path.join(settings.BASE_DIR, "iot", "course_media", "arduino_debutant")
MEDIA_PLACEHOLDER = "media_a_ajouter"

PULLDOWN_CONTENU = (
    "Pourquoi la résistance de pull-down est indispensable : sans elle, la "
    "broche est flottante et lit une valeur aléatoire ; avec une résistance "
    "de pull-down, elle lit LOW de façon fiable au repos, et HIGH dès que le "
    "5V l'emporte (bouton appuyé)."
)
MONTAGE_CONTENU = (
    f"[{MEDIA_PLACEHOLDER}] Photo du montage sur breadboard : bouton "
    "poussoir câblé avec sa résistance de pull-down 10k vers GND, LED sur "
    "la broche 7, légendes des fils."
)

TEXTE_1 = (
    "Jusqu'ici, l'Arduino ne faisait que commander une sortie (la LED). Un bouton "
    "poussoir, lui, est une entrée : l'Arduino lit son état avec `digitalRead()`, qui "
    "renvoie soit HIGH (5V, circuit fermé) soit LOW (0V, circuit ouvert).\n\n"
    "**Câblage** (3 fils) :\n"
    "- Une patte du bouton → 5V de l'Arduino\n"
    "- L'autre patte → broche 2 (entrée) ET → une résistance de 10kΩ vers GND\n"
    "- GND de l'Arduino → l'autre extrémité de la résistance"
)
TEXTE_2 = (
    "**Pourquoi la résistance de pull-down est indispensable ?** Sans elle, quand le "
    "bouton n'est PAS appuyé, la broche 2 n'est reliée à rien de précis — elle est "
    "\"flottante\", et peut lire aléatoirement HIGH ou LOW à cause du bruit électrique "
    "ambiant. La résistance de pull-down (vers GND) force la broche à lire LOW de façon "
    "fiable au repos ; quand on appuie sur le bouton, le 5V l'emporte et la broche lit "
    "HIGH. C'est exactement le même principe utilisé plus tard avec le PIR ou n'importe "
    "quel bouton dans les parcours Domotique."
)
CODE_BOUTON = (
    "// Lire un bouton poussoir et allumer une LED quand il est presse\n\n"
    "#define BOUTON_PIN 2\n"
    "#define LED_PIN 7\n\n"
    "void setup() {\n"
    "  pinMode(BOUTON_PIN, INPUT);\n"
    "  pinMode(LED_PIN, OUTPUT);\n"
    "  Serial.begin(9600);\n"
    "}\n\n"
    "void loop() {\n"
    "  int etatBouton = digitalRead(BOUTON_PIN);\n\n"
    "  if (etatBouton == HIGH) {\n"
    "    digitalWrite(LED_PIN, HIGH);\n"
    "    Serial.println(\"Bouton presse -> LED allumee\");\n"
    "  } else {\n"
    "    digitalWrite(LED_PIN, LOW);\n"
    "  }\n\n"
    "  delay(50);\n"
    "}\n"
)


class Command(BaseCommand):
    help = "Attache le schéma pull-down à la Leçon 4 du parcours Arduino débutant"

    def handle(self, *args, **options):
        parcours = Parcours.objects.filter(
            titre="Initiation à l'Électronique de base avec Arduino"
        ).first()
        if not parcours:
            self.stdout.write(self.style.ERROR(
                "Parcours introuvable — lance d'abord : python manage.py seed_arduino_debutant"
            ))
            return

        lecon4 = parcours.lecons.filter(ordre=4).first()
        if not lecon4:
            self.stdout.write(self.style.ERROR("Leçon 4 introuvable."))
            return

        # La nouvelle image s'intercale entre des blocs texte/code déjà
        # existants : toute la leçon doit être renumérotée (même idiome que
        # attach_arduino_lecon3_media).
        lecon4.blocs.all().delete()

        BlocPedagogique.objects.create(lecon=lecon4, ordre=1, type="texte", contenu=TEXTE_1)
        BlocPedagogique.objects.create(lecon=lecon4, ordre=2, type="texte", contenu=TEXTE_2)

        pulldown_bloc = BlocPedagogique.objects.create(lecon=lecon4, ordre=3, type="image", contenu=PULLDOWN_CONTENU)
        self._attach_file(pulldown_bloc, "lecon4_pulldown_diagram.png")
        self.stdout.write(self.style.SUCCESS(f"Schéma pull-down attaché (bloc id={pulldown_bloc.id}, ordre=3)."))

        BlocPedagogique.objects.create(lecon=lecon4, ordre=4, type="code", language="cpp", code=CODE_BOUTON)

        # Emplacement réservé pour la vraie photo du montage — toujours en
        # attente, aucune photo physique du circuit n'a été fournie cette fois.
        BlocPedagogique.objects.create(lecon=lecon4, ordre=5, type="image", contenu=MONTAGE_CONTENU)

        self.stdout.write(self.style.SUCCESS(
            "\nLeçon 4 à jour : texte, texte, schéma pull-down, code, photo montage (à ajouter)."
        ))

    def _attach_file(self, bloc, filename):
        path = os.path.join(ASSETS_DIR, filename)
        with open(path, "rb") as f:
            bloc.media_file.save(filename, File(f), save=False)
        bloc.save()
