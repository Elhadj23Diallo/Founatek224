"""
Cree (ou met a jour) le parcours "Initiation a l'Electronique de base avec
Arduino" : les fondamentaux avant Electronique embarquee / Domotique.

Usage : python manage.py seed_arduino_debutant
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from iot.models import Organisation, Parcours, Lecon, BlocPedagogique, Quiz, Project


MEDIA_PLACEHOLDER = "media_a_ajouter"


class Command(BaseCommand):
    help = "Seed du parcours Initiation a l'Electronique de base avec Arduino"

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
            titre="Initiation à l'Électronique de base avec Arduino",
            defaults=dict(
                organisation=org,
                created_by=formateur,
                niveau="Débutant",
                certifiant=True,
                is_published=False,
                description=(
                    "Avant de connecter quoi que ce soit à Internet, il faut savoir faire clignoter une LED, "
                    "lire un bouton, et comprendre pourquoi un circuit fonctionne — ou grille. Ce parcours "
                    "pose les fondations de l'électronique et de la programmation embarquée avec une carte "
                    "Arduino : la tension, le courant, la résistance, les entrées et sorties, les capteurs de "
                    "base. C'est le prérequis naturel avant 'Électronique embarquée' et 'Domotique', qui "
                    "supposent déjà ces bases acquises."
                ),
                materiel_requis=(
                    "1x carte Arduino Uno (ou Nano/compatible)\n"
                    "1x breadboard\n"
                    "Fils de connexion (jumper wires) mâle-mâle\n"
                    "Plusieurs LED de couleurs différentes\n"
                    "Résistances 220-330 ohms (protection LED) et 10k ohms (pull-down/diviseur de tension)\n"
                    "1x bouton poussoir (interrupteur momentané)\n"
                    "1x potentiomètre rotatif (10k ohms)\n"
                    "1x buzzer/haut-parleur piézo\n"
                    "1x servomoteur (type SG90)\n"
                    "1x photorésistance (LDR)\n"
                    "1x capteur de température analogique (LM35 ou thermistance)\n"
                    "1x câble USB pour programmer l'Arduino\n"
                    "Un ordinateur avec l'IDE Arduino installé (gratuit, arduino.cc)"
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
                duree_minutes=data.get("duree_minutes", 20),
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
            titre="Veilleuse intelligente — projet final",
            ordre=1,
            language="cpp",
            description=(
                "Assemble tout ce que tu as appris : une LED dont la luminosité s'ajuste automatiquement à "
                "l'obscurité ambiante grâce à une photorésistance (PWM), un bouton pour forcer l'allumage "
                "manuellement, et un buzzer qui confirme chaque appui par un bip. Trois entrées/sorties "
                "différentes, une seule boucle loop() qui les fait cohabiter — exactement la logique que tu "
                "retrouveras, en plus grand, dans les parcours Électronique embarquée et Domotique."
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
                "titre": "Le projet : pourquoi apprendre l'électronique avec Arduino",
                "resume": "Présentation du parcours, du projet final, et de la philosophie d'apprentissage par la pratique.",
                "duree_minutes": 15,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Avant de construire une station connectée qui parle à Internet, ou une maison qui "
                        "s'automatise toute seule, il y a une étape que personne ne peut sauter : comprendre "
                        "comment un circuit électronique fonctionne réellement, et comment le piloter avec du "
                        "code. C'est exactement l'objet de ce parcours.\n\n"
                        "Ici, pas de Wi-Fi, pas de serveur, pas d'application mobile — juste une carte "
                        "Arduino, une breadboard, quelques composants, et toi. C'est volontaire : en "
                        "supprimant la complexité du réseau, on peut se concentrer entièrement sur ce qui "
                        "compte vraiment au début — le courant, la tension, les entrées, les sorties, et la "
                        "logique de programmation qui les relie."
                    )},
                    {"type": "texte", "contenu": (
                        "**Le fil rouge du parcours : la veilleuse intelligente.** Leçon après leçon, tu vas "
                        "apprendre à manipuler une LED, un bouton, un potentiomètre, un buzzer, un "
                        "servomoteur, une photorésistance — et à la toute fin, tu assembleras plusieurs de "
                        "ces briques dans un seul projet fonctionnel : une veilleuse qui s'allume "
                        "automatiquement dans le noir, réglable manuellement, avec un retour sonore.\n\n"
                        "**Pourquoi ce parcours avant les autres ?** 'Électronique embarquée' (station "
                        "connectée) et 'Domotique' (maison intelligente) supposent que tu sais déjà lire un "
                        "capteur, écrire une boucle, câbler une breadboard sans risquer de tout griller. Ce "
                        "parcours-ci, c'est la fondation — sans elle, le reste se construit sur du sable."
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER}] Photo de tout le matériel du kit posé sur une table : Arduino Uno, breadboard, LED, résistances, bouton, potentiomètre, buzzer, servo, LDR, capteur de température."},
                ],
                "quiz": [
                    {
                        "question": "Pourquoi ce parcours n'utilise-t-il ni Wi-Fi ni serveur, contrairement à 'Électronique embarquée' ?",
                        "a": "Parce que l'Arduino Uno ne peut techniquement rien faire d'autre",
                        "b": "Pour se concentrer sur les fondamentaux (électricité, entrées/sorties) sans la complexité du réseau",
                        "c": "Parce que le Wi-Fi est dangereux pour les débutants",
                        "d": "Ce n'est pas vrai, ce parcours utilise aussi le Wi-Fi",
                        "bonne": "B",
                        "explication": "Le choix est pédagogique : isoler les bases avant d'ajouter la couche réseau, déjà traitée dans un autre parcours.",
                    },
                    {
                        "question": "Quel est le projet final de ce parcours ?",
                        "a": "Une station météo connectée",
                        "b": "Une maison domotique complète",
                        "c": "Une veilleuse intelligente combinant LED, bouton et buzzer",
                        "d": "Un robot autonome",
                        "bonne": "C",
                        "explication": "La veilleuse intelligente sert de fil rouge : chaque leçon ajoute un composant qui sera réutilisé dans ce projet final.",
                    },
                    {
                        "question": "Quel est le lien entre ce parcours et 'Électronique embarquée' / 'Domotique' ?",
                        "a": "Aucun rapport, ce sont des sujets indépendants",
                        "b": "Ce parcours est le prérequis : les deux autres supposent ces bases déjà acquises",
                        "c": "Il faut faire les trois en même temps",
                        "d": "Ce parcours remplace les deux autres",
                        "bonne": "B",
                        "explication": "Les parcours plus avancés partent du principe que tu sais déjà câbler et lire un capteur — c'est ce que ce parcours enseigne en premier.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 2,
                "titre": "Les bases de l'électricité : tension, courant, résistance",
                "resume": "Comprendre les trois grandeurs fondamentales de l'électronique avec une analogie simple, et la loi d'Ohm.",
                "duree_minutes": 25,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Impossible de câbler quoi que ce soit sans comprendre trois mots que tu vas croiser "
                        "à chaque leçon : **tension**, **courant**, **résistance**. La meilleure façon de les "
                        "comprendre, c'est une analogie avec l'eau qui circule dans un tuyau.\n\n"
                        "- **La tension** (en Volts, V) — c'est la pression de l'eau. Plus elle est forte, "
                        "plus l'eau est poussée avec force dans le tuyau.\n"
                        "- **Le courant** (en Ampères, A) — c'est le débit, la quantité d'eau qui passe "
                        "réellement par seconde.\n"
                        "- **La résistance** (en Ohms, Ω) — c'est un frein dans le tuyau : plus il est "
                        "étroit, plus il freine le débit pour une même pression.\n\n"
                        "En électronique, l'eau, ce sont les électrons ; le tuyau, c'est le fil ; le frein, "
                        "c'est la résistance (le composant) ou la résistance naturelle du circuit."
                    )},
                    {"type": "texte", "contenu": (
                        "**La loi d'Ohm — la formule la plus importante de tout le parcours** :\n\n"
                        "U = R × I\n\n"
                        "où U est la tension (V), R la résistance (Ω), et I le courant (A). Trois grandeurs, "
                        "une seule formule, et si tu en connais deux, tu calcules toujours la troisième.\n\n"
                        "**Exemple concret que tu vas utiliser dès la prochaine leçon** : une LED a besoin "
                        "d'environ 20mA (0,02A) de courant, alimentée en 5V par l'Arduino, avec une chute de "
                        "tension propre à la LED d'environ 2V. La résistance à mettre en série se calcule "
                        "ainsi : R = (5V - 2V) / 0,02A = 150Ω. On arrondit généralement à 220 ou 330Ω pour "
                        "rester prudent et protéger la LED sans trop réduire sa luminosité."
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER}] Schéma illustrant l'analogie de l'eau : un réservoir (tension), un tuyau avec un débit (courant), et un rétrécissement du tuyau (résistance), avec la formule U = R × I en légende."},
                ],
                "quiz": [
                    {
                        "question": "Dans l'analogie de l'eau, à quoi correspond la tension ?",
                        "a": "Au débit d'eau",
                        "b": "À la pression de l'eau",
                        "c": "Au diamètre du tuyau",
                        "d": "À la couleur de l'eau",
                        "bonne": "B",
                        "explication": "La tension est la force qui pousse les électrons, comme la pression pousse l'eau dans un tuyau.",
                    },
                    {
                        "question": "Quelle est la formule de la loi d'Ohm ?",
                        "a": "U = R + I",
                        "b": "I = U + R",
                        "c": "U = R × I",
                        "d": "R = U + I",
                        "bonne": "C",
                        "explication": "U = R × I — la tension est le produit de la résistance et du courant.",
                    },
                    {
                        "question": "Une LED a besoin de 20mA sous 5V, avec une chute de tension de 2V. Quelle résistance faut-il, selon la loi d'Ohm ?",
                        "a": "50 ohms",
                        "b": "100 ohms",
                        "c": "150 ohms",
                        "d": "500 ohms",
                        "bonne": "C",
                        "explication": "R = (5V - 2V) / 0,02A = 3V / 0,02A = 150Ω.",
                    },
                    {
                        "question": "Que se passe-t-il si on connecte une LED directement sur 5V, sans résistance ?",
                        "a": "Rien, c'est même recommandé",
                        "b": "Le courant n'est plus limité, la LED risque de griller",
                        "c": "La LED s'allume deux fois plus fort sans danger",
                        "d": "La tension diminue automatiquement",
                        "bonne": "B",
                        "explication": "Sans résistance pour limiter le courant, celui-ci peut dépasser largement ce que la LED supporte et la détruire.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 3,
                "titre": "La carte Arduino : premier contact",
                "resume": "Découvrir le microcontrôleur Arduino, installer l'IDE, et uploader son premier programme.",
                "duree_minutes": 20,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Une carte Arduino Uno, c'est un petit ordinateur qui ne fait qu'une chose à la fois, "
                        "mais qui la fait sans jamais s'arrêter : exécuter, en boucle, le programme qu'on lui "
                        "a envoyé. Au cœur de la carte, une puce appelée microcontrôleur (l'ATmega328P sur "
                        "l'Uno) — pas de clavier, pas d'écran, pas de système d'exploitation. Juste des "
                        "broches (pins) qu'on peut lire ou piloter, et un programme qui tourne en continu.\n\n"
                        "Pour lui donner des ordres, on utilise l'IDE Arduino (le logiciel qu'on installe sur "
                        "l'ordinateur, gratuit sur arduino.cc), on branche la carte en USB, et on envoie "
                        "('upload') notre code dessus."
                    )},
                    {"type": "texte", "contenu": (
                        "**La structure d'un programme Arduino ne change jamais** :\n"
                        "- `setup()` : tout ce qui s'exécute UNE seule fois, au démarrage (configurer une "
                        "broche, initialiser une communication...)\n"
                        "- `loop()` : tout ce qui se répète À L'INFINI, tant que la carte est alimentée\n\n"
                        "C'est cette boucle infinie qui rend l'Arduino capable de surveiller un capteur ou "
                        "de piloter un composant en continu, sans jamais se fatiguer."
                    )},
                    {"type": "code", "language": "cpp", "code": (
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
                    )},
                    {"type": "video", "contenu": f"[{MEDIA_PLACEHOLDER}] Courte vidéo (15-20s) de la LED intégrée de l'Arduino qui clignote après upload du code ci-dessus, avec le moniteur série visible affichant les messages."},
                ],
                "quiz": [
                    {
                        "question": "Que fait la fonction setup() dans un programme Arduino ?",
                        "a": "Elle se répète indéfiniment",
                        "b": "Elle s'exécute une seule fois, au démarrage",
                        "c": "Elle ne s'exécute jamais",
                        "d": "Elle éteint la carte",
                        "bonne": "B",
                        "explication": "setup() tourne une seule fois au démarrage — c'est là qu'on configure les broches et les communications.",
                    },
                    {
                        "question": "Sur quelle broche se trouve la LED intégrée de l'Arduino Uno ?",
                        "a": "Broche A0",
                        "b": "Broche 2",
                        "c": "Broche 13",
                        "d": "Il n'y a pas de LED intégrée",
                        "bonne": "C",
                        "explication": "La broche 13 est directement reliée à une LED soudée sur la carte, pratique pour les premiers tests.",
                    },
                    {
                        "question": "Que fait la fonction delay(1000) ?",
                        "a": "Elle attend 1000 secondes",
                        "b": "Elle attend 1 seconde (1000 millisecondes)",
                        "c": "Elle répète le code 1000 fois",
                        "d": "Elle éteint toutes les broches",
                        "bonne": "B",
                        "explication": "delay() prend un nombre de millisecondes en argument ; 1000ms = 1 seconde.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 4,
                "titre": "Entrées/sorties numériques : le bouton poussoir",
                "resume": "Lire un bouton avec digitalRead(), et comprendre pourquoi une résistance de pull-down est indispensable.",
                "duree_minutes": 25,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Jusqu'ici, l'Arduino ne faisait que commander une sortie (la LED). Un bouton "
                        "poussoir, lui, est une entrée : l'Arduino lit son état avec `digitalRead()`, qui "
                        "renvoie soit HIGH (5V, circuit fermé) soit LOW (0V, circuit ouvert).\n\n"
                        "**Câblage** (3 fils) :\n"
                        "- Une patte du bouton → 5V de l'Arduino\n"
                        "- L'autre patte → broche 2 (entrée) ET → une résistance de 10kΩ vers GND\n"
                        "- GND de l'Arduino → l'autre extrémité de la résistance"
                    )},
                    {"type": "texte", "contenu": (
                        "**Pourquoi la résistance de pull-down est indispensable ?** Sans elle, quand le "
                        "bouton n'est PAS appuyé, la broche 2 n'est reliée à rien de précis — elle est "
                        "\"flottante\", et peut lire aléatoirement HIGH ou LOW à cause du bruit électrique "
                        "ambiant. La résistance de pull-down (vers GND) force la broche à lire LOW de façon "
                        "fiable au repos ; quand on appuie sur le bouton, le 5V l'emporte et la broche lit "
                        "HIGH. C'est exactement le même principe utilisé plus tard avec le PIR ou n'importe "
                        "quel bouton dans les parcours Domotique."
                    )},
                    {"type": "code", "language": "cpp", "code": (
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
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER}] Photo du montage sur breadboard : bouton poussoir câblé avec sa résistance de pull-down 10k vers GND, LED sur la broche 7, légendes des fils."},
                ],
                "quiz": [
                    {
                        "question": "Que renvoie digitalRead() sur une entrée numérique ?",
                        "a": "Une valeur entre 0 et 1023",
                        "b": "HIGH ou LOW uniquement",
                        "c": "Une tension exacte en volts",
                        "d": "Toujours HIGH",
                        "bonne": "B",
                        "explication": "digitalRead() est binaire : HIGH (5V) ou LOW (0V), contrairement à analogRead() qui donne une plage de valeurs.",
                    },
                    {
                        "question": "Pourquoi une broche d'entrée non connectée (\"flottante\") est-elle un problème ?",
                        "a": "Elle peut lire HIGH ou LOW de façon aléatoire à cause du bruit électrique",
                        "b": "Elle grille immédiatement l'Arduino",
                        "c": "Ce n'est pas un problème",
                        "d": "Elle bloque tout le programme",
                        "bonne": "A",
                        "explication": "Sans résistance de pull-up/pull-down, l'entrée capte du bruit électrique ambiant et son état devient imprévisible.",
                    },
                    {
                        "question": "Dans un montage avec résistance de pull-down, que lit la broche quand le bouton N'EST PAS appuyé ?",
                        "a": "HIGH",
                        "b": "LOW",
                        "c": "Une valeur aléatoire",
                        "d": "Cela dépend de la météo",
                        "bonne": "B",
                        "explication": "La résistance de pull-down relie la broche à GND au repos, donc elle lit LOW de façon fiable.",
                    },
                    {
                        "question": "Dans le code de la leçon, à quoi sert delay(50) à la fin de loop() ?",
                        "a": "À éteindre la LED",
                        "b": "À ralentir légèrement la boucle et éviter de spammer le moniteur série",
                        "c": "C'est obligatoire, sinon le code ne compile pas",
                        "d": "À faire clignoter le bouton",
                        "bonne": "B",
                        "explication": "Une petite pause évite d'inonder le moniteur série de messages à chaque micro-cycle de la boucle.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 5,
                "titre": "Breadboard et circuits : bien câbler sans tout griller",
                "resume": "Comprendre le fonctionnement interne d'une breadboard, les circuits série/parallèle, et les erreurs de câblage à éviter.",
                "duree_minutes": 20,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Une breadboard (plaque d'essai) n'est pas juste une grille de trous : à l'intérieur, "
                        "des bandes de métal relient certains trous entre eux. En général :\n"
                        "- Les **rails** sur les bords (souvent marqués + et -) sont reliés horizontalement "
                        "sur toute la longueur — parfaits pour distribuer l'alimentation (5V et GND).\n"
                        "- Les **colonnes** centrales (5 trous par groupe, de part et d'autre de la rainure "
                        "centrale) sont reliées verticalement, PAS horizontalement — chaque colonne de 5 "
                        "trous est un même nœud électrique.\n\n"
                        "Comprendre ça évite l'erreur classique du débutant : croire que deux composants "
                        "côte à côte sur la même ligne horizontale sont connectés, alors qu'ils ne le sont "
                        "que s'ils partagent la même colonne verticale."
                    )},
                    {"type": "texte", "contenu": (
                        "**Circuit série vs circuit parallèle** :\n"
                        "- En **série**, les composants sont branchés les uns à la suite des autres — le "
                        "même courant traverse tout le monde, mais la tension se répartit entre eux.\n"
                        "- En **parallèle**, les composants sont branchés côte à côte sur les mêmes deux "
                        "points — ils reçoivent tous la même tension, mais le courant total se répartit "
                        "entre les branches.\n\n"
                        "**Le piège à éviter absolument : le court-circuit.** Relier directement le + et le "
                        "- de l'alimentation sans aucune résistance ou composant entre les deux crée un "
                        "chemin à résistance quasi nulle — un courant énorme circule d'un coup, ce qui peut "
                        "endommager la carte ou l'alimentation. Toujours vérifier son montage avant de "
                        "brancher le câble USB."
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER}] Schéma annoté d'une breadboard : rails d'alimentation horizontaux en haut/bas, colonnes de 5 trous reliées verticalement au centre, avec un exemple de montage correct vs un court-circuit à éviter."},
                ],
                "quiz": [
                    {
                        "question": "Sur une breadboard classique, comment sont reliés les trous des colonnes centrales ?",
                        "a": "Horizontalement, toute la ligne est connectée",
                        "b": "Verticalement, par groupes de 5 trous",
                        "c": "Ils ne sont jamais reliés entre eux",
                        "d": "Aléatoirement selon le modèle",
                        "bonne": "B",
                        "explication": "Chaque colonne de 5 trous de part et d'autre de la rainure centrale forme un même nœud électrique, connecté verticalement.",
                    },
                    {
                        "question": "Dans un circuit en série, que se passe-t-il si un composant tombe en panne (circuit ouvert) ?",
                        "a": "Rien, les autres composants continuent de fonctionner normalement",
                        "b": "Tout le circuit s'arrête, car le courant ne peut plus circuler",
                        "c": "Le courant double automatiquement",
                        "d": "Seuls les composants suivants s'arrêtent",
                        "bonne": "B",
                        "explication": "En série, il n'y a qu'un seul chemin pour le courant — une coupure n'importe où arrête tout le circuit.",
                    },
                    {
                        "question": "Qu'est-ce qu'un court-circuit ?",
                        "a": "Un circuit avec très peu de composants",
                        "b": "Une connexion directe entre + et - sans résistance, provoquant un courant excessif",
                        "c": "Un circuit qui fonctionne parfaitement",
                        "d": "Un circuit avec un seul fil",
                        "bonne": "B",
                        "explication": "Sans rien pour limiter le courant, un chemin direct entre + et - laisse passer un courant potentiellement destructeur.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 6,
                "titre": "Sortie analogique : le PWM et la luminosité variable",
                "resume": "Comprendre le PWM et utiliser analogWrite() pour faire varier la luminosité d'une LED.",
                "duree_minutes": 20,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "L'Arduino ne peut sortir que du HIGH (5V) ou du LOW (0V) sur une broche — pas de "
                        "vraie tension intermédiaire. Pour simuler une sortie \"analogique\" (par exemple, une "
                        "LED à 50% de luminosité), on utilise le **PWM** (Pulse Width Modulation — "
                        "modulation de largeur d'impulsion) : la broche s'allume et s'éteint très "
                        "rapidement (des centaines de fois par seconde), et c'est le **rapport** entre le "
                        "temps allumé et le temps éteint qui donne l'impression d'une luminosité "
                        "intermédiaire — l'œil humain ne voit pas le clignotement, juste la moyenne.\n\n"
                        "Seules certaines broches supportent le PWM sur l'Arduino Uno, repérables par un "
                        "symbole ~ à côté du numéro (broches 3, 5, 6, 9, 10, 11)."
                    )},
                    {"type": "code", "language": "cpp", "code": (
                        "// Faire varier la luminosite d'une LED avec le PWM (fondu progressif)\n\n"
                        "#define LED_PIN 9   // Broche PWM (marquee ~9 sur la carte)\n\n"
                        "void setup() {\n"
                        "  pinMode(LED_PIN, OUTPUT);\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  // Augmente progressivement de 0 (eteint) a 255 (luminosite max)\n"
                        "  for (int luminosite = 0; luminosite <= 255; luminosite++) {\n"
                        "    analogWrite(LED_PIN, luminosite);\n"
                        "    delay(10);\n"
                        "  }\n\n"
                        "  // Puis redescend de 255 a 0\n"
                        "  for (int luminosite = 255; luminosite >= 0; luminosite--) {\n"
                        "    analogWrite(LED_PIN, luminosite);\n"
                        "    delay(10);\n"
                        "  }\n"
                        "}\n"
                    )},
                    {"type": "video", "contenu": f"[{MEDIA_PLACEHOLDER}] Courte vidéo (15-20s) de la LED sur la broche 9 dont la luminosité monte et redescend progressivement (effet de respiration)."},
                ],
                "quiz": [
                    {
                        "question": "Que signifie PWM ?",
                        "a": "Power Watt Meter",
                        "b": "Pulse Width Modulation (modulation de largeur d'impulsion)",
                        "c": "Programmable Wire Management",
                        "d": "Positive Wave Motion",
                        "bonne": "B",
                        "explication": "Le PWM simule une sortie analogique en faisant varier le rapport temps allumé / temps éteint d'un signal numérique.",
                    },
                    {
                        "question": "Quelle plage de valeurs accepte analogWrite() ?",
                        "a": "0 à 5",
                        "b": "0 à 100",
                        "c": "0 à 255",
                        "d": "0 à 1023",
                        "bonne": "C",
                        "explication": "analogWrite() code le rapport cyclique sur 8 bits, soit 0 (toujours éteint) à 255 (toujours allumé).",
                    },
                    {
                        "question": "Toutes les broches numériques de l'Arduino Uno supportent-elles analogWrite() ?",
                        "a": "Oui, toutes sans exception",
                        "b": "Non, seulement certaines broches marquées d'un symbole ~",
                        "c": "Non, aucune ne le supporte",
                        "d": "Seule la broche 13 le supporte",
                        "bonne": "B",
                        "explication": "Sur l'Uno, seules les broches 3, 5, 6, 9, 10 et 11 sont compatibles PWM.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 7,
                "titre": "Entrée analogique : le potentiomètre",
                "resume": "Lire une valeur variable avec analogRead(), et convertir cette lecture en informations utiles.",
                "duree_minutes": 20,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Un potentiomètre est une résistance variable : en tournant son axe, on change la "
                        "tension lue sur sa broche centrale, quelque part entre 0V et 5V. `analogRead()` "
                        "convertit cette tension en une valeur numérique sur **10 bits**, donc entre 0 (0V) "
                        "et 1023 (5V) — une bien meilleure résolution que le simple HIGH/LOW du digital.\n\n"
                        "**Câblage** : les deux pattes extérieures du potentiomètre vont sur 5V et GND (dans "
                        "n'importe quel ordre), la patte centrale (le curseur) va sur une broche analogique, "
                        "par exemple A0."
                    )},
                    {"type": "code", "language": "cpp", "code": (
                        "// Lire un potentiometre et l'utiliser pour piloter la luminosite d'une LED\n\n"
                        "#define POT_PIN A0\n"
                        "#define LED_PIN 9\n\n"
                        "void setup() {\n"
                        "  pinMode(LED_PIN, OUTPUT);\n"
                        "  Serial.begin(9600);\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  int valeurBrute = analogRead(POT_PIN);       // 0 a 1023\n"
                        "  int luminosite = map(valeurBrute, 0, 1023, 0, 255);  // converti en 0-255\n\n"
                        "  analogWrite(LED_PIN, luminosite);\n\n"
                        "  Serial.print(\"Potentiometre: \");\n"
                        "  Serial.print(valeurBrute);\n"
                        "  Serial.print(\" -> Luminosite LED: \");\n"
                        "  Serial.println(luminosite);\n\n"
                        "  delay(100);\n"
                        "}\n"
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER}] Photo du potentiomètre câblé sur la breadboard (pattes extérieures sur 5V/GND, curseur sur A0), avec la LED PWM à côté."},
                ],
                "quiz": [
                    {
                        "question": "Quelle est la résolution d'analogRead() sur un Arduino Uno ?",
                        "a": "8 bits (0 à 255)",
                        "b": "10 bits (0 à 1023)",
                        "c": "16 bits (0 à 65535)",
                        "d": "1 bit (0 ou 1)",
                        "bonne": "B",
                        "explication": "Le convertisseur analogique-numérique de l'Uno code la tension lue sur 10 bits, soit 1024 valeurs possibles.",
                    },
                    {
                        "question": "À quoi sert la fonction map() utilisée dans le code de cette leçon ?",
                        "a": "À afficher une carte géographique",
                        "b": "À convertir une valeur d'une plage (0-1023) vers une autre plage (0-255)",
                        "c": "À lire le potentiomètre directement",
                        "d": "À créer un délai",
                        "bonne": "B",
                        "explication": "map() reproportionne une valeur d'une échelle source vers une échelle cible — ici, adapter 0-1023 (analogRead) à 0-255 (analogWrite).",
                    },
                    {
                        "question": "Que se passe-t-il si on branche le curseur du potentiomètre sur une broche numérique et qu'on utilise digitalRead() dessus ?",
                        "a": "Ça fonctionne exactement pareil qu'avec analogRead()",
                        "b": "On ne récupère qu'une information HIGH/LOW, on perd toute la nuance de la position",
                        "c": "Le potentiomètre est immédiatement endommagé",
                        "d": "L'Arduino refuse de démarrer",
                        "bonne": "B",
                        "explication": "digitalRead() ne renvoie que deux états — pour une valeur variable comme un potentiomètre, il faut une broche analogique et analogRead().",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 8,
                "titre": "Faire du son : le buzzer",
                "resume": "Utiliser tone() pour générer des notes et une mélodie simple avec un buzzer piézo.",
                "duree_minutes": 15,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Un buzzer piézo produit un son quand on lui envoie un signal électrique qui "
                        "vibre à une certaine fréquence. Plus la fréquence (en Hertz) est élevée, plus le "
                        "son est aigu. L'Arduino fournit une fonction toute faite pour ça : `tone(broche, "
                        "fréquence)` démarre un son, et `noTone(broche)` l'arrête.\n\n"
                        "**Câblage** : une patte du buzzer sur une broche numérique (par exemple 8), l'autre "
                        "sur GND."
                    )},
                    {"type": "code", "language": "cpp", "code": (
                        "// Jouer une melodie tres simple avec le buzzer\n\n"
                        "#define BUZZER_PIN 8\n\n"
                        "// Quelques frequences de notes, en Hertz\n"
                        "#define NOTE_DO 262\n"
                        "#define NOTE_RE 294\n"
                        "#define NOTE_MI 330\n"
                        "#define NOTE_FA 349\n"
                        "#define NOTE_SOL 392\n\n"
                        "void setup() {\n"
                        "  int melodie[] = {NOTE_DO, NOTE_RE, NOTE_MI, NOTE_FA, NOTE_SOL};\n\n"
                        "  for (int i = 0; i < 5; i++) {\n"
                        "    tone(BUZZER_PIN, melodie[i]);\n"
                        "    delay(300);\n"
                        "    noTone(BUZZER_PIN);\n"
                        "    delay(50);  // petite pause entre les notes\n"
                        "  }\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  // rien ici, la melodie ne joue qu'une fois au demarrage\n"
                        "}\n"
                    )},
                    {"type": "video", "contenu": f"[{MEDIA_PLACEHOLDER}] Courte vidéo (10-15s) du buzzer qui joue la mélodie de cinq notes au démarrage de l'Arduino."},
                ],
                "quiz": [
                    {
                        "question": "Que fait la fonction tone(broche, fréquence) ?",
                        "a": "Elle éteint le son",
                        "b": "Elle génère un son à la fréquence donnée sur la broche indiquée",
                        "c": "Elle mesure le volume sonore ambiant",
                        "d": "Elle allume une LED",
                        "bonne": "B",
                        "explication": "tone() fait vibrer le buzzer à la fréquence précisée, produisant un son dont la hauteur dépend de cette fréquence.",
                    },
                    {
                        "question": "Dans quelle unité s'exprime la fréquence d'une note musicale pour tone() ?",
                        "a": "En Volts",
                        "b": "En Hertz (Hz)",
                        "c": "En Ohms",
                        "d": "En millisecondes",
                        "bonne": "B",
                        "explication": "La fréquence, en Hertz, correspond au nombre de vibrations par seconde — plus elle est élevée, plus le son est aigu.",
                    },
                    {
                        "question": "Pourquoi le code de cette leçon place-t-il la mélodie dans setup() plutôt que dans loop() ?",
                        "a": "Par erreur, ça devrait être dans loop()",
                        "b": "Pour qu'elle ne joue qu'une seule fois au démarrage, pas en boucle infinie",
                        "c": "loop() ne peut pas contenir de son",
                        "d": "Ça n'a aucune importance",
                        "bonne": "B",
                        "explication": "Tout ce qui est dans setup() ne s'exécute qu'une fois — pratique pour un son de démarrage qui ne doit pas se répéter sans arrêt.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 9,
                "titre": "Le servomoteur : créer du mouvement",
                "resume": "Contrôler l'angle d'un servomoteur avec la librairie Servo, en position fixe puis pilotée par un potentiomètre.",
                "duree_minutes": 20,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Un servomoteur est un petit moteur qui, au lieu de tourner en continu comme un "
                        "moteur classique, se positionne à un **angle précis** entre 0° et 180°, et le "
                        "maintient. C'est ce qui permet de piloter un volet, une barrière miniature, ou "
                        "l'aiguille d'un cadran.\n\n"
                        "En interne, il reçoit lui aussi un signal PWM, mais interprété différemment d'une "
                        "LED : la durée de l'impulsion indique l'angle voulu, pas une luminosité. "
                        "Heureusement, la librairie standard `Servo.h` cache toute cette complexité derrière "
                        "une fonction simple : `write(angle)`."
                    )},
                    {"type": "code", "language": "cpp", "code": (
                        "// Piloter un servomoteur : balayage automatique de 0 a 180 degres\n\n"
                        "#include <Servo.h>\n\n"
                        "Servo monServo;\n"
                        "#define SERVO_PIN 10\n\n"
                        "void setup() {\n"
                        "  monServo.attach(SERVO_PIN);\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  for (int angle = 0; angle <= 180; angle += 5) {\n"
                        "    monServo.write(angle);\n"
                        "    delay(50);\n"
                        "  }\n\n"
                        "  for (int angle = 180; angle >= 0; angle -= 5) {\n"
                        "    monServo.write(angle);\n"
                        "    delay(50);\n"
                        "  }\n"
                        "}\n\n"
                        "// Pour piloter le servo avec le potentiometre de la lecon 7, remplace loop() par :\n"
                        "// void loop() {\n"
                        "//   int valeurBrute = analogRead(A0);\n"
                        "//   int angle = map(valeurBrute, 0, 1023, 0, 180);\n"
                        "//   monServo.write(angle);\n"
                        "//   delay(20);\n"
                        "// }\n"
                    )},
                    {"type": "video", "contenu": f"[{MEDIA_PLACEHOLDER}] Courte vidéo (15-20s) du servomoteur qui balaie automatiquement de 0° à 180° et revient, puis (optionnel) piloté à la main via le potentiomètre."},
                ],
                "quiz": [
                    {
                        "question": "Quelle est la différence principale entre un servomoteur et un moteur classique ?",
                        "a": "Le servomoteur tourne plus vite",
                        "b": "Le servomoteur se positionne à un angle précis et le maintient, il ne tourne pas en continu",
                        "c": "Il n'y a aucune différence",
                        "d": "Le servomoteur ne fonctionne qu'en courant continu",
                        "bonne": "B",
                        "explication": "Un servomoteur est conçu pour atteindre et maintenir un angle précis (0-180°), contrairement à un moteur classique qui tourne librement.",
                    },
                    {
                        "question": "Quelle fonction de la librairie Servo permet de fixer l'angle du servomoteur ?",
                        "a": "attach()",
                        "b": "write()",
                        "c": "begin()",
                        "d": "read()",
                        "bonne": "B",
                        "explication": "write(angle) envoie la commande de position au servomoteur, entre 0 et 180 degrés.",
                    },
                    {
                        "question": "Pourquoi peut-on réutiliser le potentiomètre de la leçon 7 pour piloter ce servomoteur ?",
                        "a": "On ne peut pas, ce sont des composants incompatibles",
                        "b": "Parce que map() permet de convertir la même lecture analogique (0-1023) vers n'importe quelle plage de sortie, y compris 0-180",
                        "c": "Le potentiomètre est directement branché sur le servomoteur, sans passer par l'Arduino",
                        "d": "Le servomoteur lit lui-même le potentiomètre",
                        "bonne": "B",
                        "explication": "map() est justement l'outil qui permet de réutiliser une même entrée (potentiomètre) pour piloter des sorties très différentes (LED en 0-255, servo en 0-180).",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 10,
                "titre": "Capteurs de base : photorésistance et température",
                "resume": "Lire une photorésistance (LDR) via un diviseur de tension, et un capteur de température analogique.",
                "duree_minutes": 25,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Une **photorésistance (LDR)** est un composant dont la résistance change avec la "
                        "lumière : elle est haute dans le noir (plusieurs dizaines de kΩ) et basse en pleine "
                        "lumière (quelques centaines d'Ω). Seule, elle ne donne rien de mesurable — il faut "
                        "l'associer à une résistance fixe (10kΩ) en **diviseur de tension** : le point entre "
                        "les deux composants donne une tension qui varie selon la lumière ambiante, "
                        "lisible avec `analogRead()`.\n\n"
                        "**Câblage** : 5V → LDR → point de mesure (vers une broche analogique, ex A1) → "
                        "résistance 10kΩ → GND."
                    )},
                    {"type": "texte", "contenu": (
                        "**Le capteur de température** (LM35 ou thermistance) fonctionne sur le même "
                        "principe : une tension analogique, lue avec `analogRead()`, qu'il faut ensuite "
                        "convertir en degrés selon la formule propre au capteur utilisé. Pour un LM35 par "
                        "exemple, la sortie est directement proportionnelle : 10mV par degré Celsius, ce qui "
                        "simplifie beaucoup la conversion."
                    )},
                    {"type": "code", "language": "cpp", "code": (
                        "// Lire une photoresistance (LDR) et allumer une LED automatiquement dans le noir\n\n"
                        "#define LDR_PIN A1\n"
                        "#define LED_PIN 9\n"
                        "#define SEUIL_OBSCURITE 400   // A ajuster selon ton montage et ta piece\n\n"
                        "void setup() {\n"
                        "  pinMode(LED_PIN, OUTPUT);\n"
                        "  Serial.begin(9600);\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  int luminositeAmbiante = analogRead(LDR_PIN);\n"
                        "  Serial.print(\"Luminosite (LDR): \");\n"
                        "  Serial.println(luminositeAmbiante);\n\n"
                        "  if (luminositeAmbiante < SEUIL_OBSCURITE) {\n"
                        "    digitalWrite(LED_PIN, HIGH);   // Il fait sombre -> on allume\n"
                        "  } else {\n"
                        "    digitalWrite(LED_PIN, LOW);\n"
                        "  }\n\n"
                        "  delay(200);\n"
                        "}\n"
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER}] Photo du montage : LDR en diviseur de tension avec résistance 10k vers GND, capteur de température à côté, légendes des broches A1 (LDR) et A2 (température)."},
                ],
                "quiz": [
                    {
                        "question": "Comment varie la résistance d'une photorésistance (LDR) selon la lumière ?",
                        "a": "Elle est constante, la lumière n'a aucun effet",
                        "b": "Elle augmente dans le noir et diminue en pleine lumière",
                        "c": "Elle diminue dans le noir et augmente en pleine lumière",
                        "d": "Elle ne fonctionne qu'en pleine obscurité totale",
                        "bonne": "B",
                        "explication": "Une LDR a une haute résistance dans le noir et une résistance basse en pleine lumière — c'est l'inverse qui serait faux.",
                    },
                    {
                        "question": "Pourquoi faut-il associer la LDR à une résistance fixe (diviseur de tension) au lieu de la lire seule ?",
                        "a": "Ce n'est pas nécessaire, on peut la lire directement",
                        "b": "Seule, la LDR ne produit pas de tension mesurable ; le diviseur transforme sa variation de résistance en une tension lisible",
                        "c": "La résistance fixe protège l'Arduino contre les surtensions uniquement",
                        "d": "C'est purement décoratif",
                        "bonne": "B",
                        "explication": "Un diviseur de tension entre la LDR et une résistance fixe crée un point milieu dont la tension varie avec la lumière — c'est ce point qu'on lit avec analogRead().",
                    },
                    {
                        "question": "Pour un capteur LM35, quelle est la relation entre la tension de sortie et la température ?",
                        "a": "Aucune relation, il faut une table de correspondance complexe",
                        "b": "10mV par degré Celsius, une relation directement proportionnelle",
                        "c": "1V par degré Celsius",
                        "d": "La sortie est toujours fixe à 5V",
                        "bonne": "B",
                        "explication": "Le LM35 est calibré pour donner 10mV de sortie par degré Celsius, ce qui rend la conversion simple par calcul.",
                    },
                    {
                        "question": "Dans le code de cette leçon, à quoi sert la constante SEUIL_OBSCURITE ?",
                        "a": "Elle fixe la luminosité maximale de la LED",
                        "b": "Elle définit la valeur de luminosité ambiante en dessous de laquelle on considère qu'il fait sombre",
                        "c": "Elle n'a aucun effet sur le comportement du programme",
                        "d": "Elle mesure la température",
                        "bonne": "B",
                        "explication": "C'est le seuil de décision : si la lecture de la LDR passe en dessous, le programme considère qu'il fait sombre et allume la LED.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 11,
                "titre": "Le moniteur série : déboguer comme un pro",
                "resume": "Utiliser Serial.print()/println() pour observer en direct ce que fait réellement le programme.",
                "duree_minutes": 15,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Le moniteur série est l'outil de débogage le plus utile en électronique embarquée : "
                        "il affiche, en direct sur l'ordinateur, tout ce que l'Arduino décide de lui "
                        "envoyer via le câble USB. C'est ce qui permet de répondre à la question que tout "
                        "débutant se pose face à un montage qui ne marche pas : \"est-ce que mon code fait "
                        "vraiment ce que je crois qu'il fait ?\"\n\n"
                        "Trois fonctions suffisent pour presque tout :\n"
                        "- `Serial.begin(9600)` (dans setup()) : démarre la communication, à la même vitesse "
                        "que celle réglée dans le moniteur série de l'IDE\n"
                        "- `Serial.print(valeur)` : affiche une valeur sans retour à la ligne\n"
                        "- `Serial.println(valeur)` : affiche une valeur ET revient à la ligne"
                    )},
                    {"type": "code", "language": "cpp", "code": (
                        "// Exemple complet : logguer plusieurs lectures sur une seule ligne lisible\n\n"
                        "#define POT_PIN A0\n"
                        "#define LDR_PIN A1\n"
                        "#define BOUTON_PIN 2\n\n"
                        "void setup() {\n"
                        "  pinMode(BOUTON_PIN, INPUT);\n"
                        "  Serial.begin(9600);\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  int potentiometre = analogRead(POT_PIN);\n"
                        "  int luminosite = analogRead(LDR_PIN);\n"
                        "  int bouton = digitalRead(BOUTON_PIN);\n\n"
                        "  Serial.print(\"Pot: \");\n"
                        "  Serial.print(potentiometre);\n"
                        "  Serial.print(\" | LDR: \");\n"
                        "  Serial.print(luminosite);\n"
                        "  Serial.print(\" | Bouton: \");\n"
                        "  Serial.println(bouton == HIGH ? \"presse\" : \"relache\");\n\n"
                        "  delay(200);\n"
                        "}\n"
                    )},
                ],
                "quiz": [
                    {
                        "question": "Quelle fonction faut-il appeler dans setup() avant d'utiliser Serial.print() ?",
                        "a": "Serial.print()",
                        "b": "Serial.begin(vitesse)",
                        "c": "Serial.start()",
                        "d": "Aucune, ce n'est pas nécessaire",
                        "bonne": "B",
                        "explication": "Serial.begin() initialise la communication série à une vitesse donnée (souvent 9600 bauds), indispensable avant tout print().",
                    },
                    {
                        "question": "Quelle est la différence entre Serial.print() et Serial.println() ?",
                        "a": "Aucune différence",
                        "b": "println() ajoute un retour à la ligne après l'affichage, pas print()",
                        "c": "print() affiche en majuscules",
                        "d": "println() est plus rapide",
                        "bonne": "B",
                        "explication": "println() (avec 'ln' pour 'line') passe à la ligne suivante après avoir affiché la valeur, contrairement à print().",
                    },
                    {
                        "question": "Pourquoi le moniteur série est-il particulièrement utile pour déboguer un montage électronique ?",
                        "a": "Il répare automatiquement les erreurs de câblage",
                        "b": "Il permet de voir en direct les valeurs réellement lues/calculées par le programme, sans deviner",
                        "c": "Il n'a aucune utilité pratique",
                        "d": "Il remplace le besoin de câbler quoi que ce soit",
                        "bonne": "B",
                        "explication": "Sans moniteur série, on ne peut qu'observer le comportement physique (LED, son) ; avec lui, on voit les valeurs internes exactes du programme.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 12,
                "titre": "Projet final : la veilleuse intelligente",
                "resume": "Assembler LDR, LED en PWM, bouton et buzzer dans un seul projet cohérent.",
                "duree_minutes": 30,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "C'est le moment de faire cohabiter tout ce qui a été appris séparément : la lecture "
                        "de la photorésistance (leçon 10), la sortie PWM pour la LED (leçon 6), le bouton "
                        "avec sa résistance de pull-down (leçon 4), et le buzzer pour le retour sonore "
                        "(leçon 8).\n\n"
                        "**Cahier des charges de la veilleuse intelligente** :\n"
                        "- Dans le noir, la LED s'allume automatiquement, avec une luminosité qui suit "
                        "l'obscurité ambiante (plus il fait sombre, plus elle est forte)\n"
                        "- Un appui sur le bouton force l'état de la LED (allumée à fond ou éteinte), "
                        "indépendamment de la luminosité ambiante, jusqu'au prochain appui\n"
                        "- Chaque appui sur le bouton déclenche un bref bip du buzzer, pour confirmer la "
                        "prise en compte"
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER}] Photo du montage complet sur breadboard : Arduino + LDR (diviseur de tension) + LED PWM + bouton poussoir + buzzer, vue d'ensemble avec étiquettes de chaque fil."},
                    {"type": "code", "language": "cpp", "code": (
                        "// VEILLEUSE INTELLIGENTE - Projet final\n"
                        "// Assemble : LDR + LED PWM + bouton (mode manuel) + buzzer\n\n"
                        "#define LDR_PIN A1\n"
                        "#define LED_PIN 9\n"
                        "#define BOUTON_PIN 2\n"
                        "#define BUZZER_PIN 8\n\n"
                        "#define SEUIL_OBSCURITE 400\n\n"
                        "bool modeManuelActif = false;\n"
                        "bool manuelAllume = false;\n"
                        "bool dernierLectureBouton = LOW, boutonStable = LOW;\n"
                        "unsigned long dernierChangementBouton = 0;\n"
                        "const unsigned long DELAI_DEBOUNCE = 50;\n\n"
                        "void gererBouton() {\n"
                        "  bool lectureBrute = digitalRead(BOUTON_PIN);\n"
                        "  if (lectureBrute != dernierLectureBouton) dernierChangementBouton = millis();\n\n"
                        "  if ((millis() - dernierChangementBouton) > DELAI_DEBOUNCE) {\n"
                        "    if (lectureBrute != boutonStable) {\n"
                        "      boutonStable = lectureBrute;\n"
                        "      if (boutonStable == HIGH) {\n"
                        "        // Bascule le mode manuel : force allume, puis force eteint, puis retour auto\n"
                        "        if (!modeManuelActif) {\n"
                        "          modeManuelActif = true;\n"
                        "          manuelAllume = true;\n"
                        "        } else if (manuelAllume) {\n"
                        "          manuelAllume = false;\n"
                        "        } else {\n"
                        "          modeManuelActif = false;  // retour au mode automatique\n"
                        "        }\n"
                        "        tone(BUZZER_PIN, 440);   // bip de confirmation\n"
                        "        delay(80);\n"
                        "        noTone(BUZZER_PIN);\n"
                        "      }\n"
                        "    }\n"
                        "  }\n"
                        "  dernierLectureBouton = lectureBrute;\n"
                        "}\n\n"
                        "void setup() {\n"
                        "  pinMode(LED_PIN, OUTPUT);\n"
                        "  pinMode(BOUTON_PIN, INPUT);\n"
                        "  Serial.begin(9600);\n"
                        "  Serial.println(\"Veilleuse intelligente prete.\");\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  gererBouton();\n\n"
                        "  if (modeManuelActif) {\n"
                        "    analogWrite(LED_PIN, manuelAllume ? 255 : 0);\n"
                        "  } else {\n"
                        "    int luminositeAmbiante = analogRead(LDR_PIN);\n"
                        "    if (luminositeAmbiante < SEUIL_OBSCURITE) {\n"
                        "      // Plus il fait sombre, plus la LED est forte\n"
                        "      int intensite = map(luminositeAmbiante, 0, SEUIL_OBSCURITE, 255, 0);\n"
                        "      analogWrite(LED_PIN, intensite);\n"
                        "    } else {\n"
                        "      analogWrite(LED_PIN, 0);\n"
                        "    }\n"
                        "  }\n\n"
                        "  delay(20);\n"
                        "}\n"
                    )},
                    {"type": "video", "contenu": f"[{MEDIA_PLACEHOLDER}] Vidéo de démonstration (1-2 min) : la LED qui s'allume progressivement quand on assombrit la LDR (main au-dessus), puis appui sur le bouton pour forcer l'état manuel avec le bip du buzzer à chaque appui."},
                    {"type": "texte", "contenu": (
                        "**Pour aller plus loin** (défis bonus une fois le montage de base validé) :\n"
                        "- Ajouter le servomoteur (leçon 9) pour ouvrir/fermer un petit volet devant la LED\n"
                        "- Ajouter un capteur de température : buzzer d'alerte si la température dépasse un "
                        "seuil\n"
                        "- Remplacer le seuil fixe SEUIL_OBSCURITE par une calibration automatique au "
                        "démarrage (mesurer la luminosité ambiante pendant quelques secondes)\n\n"
                        "Tu as maintenant manipulé une entrée numérique, une entrée analogique, une sortie "
                        "PWM, et un son — les quatre briques de base de presque tous les projets "
                        "électroniques. C'est exactement sur cette fondation que reposent les parcours "
                        "Électronique embarquée et Domotique."
                    )},
                ],
                "quiz": [
                    {
                        "question": "Dans le projet final, que fait un premier appui sur le bouton ?",
                        "a": "Il coupe complètement l'alimentation",
                        "b": "Il active le mode manuel et force la LED à pleine luminosité",
                        "c": "Il rien du tout",
                        "d": "Il change la couleur de la LED",
                        "bonne": "B",
                        "explication": "Le premier appui bascule modeManuelActif à true et manuelAllume à true, forçant la LED au maximum.",
                    },
                    {
                        "question": "En mode automatique (sans intervention manuelle), comment la luminosité de la LED est-elle calculée ?",
                        "a": "Elle est toujours fixe à 255",
                        "b": "Elle dépend de la lecture de la LDR via map(), plus il fait sombre, plus elle est forte",
                        "c": "Elle dépend uniquement du bouton",
                        "d": "Elle clignote aléatoirement",
                        "bonne": "B",
                        "explication": "gererLED (dans loop()) utilise map() pour convertir la lecture LDR en intensité PWM inversement proportionnelle à la luminosité ambiante.",
                    },
                    {
                        "question": "Quel est l'objectif pédagogique principal de cette dernière leçon ?",
                        "a": "Apprendre un nouveau composant",
                        "b": "Assembler toutes les briques précédentes (entrée numérique, entrée analogique, sortie PWM, son) en un seul projet cohérent",
                        "c": "Revoir uniquement la théorie de la loi d'Ohm",
                        "d": "Apprendre à souder",
                        "bonne": "B",
                        "explication": "C'est la leçon d'intégration : elle ne présente rien de nouveau, elle combine ce qui précède avec une logique claire de priorité (manuel > automatique).",
                    },
                    {
                        "question": "Pourquoi utilise-t-on un anti-rebond (debounce) sur le bouton dans ce projet ?",
                        "a": "Pour ralentir volontairement le programme",
                        "b": "Pour éviter qu'un seul appui physique ne soit interprété comme plusieurs appuis à cause de micro-oscillations mécaniques",
                        "c": "Ce n'est pas un anti-rebond, c'est une coïncidence",
                        "d": "Pour économiser de l'énergie",
                        "bonne": "B",
                        "explication": "Un bouton mécanique 'rebondit' électriquement pendant quelques millisecondes à chaque appui ; le debounce (delai + etat stable) filtre ce bruit pour ne compter qu'un seul vrai appui.",
                    },
                ],
            },
        ]

    # ------------------------------------------------------------------
    def _final_code(self):
        return (
            "// VEILLEUSE INTELLIGENTE - Code complet du projet final\n"
            "// Assemble : LDR + LED PWM + bouton (mode manuel) + buzzer\n\n"
            "#define LDR_PIN A1\n"
            "#define LED_PIN 9\n"
            "#define BOUTON_PIN 2\n"
            "#define BUZZER_PIN 8\n\n"
            "#define SEUIL_OBSCURITE 400\n\n"
            "bool modeManuelActif = false;\n"
            "bool manuelAllume = false;\n"
            "bool dernierLectureBouton = LOW, boutonStable = LOW;\n"
            "unsigned long dernierChangementBouton = 0;\n"
            "const unsigned long DELAI_DEBOUNCE = 50;\n\n"
            "void gererBouton() {\n"
            "  bool lectureBrute = digitalRead(BOUTON_PIN);\n"
            "  if (lectureBrute != dernierLectureBouton) dernierChangementBouton = millis();\n\n"
            "  if ((millis() - dernierChangementBouton) > DELAI_DEBOUNCE) {\n"
            "    if (lectureBrute != boutonStable) {\n"
            "      boutonStable = lectureBrute;\n"
            "      if (boutonStable == HIGH) {\n"
            "        if (!modeManuelActif) {\n"
            "          modeManuelActif = true;\n"
            "          manuelAllume = true;\n"
            "        } else if (manuelAllume) {\n"
            "          manuelAllume = false;\n"
            "        } else {\n"
            "          modeManuelActif = false;\n"
            "        }\n"
            "        tone(BUZZER_PIN, 440);\n"
            "        delay(80);\n"
            "        noTone(BUZZER_PIN);\n"
            "      }\n"
            "    }\n"
            "  }\n"
            "  dernierLectureBouton = lectureBrute;\n"
            "}\n\n"
            "void setup() {\n"
            "  pinMode(LED_PIN, OUTPUT);\n"
            "  pinMode(BOUTON_PIN, INPUT);\n"
            "  Serial.begin(9600);\n"
            "  Serial.println(\"Veilleuse intelligente prete.\");\n"
            "}\n\n"
            "void loop() {\n"
            "  gererBouton();\n\n"
            "  if (modeManuelActif) {\n"
            "    analogWrite(LED_PIN, manuelAllume ? 255 : 0);\n"
            "  } else {\n"
            "    int luminositeAmbiante = analogRead(LDR_PIN);\n"
            "    if (luminositeAmbiante < SEUIL_OBSCURITE) {\n"
            "      int intensite = map(luminositeAmbiante, 0, SEUIL_OBSCURITE, 255, 0);\n"
            "      analogWrite(LED_PIN, intensite);\n"
            "    } else {\n"
            "      analogWrite(LED_PIN, 0);\n"
            "    }\n"
            "  }\n\n"
            "  delay(20);\n"
            "}\n"
        )
