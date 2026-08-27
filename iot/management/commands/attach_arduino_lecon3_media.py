"""
Attache les images reelles a la Lecon 3 du parcours "Initiation a
l'Electronique de base avec Arduino" (pinout de la carte + schema du cycle
setup/loop), intercalees entre les blocs de texte existants.

Contrairement a attach_arduino_lecon1_media / lecon2_media (qui ne touchent
que les blocs image/interactif), les nouvelles images ici prennent place
ENTRE des blocs texte/code deja existants : il faut donc renumeroter toute
la lecon. Cette commande recree donc l'integralite des blocs de la Lecon 3,
avec le meme contenu texte/code que seed_arduino_debutant (copie verbatim),
plus les deux images inserees au bon endroit — rejouable sans dependre d'un
chemin propre a une machine, les fichiers sources vivant dans
iot/course_media/arduino_debutant/ (verses au depot Git).

Usage : python manage.py attach_arduino_lecon3_media
"""
import os
from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from iot.models import Parcours, BlocPedagogique

ASSETS_DIR = os.path.join(settings.BASE_DIR, "iot", "course_media", "arduino_debutant")
MEDIA_PLACEHOLDER = "media_a_ajouter"

PINOUT_CONTENU = (
    "Diagramme des broches (pinout) de l'Arduino Uno R3 — les broches "
    "numériques, analogiques, d'alimentation et de communication (SPI/I2C/"
    "PWM) que tu utiliseras tout au long de ce parcours."
)
SETUP_LOOP_CONTENU = (
    "Schéma du cycle d'exécution d'un programme Arduino : setup() "
    "s'exécute une seule fois au démarrage, puis loop() se répète à "
    "l'infini tant que la carte est alimentée."
)

TEXTE_1 = (
    "Une carte Arduino Uno, c'est un petit ordinateur qui ne fait qu'une chose à la fois, "
    "mais qui la fait sans jamais s'arrêter : exécuter, en boucle, le programme qu'on lui "
    "a envoyé. Au cœur de la carte, une puce appelée microcontrôleur (l'ATmega328P sur "
    "l'Uno) — pas de clavier, pas d'écran, pas de système d'exploitation. Juste des "
    "broches (pins) qu'on peut lire ou piloter, et un programme qui tourne en continu.\n\n"
    "Pour lui donner des ordres, on utilise l'IDE Arduino (le logiciel qu'on installe sur "
    "l'ordinateur, gratuit sur arduino.cc), on branche la carte en USB, et on envoie "
    "('upload') notre code dessus."
)
TEXTE_2 = (
    "**La structure d'un programme Arduino ne change jamais** :\n"
    "- `setup()` : tout ce qui s'exécute UNE seule fois, au démarrage (configurer une "
    "broche, initialiser une communication...)\n"
    "- `loop()` : tout ce qui se répète À L'INFINI, tant que la carte est alimentée\n\n"
    "C'est cette boucle infinie qui rend l'Arduino capable de surveiller un capteur ou "
    "de piloter un composant en continu, sans jamais se fatiguer."
)
CODE_BLINK = (
    "// Premier programme : faire clignoter la LED intégrée de l'Arduino\n"
    "// L'équivalent du \"Hello World\" en électronique embarquée.\n\n"
    "#define LED_PIN 13   // La LED intégrée de l'Arduino Uno est sur la broche 13\n\n"
    "void setup() {\n"
    "  pinMode(LED_PIN, OUTPUT);   // Déclare la broche comme une sortie\n"
    "  Serial.begin(9600);          // Démarre la communication avec l'ordinateur\n"
    "  Serial.println(\"Arduino pret.\");\n"
    "}\n\n"
    "void loop() {\n"
    "  digitalWrite(LED_PIN, HIGH);  // Allume la LED\n"
    "  Serial.println(\"LED allumee\");\n"
    "  delay(1000);                    // Attend 1 seconde (1000 millisecondes)\n\n"
    "  digitalWrite(LED_PIN, LOW);    // Eteint la LED\n"
    "  Serial.println(\"LED eteinte\");\n"
    "  delay(1000);\n"
    "}\n"
)
VIDEO_CONTENU = (
    f"[{MEDIA_PLACEHOLDER}] Courte vidéo (15-20s) de la LED intégrée de l'Arduino qui "
    "clignote après upload du code ci-dessus, avec le moniteur série visible affichant "
    "les messages."
)


class Command(BaseCommand):
    help = "Attache le pinout et le schéma setup/loop à la Leçon 3 du parcours Arduino débutant"

    def handle(self, *args, **options):
        parcours = Parcours.objects.filter(
            titre="Initiation à l'Électronique de base avec Arduino"
        ).first()
        if not parcours:
            self.stdout.write(self.style.ERROR(
                "Parcours introuvable — lance d'abord : python manage.py seed_arduino_debutant"
            ))
            return

        lecon3 = parcours.lecons.filter(ordre=3).first()
        if not lecon3:
            self.stdout.write(self.style.ERROR("Leçon 3 introuvable."))
            return

        # Les nouvelles images s'intercalent entre des blocs texte/code déjà
        # existants : toute la leçon doit être renumérotée. On recrée donc
        # l'intégralité des blocs (contenu texte/code copié verbatim depuis
        # seed_arduino_debutant) plutôt que de ne toucher qu'un sous-type,
        # pour garder une seule source de vérité sur l'ordre final.
        lecon3.blocs.all().delete()

        BlocPedagogique.objects.create(lecon=lecon3, ordre=1, type="texte", contenu=TEXTE_1)

        pinout_bloc = BlocPedagogique.objects.create(lecon=lecon3, ordre=2, type="image", contenu=PINOUT_CONTENU)
        self._attach_file(pinout_bloc, "lecon3_pinout.webp")
        self.stdout.write(self.style.SUCCESS(f"Pinout attaché (bloc id={pinout_bloc.id}, ordre=2)."))

        BlocPedagogique.objects.create(lecon=lecon3, ordre=3, type="texte", contenu=TEXTE_2)

        loop_bloc = BlocPedagogique.objects.create(lecon=lecon3, ordre=4, type="image", contenu=SETUP_LOOP_CONTENU)
        self._attach_file(loop_bloc, "lecon3_setup_loop.png")
        self.stdout.write(self.style.SUCCESS(f"Schéma setup/loop attaché (bloc id={loop_bloc.id}, ordre=4)."))

        BlocPedagogique.objects.create(lecon=lecon3, ordre=5, type="code", language="cpp", code=CODE_BLINK)
        BlocPedagogique.objects.create(lecon=lecon3, ordre=6, type="video", contenu=VIDEO_CONTENU)

        self.stdout.write(self.style.SUCCESS(
            "\nLeçon 3 à jour : texte, pinout, texte, schéma setup/loop, code, vidéo (à ajouter)."
        ))

    def _attach_file(self, bloc, filename):
        path = os.path.join(ASSETS_DIR, filename)
        with open(path, "rb") as f:
            bloc.media_file.save(filename, File(f), save=False)
        bloc.save()
