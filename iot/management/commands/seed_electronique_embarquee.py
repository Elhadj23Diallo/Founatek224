"""
Cree (ou met a jour) le parcours "Electronique embarquee" : Station de mesure
environnementale connectee, decoupe en apprentissage par le projet.

Usage : python manage.py seed_electronique_embarquee
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from iot.models import Organisation, Parcours, Lecon, BlocPedagogique, Quiz, Project


MEDIA_PLACEHOLDER_IMG = "media_a_ajouter"
MEDIA_PLACEHOLDER_VIDEO = "media_a_ajouter"


class Command(BaseCommand):
    help = "Seed du parcours Electronique embarquee (station environnementale connectee)"

    def handle(self, *args, **options):
        formateur = User.objects.filter(username="elhadj").first()
        if not formateur:
            self.stdout.write(self.style.ERROR("Utilisateur 'elhadj' introuvable."))
            return

        org = Organisation.objects.filter(nom="Founatek Academy").first()
        if not org and hasattr(formateur, "formateur_profile"):
            org = formateur.formateur_profile.organisation
        if not org:
            org = Organisation.objects.first()
        if not org:
            org = Organisation.objects.create(nom="Founatek Academy", type="Entreprise")
            self.stdout.write(self.style.WARNING(f"Organisation créée automatiquement : {org.nom}"))
        if not hasattr(formateur, "formateur_profile"):
            from iot.models import FormateurProfile
            FormateurProfile.objects.create(user=formateur, organisation=org)
            self.stdout.write(self.style.WARNING(f"FormateurProfile créé automatiquement pour {formateur.username}"))

        parcours, created = Parcours.objects.update_or_create(
            titre="Électronique embarquée : Station de mesure environnementale connectée",
            defaults=dict(
                organisation=org,
                created_by=formateur,
                niveau="Débutant",
                certifiant=True,
                is_published=False,
                description=(
                    "Apprends l'électronique embarquée non pas dans l'abstrait, mais en construisant, "
                    "brique par brique, une vraie station connectée capable de mesurer la température, "
                    "l'humidité et la qualité de l'air, puis d'envoyer ces données sur Internet en temps réel. "
                    "Chaque composant est étudié en détail avant d'être assemblé dans le projet final — "
                    "exactement le genre d'objet qui, dans une chambre d'étudiant, peut devenir le prototype "
                    "d'un vrai produit."
                ),
            ),
        )
        self.stdout.write(self.style.SUCCESS(f"Parcours {'créé' if created else 'mis à jour'} : {parcours.titre} (id={parcours.id})"))

        for l in list(Lecon.objects.filter(parcours=parcours)):
            l.delete()

        lessons = self._lessons_data()
        for data in lessons:
            lecon = Lecon.objects.create(
                parcours=parcours,
                titre=data["titre"],
                ordre=data["ordre"],
                resume=data["resume"],
            )
            for i, bloc in enumerate(data["blocs"], start=1):
                BlocPedagogique.objects.create(
                    lecon=lecon,
                    ordre=i,
                    type=bloc["type"],
                    contenu=bloc.get("contenu"),
                    code=bloc.get("code"),
                    language=bloc.get("language"),
                )
            for q in data.get("quiz", []):
                Quiz.objects.create(
                    lecon=lecon,
                    question=q["question"],
                    choix_a=q["a"], choix_b=q["b"], choix_c=q["c"], choix_d=q["d"],
                    bonne_reponse=q["bonne"],
                    plusieurs_reponses=q.get("plusieurs", False),
                    explication=q.get("explication", ""),
                )
            self.stdout.write(f"  Leçon {data['ordre']} créée : {data['titre']} ({len(data['blocs'])} blocs, {len(data.get('quiz', []))} questions)")

        Project.objects.filter(parcours=parcours).delete()
        Project.objects.create(
            parcours=parcours,
            titre="Station de mesure environnementale connectée — projet final",
            ordre=1,
            language="cpp",
            description=(
                "Assemble tout ce que tu as appris : ESP32, alimentation, capteur DHT22 (température/humidité), "
                "capteur MQ135 (qualité de l'air), écran OLED, et envoi des mesures vers une API en Wi-Fi. "
                "Le résultat : un boîtier autonome qui affiche localement les mesures ET les envoie sur Internet, "
                "exactement comme la première version d'Air Conakry IQ Pro."
            ),
            code=self._final_code(),
        )
        self.stdout.write(self.style.SUCCESS("Projet final créé."))
        self.stdout.write(self.style.WARNING(
            "\nN'oublie pas : les blocs 'image'/'vidéo' sont des emplacements réservés (contenu = "
            "description de ce qu'il faut ajouter). Va dans Gérer les Blocs (dashboard formateur) pour "
            "uploader tes photos/vidéos, puis publie le parcours (is_published) quand tu es prêt."
        ))

    # ------------------------------------------------------------------
    def _lessons_data(self):
        return [
            # ============================================================
            {
                "ordre": 1,
                "titre": "Le projet : pourquoi construire une station connectée ?",
                "resume": "Présentation du projet final, du matériel nécessaire, et de la philosophie du cours.",
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Il est une heure du matin, quelque part dans une petite chambre. Un jeune ingénieur "
                        "rentre d'une longue journée de travail, épuisé. Sur son bureau : une carte électronique "
                        "de la taille d'une pièce de monnaie, un capteur, un fouillis de fils multicolores. "
                        "Pas de laboratoire climatisé, pas de matériel de marque — juste des composants achetés "
                        "centime par centime, et une question qui ne le lâche pas : et si l'air que respire sa "
                        "ville pouvait enfin se mesurer, se comprendre, se protéger ?\n\n"
                        "C'est exactement ce que tu vas apprendre à construire dans ce parcours : une **station "
                        "de mesure environnementale connectée**. Un petit boîtier capable de mesurer la "
                        "température, l'humidité et la qualité de l'air d'un lieu, de l'afficher localement sur "
                        "un écran, et d'envoyer ces données sur Internet pour qu'on puisse les consulter à "
                        "distance, en temps réel.\n\n"
                        "Ce n'est pas un exercice académique déconnecté du réel. C'est, à une échelle réduite, "
                        "le prototype du genre d'objet qui peut réellement changer la vie de quelqu'un — "
                        "prévenir une famille d'un pic de pollution, alerter un agriculteur d'une chaleur "
                        "excessive, ou simplement donner à voir ce qui, avant, restait invisible.\n\n"
                        "**La méthode de ce parcours** : plutôt que d'apprendre la théorie de chaque composant "
                        "dans le vide, on va procéder à l'envers. Chaque leçon isole UN composant du projet "
                        "final, te l'explique en détail (comment il fonctionne, pourquoi il existe, comment le "
                        "câbler et le programmer seul), puis, à la dernière leçon, on assemble tout. Tu ne "
                        "sauras jamais \"un peu de tout\" — tu sauras vraiment comment fonctionne chaque brique, "
                        "et tu sauras surtout comment les faire parler ensemble."
                    )},
                    {"type": "texte", "contenu": (
                        "**Ce qu'il te faut pour suivre ce parcours en pratique** (matériel, ~15-25 € au total "
                        "selon où tu achètes) :\n"
                        "- 1 carte ESP32 (DevKit V1 ou équivalent)\n"
                        "- 1 capteur DHT22 (température/humidité)\n"
                        "- 1 capteur MQ135 (qualité de l'air / gaz)\n"
                        "- 1 écran OLED 0.96\" I2C (SSD1306)\n"
                        "- 1 breadboard + fils de connexion (jumper wires)\n"
                        "- 1 câble USB pour programmer l'ESP32\n\n"
                        "Si tu n'as pas encore le matériel, ce n'est pas grave : lis et comprends chaque leçon "
                        "en détail dès maintenant, teste le câblage et le code dès que tu reçois les composants. "
                        "L'important, comme toujours, c'est de comprendre AVANT de brancher — pas l'inverse."
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER_IMG}] Photo du kit complet posé sur une table : ESP32, DHT22, MQ135, écran OLED, breadboard, fils — vue d'ensemble avant assemblage."},
                ],
                "quiz": [
                    {
                        "question": "Quelle est la méthode pédagogique de ce parcours ?",
                        "a": "Apprendre toute la théorie d'abord, la pratique ne vient jamais",
                        "b": "Étudier chaque composant du projet final un par un, puis tout assembler à la fin",
                        "c": "Copier du code sans comprendre comment il fonctionne",
                        "d": "Apprendre uniquement à souder",
                        "bonne": "B",
                        "explication": "On isole chaque composant pour bien le comprendre, avant de les assembler dans le projet final — l'apprentissage par la pratique.",
                    },
                    {
                        "question": "Quel est l'objectif final du projet de ce parcours ?",
                        "a": "Allumer une simple LED",
                        "b": "Construire un jeu vidéo",
                        "c": "Une station qui mesure temp./humidité/qualité de l'air et envoie les données sur Internet",
                        "d": "Réparer un vieux téléviseur",
                        "bonne": "C",
                        "explication": "Le projet final assemble ESP32, DHT22, MQ135, écran OLED et connexion Wi-Fi pour créer une vraie station connectée.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 2,
                "titre": "Le cerveau du montage : le microcontrôleur ESP32",
                "resume": "Comprendre ce qu'est un microcontrôleur, pourquoi l'ESP32, et écrire son premier programme.",
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Imagine un ordinateur minuscule, pas plus grand qu'une boîte d'allumettes, qui n'a "
                        "besoin ni d'écran, ni de clavier, ni de souris pour fonctionner. Il n'a qu'un seul "
                        "travail : exécuter, en boucle, sans jamais s'arrêter, le programme qu'on lui a donné. "
                        "C'est ça, un **microcontrôleur**.\n\n"
                        "Contrairement à ton PC qui fait tourner des dizaines de programmes en même temps "
                        "(navigateur, musique, messagerie...), un microcontrôleur fait UNE seule chose, mais "
                        "il la fait indéfiniment et de façon fiable : lire un capteur, allumer une LED, envoyer "
                        "une donnée sur le réseau. C'est le cœur — ou plutôt le cerveau — de tout objet "
                        "connecté que tu croises au quotidien : une box internet, un thermostat intelligent, "
                        "une machine à laver récente.\n\n"
                        "**Pourquoi l'ESP32 précisément ?** Il existe des dizaines de microcontrôleurs "
                        "(Arduino Uno, PIC, STM32...). On choisit l'ESP32 pour ce projet pour une raison très "
                        "concrète : il a le **Wi-Fi intégré**. Pas besoin d'ajouter un module supplémentaire "
                        "pour envoyer nos données sur Internet — tout est déjà dans la puce, pour moins de "
                        "5 €. C'est exactement le genre de choix pragmatique qu'on fait quand on construit "
                        "avec un budget serré : pas le matériel le plus prestigieux, le matériel le plus "
                        "efficace pour l'objectif visé."
                    )},
                    {"type": "texte", "contenu": (
                        "**Comment ça fonctionne, concrètement ?** Un programme pour microcontrôleur "
                        "(on l'appelle un \"firmware\" ou un \"sketch\") a toujours la même structure en deux "
                        "parties :\n"
                        "- `setup()` : tout ce qui s'exécute UNE seule fois, au démarrage (initialiser une "
                        "connexion, configurer une broche...)\n"
                        "- `loop()` : tout ce qui se répète À L'INFINI, tant que la carte est alimentée\n\n"
                        "C'est cette boucle infinie qui rend le microcontrôleur si adapté à notre station : "
                        "il va, encore et encore, lire les capteurs, afficher les valeurs, et les envoyer — "
                        "sans jamais se fatiguer, 24h/24."
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER_IMG}] Photo de la carte ESP32 seule, avec les broches (pins) annotées : VIN, GND, GPIO, 3V3."},
                    {"type": "code", "language": "cpp", "code": (
                        "// Premier programme : faire clignoter la LED intégrée de l'ESP32\n"
                        "// C'est l'équivalent du \"Hello World\" en électronique embarquée.\n\n"
                        "#define LED_PIN 2   // La plupart des ESP32 ont une LED sur le GPIO 2\n\n"
                        "void setup() {\n"
                        "  Serial.begin(115200);      // Démarre la communication avec l'ordinateur\n"
                        "  pinMode(LED_PIN, OUTPUT);  // Déclare la broche comme une sortie\n"
                        "  Serial.println(\"ESP32 pret.\");\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  digitalWrite(LED_PIN, HIGH);  // Allume la LED\n"
                        "  Serial.println(\"LED allumee\");\n"
                        "  delay(1000);                   // Attend 1 seconde\n\n"
                        "  digitalWrite(LED_PIN, LOW);    // Eteint la LED\n"
                        "  Serial.println(\"LED eteinte\");\n"
                        "  delay(1000);\n"
                        "}\n"
                    )},
                    {"type": "video", "contenu": f"[{MEDIA_PLACEHOLDER_VIDEO}] Courte vidéo (15-30s) de la LED de l'ESP32 qui clignote après upload du code ci-dessus."},
                ],
                "quiz": [
                    {
                        "question": "Pourquoi choisit-on l'ESP32 plutôt qu'un Arduino Uno classique pour ce projet ?",
                        "a": "Il est plus gros",
                        "b": "Il a le Wi-Fi intégré, nécessaire pour envoyer les données sur Internet",
                        "c": "Il coûte plus cher",
                        "d": "Il n'a pas de GPIO",
                        "bonne": "B",
                        "explication": "L'ESP32 intègre le Wi-Fi directement dans la puce, ce qui est indispensable pour notre station connectée.",
                    },
                    {
                        "question": "Que fait la fonction loop() dans un programme pour microcontrôleur ?",
                        "a": "Elle s'exécute une seule fois au démarrage",
                        "b": "Elle ne s'exécute jamais",
                        "c": "Elle se répète indéfiniment tant que la carte est alimentée",
                        "d": "Elle éteint la carte",
                        "bonne": "C",
                        "explication": "loop() tourne en boucle infinie — c'est ce qui permet au microcontrôleur de lire les capteurs en continu.",
                    },
                    {
                        "question": "Parmi ces affirmations, lesquelles sont vraies à propos de l'ESP32 ? (plusieurs réponses possibles)",
                        "a": "Il a le Wi-Fi intégré",
                        "b": "Il n'a aucune broche GPIO",
                        "c": "On ne peut pas le reprogrammer une fois flashé",
                        "d": "On le programme avec l'IDE Arduino (ou équivalent)",
                        "bonne": "A,D",
                        "plusieurs": True,
                        "explication": "L'ESP32 a le Wi-Fi intégré et se programme via l'IDE Arduino (ou PlatformIO) — il a bien des GPIO et peut être reflashé autant de fois que nécessaire.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 3,
                "titre": "L'électricité qui l'alimente : tension, courant, résistance",
                "resume": "Comprendre les bases de l'électricité (loi d'Ohm) avant de brancher le moindre capteur.",
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Avant de brancher un seul capteur, il faut comprendre ce qui circule réellement dans "
                        "ces petits fils colorés. Voici l'analogie la plus utile qu'on puisse te donner, et "
                        "qui ne vieillit jamais : **l'électricité, c'est de l'eau dans un tuyau.**\n\n"
                        "- La **tension** (en Volts, V), c'est la pression de l'eau — ce qui pousse le courant "
                        "à circuler. Plus la pression est forte, plus l'eau (le courant) veut avancer.\n"
                        "- Le **courant** (en Ampères, A), c'est le débit d'eau qui circule réellement dans le "
                        "tuyau à un instant donné.\n"
                        "- La **résistance** (en Ohms, Ω), c'est un rétrécissement du tuyau qui freine le "
                        "débit. Plus le tuyau est étroit (résistance élevée), moins l'eau (le courant) passe "
                        "pour une même pression (tension).\n\n"
                        "Ces trois grandeurs sont liées par une seule formule, la plus importante de toute "
                        "l'électronique — la **loi d'Ohm** :\n\n"
                        "**U = R × I**  (Tension = Résistance × Courant)\n\n"
                        "Pourquoi c'est vital de la connaître ? Parce qu'un composant électronique — une LED, "
                        "un capteur, l'ESP32 lui-même — a des limites précises de tension et de courant qu'il "
                        "peut supporter. Le dépasser, c'est le griller. Littéralement : un filet de fumée, une "
                        "odeur de plastique brûlé, et le composant est mort. C'est une expérience que tout "
                        "électronicien débutant finit par vivre au moins une fois — le but de cette leçon "
                        "est de te l'épargner autant que possible."
                    )},
                    {"type": "texte", "contenu": (
                        "**Cas concret : pourquoi on met toujours une résistance devant une LED.**\n\n"
                        "Une LED classique fonctionne autour de 2V et supporte au maximum environ 20 mA de "
                        "courant. Or l'ESP32 fournit du 3.3V sur ses broches de sortie. Si on branche la LED "
                        "directement, sans rien pour limiter le courant, on lui envoie trop de tension d'un "
                        "coup : elle grille en une fraction de seconde.\n\n"
                        "La solution : ajouter une résistance en série (typiquement 220Ω à 330Ω) qui va "
                        "\"absorber\" l'excédent de tension et limiter le courant à une valeur sûre. C'est la "
                        "loi d'Ohm appliquée directement : on calcule R pour que le courant I reste sous la "
                        "limite de la LED.\n\n"
                        "Ce principe — protéger un composant fragile avec une résistance ou un circuit de "
                        "protection adapté — tu vas le retrouver à chaque leçon de ce parcours, avec chaque "
                        "nouveau capteur."
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER_IMG}] Schéma ou photo d'un montage LED + résistance sur breadboard, avec les valeurs annotées."},
                    {"type": "code", "language": "cpp", "code": (
                        "// Application directe : LED + resistance, controlee par l'ESP32\n"
                        "// Cablage : GPIO 4 -> resistance 220 ohms -> patte longue (+) de la LED\n"
                        "// patte courte (-) de la LED -> GND\n\n"
                        "#define LED_PIN 4\n\n"
                        "void setup() {\n"
                        "  pinMode(LED_PIN, OUTPUT);\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  digitalWrite(LED_PIN, HIGH);\n"
                        "  delay(500);\n"
                        "  digitalWrite(LED_PIN, LOW);\n"
                        "  delay(500);\n"
                        "}\n"
                    )},
                ],
                "quiz": [
                    {
                        "question": "Parmi ces associations grandeur/unité, lesquelles sont correctes ? (plusieurs réponses possibles)",
                        "a": "Tension — Volt",
                        "b": "Courant — Ampère",
                        "c": "Résistance — Ohm",
                        "d": "Puissance — Ohm",
                        "bonne": "A,B,C",
                        "plusieurs": True,
                        "explication": "Tension en Volts, courant en Ampères, résistance en Ohms. La puissance, elle, se mesure en Watts — pas en Ohms.",
                    },
                    {
                        "question": "Que dit la loi d'Ohm ?",
                        "a": "U = R × I",
                        "b": "U = R + I",
                        "c": "R = U + I",
                        "d": "I = U + R",
                        "bonne": "A",
                        "explication": "Tension = Résistance × Courant. C'est la formule de base de toute l'électronique.",
                    },
                    {
                        "question": "Pourquoi met-on une résistance en série avec une LED ?",
                        "a": "Pour la faire briller plus fort",
                        "b": "Pour limiter le courant et éviter de la griller",
                        "c": "Ça n'a aucune utilité",
                        "d": "Pour changer sa couleur",
                        "bonne": "B",
                        "explication": "Sans résistance, le courant serait trop élevé pour la LED, qui grillerait instantanément.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 4,
                "titre": "Mesurer le monde : le capteur de température et d'humidité (DHT22)",
                "resume": "Câbler et lire un capteur DHT22 avec l'ESP32.",
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Un microcontrôleur, aussi puissant soit-il, est aveugle et sourd au monde physique "
                        "qui l'entoure : il ne \"sait\" rien tant qu'on ne lui donne pas les moyens de mesurer. "
                        "C'est le rôle des **capteurs** : traduire une grandeur physique (température, "
                        "humidité, lumière, pression...) en un signal électrique que le microcontrôleur peut "
                        "lire et interpréter.\n\n"
                        "Le **DHT22** est l'un des capteurs les plus utilisés en électronique embarquée pour "
                        "mesurer deux grandeurs à la fois : la température (précision ±0.5°C) et l'humidité "
                        "relative de l'air (précision ±2%). À l'intérieur, un petit composant sensible réagit "
                        "physiquement à la chaleur et à l'humidité ambiante, et convertit cette réaction en "
                        "une donnée numérique envoyée sur un seul fil.\n\n"
                        "**Pourquoi c'est essentiel pour notre projet ?** Une station environnementale sans "
                        "mesure de température ni d'humidité, ce n'est pas vraiment une station environnementale. "
                        "Ce sont deux des indicateurs les plus basiques mais les plus demandés — pour "
                        "l'agriculture, pour le confort domestique, pour anticiper un risque sanitaire lors "
                        "d'une canicule."
                    )},
                    {"type": "texte", "contenu": (
                        "**Câblage du DHT22 sur l'ESP32** (3 fils) :\n"
                        "- Broche VCC (+) → 3.3V de l'ESP32\n"
                        "- Broche GND (-) → GND de l'ESP32\n"
                        "- Broche DATA (signal) → GPIO 15 de l'ESP32 (ou tout autre GPIO libre)\n\n"
                        "Certains modules DHT22 vendus sur une petite carte incluent déjà une résistance de "
                        "\"pull-up\" — si ce n'est pas le cas sur le tien, il faut ajouter une résistance de "
                        "10kΩ entre DATA et VCC pour stabiliser le signal.\n\n"
                        "Pour lire ce capteur en code, on utilise une bibliothèque toute faite (`DHT sensor "
                        "library` d'Adafruit) qui s'occupe de décoder le signal complexe envoyé par le "
                        "capteur — inutile de réinventer ce protocole à la main."
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER_IMG}] Photo du câblage DHT22 → ESP32 sur breadboard, avec les 3 fils VCC/GND/DATA bien visibles et étiquetés."},
                    {"type": "code", "language": "cpp", "code": (
                        "// Lecture du capteur DHT22 (temperature + humidite)\n"
                        "// Necessite la bibliotheque \"DHT sensor library\" (Adafruit) via le gestionnaire\n"
                        "// de bibliotheques de l'IDE Arduino.\n\n"
                        "#include <DHT.h>\n\n"
                        "#define DHTPIN 15\n"
                        "#define DHTTYPE DHT22\n"
                        "DHT dht(DHTPIN, DHTTYPE);\n\n"
                        "void setup() {\n"
                        "  Serial.begin(115200);\n"
                        "  dht.begin();\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  float humidite = dht.readHumidity();\n"
                        "  float temperature = dht.readTemperature();\n\n"
                        "  if (isnan(humidite) || isnan(temperature)) {\n"
                        "    Serial.println(\"Erreur de lecture du capteur DHT22 !\");\n"
                        "  } else {\n"
                        "    Serial.print(\"Temperature: \");\n"
                        "    Serial.print(temperature);\n"
                        "    Serial.print(\" C  |  Humidite: \");\n"
                        "    Serial.print(humidite);\n"
                        "    Serial.println(\" %\");\n"
                        "  }\n\n"
                        "  delay(2000); // Le DHT22 ne peut pas etre lu plus rapidement qu'environ 1x/2s\n"
                        "}\n"
                    )},
                ],
                "quiz": [
                    {
                        "question": "Quel est le rôle d'un capteur comme le DHT22 ?",
                        "a": "Traduire une grandeur physique en signal électrique lisible par le microcontrôleur",
                        "b": "Alimenter la carte en électricité",
                        "c": "Envoyer les données sur Internet",
                        "d": "Afficher les données sur un écran",
                        "bonne": "A",
                        "explication": "Un capteur convertit une grandeur physique (température, humidité...) en signal électrique interprétable.",
                    },
                    {
                        "question": "Quelles grandeurs le capteur DHT22 mesure-t-il ? (plusieurs réponses possibles)",
                        "a": "La température",
                        "b": "L'humidité relative de l'air",
                        "c": "La qualité de l'air (gaz polluants)",
                        "d": "La pression atmosphérique",
                        "bonne": "A,B",
                        "plusieurs": True,
                        "explication": "Le DHT22 mesure uniquement température et humidité — la qualité de l'air (MQ135) et la pression sont d'autres capteurs.",
                    },
                    {
                        "question": "Pourquoi utilise-t-on une bibliothèque (DHT sensor library) plutôt que de lire le capteur 'à la main' ?",
                        "a": "Parce que c'est obligatoire par la loi",
                        "b": "Parce que le protocole de communication du DHT22 est complexe à décoder soi-même",
                        "c": "Parce que ça ralentit le programme",
                        "d": "Ce n'est pas utile, on peut s'en passer facilement",
                        "bonne": "B",
                        "explication": "La bibliothèque encapsule le protocole de communication propriétaire du capteur, ce qui évite d'avoir à le réimplémenter.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 5,
                "titre": "Respirer les données : le capteur de qualité de l'air (MQ135)",
                "resume": "Comprendre et câbler un capteur de gaz analogique, cœur de la mesure de pollution.",
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Voici le composant qui donne tout son sens à une \"station environnementale\" : le "
                        "capteur de qualité de l'air. Le **MQ135** est un capteur de gaz bon marché (quelques "
                        "euros), sensible à un ensemble de polluants et gaz présents dans l'air ambiant : "
                        "dioxyde de carbone (CO2), ammoniac, benzène, fumée, et d'autres composés organiques "
                        "volatils.\n\n"
                        "**Comment ça marche à l'intérieur ?** Le MQ135 contient un petit élément chauffant "
                        "recouvert d'un matériau semi-conducteur (dioxyde d'étain, SnO2) dont la résistance "
                        "électrique varie selon la concentration de gaz présents dans l'air. Plus il y a de "
                        "gaz polluants, plus sa résistance change — et cette variation se traduit par une "
                        "tension analogique qu'on peut lire directement sur une broche de l'ESP32.\n\n"
                        "**Une précision honnête, qu'il faut connaître dès le départ** : le MQ135 donne une "
                        "indication relative de la qualité de l'air, pas une mesure de laboratoire ultra-"
                        "précise en parties par million exactes de chaque gaz. Pour un vrai déploiement "
                        "professionnel de qualité industrielle, on utilise des capteurs plus chers et calibrés "
                        "(comme les capteurs PM2.5/PM10 à faisceau laser). Mais pour apprendre — et pour "
                        "construire un premier prototype fonctionnel et utile — le MQ135 est exactement le "
                        "bon compromis entre coût et pertinence pédagogique. C'est avec ce genre de capteur "
                        "\"suffisant plutôt que parfait\" que naissent la plupart des vrais prototypes."
                    )},
                    {"type": "texte", "contenu": (
                        "**Câblage du MQ135 sur l'ESP32** :\n"
                        "- VCC → 5V (le MQ135 a besoin de 5V pour son élément chauffant — utiliser la broche "
                        "VIN de l'ESP32 si alimenté par USB, qui fournit ~5V)\n"
                        "- GND → GND\n"
                        "- AOUT (sortie analogique) → GPIO 34 de l'ESP32 (une broche compatible ADC — "
                        "convertisseur analogique-numérique)\n\n"
                        "**Point important à retenir** : le MQ135 a besoin de \"chauffer\" pendant quelques "
                        "minutes (idéalement 24 à 48h la toute première fois, puis quelques minutes à chaque "
                        "redémarrage) avant de donner des mesures stables. Ne t'inquiète pas si les toutes "
                        "premières lectures semblent erratiques — c'est normal, le capteur est en train de "
                        "se stabiliser thermiquement."
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER_IMG}] Photo du module MQ135 avec ses 4 broches (VCC, GND, DOUT, AOUT) annotées, câblé sur breadboard."},
                    {"type": "code", "language": "cpp", "code": (
                        "// Lecture du capteur MQ135 (qualite de l'air, valeur brute analogique)\n\n"
                        "#define MQ135_PIN 34  // Broche ADC de l'ESP32\n\n"
                        "void setup() {\n"
                        "  Serial.begin(115200);\n"
                        "  Serial.println(\"Prechauffage du capteur MQ135...\");\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  int valeurBrute = analogRead(MQ135_PIN);       // 0 a 4095 (ADC 12 bits de l'ESP32)\n"
                        "  float pourcentage = (valeurBrute / 4095.0) * 100.0;\n\n"
                        "  Serial.print(\"MQ135 valeur brute: \");\n"
                        "  Serial.print(valeurBrute);\n"
                        "  Serial.print(\"  (\");\n"
                        "  Serial.print(pourcentage);\n"
                        "  Serial.println(\"% de l'echelle du capteur)\");\n\n"
                        "  // Plus la valeur est elevee, plus la concentration de gaz detectee est importante.\n"
                        "  if (pourcentage > 60) {\n"
                        "    Serial.println(\"-> Air potentiellement pollue, ventiler la piece.\");\n"
                        "  }\n\n"
                        "  delay(2000);\n"
                        "}\n"
                    )},
                ],
                "quiz": [
                    {
                        "question": "Sur quel principe physique repose le MQ135 ?",
                        "a": "La résistance d'un matériau semi-conducteur varie selon la concentration de gaz",
                        "b": "Un laser mesure la distance des particules",
                        "c": "Une caméra filme l'air",
                        "d": "Un GPS localise les polluants",
                        "bonne": "A",
                        "explication": "Le matériau semi-conducteur du MQ135 change de résistance en présence de gaz polluants, ce qui produit une tension analogique mesurable.",
                    },
                    {
                        "question": "Pourquoi le MQ135 doit-il 'chauffer' avant de donner une mesure stable ?",
                        "a": "Ce n'est pas vrai, il est instantané",
                        "b": "Son élément chauffant a besoin de temps pour stabiliser sa température de fonctionnement",
                        "c": "Pour recharger sa batterie",
                        "d": "Pour se connecter au Wi-Fi",
                        "bonne": "B",
                        "explication": "Le capteur intègre un élément chauffant nécessaire à sa réaction chimique — d'où un temps de préchauffage avant mesure fiable.",
                    },
                    {
                        "question": "Quelle broche de l'ESP32 utilise-t-on pour lire une sortie ANALOGIQUE comme celle du MQ135 ?",
                        "a": "N'importe quelle broche numérique",
                        "b": "Une broche compatible ADC (convertisseur analogique-numérique), ex. GPIO 34",
                        "c": "La broche GND uniquement",
                        "d": "Le port USB",
                        "bonne": "B",
                        "explication": "Seules certaines broches de l'ESP32 sont reliées à un ADC capable de lire une tension analogique variable.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 6,
                "titre": "Afficher l'information : l'écran OLED",
                "resume": "Câbler un écran OLED en I2C et y afficher les mesures des capteurs.",
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Mesurer, c'est bien. Mais une donnée invisible ne sert à personne. C'est là "
                        "qu'intervient l'**écran OLED** : un petit afficheur (souvent 0.96 pouce, soit environ "
                        "2.5 cm) capable d'afficher du texte et des formes simples, sans avoir besoin de "
                        "rétroéclairage — chaque pixel s'allume individuellement, ce qui donne un contraste "
                        "net même dans une pièce sombre, pour une consommation électrique minime.\n\n"
                        "**Pourquoi un écran local, alors qu'on envoie déjà les données sur Internet ?** "
                        "Parce qu'un vrai objet connecté utile doit rester utile même sans connexion — si le "
                        "Wi-Fi tombe, si le serveur est injoignable, l'utilisateur doit quand même pouvoir "
                        "lire la température de la pièce en jetant un œil au boîtier. C'est une leçon de "
                        "conception qu'on retrouve dans presque tous les bons produits IoT : ne jamais rendre "
                        "l'appareil totalement dépendant du réseau pour son utilité la plus basique.\n\n"
                        "**Le protocole I2C.** Contrairement au DHT22 qui utilise un simple fil de données, "
                        "l'écran OLED communique généralement via le protocole **I2C**, qui permet de "
                        "faire dialoguer plusieurs composants sur seulement 2 fils (SDA pour la donnée, SCL "
                        "pour l'horloge/synchronisation). C'est un des grands avantages de l'I2C : on peut "
                        "brancher plusieurs capteurs I2C différents sur les MÊMES 2 fils, chacun étant "
                        "identifié par une adresse unique (souvent 0x3C pour l'écran OLED SSD1306)."
                    )},
                    {"type": "texte", "contenu": (
                        "**Câblage de l'écran OLED (I2C) sur l'ESP32** :\n"
                        "- VCC → 3.3V\n"
                        "- GND → GND\n"
                        "- SDA → GPIO 21 (broche I2C par défaut de l'ESP32)\n"
                        "- SCL → GPIO 22 (broche I2C par défaut de l'ESP32)\n\n"
                        "Bibliothèques nécessaires : `Adafruit SSD1306` et `Adafruit GFX Library`, "
                        "installables depuis le gestionnaire de bibliothèques de l'IDE Arduino."
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER_IMG}] Photo de l'écran OLED câblé (4 fils VCC/GND/SDA/SCL) affichant du texte de test, branché sur l'ESP32."},
                    {"type": "code", "language": "cpp", "code": (
                        "// Affichage de texte sur ecran OLED I2C (SSD1306)\n\n"
                        "#include <Wire.h>\n"
                        "#include <Adafruit_GFX.h>\n"
                        "#include <Adafruit_SSD1306.h>\n\n"
                        "#define SCREEN_WIDTH 128\n"
                        "#define SCREEN_HEIGHT 64\n"
                        "Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);\n\n"
                        "void setup() {\n"
                        "  Serial.begin(115200);\n"
                        "  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {\n"
                        "    Serial.println(\"Ecran OLED non detecte !\");\n"
                        "    while (true);\n"
                        "  }\n"
                        "  display.clearDisplay();\n"
                        "  display.setTextColor(SSD1306_WHITE);\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  float temperature = 24.5;  // Remplace plus tard par dht.readTemperature()\n"
                        "  float humidite = 58.0;     // Remplace plus tard par dht.readHumidity()\n\n"
                        "  display.clearDisplay();\n"
                        "  display.setTextSize(1);\n"
                        "  display.setCursor(0, 0);\n"
                        "  display.println(\"Station environnementale\");\n"
                        "  display.setTextSize(2);\n"
                        "  display.setCursor(0, 20);\n"
                        "  display.print(temperature);\n"
                        "  display.println(\" C\");\n"
                        "  display.setCursor(0, 45);\n"
                        "  display.print(humidite);\n"
                        "  display.println(\" %\");\n"
                        "  display.display();\n\n"
                        "  delay(2000);\n"
                        "}\n"
                    )},
                ],
                "quiz": [
                    {
                        "question": "Pourquoi garder un écran local même si les données sont envoyées sur Internet ?",
                        "a": "Ce n'est pas utile, on peut s'en passer",
                        "b": "Pour que l'appareil reste utile même sans connexion réseau",
                        "c": "Pour décorer le boîtier",
                        "d": "Ça n'a aucun rapport avec la fiabilité",
                        "bonne": "B",
                        "explication": "Un bon objet connecté doit rester utile localement, même en cas de coupure réseau.",
                    },
                    {
                        "question": "Quels sont les deux fils de communication utilisés par le protocole I2C ? (plusieurs réponses possibles)",
                        "a": "SDA",
                        "b": "SCL",
                        "c": "VCC",
                        "d": "GND",
                        "bonne": "A,B",
                        "plusieurs": True,
                        "explication": "SDA transporte la donnée, SCL l'horloge de synchronisation. VCC et GND alimentent le composant mais ne transportent pas la communication.",
                    },
                    {
                        "question": "À quoi sert l'adresse I2C (ex. 0x3C) d'un composant ?",
                        "a": "À rien, c'est juste un numéro de série",
                        "b": "À identifier ce composant précis quand plusieurs partagent les mêmes 2 fils SDA/SCL",
                        "c": "À définir sa couleur",
                        "d": "À le connecter au Wi-Fi",
                        "bonne": "B",
                        "explication": "Chaque appareil I2C a une adresse unique qui permet au microcontrôleur de savoir à qui il s'adresse sur le bus partagé.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 7,
                "titre": "Parler à Internet : connexion Wi-Fi et envoi des données",
                "resume": "Connecter l'ESP32 au Wi-Fi et envoyer les mesures vers une API par requête HTTP.",
                "blocs": [
                    {"type": "texte", "contenu": (
                        "On arrive à la brique qui transforme un simple montage électronique en véritable "
                        "**objet connecté** : la capacité d'envoyer les mesures sur Internet, pour qu'elles "
                        "soient stockées, consultées, analysées — potentiellement depuis n'importe où dans le "
                        "monde. C'est exactement le principe derrière l'application mobile ou le tableau de "
                        "bord web que tu utilises déjà dans Founatek : quelque part, un ESP32 mesure, et "
                        "quelque part ailleurs, un serveur reçoit et affiche.\n\n"
                        "**Le principe en deux étapes** :\n"
                        "1. L'ESP32 se connecte au réseau Wi-Fi (comme ton téléphone le fait avec ta box "
                        "internet à la maison)\n"
                        "2. Une fois connecté, il envoie une **requête HTTP** — le même protocole qu'utilise "
                        "ton navigateur pour charger une page web — vers une adresse (API) qui va recevoir "
                        "et enregistrer les données\n\n"
                        "On envoie généralement les données au format **JSON**, un format texte simple et "
                        "universel pour structurer de l'information : `{\"temperature\": 24.5, \"humidite\": 58}`. "
                        "C'est un langage que quasiment tous les serveurs web du monde savent lire, quelle que "
                        "soit la technologie utilisée derrière (Django, comme dans Founatek, ou toute autre)."
                    )},
                    {"type": "texte", "contenu": (
                        "**Un point de vigilance essentiel, appris à la dure par beaucoup de débutants** : "
                        "toujours vérifier que la connexion Wi-Fi a réussi AVANT d'essayer d'envoyer une "
                        "requête. Un ESP32 qui tente d'envoyer des données sans réseau ne plante pas — il "
                        "échoue simplement en silence, et tu peux passer des heures à chercher \"pourquoi ça "
                        "ne marche pas\" alors que le problème est juste : pas de Wi-Fi. D'où l'habitude, "
                        "essentielle dans tout ce code, d'afficher des messages de diagnostic clairs sur le "
                        "port série à chaque étape."
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER_IMG}] Capture d'écran du moniteur série montrant la séquence : connexion Wi-Fi réussie, puis envoi de données, puis réponse du serveur."},
                    {"type": "code", "language": "cpp", "code": (
                        "// Connexion Wi-Fi + envoi des mesures vers une API (requete HTTP POST en JSON)\n\n"
                        "#include <WiFi.h>\n"
                        "#include <HTTPClient.h>\n\n"
                        "const char* ssid = \"NOM_DE_TON_WIFI\";\n"
                        "const char* password = \"MOT_DE_PASSE_WIFI\";\n"
                        "const char* serverUrl = \"https://founatek224.pythonanywhere.com/api/mobile/mesures/\";\n\n"
                        "void connecterWifi() {\n"
                        "  Serial.print(\"Connexion au Wi-Fi\");\n"
                        "  WiFi.begin(ssid, password);\n"
                        "  while (WiFi.status() != WL_CONNECTED) {\n"
                        "    delay(500);\n"
                        "    Serial.print(\".\");\n"
                        "  }\n"
                        "  Serial.println(\"\\nWi-Fi connecte ! IP: \" + WiFi.localIP().toString());\n"
                        "}\n\n"
                        "void envoyerMesure(float temperature, float humidite, int qualiteAir) {\n"
                        "  if (WiFi.status() != WL_CONNECTED) {\n"
                        "    Serial.println(\"Pas de Wi-Fi, envoi annule.\");\n"
                        "    return;\n"
                        "  }\n\n"
                        "  HTTPClient http;\n"
                        "  http.begin(serverUrl);\n"
                        "  http.addHeader(\"Content-Type\", \"application/json\");\n\n"
                        "  String payload = \"{\\\"temperature\\\":\" + String(temperature) +\n"
                        "                    \",\\\"humidite\\\":\" + String(humidite) +\n"
                        "                    \",\\\"qualite_air\\\":\" + String(qualiteAir) + \"}\";\n\n"
                        "  int codeReponse = http.POST(payload);\n"
                        "  Serial.print(\"Code reponse serveur: \");\n"
                        "  Serial.println(codeReponse);\n"
                        "  http.end();\n"
                        "}\n\n"
                        "void setup() {\n"
                        "  Serial.begin(115200);\n"
                        "  connecterWifi();\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  envoyerMesure(24.5, 58.0, 42);  // Valeurs a remplacer par les vraies lectures capteurs\n"
                        "  delay(60000); // Envoi toutes les minutes\n"
                        "}\n"
                    )},
                ],
                "quiz": [
                    {
                        "question": "Quel protocole utilise-t-on pour envoyer les données vers un serveur, comme le fait un navigateur web ?",
                        "a": "Bluetooth",
                        "b": "HTTP",
                        "c": "USB",
                        "d": "Infrarouge",
                        "bonne": "B",
                        "explication": "HTTP est le protocole standard du web, utilisé aussi bien par les navigateurs que par les objets connectés.",
                    },
                    {
                        "question": "Que faut-il pour que l'ESP32 envoie correctement une mesure vers l'API ? (plusieurs réponses possibles)",
                        "a": "Être connecté au Wi-Fi",
                        "b": "Envoyer une requête au format HTTP",
                        "c": "Formater les données en JSON",
                        "d": "Avoir un écran OLED branché",
                        "bonne": "A,B,C",
                        "plusieurs": True,
                        "explication": "Wi-Fi, HTTP et JSON sont les trois ingrédients nécessaires pour envoyer une mesure à l'API — l'écran OLED est utile pour l'affichage local mais pas requis pour l'envoi réseau.",
                    },
                    {
                        "question": "Pourquoi faut-il toujours vérifier l'état de la connexion Wi-Fi avant d'envoyer une requête ?",
                        "a": "Ce n'est pas nécessaire",
                        "b": "Parce qu'une tentative d'envoi sans réseau échoue silencieusement, ce qui complique le débogage",
                        "c": "Pour ralentir le programme volontairement",
                        "d": "Pour économiser de la mémoire uniquement",
                        "bonne": "B",
                        "explication": "Sans cette vérification, l'échec est silencieux et difficile à diagnostiquer — d'où l'importance des messages de diagnostic.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 8,
                "titre": "Assemblage final : la station environnementale complète",
                "resume": "Rassembler tous les composants appris dans un seul montage et un seul programme fonctionnel.",
                "blocs": [
                    {"type": "texte", "contenu": (
                        "C'est le moment que toutes les leçons précédentes préparaient : rassembler chaque "
                        "brique apprise séparément — le microcontrôleur, l'alimentation maîtrisée, le capteur "
                        "de température/humidité, le capteur de qualité de l'air, l'écran d'affichage, la "
                        "connexion Internet — en un seul objet fonctionnel.\n\n"
                        "C'est souvent à cette étape que les vrais apprentissages arrivent — pas dans la "
                        "théorie de chaque capteur pris isolément, mais dans la confrontation de tous ces "
                        "éléments qui doivent désormais cohabiter sur les mêmes broches, la même alimentation, "
                        "le même programme, sans se marcher dessus. Un GPIO déjà utilisé par un capteur ne "
                        "peut pas servir à un autre en même temps ; l'alimentation doit supporter tous les "
                        "composants simultanément ; le programme doit lire, afficher ET envoyer, dans le bon "
                        "ordre, sans bloquer le reste.\n\n"
                        "**Plan de câblage complet** :\n"
                        "- DHT22 → DATA sur GPIO 15\n"
                        "- MQ135 → AOUT sur GPIO 34\n"
                        "- Écran OLED → SDA sur GPIO 21, SCL sur GPIO 22\n"
                        "- Tous les VCC des capteurs 3.3V → 3.3V de l'ESP32 (le MQ135 va sur VIN/5V à part)\n"
                        "- Tous les GND → un même point commun de masse (très important : tous les GND "
                        "doivent être reliés ensemble, sinon les mesures seront incohérentes)"
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER_IMG}] Photo du montage complet sur breadboard : ESP32 + DHT22 + MQ135 + écran OLED, tous câblés ensemble, vue d'ensemble claire avec étiquettes."},
                    {"type": "video", "contenu": f"[{MEDIA_PLACEHOLDER_VIDEO}] Vidéo de démonstration (1-2 min) : la station qui affiche les mesures sur l'écran OLED, puis démonstration du dashboard web/app recevant les données en direct."},
                    {"type": "texte", "contenu": (
                        "Le code complet ci-dessous rassemble tout ce que tu as appris : lecture des deux "
                        "capteurs, affichage local sur l'écran OLED, et envoi périodique vers l'API — "
                        "exactement la structure derrière une vraie station connectée en production. Prends "
                        "le temps de le relire ligne par ligne : tu dois être capable d'expliquer à quelqu'un "
                        "d'autre ce que fait chaque bloc, sans avoir besoin de le deviner."
                    )},
                    {"type": "code", "language": "cpp", "code": (
                        "// STATION ENVIRONNEMENTALE CONNECTEE - Code complet du projet final\n"
                        "// Assemble : ESP32 + DHT22 + MQ135 + ecran OLED + envoi Wi-Fi vers l'API\n\n"
                        "#include <WiFi.h>\n"
                        "#include <HTTPClient.h>\n"
                        "#include <DHT.h>\n"
                        "#include <Wire.h>\n"
                        "#include <Adafruit_GFX.h>\n"
                        "#include <Adafruit_SSD1306.h>\n\n"
                        "#define DHTPIN 15\n"
                        "#define DHTTYPE DHT22\n"
                        "#define MQ135_PIN 34\n"
                        "#define SCREEN_WIDTH 128\n"
                        "#define SCREEN_HEIGHT 64\n\n"
                        "const char* ssid = \"NOM_DE_TON_WIFI\";\n"
                        "const char* password = \"MOT_DE_PASSE_WIFI\";\n"
                        "const char* serverUrl = \"https://founatek224.pythonanywhere.com/api/mobile/mesures/\";\n\n"
                        "DHT dht(DHTPIN, DHTTYPE);\n"
                        "Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);\n\n"
                        "unsigned long dernierEnvoi = 0;\n"
                        "const unsigned long INTERVALLE_ENVOI = 60000; // 1 minute\n\n"
                        "void connecterWifi() {\n"
                        "  Serial.print(\"Connexion Wi-Fi\");\n"
                        "  WiFi.begin(ssid, password);\n"
                        "  int tentatives = 0;\n"
                        "  while (WiFi.status() != WL_CONNECTED && tentatives < 20) {\n"
                        "    delay(500);\n"
                        "    Serial.print(\".\");\n"
                        "    tentatives++;\n"
                        "  }\n"
                        "  Serial.println(WiFi.status() == WL_CONNECTED ? \"\\nWi-Fi OK\" : \"\\nEchec Wi-Fi\");\n"
                        "}\n\n"
                        "void afficherEcran(float t, float h, int air) {\n"
                        "  display.clearDisplay();\n"
                        "  display.setTextSize(1);\n"
                        "  display.setCursor(0, 0);\n"
                        "  display.println(\"Station env. - Founatek\");\n"
                        "  display.setTextSize(1);\n"
                        "  display.setCursor(0, 16);\n"
                        "  display.print(\"Temp: \"); display.print(t); display.println(\" C\");\n"
                        "  display.setCursor(0, 30);\n"
                        "  display.print(\"Humi: \"); display.print(h); display.println(\" %\");\n"
                        "  display.setCursor(0, 44);\n"
                        "  display.print(\"Air : \"); display.print(air); display.println(\" /4095\");\n"
                        "  display.display();\n"
                        "}\n\n"
                        "void envoyerMesure(float t, float h, int air) {\n"
                        "  if (WiFi.status() != WL_CONNECTED) { connecterWifi(); }\n"
                        "  if (WiFi.status() != WL_CONNECTED) return;\n\n"
                        "  HTTPClient http;\n"
                        "  http.begin(serverUrl);\n"
                        "  http.addHeader(\"Content-Type\", \"application/json\");\n"
                        "  String payload = \"{\\\"temperature\\\":\" + String(t) +\n"
                        "                    \",\\\"humidite\\\":\" + String(h) +\n"
                        "                    \",\\\"qualite_air\\\":\" + String(air) + \"}\";\n"
                        "  int code = http.POST(payload);\n"
                        "  Serial.print(\"Envoi -> code reponse: \"); Serial.println(code);\n"
                        "  http.end();\n"
                        "}\n\n"
                        "void setup() {\n"
                        "  Serial.begin(115200);\n"
                        "  dht.begin();\n"
                        "  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {\n"
                        "    Serial.println(\"Ecran OLED non detecte !\");\n"
                        "  }\n"
                        "  display.clearDisplay();\n"
                        "  display.setTextColor(SSD1306_WHITE);\n"
                        "  connecterWifi();\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  float temperature = dht.readTemperature();\n"
                        "  float humidite = dht.readHumidity();\n"
                        "  int qualiteAir = analogRead(MQ135_PIN);\n\n"
                        "  if (!isnan(temperature) && !isnan(humidite)) {\n"
                        "    afficherEcran(temperature, humidite, qualiteAir);\n\n"
                        "    if (millis() - dernierEnvoi >= INTERVALLE_ENVOI) {\n"
                        "      envoyerMesure(temperature, humidite, qualiteAir);\n"
                        "      dernierEnvoi = millis();\n"
                        "    }\n"
                        "  } else {\n"
                        "    Serial.println(\"Erreur lecture DHT22.\");\n"
                        "  }\n\n"
                        "  delay(2000);\n"
                        "}\n"
                    )},
                    {"type": "texte", "contenu": (
                        "**Pour aller plus loin** (défis bonus, une fois le montage de base validé) :\n"
                        "- Ajouter une batterie et un panneau solaire pour une station autonome, sans câble\n"
                        "- Ajouter une LED ou un buzzer qui s'active automatiquement si l'air devient mauvais "
                        "(seuil sur la lecture du MQ135)\n"
                        "- Faire dormir l'ESP32 entre deux mesures (\"deep sleep\") pour économiser l'énergie "
                        "sur batterie\n"
                        "- Explorer le remplacement du MQ135 par un capteur PM2.5/PM10 plus précis pour un "
                        "projet de qualité professionnelle\n\n"
                        "Tu as maintenant, brique par brique, construit exactement le type d'objet qui peut "
                        "changer une façon de vivre — que ce soit dans une maison, une salle de classe, ou "
                        "une ville entière. Ce n'est plus une théorie apprise sur le papier : c'est un objet "
                        "qui existe, qui mesure, qui parle. À toi de décider jusqu'où tu veux le pousser."
                    )},
                ],
                "quiz": [
                    {
                        "question": "Pourquoi tous les GND des composants doivent-ils être reliés ensemble dans le montage final ?",
                        "a": "Ce n'est pas nécessaire",
                        "b": "Pour avoir une référence de masse commune, sinon les mesures deviennent incohérentes",
                        "c": "Pour économiser des fils",
                        "d": "Pour alimenter les composants",
                        "bonne": "B",
                        "explication": "Une masse (GND) commune est indispensable pour que toutes les tensions mesurées soient comparables entre elles.",
                    },
                    {
                        "question": "Dans le code final, à quoi sert la variable 'dernierEnvoi' avec 'millis()' ?",
                        "a": "À éteindre l'écran",
                        "b": "À espacer les envois réseau sans bloquer le reste du programme avec un delay() trop long",
                        "c": "À mesurer la température",
                        "d": "Elle ne sert à rien",
                        "bonne": "B",
                        "explication": "Comparer millis() à un dernier envoi permet de temporiser l'envoi réseau sans geler la lecture des capteurs et l'affichage.",
                    },
                    {
                        "question": "Quel est l'objectif pédagogique principal de cette dernière leçon ?",
                        "a": "Apprendre un nouveau composant",
                        "b": "Assembler tous les composants déjà appris en un seul objet fonctionnel complet",
                        "c": "Refaire la théorie de la loi d'Ohm",
                        "d": "Apprendre à souder",
                        "bonne": "B",
                        "explication": "C'est la leçon d'intégration : elle ne présente rien de nouveau, elle rassemble tout ce qui précède.",
                    },
                ],
            },
        ]

    def _final_code(self):
        # Meme code complet que la derniere lecon, reutilise pour le Project.
        return self._lessons_data()[-1]["blocs"][-2]["code"]
