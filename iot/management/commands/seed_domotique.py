"""
Cree (ou met a jour) le parcours "Domotique" : La Maison Connectee Intelligente,
decoupe en apprentissage par le projet. Plus detaille que le premier cours
(Electronique embarquee) : plus d'explications par lecon, plus de questions,
melange de quiz a reponse unique et a choix multiples.

Usage : python manage.py seed_domotique
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from iot.models import Organisation, Parcours, Lecon, BlocPedagogique, Quiz, Project


MEDIA_PLACEHOLDER = "media_a_ajouter"


class Command(BaseCommand):
    help = "Seed du parcours Domotique (maison connectee intelligente)"

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
            titre="Domotique : La Maison Connectée Intelligente",
            defaults=dict(
                organisation=org,
                created_by=formateur,
                niveau="Intermédiaire",
                certifiant=True,
                is_published=False,
                description=(
                    "Va au-delà de la simple mesure : apprends à faire AGIR l'électronique sur le monde "
                    "réel. Ce parcours construit, brique par brique, une véritable installation domotique — "
                    "un système qui allume une lumière quand quelqu'un entre dans une pièce, régule "
                    "automatiquement la température, garde un contrôle manuel de secours, et se pilote à "
                    "distance depuis une application. C'est le pont entre 'mesurer le monde' (le parcours "
                    "Électronique embarquée) et 'agir sur le monde' — la vraie définition de la domotique."
                ),
                materiel_requis=(
                    "1x carte ESP32 (DevKit V1 ou équivalent)\n"
                    "1x module relais 2 canaux (5V, opto-isolé) — ATTENTION : partie 220V, prudence absolue\n"
                    "1x capteur de mouvement PIR (HC-SR501)\n"
                    "1x capteur DHT22 (température/humidité)\n"
                    "1x écran LCD 16x2 avec module I2C (adresse 0x27 la plupart du temps)\n"
                    "1x bouton poussoir (interrupteur momentané)\n"
                    "1x résistance 10k ohms (pull-down du bouton)\n"
                    "1x ampoule ou petit appareil basse tension (12V max) OU une simple LED de forte puissance "
                    "pour simuler la charge pilotée par le relais SANS toucher au 220V en pratique\n"
                    "1x breadboard + fils de connexion\n"
                    "1x câble USB pour programmer l'ESP32\n"
                    "Un ordinateur avec l'IDE Arduino installé"
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
                duree_minutes=data.get("duree_minutes", 25),
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
            titre="Maison connectée intelligente — projet final",
            ordre=1,
            language="cpp",
            description=(
                "Assemble tout : ESP32, relais (lumière pilotée), PIR (détection de présence), DHT22 "
                "(température), écran LCD (tableau de bord physique), bouton poussoir (contrôle local de "
                "secours), et une règle d'automatisation simple (si mouvement détecté ET qu'il fait sombre, "
                "allume la lumière automatiquement). Le résultat : une vraie maquette de maison intelligente, "
                "pilotable à la fois automatiquement, manuellement, et à distance."
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
                "titre": "Le projet : de la mesure à l'action",
                "resume": "Présentation du projet final, du matériel nécessaire, et de ce qui distingue la domotique de la simple mesure.",
                "duree_minutes": 20,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Une station qui mesure la température, c'est utile. Mais une maison qui **réagit** "
                        "à cette température — qui allume le ventilateur toute seule quand il fait trop "
                        "chaud, qui éclaire un couloir quand quelqu'un y entre, qui garde une trace de qui a "
                        "activé quoi et quand — c'est un métier différent. C'est la domotique : l'électronique "
                        "qui ne se contente plus d'observer le monde, mais qui AGIT dessus.\n\n"
                        "Pense à la différence entre un thermomètre accroché au mur et un thermostat "
                        "intelligent. Les deux mesurent la même température. Mais seul le second peut "
                        "décider, seul, d'allumer le chauffage. C'est exactement le saut que ce parcours te "
                        "fait franchir.\n\n"
                        "**Le projet que tu vas construire** : une maquette de maison connectée capable de :\n"
                        "- Allumer/éteindre une lumière automatiquement selon la présence détectée\n"
                        "- Réguler intelligemment selon la température ambiante\n"
                        "- Afficher l'état du système en temps réel sur un petit écran physique\n"
                        "- Garder un interrupteur manuel de secours, toujours fonctionnel — même si le "
                        "Wi-Fi tombe\n"
                        "- Se piloter à distance depuis une application (le même principe qu'utilise "
                        "Founatek pour ses vrais relais connectés)\n\n"
                        "**Une règle d'or que tu vas retrouver à chaque leçon** : dans un vrai système "
                        "domotique, plus l'enjeu est important (une porte, une lumière, un appareil branché "
                        "sur secteur), plus il faut prévoir un moyen de reprendre le contrôle manuellement. "
                        "Un système 100% automatique et sans filet de sécurité n'est pas de la bonne "
                        "domotique — c'est un piège. On va construire les deux ensemble, dès le départ."
                    )},
                    {"type": "texte", "contenu": (
                        "**Une histoire vraie, pour comprendre pourquoi la prudence n'est jamais optionnelle.**\n\n"
                        "Beaucoup de débutants en électronique, en découvrant qu'un relais permet de piloter "
                        "n'importe quel appareil électrique depuis un microcontrôleur, veulent immédiatement "
                        "brancher une vraie lampe sur secteur (220V). C'est exactement le réflexe qu'il faut "
                        "éviter au début. Le courant qui circule dans une prise murale peut tuer en une "
                        "fraction de seconde si le montage est mal isolé — ce n'est pas une exagération, "
                        "c'est un fait physique. La leçon 2 de ce parcours, avant même de toucher le premier "
                        "composant, est entièrement consacrée à cette sécurité. Ne la saute pas.\n\n"
                        "Pour ce cours, on simulera la charge pilotée par le relais avec une simple LED de "
                        "forte puissance ou un appareil basse tension (12V maximum) — le principe électronique "
                        "et le code sont rigoureusement identiques à ceux d'un vrai relais 220V, sans le "
                        "danger. Une fois les bases maîtrisées et si tu veux vraiment piloter du 220V, "
                        "fais-toi accompagner par quelqu'un d'expérimenté ou utilise un module relais "
                        "certifié avec boîtier isolé — jamais de fils dénudés à l'air libre."
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER}] Photo du kit complet : ESP32, module relais, PIR, DHT22, écran LCD I2C, bouton poussoir, posés côte à côte avant assemblage."},
                ],
                "quiz": [
                    {
                        "question": "Quelle est la différence fondamentale entre une station de mesure et un système domotique ?",
                        "a": "La domotique agit sur le monde physique, pas seulement le mesurer",
                        "b": "Il n'y a aucune différence",
                        "c": "La domotique ne mesure jamais rien",
                        "d": "La domotique n'utilise pas d'électronique",
                        "bonne": "A",
                        "explication": "Une station mesure ; un système domotique mesure ET agit (allumer, éteindre, réguler) en conséquence.",
                    },
                    {
                        "question": "Pourquoi ce cours simule-t-il la charge du relais avec une LED/appareil basse tension plutôt qu'une vraie lampe secteur ?",
                        "a": "Par manque de budget uniquement",
                        "b": "Le 220V est dangereux pour un débutant mal isolé ; le principe électronique reste identique en basse tension",
                        "c": "Les LED sont plus jolies",
                        "d": "Les relais ne fonctionnent pas avec du 220V",
                        "bonne": "B",
                        "explication": "La sécurité prime : on apprend le même principe (piloter une charge via un relais) sans le risque électrique du secteur.",
                    },
                    {
                        "question": "Quels éléments fait partie du projet final de ce parcours ? (plusieurs réponses possibles)",
                        "a": "Détection de présence automatique",
                        "b": "Régulation selon la température",
                        "c": "Un interrupteur manuel de secours",
                        "d": "Un GPS pour localiser la maison",
                        "bonne": "A,B,C",
                        "plusieurs": True,
                        "explication": "Le projet combine présence, température, affichage, contrôle manuel et pilotage à distance — pas de GPS.",
                    },
                    {
                        "question": "Selon la 'règle d'or' de cette leçon, que doit-on toujours prévoir pour les fonctions à fort enjeu (porte, lumière, appareil secteur) ?",
                        "a": "Rien, l'automatisation doit être totale",
                        "b": "Un moyen de reprendre le contrôle manuellement",
                        "c": "Un mot de passe complexe uniquement",
                        "d": "Un abonnement premium",
                        "bonne": "B",
                        "explication": "Un système domotique fiable garde toujours un filet de sécurité manuel, surtout si le réseau ou l'automatisation tombe en panne.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 2,
                "titre": "Sécurité électrique : ce qu'il faut savoir avant de toucher un relais",
                "resume": "Comprendre les dangers du secteur, l'isolation galvanique, et les bons réflexes avant tout montage domotique.",
                "duree_minutes": 20,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Cette leçon ne contient aucun code. C'est volontaire. Avant d'apprendre À FAIRE "
                        "quelque chose en domotique, il faut apprendre à ne PAS se blesser en le faisant.\n\n"
                        "**Pourquoi le secteur (220V) est-il si dangereux, concrètement ?** Le corps humain "
                        "conduit l'électricité. À partir d'environ 30 mA traversant le cœur, le courant peut "
                        "provoquer une fibrillation cardiaque potentiellement mortelle. Une prise de courant "
                        "domestique peut délivrer plusieurs ampères — largement de quoi dépasser ce seuil en "
                        "une fraction de seconde si le corps devient un chemin entre deux points de "
                        "potentiels différents (par exemple, un fil dénudé touché en même temps qu'un objet "
                        "relié à la terre).\n\n"
                        "**Le rôle du relais n'est pas seulement de \"commander\" un appareil — c'est aussi, "
                        "et surtout, un composant de sécurité.** Un relais correctement choisi assure une "
                        "**isolation galvanique** : le circuit basse tension (3.3V/5V, celui de l'ESP32, "
                        "totalement inoffensif) et le circuit haute tension (220V, celui de l'appareil "
                        "piloté) ne sont JAMAIS connectés électriquement entre eux. Seul un signal magnétique "
                        "(la bobine du relais) fait le lien. C'est ce qui permet à un enfant de toucher sans "
                        "risque les broches côté ESP32 pendant qu'un adulte manipule prudemment le côté "
                        "secteur, séparément."
                    )},
                    {"type": "texte", "contenu": (
                        "**Les règles non négociables pour ce parcours et au-delà :**\n\n"
                        "1. **Jamais de montage 220V improvisé sur une breadboard.** Une breadboard n'est pas "
                        "conçue pour isoler correctement le secteur — utilise toujours un module relais avec "
                        "boîtier fermé et bornes à vis pour la partie haute tension.\n"
                        "2. **Toujours débrancher l'appareil du secteur avant de câbler quoi que ce soit** "
                        "côté relais — jamais de câblage sous tension.\n"
                        "3. **Ne jamais laisser de fils dénudés à l'air libre** côté 220V — gaine, "
                        "domino, ou bornier fermé systématiquement.\n"
                        "4. **En cas de doute, ne pas essayer.** Demande à quelqu'un d'expérimenté, ou reste "
                        "en basse tension (12V et moins) pour t'entraîner — c'est exactement ce que fait ce "
                        "cours.\n"
                        "5. **Un relais mal dimensionné est un risque d'incendie**, pas seulement "
                        "d'électrocution — toujours vérifier le courant maximum supporté (souvent indiqué "
                        "sur le module, ex: 10A/250VAC) avant de brancher un appareil.\n\n"
                        "Ce n'est pas de la paranoïa — c'est exactement la discipline qu'applique n'importe "
                        "quel électricien professionnel, même pour une simple ampoule. La prudence n'est pas "
                        "l'ennemie de l'apprentissage pratique ; elle est ce qui permet de continuer à "
                        "pratiquer longtemps."
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER}] Photo d'un module relais fermé avec ses bornes à vis côté 220V bien identifiées (NO/NC/COM) et son côté logique 3.3V/5V séparé, avec légendes."},
                ],
                "quiz": [
                    {
                        "question": "À partir de quel ordre de grandeur de courant traversant le cœur le risque de fibrillation cardiaque devient-il significatif ?",
                        "a": "Environ 30 mA",
                        "b": "Environ 30 A",
                        "c": "Environ 300 V",
                        "d": "Aucun risque n'existe en dessous de 1000V",
                        "bonne": "A",
                        "explication": "Un courant de l'ordre de 30 milliampères traversant le cœur peut suffire à provoquer une fibrillation.",
                    },
                    {
                        "question": "Quel est le rôle de sécurité principal d'un relais dans un montage domotique ?",
                        "a": "Il accélère le microcontrôleur",
                        "b": "Il assure une isolation galvanique entre le circuit basse tension et le circuit haute tension",
                        "c": "Il remplace le Wi-Fi",
                        "d": "Il n'a aucun rôle de sécurité",
                        "bonne": "B",
                        "explication": "L'isolation galvanique du relais sépare électriquement le côté commande (sûr) du côté puissance (dangereux).",
                    },
                    {
                        "question": "Quelles sont des règles de sécurité correctes pour manipuler un relais piloté du 220V ? (plusieurs réponses possibles)",
                        "a": "Toujours débrancher l'appareil avant de câbler",
                        "b": "Utiliser une breadboard classique pour la partie 220V",
                        "c": "Ne jamais laisser de fils dénudés à l'air libre côté secteur",
                        "d": "Vérifier le courant maximum supporté par le relais avant de brancher un appareil",
                        "bonne": "A,C,D",
                        "plusieurs": True,
                        "explication": "La breadboard n'est jamais adaptée à la haute tension — toutes les autres règles sont correctes et indispensables.",
                    },
                    {
                        "question": "Pourquoi ce cours utilise-t-il volontairement du 12V ou moins pour les exercices pratiques ?",
                        "a": "Pour économiser de l'argent uniquement",
                        "b": "Parce que la basse tension permet d'apprendre le même principe sans le danger du secteur",
                        "c": "Parce que l'ESP32 ne peut pas piloter de relais 220V",
                        "d": "Ce n'est pas volontaire, c'est une contrainte technique",
                        "bonne": "B",
                        "explication": "Le choix pédagogique est délibéré : même logique de contrôle, sans le risque réel du 220V pendant l'apprentissage.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 3,
                "titre": "Le cerveau côté domotique : l'ESP32 comme centre de décision",
                "resume": "Comment l'ESP32 passe du rôle de 'lecteur de capteurs' à celui de 'centre de décision' qui déclenche des actions.",
                "duree_minutes": 20,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Si tu as déjà suivi le parcours Électronique embarquée, tu connais déjà l'ESP32 "
                        "comme lecteur de capteurs. En domotique, son rôle s'élargit : il devient un vrai "
                        "**centre de décision**. Il ne se contente plus de lire une valeur et de l'envoyer — "
                        "il compare cette valeur à des règles, et déclenche des actions en conséquence.\n\n"
                        "C'est la structure logique que tu vas retrouver dans presque tout le code de ce "
                        "parcours :\n\n"
                        "```\n"
                        "LIRE l'état du capteur\n"
                        "SI condition remplie ALORS\n"
                        "    DECLENCHER l'action (relais, écran, notification...)\n"
                        "SINON\n"
                        "    Ne rien faire, ou revenir à l'état par défaut\n"
                        "```\n\n"
                        "Cette structure s'appelle une **machine à états simple** — le système est toujours "
                        "dans un état (par exemple 'lumière éteinte'), et ne change d'état que lorsqu'une "
                        "condition précise est remplie (par exemple 'présence détectée ET il fait sombre'). "
                        "C'est un concept que tu vas retrouver dans absolument tous les objets connectés du "
                        "monde réel, de ton frigo intelligent au feu de circulation automatique."
                    )},
                    {"type": "texte", "contenu": (
                        "**Pourquoi le Wi-Fi reste indispensable, même pour une décision \"locale\" ?** "
                        "Techniquement, l'ESP32 peut décider d'allumer une lumière tout seul, sans jamais "
                        "parler à Internet — c'est ce qu'on appelle une décision **locale** ou **edge** "
                        "(en périphérie du réseau). Mais une vraie maison connectée a aussi besoin de "
                        "décisions **distantes** : que tu puisses, depuis ton téléphone à l'autre bout de la "
                        "ville, voir que la lumière du salon est allumée et l'éteindre toi-même.\n\n"
                        "Un bon système domotique combine toujours les deux : des règles locales rapides qui "
                        "fonctionnent même sans réseau (sécurité et réactivité), et une couche distante "
                        "pour la supervision et le contrôle manuel à distance (confort et flexibilité). "
                        "C'est exactement l'architecture qu'utilise Founatek pour ses relais connectés : "
                        "chaque appareil garde sa logique locale, mais peut aussi recevoir des ordres et "
                        "remonter son état via l'API de la plateforme."
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER}] Schéma simple (dessiné ou capture) illustrant la boucle 'lire capteur -> comparer à une règle -> déclencher une action', avec une flèche vers 'et aussi remonter l'état vers l'app'."},
                    {"type": "code", "language": "cpp", "code": (
                        "// Structure de base d'une decision domotique : lire, comparer, agir\n\n"
                        "#define CAPTEUR_PIN 34   // Exemple : capteur quelconque en entree\n"
                        "#define ACTION_PIN 26    // Exemple : sortie pilotant une action (LED/relais)\n\n"
                        "void setup() {\n"
                        "  Serial.begin(115200);\n"
                        "  pinMode(CAPTEUR_PIN, INPUT);\n"
                        "  pinMode(ACTION_PIN, OUTPUT);\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  int valeurCapteur = digitalRead(CAPTEUR_PIN);\n\n"
                        "  // LIRE -> COMPARER -> AGIR\n"
                        "  if (valeurCapteur == HIGH) {\n"
                        "    digitalWrite(ACTION_PIN, HIGH);\n"
                        "    Serial.println(\"Condition remplie -> action declenchee\");\n"
                        "  } else {\n"
                        "    digitalWrite(ACTION_PIN, LOW);\n"
                        "  }\n\n"
                        "  delay(200);\n"
                        "}\n"
                    )},
                ],
                "quiz": [
                    {
                        "question": "En domotique, quel rôle supplémentaire prend l'ESP32 par rapport à une simple station de mesure ?",
                        "a": "Celui de centre de décision qui déclenche des actions",
                        "b": "Aucun rôle supplémentaire",
                        "c": "Il devient uniquement un écran",
                        "d": "Il remplace le capteur",
                        "bonne": "A",
                        "explication": "L'ESP32 compare les mesures à des règles et déclenche des actions — il décide, il ne fait plus qu'observer.",
                    },
                    {
                        "question": "Qu'est-ce qu'une décision 'locale' (edge) en domotique ?",
                        "a": "Une décision prise uniquement par un serveur distant",
                        "b": "Une décision prise directement par l'appareil, sans dépendre du réseau",
                        "c": "Une décision impossible techniquement",
                        "d": "Une décision qui nécessite toujours le Wi-Fi",
                        "bonne": "B",
                        "explication": "Une décision locale/edge est prise par l'appareil lui-même, ce qui la rend rapide et fiable même sans connexion.",
                    },
                    {
                        "question": "Pourquoi combiner décisions locales ET décisions distantes dans un bon système domotique ? (plusieurs réponses possibles)",
                        "a": "Les décisions locales restent fiables même sans réseau",
                        "b": "Les décisions distantes permettent la supervision et le contrôle depuis l'app",
                        "c": "Ça n'a aucun intérêt, une seule des deux suffit toujours",
                        "d": "Ça correspond à l'architecture réellement utilisée par Founatek pour ses relais",
                        "bonne": "A,B,D",
                        "plusieurs": True,
                        "explication": "Combiner les deux apporte fiabilité (local) et confort/flexibilité (distant) — c'est le modèle utilisé en pratique.",
                    },
                    {
                        "question": "Dans le code d'exemple, quelle est la séquence logique appliquée à chaque tour de boucle ?",
                        "a": "Agir, puis lire, puis comparer",
                        "b": "Lire le capteur, comparer à une condition, déclencher l'action",
                        "c": "Seulement lire, sans jamais agir",
                        "d": "Seulement agir, sans jamais lire",
                        "bonne": "B",
                        "explication": "C'est la structure de base : lire -> comparer -> agir, répétée en continu dans loop().",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 4,
                "titre": "Le module relais : piloter une charge en toute sécurité",
                "resume": "Câbler et piloter un module relais opto-isolé pour contrôler un appareil basse tension.",
                "duree_minutes": 30,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Après la théorie de sécurité de la leçon 2, place à la pratique — en restant en "
                        "basse tension. Le **module relais** que tu vas utiliser contient en réalité deux "
                        "circuits distincts sur une même petite carte :\n\n"
                        "1. Un circuit de commande basse tension (3.3V/5V), qui reçoit un signal du GPIO de "
                        "l'ESP32\n"
                        "2. Un interrupteur mécanique réel (l'élément qui \"clique\" quand tu actionnes le "
                        "relais), relié à trois bornes : **COM** (commun), **NO** (normalement ouvert), et "
                        "**NC** (normalement fermé)\n\n"
                        "Quand le relais est au repos, COM est relié à NC (circuit fermé) et déconnecté de "
                        "NO (circuit ouvert). Quand l'ESP32 active le relais, l'inverse se produit : COM se "
                        "connecte à NO, et se déconnecte de NC. C'est ce mécanisme simple — un aimant qui "
                        "attire ou relâche un petit levier métallique — qui permet à un signal électrique "
                        "minuscule (quelques milliampères) de contrôler un courant potentiellement bien plus "
                        "important.\n\n"
                        "**Beaucoup de modules relais bon marché s'activent en logique inversée** : "
                        "envoyer LOW (0V) active le relais, et HIGH (3.3V/5V) le désactive — l'inverse de ce "
                        "qu'on attendrait intuitivement. Vérifie toujours la documentation de ton module "
                        "précis avant de câbler quoi que ce soit — c'est l'erreur numéro un des débutants sur "
                        "ce composant."
                    )},
                    {"type": "texte", "contenu": (
                        "**Câblage pour ce parcours (charge basse tension simulée)** :\n"
                        "- Module relais VCC → 5V de l'ESP32 (broche VIN)\n"
                        "- Module relais GND → GND\n"
                        "- Module relais IN (signal) → GPIO 26 de l'ESP32\n"
                        "- Côté charge : borne COM → une extrémité de ta LED/appareil basse tension, borne "
                        "NO → alimentation 5V ou 12V (selon la charge), l'autre extrémité de la charge → GND\n\n"
                        "**Une bonne pratique pour ce projet** : toujours démarrer le relais en position "
                        "\"sécurisée\" (généralement désactivé) dans `setup()`, avant même de lire quoi que ce "
                        "soit d'autre. Ça évite qu'un redémarrage inattendu de l'ESP32 (coupure de courant, "
                        "bug, mise à jour) ne laisse un appareil allumé sans contrôle."
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER}] Photo du module relais câblé à l'ESP32 (VCC/GND/IN) avec les bornes COM/NO/NC bien visibles et une charge basse tension connectée côté NO."},
                    {"type": "code", "language": "cpp", "code": (
                        "// Pilotage d'un relais (attention : verifier la logique de ton module, HIGH ou LOW actif)\n\n"
                        "#define RELAIS_PIN 26\n"
                        "#define RELAIS_ACTIF LOW   // Change en HIGH si ton module n'est pas a logique inversee\n"
                        "#define RELAIS_INACTIF HIGH\n\n"
                        "void setup() {\n"
                        "  Serial.begin(115200);\n"
                        "  pinMode(RELAIS_PIN, OUTPUT);\n"
                        "  digitalWrite(RELAIS_PIN, RELAIS_INACTIF);  // Etat de depart securise\n"
                        "  Serial.println(\"Relais initialise en position OFF.\");\n"
                        "}\n\n"
                        "void allumer() {\n"
                        "  digitalWrite(RELAIS_PIN, RELAIS_ACTIF);\n"
                        "  Serial.println(\"Relais ON\");\n"
                        "}\n\n"
                        "void eteindre() {\n"
                        "  digitalWrite(RELAIS_PIN, RELAIS_INACTIF);\n"
                        "  Serial.println(\"Relais OFF\");\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  allumer();\n"
                        "  delay(3000);\n"
                        "  eteindre();\n"
                        "  delay(3000);\n"
                        "}\n"
                    )},
                ],
                "quiz": [
                    {
                        "question": "Que représentent les bornes COM, NO et NC d'un module relais ?",
                        "a": "Commun, Normalement Ouvert, Normalement Fermé",
                        "b": "Courant, Norme, Circuit",
                        "c": "Ce sont des broches de programmation",
                        "d": "Elles n'ont pas de signification particulière",
                        "bonne": "A",
                        "explication": "COM = commun, NO = normalement ouvert, NC = normalement fermé — les trois bornes de l'interrupteur du relais.",
                    },
                    {
                        "question": "Qu'est-ce que la 'logique inversée' fréquente sur les modules relais bon marché ?",
                        "a": "LOW active le relais, HIGH le désactive",
                        "b": "Le relais ne fonctionne jamais",
                        "c": "Il faut deux ESP32 pour le piloter",
                        "d": "Le relais s'active tout seul sans signal",
                        "bonne": "A",
                        "explication": "De nombreux modules s'activent quand le signal est à LOW (0V) plutôt qu'à HIGH — il faut vérifier la doc du module précis.",
                    },
                    {
                        "question": "Pourquoi initialiser le relais en position 'inactive' dès le début de setup() ?",
                        "a": "Pour économiser du code",
                        "b": "Pour éviter qu'un redémarrage inattendu ne laisse un appareil allumé sans contrôle",
                        "c": "Ce n'est pas nécessaire",
                        "d": "Pour accélérer le démarrage du Wi-Fi",
                        "bonne": "B",
                        "explication": "Démarrer dans un état sûr évite les surprises après un reboot imprévu de la carte.",
                    },
                    {
                        "question": "Quelles affirmations sur le fonctionnement mécanique d'un relais sont vraies ? (plusieurs réponses possibles)",
                        "a": "Il contient un aimant qui attire ou relâche un levier métallique",
                        "b": "Il permet à un petit courant de commande de contrôler un courant plus important",
                        "c": "Il transforme le courant continu en courant alternatif",
                        "d": "Au repos, COM est généralement relié à NC",
                        "bonne": "A,B,D",
                        "plusieurs": True,
                        "explication": "Le relais est un interrupteur électromécanique isolé — il ne transforme pas le type de courant, il commute simplement un circuit.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 5,
                "titre": "Le capteur de mouvement PIR : détecter une présence",
                "resume": "Comprendre et câbler un capteur infrarouge passif pour détecter automatiquement une présence humaine.",
                "duree_minutes": 25,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Le capteur **PIR** (Passive InfraRed — infrarouge passif) est le composant qui rend "
                        "possible l'un des cas d'usage les plus emblématiques de la domotique : la lumière "
                        "qui s'allume toute seule quand on entre dans une pièce.\n\n"
                        "**Comment ça marche, sans magie ?** Tout corps chaud (dont le corps humain, autour "
                        "de 37°C) émet naturellement un rayonnement infrarouge invisible à l'œil nu. Le "
                        "capteur PIR contient une petite lentille (souvent visible, en forme de dôme "
                        "segmenté) qui divise son champ de vision en plusieurs zones. Quand un corps chaud "
                        "se déplace d'une zone à l'autre, le capteur détecte une **variation** du "
                        "rayonnement infrarouge reçu — pas la présence en elle-même, mais le CHANGEMENT. "
                        "C'est pour ça qu'un PIR détecte très bien un humain qui marche, mais peut manquer "
                        "quelqu'un resté parfaitement immobile pendant plusieurs minutes.\n\n"
                        "Le mot \"passif\" dans son nom est important : contrairement à un radar ou un "
                        "sonar, le PIR n'émet rien lui-même — il se contente d'observer les infrarouges déjà "
                        "présents dans son environnement. C'est ce qui le rend extrêmement économe en "
                        "énergie, parfait pour un système qui doit surveiller en continu."
                    )},
                    {"type": "texte", "contenu": (
                        "**Les deux réglages physiques du module HC-SR501** (les deux petits potentiomètres "
                        "sur la carte) :\n"
                        "- **Sensibilité** : jusqu'à quelle distance le capteur détecte un mouvement "
                        "(généralement réglable de ~3m à ~7m)\n"
                        "- **Délai** (time delay) : combien de temps la sortie reste à HIGH après une "
                        "détection, avant de redescendre à LOW — utile pour éviter que la lumière ne "
                        "clignote sans arrêt pendant qu'une personne bouge dans la pièce\n\n"
                        "**Câblage** (3 fils, très simple) :\n"
                        "- VCC → 5V de l'ESP32\n"
                        "- GND → GND\n"
                        "- OUT (signal numérique) → GPIO 27\n\n"
                        "**Un piège classique pour les débutants** : le PIR a besoin d'un court temps de "
                        "stabilisation après sa mise sous tension (souvent 30 à 60 secondes) pendant lequel "
                        "il peut donner des lectures erratiques, le temps que le capteur infrarouge "
                        "s'équilibre avec la température ambiante. Si tes premiers tests semblent "
                        "\"détecter n'importe quoi\", attends simplement une minute avant de recommencer."
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER}] Photo du module PIR HC-SR501 câblé (VCC/GND/OUT) avec les deux potentiomètres de réglage (sensibilité, délai) annotés."},
                    {"type": "video", "contenu": f"[{MEDIA_PLACEHOLDER}] Courte vidéo (20-30s) montrant une main qui passe devant le PIR et déclenche l'allumage de la LED témoin sur le moniteur série."},
                    {"type": "code", "language": "cpp", "code": (
                        "// Detection de presence avec un capteur PIR HC-SR501\n\n"
                        "#define PIR_PIN 27\n\n"
                        "void setup() {\n"
                        "  Serial.begin(115200);\n"
                        "  pinMode(PIR_PIN, INPUT);\n"
                        "  Serial.println(\"Stabilisation du capteur PIR (attendre ~30-60s)...\");\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  int mouvement = digitalRead(PIR_PIN);\n\n"
                        "  if (mouvement == HIGH) {\n"
                        "    Serial.println(\"Presence detectee !\");\n"
                        "  } else {\n"
                        "    Serial.println(\"Aucun mouvement.\");\n"
                        "  }\n\n"
                        "  delay(500);\n"
                        "}\n"
                    )},
                ],
                "quiz": [
                    {
                        "question": "Que signifie le 'P' de PIR (capteur infrarouge passif) ?",
                        "a": "Puissant",
                        "b": "Passif — il n'émet rien, il observe seulement le rayonnement déjà présent",
                        "c": "Programmable",
                        "d": "Périodique",
                        "bonne": "B",
                        "explication": "Contrairement à un radar actif, le PIR ne fait qu'observer l'infrarouge ambiant, sans rien émettre.",
                    },
                    {
                        "question": "Qu'est-ce que le PIR détecte réellement ?",
                        "a": "La chaleur absolue d'un corps",
                        "b": "Une variation du rayonnement infrarouge quand un corps chaud se déplace",
                        "c": "Le son",
                        "d": "La lumière visible",
                        "bonne": "B",
                        "explication": "Le PIR détecte le changement de rayonnement infrarouge lié au mouvement, pas la simple présence statique.",
                    },
                    {
                        "question": "Quels réglages physiques trouve-t-on généralement sur un module PIR HC-SR501 ? (plusieurs réponses possibles)",
                        "a": "La sensibilité (distance de détection)",
                        "b": "Le délai avant que la sortie ne redescende à LOW",
                        "c": "Le volume sonore",
                        "d": "La couleur de la LED",
                        "bonne": "A,B",
                        "plusieurs": True,
                        "explication": "Deux potentiomètres réglables : sensibilité (portée) et délai (durée du signal HIGH après détection).",
                    },
                    {
                        "question": "Pourquoi les premières lectures d'un PIR juste après sa mise sous tension peuvent-elles sembler erratiques ?",
                        "a": "Le capteur est cassé",
                        "b": "Il a besoin d'un court temps de stabilisation thermique",
                        "c": "Il faut le reprogrammer",
                        "d": "C'est normal et ça ne change jamais",
                        "bonne": "B",
                        "explication": "Un temps de stabilisation (souvent 30 à 60s) est nécessaire pour que le capteur s'équilibre avec la température ambiante.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 6,
                "titre": "DHT22 pour la domotique : chauffage et climatisation automatiques",
                "resume": "Réutiliser le capteur DHT22 non plus pour mesurer, mais pour déclencher des actions de régulation.",
                "duree_minutes": 20,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Tu connais peut-être déjà le DHT22 comme simple capteur de mesure (parcours "
                        "Électronique embarquée). Ici, on lui donne un rôle différent : celui de "
                        "**déclencheur de régulation**. La différence n'est pas dans le câblage — c'est "
                        "exactement le même — mais dans ce que le code fait de la mesure.\n\n"
                        "C'est un excellent exemple de ce qu'on appelle en génie logiciel la "
                        "**réutilisation** : le même composant, le même code de lecture, mais une logique "
                        "de décision complètement différente greffée par-dessus. C'est aussi pour ça que la "
                        "méthode de ce cours (isoler chaque composant, bien le comprendre) paie sur le long "
                        "terme — un composant bien maîtrisé se réutilise dans des dizaines de projets "
                        "différents.\n\n"
                        "**La règle de régulation qu'on va implémenter** : si la température dépasse un "
                        "seuil (par exemple 28°C), on active une sortie qui, dans un vrai système, piloterait "
                        "un ventilateur ou une climatisation via un relais — exactement celui de la leçon 4. "
                        "Si la température redescend sous un second seuil légèrement inférieur (par exemple "
                        "26°C), on désactive cette sortie."
                    )},
                    {"type": "texte", "contenu": (
                        "**Pourquoi deux seuils différents plutôt qu'un seul (28°C pour allumer, 26°C pour "
                        "éteindre, pas 28°C pour les deux) ?** C'est un concept fondamental en automatisation "
                        "appelé **hystérésis**. Si on utilisait un seul seuil à 28°C, dès que la température "
                        "oscillerait naturellement autour de cette valeur (27.9°C, 28.1°C, 27.8°C...), le "
                        "ventilateur s'allumerait et s'éteindrait en permanence — un comportement qu'on "
                        "appelle le \"battement\" (chattering), qui use prématurément le relais et rend le "
                        "système bruyant et instable.\n\n"
                        "En introduisant un écart entre le seuil d'activation et le seuil de désactivation, "
                        "le système devient stable : une fois allumé, il reste allumé jusqu'à ce que la "
                        "température baisse clairement, pas juste d'un dixième de degré. Tu vas retrouver ce "
                        "principe d'hystérésis dans absolument tous les vrais thermostats du marché — ce "
                        "n'est pas une astuce de débutant, c'est une pratique d'ingénierie standard."
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER}] Graphique ou schéma simple montrant la courbe de température avec les deux seuils (allumage/extinction) et les zones où le ventilateur est ON/OFF."},
                    {"type": "code", "language": "cpp", "code": (
                        "// Regulation de temperature avec hysteresis (evite le battement du relais)\n\n"
                        "#include <DHT.h>\n\n"
                        "#define DHTPIN 15\n"
                        "#define DHTTYPE DHT22\n"
                        "#define VENTILATEUR_PIN 25\n\n"
                        "const float SEUIL_ALLUMAGE = 28.0;   // Active le ventilateur au-dessus\n"
                        "const float SEUIL_EXTINCTION = 26.0; // Desactive le ventilateur en dessous\n\n"
                        "DHT dht(DHTPIN, DHTTYPE);\n"
                        "bool ventilateurActif = false;\n\n"
                        "void setup() {\n"
                        "  Serial.begin(115200);\n"
                        "  dht.begin();\n"
                        "  pinMode(VENTILATEUR_PIN, OUTPUT);\n"
                        "  digitalWrite(VENTILATEUR_PIN, LOW);\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  float temperature = dht.readTemperature();\n\n"
                        "  if (!isnan(temperature)) {\n"
                        "    if (!ventilateurActif && temperature >= SEUIL_ALLUMAGE) {\n"
                        "      ventilateurActif = true;\n"
                        "      digitalWrite(VENTILATEUR_PIN, HIGH);\n"
                        "      Serial.println(\"Temperature elevee -> ventilateur ON\");\n"
                        "    } else if (ventilateurActif && temperature <= SEUIL_EXTINCTION) {\n"
                        "      ventilateurActif = false;\n"
                        "      digitalWrite(VENTILATEUR_PIN, LOW);\n"
                        "      Serial.println(\"Temperature normale -> ventilateur OFF\");\n"
                        "    }\n"
                        "  }\n\n"
                        "  delay(2000);\n"
                        "}\n"
                    )},
                ],
                "quiz": [
                    {
                        "question": "Qu'est-ce que l'hystérésis, dans le contexte d'une régulation de température ?",
                        "a": "Un défaut du capteur DHT22",
                        "b": "L'utilisation de deux seuils différents (allumage/extinction) pour éviter les oscillations rapides",
                        "c": "Un protocole de communication Wi-Fi",
                        "d": "Un type de relais spécial",
                        "bonne": "B",
                        "explication": "L'hystérésis introduit un écart entre seuil d'activation et de désactivation pour stabiliser le système.",
                    },
                    {
                        "question": "Que se passerait-il si on utilisait un seul seuil unique (ex: 28°C) pour allumer ET éteindre le ventilateur ?",
                        "a": "Rien de particulier",
                        "b": "Un risque de 'battement' : le relais s'allume/s'éteint en permanence autour du seuil",
                        "c": "Le ventilateur ne s'allumerait jamais",
                        "d": "Le capteur DHT22 serait endommagé",
                        "bonne": "B",
                        "explication": "Sans écart entre les seuils, de petites oscillations naturelles de température font battre le relais en continu.",
                    },
                    {
                        "question": "Dans cette leçon, qu'est-ce qui change par rapport à l'usage du DHT22 dans le parcours Électronique embarquée ? (plusieurs réponses possibles)",
                        "a": "Le câblage physique du capteur",
                        "b": "La logique de décision appliquée à la mesure",
                        "c": "Le fait que la mesure déclenche maintenant une action (relais)",
                        "d": "Le capteur lui-même change de modèle",
                        "bonne": "B,C",
                        "plusieurs": True,
                        "explication": "Le câblage et le capteur restent identiques ; ce qui change, c'est ce que le code FAIT de la mesure.",
                    },
                    {
                        "question": "Dans le code d'exemple, à quelle condition le ventilateur s'éteint-il ?",
                        "a": "Dès que la température descend sous le seuil d'allumage",
                        "b": "Uniquement quand la température descend sous le seuil d'extinction, ET que le ventilateur était actif",
                        "c": "Jamais automatiquement",
                        "d": "Toutes les 2 secondes, peu importe la température",
                        "bonne": "B",
                        "explication": "La condition vérifie ventilateurActif ET temperature <= SEUIL_EXTINCTION, exactement le principe d'hystérésis.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 7,
                "titre": "Écran LCD I2C : le tableau de bord physique de la maison",
                "resume": "Câbler et afficher l'état du système domotique sur un écran LCD 16x2 via I2C.",
                "duree_minutes": 25,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Un système domotique qui prend des décisions dans l'ombre, sans jamais rien "
                        "montrer, inspire rarement confiance. Imagine rentrer chez toi et ne pas savoir si "
                        "le système de sécurité est actif, si le chauffage a bien démarré, ou si le PIR "
                        "fonctionne encore. Un petit écran physique, directement sur le boîtier, résout ce "
                        "problème simplement : l'état du système est visible d'un coup d'œil, sans même "
                        "sortir son téléphone.\n\n"
                        "L'**écran LCD 16x2** (16 caractères sur 2 lignes) est un classique increvable de "
                        "l'électronique amateur — peu de résolution comparé à l'écran OLED déjà vu dans "
                        "l'autre parcours, mais extrêmement lisible même en plein soleil, robuste, et très "
                        "peu gourmand en broches grâce au **module I2C** qui l'accompagne : sans lui, un LCD "
                        "16x2 nécessiterait 6 à 11 fils pour fonctionner ; avec le module I2C soudé dessus, "
                        "il ne demande plus que 4 fils (VCC, GND, SDA, SCL) — exactement le même protocole "
                        "I2C que l'écran OLED du premier parcours.\n\n"
                        "**Un détail pratique important** : le module I2C intègre presque toujours un petit "
                        "potentiomètre de réglage du contraste. Si ton écran affiche des rectangles pleins "
                        "ou reste totalement blanc malgré un câblage correct, c'est presque toujours ce "
                        "réglage qu'il faut ajuster avec un petit tournevis, pas un problème de code."
                    )},
                    {"type": "texte", "contenu": (
                        "**Câblage** (identique en principe à l'écran OLED, même protocole I2C) :\n"
                        "- VCC → 5V (contrairement à l'OLED qui tourne souvent en 3.3V, le LCD I2C préfère "
                        "généralement le 5V — vérifie la doc de ton module précis)\n"
                        "- GND → GND\n"
                        "- SDA → GPIO 21\n"
                        "- SCL → GPIO 22\n\n"
                        "**Adressage I2C** : la plupart des modules LCD I2C utilisent l'adresse `0x27`, "
                        "mais certains utilisent `0x3F`. Si l'écran reste muet, un petit programme "
                        "\"scanner I2C\" (qui teste toutes les adresses possibles et affiche celles qui "
                        "répondent) résout ce problème en quelques secondes — c'est le premier réflexe à "
                        "avoir avant de suspecter un câblage défectueux."
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER}] Photo de l'écran LCD 16x2 avec son module I2C soudé dessus, câblage 4 fils vers l'ESP32, affichant un texte de test type 'Maison OK'."},
                    {"type": "code", "language": "cpp", "code": (
                        "// Affichage de l'etat du systeme sur ecran LCD 16x2 en I2C\n"
                        "// Necessite les bibliotheques \"LiquidCrystal I2C\" (ex: par Frank de Brabander)\n\n"
                        "#include <Wire.h>\n"
                        "#include <LiquidCrystal_I2C.h>\n\n"
                        "LiquidCrystal_I2C lcd(0x27, 16, 2);  // Adresse 0x27, 16 colonnes, 2 lignes\n\n"
                        "void setup() {\n"
                        "  Wire.begin();\n"
                        "  lcd.init();\n"
                        "  lcd.backlight();\n"
                        "  lcd.setCursor(0, 0);\n"
                        "  lcd.print(\"Maison connectee\");\n"
                        "  lcd.setCursor(0, 1);\n"
                        "  lcd.print(\"Init...\");\n"
                        "  delay(1500);\n"
                        "}\n\n"
                        "void afficherEtat(bool presence, float temperature, bool lumiereOn) {\n"
                        "  lcd.clear();\n"
                        "  lcd.setCursor(0, 0);\n"
                        "  lcd.print(presence ? \"Presence: OUI\" : \"Presence: NON\");\n"
                        "  lcd.setCursor(0, 1);\n"
                        "  lcd.print(\"T:\");\n"
                        "  lcd.print(temperature, 1);\n"
                        "  lcd.print(\"C Lum:\");\n"
                        "  lcd.print(lumiereOn ? \"ON\" : \"OFF\");\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  afficherEtat(true, 27.5, true);  // Valeurs d'exemple\n"
                        "  delay(2000);\n"
                        "}\n"
                    )},
                ],
                "quiz": [
                    {
                        "question": "Combien de fils sont nécessaires pour piloter un écran LCD 16x2 grâce à son module I2C ?",
                        "a": "1",
                        "b": "4 (VCC, GND, SDA, SCL)",
                        "c": "11",
                        "d": "16",
                        "bonne": "B",
                        "explication": "Le module I2C réduit un câblage qui demanderait normalement 6 à 11 fils à seulement 4 fils.",
                    },
                    {
                        "question": "Que faut-il vérifier en premier si l'écran LCD affiche des rectangles pleins ou reste blanc malgré un câblage correct ?",
                        "a": "Le potentiomètre de réglage du contraste sur le module I2C",
                        "b": "Le processeur de l'ESP32",
                        "c": "La météo",
                        "d": "Rien, c'est un défaut irréparable",
                        "bonne": "A",
                        "explication": "C'est presque toujours un problème de réglage du contraste, ajustable via le petit potentiomètre du module I2C.",
                    },
                    {
                        "question": "Quelles adresses I2C sont couramment utilisées par les modules LCD I2C ? (plusieurs réponses possibles)",
                        "a": "0x27",
                        "b": "0x3F",
                        "c": "0xFF",
                        "d": "0x00",
                        "bonne": "A,B",
                        "plusieurs": True,
                        "explication": "0x27 et 0x3F sont les deux adresses les plus fréquentes selon le fabricant du module I2C.",
                    },
                    {
                        "question": "Pourquoi ajouter un écran physique à un système domotique qui a déjà une app mobile ?",
                        "a": "Ce n'est jamais utile",
                        "b": "Pour donner une visibilité immédiate de l'état du système sans dépendre du téléphone",
                        "c": "Pour remplacer complètement l'app",
                        "d": "Uniquement pour la décoration",
                        "bonne": "B",
                        "explication": "Un écran local offre une confiance et une visibilité immédiates, complémentaires au contrôle à distance.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 8,
                "titre": "Le bouton poussoir : garder la main, toujours",
                "resume": "Ajouter un contrôle manuel de secours, prioritaire sur l'automatisation, avec gestion des rebonds.",
                "duree_minutes": 25,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "On revient ici sur la \"règle d'or\" annoncée dans la toute première leçon : un "
                        "système automatique doit toujours garder un moyen de reprendre la main manuellement. "
                        "Le composant le plus simple qui existe pour ça — un **bouton poussoir** — est aussi "
                        "l'un des plus mal compris par les débutants, à cause d'un phénomène physique appelé "
                        "le **rebond** (bounce).\n\n"
                        "**Le rebond, qu'est-ce que c'est concrètement ?** Quand tu appuies sur un bouton "
                        "mécanique, le contact métallique à l'intérieur ne se ferme pas instantanément et "
                        "proprement — il \"rebondit\" plusieurs fois en quelques millisecondes avant de se "
                        "stabiliser, un peu comme une balle qui rebondit avant de s'immobiliser. Résultat : "
                        "un microcontrôleur qui lit l'état du bouton des milliers de fois par seconde peut "
                        "détecter 3, 5, ou 10 appuis pour un seul vrai appui humain — ce qui, dans un système "
                        "qui \"bascule\" un état (allumé devient éteint, éteint devient allumé) à chaque "
                        "appui, produit un comportement complètement imprévisible.\n\n"
                        "La solution s'appelle le **débounce** (anti-rebond) : ignorer les changements d'état "
                        "trop rapprochés dans le temps, en ne considérant un appui comme \"réel\" que s'il "
                        "reste stable pendant quelques millisecondes."
                    )},
                    {"type": "texte", "contenu": (
                        "**Câblage avec résistance de pull-down** :\n"
                        "- Une patte du bouton → 3.3V\n"
                        "- L'autre patte du bouton → GPIO 32 ET → une résistance de 10kΩ → GND\n\n"
                        "Cette résistance de \"pull-down\" garantit que le GPIO lit un état LOW clair et "
                        "stable quand le bouton n'est pas pressé (sans elle, l'entrée \"flotterait\" et "
                        "donnerait des lectures aléatoires) et bascule à HIGH uniquement pendant l'appui "
                        "réel.\n\n"
                        "**Le principe de priorité qu'on implémente dans ce projet** : quand le bouton est "
                        "pressé, il force un changement d'état de la lumière IMMÉDIATEMENT, et ce changement "
                        "\"manuel\" reste actif un certain temps avant que l'automatisation (PIR, "
                        "température...) ne reprenne la main. C'est exactement le comportement qu'on attend "
                        "d'un interrupteur physique dans une vraie maison : s'il existe, c'est qu'il doit "
                        "toujours avoir le dernier mot, au moins temporairement."
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER}] Photo du bouton poussoir câblé avec sa résistance de pull-down 10k, montage complet sur breadboard."},
                    {"type": "code", "language": "cpp", "code": (
                        "// Bouton poussoir avec anti-rebond (debounce) et priorite manuelle\n\n"
                        "#define BOUTON_PIN 32\n"
                        "#define LUMIERE_PIN 26\n\n"
                        "bool lumiereEtat = false;\n"
                        "bool dernierLectureBouton = LOW;\n"
                        "bool boutonStable = LOW;\n"
                        "unsigned long dernierChangement = 0;\n"
                        "const unsigned long DELAI_DEBOUNCE = 50; // millisecondes\n\n"
                        "void setup() {\n"
                        "  Serial.begin(115200);\n"
                        "  pinMode(BOUTON_PIN, INPUT);\n"
                        "  pinMode(LUMIERE_PIN, OUTPUT);\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  bool lectureBrute = digitalRead(BOUTON_PIN);\n\n"
                        "  if (lectureBrute != dernierLectureBouton) {\n"
                        "    dernierChangement = millis(); // Reinitialise le chrono a chaque changement brut\n"
                        "  }\n\n"
                        "  // On ne valide le changement que si l'etat est reste stable assez longtemps\n"
                        "  if ((millis() - dernierChangement) > DELAI_DEBOUNCE) {\n"
                        "    if (lectureBrute != boutonStable) {\n"
                        "      boutonStable = lectureBrute;\n"
                        "      if (boutonStable == HIGH) {\n"
                        "        lumiereEtat = !lumiereEtat; // Bascule l'etat sur un vrai appui valide\n"
                        "        digitalWrite(LUMIERE_PIN, lumiereEtat);\n"
                        "        Serial.println(lumiereEtat ? \"Lumiere ON (manuel)\" : \"Lumiere OFF (manuel)\");\n"
                        "      }\n"
                        "    }\n"
                        "  }\n\n"
                        "  dernierLectureBouton = lectureBrute;\n"
                        "}\n"
                    )},
                ],
                "quiz": [
                    {
                        "question": "Qu'est-ce que le phénomène de 'rebond' (bounce) sur un bouton poussoir ?",
                        "a": "Le bouton physique rebondit sur la table",
                        "b": "Le contact métallique interne fluctue plusieurs fois avant de se stabiliser lors d'un appui",
                        "c": "Un bug logiciel uniquement",
                        "d": "Un phénomène qui n'existe que sur les boutons tactiles",
                        "bonne": "B",
                        "explication": "Le rebond est mécanique : le contact interne oscille brièvement avant de se stabiliser, produisant plusieurs signaux pour un seul appui.",
                    },
                    {
                        "question": "À quoi sert une résistance de pull-down sur un bouton poussoir ?",
                        "a": "À accélérer le microcontrôleur",
                        "b": "À garantir un état LOW stable quand le bouton n'est pas pressé, évitant une entrée flottante",
                        "c": "À alimenter la lumière directement",
                        "d": "Elle n'a aucune utilité",
                        "bonne": "B",
                        "explication": "Sans elle, le GPIO lirait un état électriquement indéterminé (flottant) quand le bouton n'est pas pressé.",
                    },
                    {
                        "question": "Dans le code d'exemple, que doit faire l'état du bouton pour être considéré comme un appui valide ?",
                        "a": "Changer instantanément, peu importe la durée",
                        "b": "Rester stable pendant au moins DELAI_DEBOUNCE millisecondes",
                        "c": "Rien, tout changement est toujours valide",
                        "d": "Être appuyé exactement 2 fois",
                        "bonne": "B",
                        "explication": "Le debounce n'accepte un changement que si l'état reste stable au-delà du délai défini, filtrant ainsi les rebonds parasites.",
                    },
                    {
                        "question": "Pourquoi le bouton manuel doit-il avoir la priorité sur l'automatisation (PIR, température) dans une bonne conception domotique ? (plusieurs réponses possibles)",
                        "a": "Parce que l'utilisateur doit toujours pouvoir reprendre le contrôle",
                        "b": "Parce que c'est le comportement attendu d'un interrupteur physique dans une vraie maison",
                        "c": "Ce n'est jamais souhaitable, l'automatisation doit toujours primer",
                        "d": "Parce que ça correspond à la 'règle d'or' énoncée dès la première leçon du parcours",
                        "bonne": "A,B,D",
                        "plusieurs": True,
                        "explication": "Le contrôle manuel prioritaire est un principe de conception central de ce parcours, cohérent avec la sécurité et l'usage réel.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 9,
                "titre": "Automatisation et connexion à l'app Founatek",
                "resume": "Combiner les règles d'automatisation et connecter le système au vrai Hub IoT Founatek pour un pilotage à distance.",
                "duree_minutes": 30,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "C'est ici que toutes les briques précédentes se combinent en une vraie règle "
                        "d'automatisation : **\"si mouvement détecté ET qu'il fait sombre, allume la "
                        "lumière automatiquement\"**. Ce type de règle conditionnelle combinant plusieurs "
                        "capteurs s'appelle une **règle composite** — et c'est exactement le type de logique "
                        "qu'utilise Founatek dans son propre module de règles automatiques (celui que tu "
                        "peux configurer depuis le Hub IoT sur le site ou l'app, pour tes vrais capteurs "
                        "connectés).\n\n"
                        "**Pourquoi combiner deux conditions plutôt qu'une seule ?** Une lumière qui "
                        "s'allume à chaque mouvement, même en plein jour, gaspille de l'énergie et devient "
                        "vite agaçante. En ajoutant une seconde condition (par exemple, une valeur de "
                        "luminosité ambiante basse, ou tout simplement une plage horaire), la règle devient "
                        "réellement utile plutôt que simplement réactive. C'est la différence entre de "
                        "l'automatisation basique et de l'automatisation intelligente.\n\n"
                        "Pour ce parcours, on simplifie en utilisant une variable manuelle `ilFaitSombre` "
                        "(que tu peux imaginer reliée à un capteur de luminosité LDR, non couvert dans ce "
                        "cours, ou simplement à une plage horaire calculée)."
                    )},
                    {"type": "texte", "contenu": (
                        "**Se connecter à la vraie plateforme Founatek.** Ton système domotique de "
                        "test devient réellement utile le jour où il peut remonter son état vers ton compte "
                        "Founatek — exactement comme le font les relais physiques du Hub IoT que tu utilises "
                        "peut-être déjà sur l'app mobile. Le principe technique est identique à celui vu "
                        "dans le parcours Électronique embarquée pour l'envoi de mesures : une connexion "
                        "Wi-Fi, puis une requête HTTP vers l'API de la plateforme.\n\n"
                        "**Un point important à connaître avant de te lancer** : les appareils envoient "
                        "leurs données au serveur Founatek via une clé d'API propre à ton compte (pas ton "
                        "mot de passe personnel). Retrouve cette clé dans ton profil sur le site ou l'app, "
                        "et ne la partage jamais publiquement — traite-la comme un mot de passe. Le code "
                        "ci-dessous montre le principe général ; adapte l'URL exacte et le format des "
                        "données à la documentation la plus récente de ton compte formateur, qui peut "
                        "évoluer."
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER}] Capture d'écran de l'app mobile Founatek montrant l'onglet Relais/Appareils avec l'état d'un relais réel visible en direct."},
                    {"type": "code", "language": "cpp", "code": (
                        "// Regle d'automatisation composite + remontee d'etat vers l'API Founatek\n\n"
                        "#include <WiFi.h>\n"
                        "#include <HTTPClient.h>\n\n"
                        "const char* ssid = \"NOM_DE_TON_WIFI\";\n"
                        "const char* password = \"MOT_DE_PASSE_WIFI\";\n"
                        "const char* apiKey = \"TA_CLE_API_FOUNATEK\";  // Recuperable dans ton profil\n"
                        "const char* serverUrl = \"https://founatek224.pythonanywhere.com/api/mobile/domotique/etat/\";\n\n"
                        "#define PIR_PIN 27\n"
                        "#define LUMIERE_PIN 26\n\n"
                        "bool ilFaitSombre = true; // A remplacer par un capteur LDR ou une plage horaire reelle\n"
                        "bool lumiereAuto = false;\n\n"
                        "void connecterWifi() {\n"
                        "  WiFi.begin(ssid, password);\n"
                        "  int tentatives = 0;\n"
                        "  while (WiFi.status() != WL_CONNECTED && tentatives < 20) {\n"
                        "    delay(500);\n"
                        "    tentatives++;\n"
                        "  }\n"
                        "}\n\n"
                        "void envoyerEtat(bool presence, bool lumiereOn) {\n"
                        "  if (WiFi.status() != WL_CONNECTED) { connecterWifi(); }\n"
                        "  if (WiFi.status() != WL_CONNECTED) return;\n\n"
                        "  HTTPClient http;\n"
                        "  http.begin(serverUrl);\n"
                        "  http.addHeader(\"Content-Type\", \"application/json\");\n"
                        "  http.addHeader(\"X-API-KEY\", apiKey);\n"
                        "  String payload = \"{\\\"presence\\\":\" + String(presence ? \"true\" : \"false\") +\n"
                        "                    \",\\\"lumiere\\\":\" + String(lumiereOn ? \"true\" : \"false\") + \"}\";\n"
                        "  int code = http.POST(payload);\n"
                        "  Serial.print(\"Envoi etat -> code: \"); Serial.println(code);\n"
                        "  http.end();\n"
                        "}\n\n"
                        "void setup() {\n"
                        "  Serial.begin(115200);\n"
                        "  pinMode(PIR_PIN, INPUT);\n"
                        "  pinMode(LUMIERE_PIN, OUTPUT);\n"
                        "  connecterWifi();\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  bool presence = digitalRead(PIR_PIN) == HIGH;\n\n"
                        "  // Regle composite : presence ET obscurite -> allumage automatique\n"
                        "  if (presence && ilFaitSombre) {\n"
                        "    lumiereAuto = true;\n"
                        "  } else if (!presence) {\n"
                        "    lumiereAuto = false;\n"
                        "  }\n"
                        "  digitalWrite(LUMIERE_PIN, lumiereAuto ? HIGH : LOW);\n\n"
                        "  envoyerEtat(presence, lumiereAuto);\n"
                        "  delay(5000);\n"
                        "}\n"
                    )},
                ],
                "quiz": [
                    {
                        "question": "Qu'est-ce qu'une 'règle composite' en automatisation domotique ?",
                        "a": "Une règle qui combine plusieurs conditions (ex: présence ET obscurité)",
                        "b": "Une règle qui ne dépend que d'un seul capteur",
                        "c": "Une règle qui ne fonctionne jamais",
                        "d": "Un type de capteur particulier",
                        "bonne": "A",
                        "explication": "Une règle composite combine plusieurs conditions pour une automatisation plus pertinente que la simple réaction à un seul signal.",
                    },
                    {
                        "question": "Pourquoi ajouter la condition 'obscurité' en plus de la présence pour allumer une lumière automatiquement ?",
                        "a": "Ça n'a aucun intérêt",
                        "b": "Pour éviter d'allumer inutilement en plein jour et rendre l'automatisation réellement pertinente",
                        "c": "Parce que le PIR ne fonctionne pas le jour",
                        "d": "Pour ralentir le système volontairement",
                        "bonne": "B",
                        "explication": "Combiner présence et obscurité évite le gaspillage énergétique et les activations inutiles en plein jour.",
                    },
                    {
                        "question": "Avec quoi un appareil s'authentifie-t-il généralement auprès de l'API Founatek, plutôt qu'avec le mot de passe personnel de l'utilisateur ?",
                        "a": "Une clé d'API propre au compte",
                        "b": "Le numéro de série de l'ESP32",
                        "c": "Aucune authentification n'est nécessaire",
                        "d": "L'adresse MAC du routeur",
                        "bonne": "A",
                        "explication": "Les appareils utilisent une clé d'API dédiée, à garder confidentielle comme un mot de passe.",
                    },
                    {
                        "question": "Quels éléments apparaissent dans le code final de cette leçon ? (plusieurs réponses possibles)",
                        "a": "Une connexion Wi-Fi",
                        "b": "Une règle combinant présence et obscurité",
                        "c": "L'envoi de l'état vers une API via HTTP",
                        "d": "La lecture d'un capteur de son",
                        "bonne": "A,B,C",
                        "plusieurs": True,
                        "explication": "Le code combine Wi-Fi, règle composite et remontée HTTP de l'état — aucun capteur de son n'est utilisé dans ce parcours.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 10,
                "titre": "Assemblage final : la maison connectée complète",
                "resume": "Rassembler relais, PIR, DHT22, écran LCD et bouton poussoir dans un seul système domotique fonctionnel.",
                "duree_minutes": 45,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "C'est le moment de faire cohabiter tous les composants appris séparément : le "
                        "relais (leçon 4), le PIR (leçon 5), le DHT22 en mode régulation (leçon 6), l'écran "
                        "LCD (leçon 7), et le bouton poussoir prioritaire (leçon 8) — le tout couronné par la "
                        "règle d'automatisation et la connexion à l'app (leçon 9).\n\n"
                        "**Plan de câblage complet** :\n"
                        "- Relais (lumière) → GPIO 26\n"
                        "- PIR → GPIO 27\n"
                        "- DHT22 → GPIO 15\n"
                        "- Écran LCD I2C → SDA GPIO 21, SCL GPIO 22\n"
                        "- Bouton poussoir → GPIO 32 (avec résistance pull-down 10kΩ)\n\n"
                        "**Le défi principal de cette leçon n'est pas technique, il est logique** : "
                        "décider dans quel ORDRE de priorité les différentes sources de décision "
                        "s'appliquent. Dans le code ci-dessous, l'ordre choisi est : le bouton manuel a "
                        "toujours la priorité absolue (règle d'or de la leçon 1 et 8) ; en son absence, "
                        "l'automatisation présence+obscurité prend le relais ; et en parallèle, "
                        "indépendamment de la lumière, la régulation de température suit sa propre logique "
                        "d'hystérésis. Trois logiques différentes, coexistant sans se marcher dessus, parce "
                        "que chacune contrôle une sortie distincte ou respecte un ordre de priorité clair."
                    )},
                    {"type": "image", "contenu": f"[{MEDIA_PLACEHOLDER}] Photo du montage complet sur breadboard : ESP32 + relais + PIR + DHT22 + écran LCD + bouton, vue d'ensemble claire avec étiquettes de chaque fil."},
                    {"type": "video", "contenu": f"[{MEDIA_PLACEHOLDER}] Vidéo de démonstration (1-2 min) : passage devant le PIR qui allume la lumière automatiquement, appui sur le bouton qui force l'état manuellement, écran LCD qui affiche l'état en direct."},
                    {"type": "code", "language": "cpp", "code": (
                        "// MAISON CONNECTEE INTELLIGENTE - Code complet du projet final\n"
                        "// Assemble : ESP32 + relais + PIR + DHT22 + ecran LCD I2C + bouton poussoir\n\n"
                        "#include <WiFi.h>\n"
                        "#include <HTTPClient.h>\n"
                        "#include <DHT.h>\n"
                        "#include <Wire.h>\n"
                        "#include <LiquidCrystal_I2C.h>\n\n"
                        "#define RELAIS_PIN 26\n"
                        "#define PIR_PIN 27\n"
                        "#define DHTPIN 15\n"
                        "#define DHTTYPE DHT22\n"
                        "#define BOUTON_PIN 32\n\n"
                        "const char* ssid = \"NOM_DE_TON_WIFI\";\n"
                        "const char* password = \"MOT_DE_PASSE_WIFI\";\n"
                        "const char* serverUrl = \"https://founatek224.pythonanywhere.com/api/mobile/domotique/etat/\";\n\n"
                        "DHT dht(DHTPIN, DHTTYPE);\n"
                        "LiquidCrystal_I2C lcd(0x27, 16, 2);\n\n"
                        "const float SEUIL_ALLUMAGE_VENTILO = 28.0;\n"
                        "const float SEUIL_EXTINCTION_VENTILO = 26.0;\n"
                        "bool ilFaitSombre = true;\n\n"
                        "bool lumiereEtat = false;\n"
                        "bool modeManuelActif = false;\n"
                        "bool ventilateurActif = false;\n"
                        "bool dernierLectureBouton = LOW, boutonStable = LOW;\n"
                        "unsigned long dernierChangementBouton = 0;\n"
                        "unsigned long dernierEnvoi = 0;\n"
                        "const unsigned long DELAI_DEBOUNCE = 50;\n"
                        "const unsigned long INTERVALLE_ENVOI = 10000;\n\n"
                        "void connecterWifi() {\n"
                        "  WiFi.begin(ssid, password);\n"
                        "  int tentatives = 0;\n"
                        "  while (WiFi.status() != WL_CONNECTED && tentatives < 20) { delay(500); tentatives++; }\n"
                        "}\n\n"
                        "void gererBouton() {\n"
                        "  bool lectureBrute = digitalRead(BOUTON_PIN);\n"
                        "  if (lectureBrute != dernierLectureBouton) dernierChangementBouton = millis();\n\n"
                        "  if ((millis() - dernierChangementBouton) > DELAI_DEBOUNCE) {\n"
                        "    if (lectureBrute != boutonStable) {\n"
                        "      boutonStable = lectureBrute;\n"
                        "      if (boutonStable == HIGH) {\n"
                        "        lumiereEtat = !lumiereEtat;\n"
                        "        modeManuelActif = true;  // Le bouton prend la priorite\n"
                        "      }\n"
                        "    }\n"
                        "  }\n"
                        "  dernierLectureBouton = lectureBrute;\n"
                        "}\n\n"
                        "void gererAutomatisationLumiere(bool presence) {\n"
                        "  if (modeManuelActif) return;  // Priorite absolue au controle manuel\n"
                        "  if (presence && ilFaitSombre) lumiereEtat = true;\n"
                        "  else if (!presence) lumiereEtat = false;\n"
                        "}\n\n"
                        "void gererVentilateur(float temperature) {\n"
                        "  if (isnan(temperature)) return;\n"
                        "  if (!ventilateurActif && temperature >= SEUIL_ALLUMAGE_VENTILO) ventilateurActif = true;\n"
                        "  else if (ventilateurActif && temperature <= SEUIL_EXTINCTION_VENTILO) ventilateurActif = false;\n"
                        "}\n\n"
                        "void afficherEtat(bool presence, float temperature) {\n"
                        "  lcd.clear();\n"
                        "  lcd.setCursor(0, 0);\n"
                        "  lcd.print(presence ? \"Presence:OUI \" : \"Presence:NON \");\n"
                        "  lcd.setCursor(0, 1);\n"
                        "  lcd.print(\"T:\"); lcd.print(temperature, 1);\n"
                        "  lcd.print(\"C L:\"); lcd.print(lumiereEtat ? \"ON\" : \"OFF\");\n"
                        "}\n\n"
                        "void envoyerEtat(bool presence, float temperature) {\n"
                        "  if (WiFi.status() != WL_CONNECTED) { connecterWifi(); }\n"
                        "  if (WiFi.status() != WL_CONNECTED) return;\n"
                        "  HTTPClient http;\n"
                        "  http.begin(serverUrl);\n"
                        "  http.addHeader(\"Content-Type\", \"application/json\");\n"
                        "  String payload = \"{\\\"presence\\\":\" + String(presence ? \"true\" : \"false\") +\n"
                        "                    \",\\\"lumiere\\\":\" + String(lumiereEtat ? \"true\" : \"false\") +\n"
                        "                    \",\\\"ventilateur\\\":\" + String(ventilateurActif ? \"true\" : \"false\") +\n"
                        "                    \",\\\"temperature\\\":\" + String(temperature) + \"}\";\n"
                        "  int code = http.POST(payload);\n"
                        "  Serial.print(\"Envoi -> code: \"); Serial.println(code);\n"
                        "  http.end();\n"
                        "}\n\n"
                        "void setup() {\n"
                        "  Serial.begin(115200);\n"
                        "  pinMode(RELAIS_PIN, OUTPUT);\n"
                        "  pinMode(PIR_PIN, INPUT);\n"
                        "  pinMode(BOUTON_PIN, INPUT);\n"
                        "  digitalWrite(RELAIS_PIN, LOW);\n"
                        "  dht.begin();\n"
                        "  Wire.begin();\n"
                        "  lcd.init();\n"
                        "  lcd.backlight();\n"
                        "  connecterWifi();\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  bool presence = digitalRead(PIR_PIN) == HIGH;\n"
                        "  float temperature = dht.readTemperature();\n\n"
                        "  gererBouton();\n"
                        "  gererAutomatisationLumiere(presence);\n"
                        "  gererVentilateur(temperature);\n\n"
                        "  digitalWrite(RELAIS_PIN, lumiereEtat ? HIGH : LOW);\n"
                        "  afficherEtat(presence, temperature);\n\n"
                        "  if (millis() - dernierEnvoi >= INTERVALLE_ENVOI) {\n"
                        "    envoyerEtat(presence, temperature);\n"
                        "    dernierEnvoi = millis();\n"
                        "  }\n\n"
                        "  delay(300);\n"
                        "}\n"
                    )},
                    {"type": "texte", "contenu": (
                        "**Pour aller plus loin** (défis bonus une fois le montage de base validé) :\n"
                        "- Ajouter un capteur de luminosité (LDR) pour remplacer la variable "
                        "`ilFaitSombre` par une vraie mesure\n"
                        "- Ajouter un minuteur : la lumière s'éteint automatiquement après X minutes sans "
                        "nouvelle détection de présence\n"
                        "- Piloter deux zones distinctes (deux relais, deux PIR) pour simuler deux pièces\n"
                        "- Ajouter une notification (email, comme le fait déjà Founatek pour les alertes) "
                        "quand une présence est détectée en dehors des horaires habituels — les débuts "
                        "d'un système de sécurité domestique\n\n"
                        "Tu as maintenant construit un système qui ne se contente plus d'observer — il "
                        "décide, il agit, et il garde toujours un humain dans la boucle quand c'est "
                        "nécessaire. C'est exactement la philosophie derrière chaque appareil connecté "
                        "sérieux, du thermostat au portail automatique."
                    )},
                ],
                "quiz": [
                    {
                        "question": "Dans le code final, quelle logique a la priorité absolue sur l'état de la lumière ?",
                        "a": "L'automatisation PIR uniquement",
                        "b": "Le bouton manuel (modeManuelActif)",
                        "c": "La température",
                        "d": "L'heure de la journée",
                        "bonne": "B",
                        "explication": "gererAutomatisationLumiere() retourne immédiatement si modeManuelActif est vrai, laissant le bouton prioritaire.",
                    },
                    {
                        "question": "Pourquoi la régulation du ventilateur (gererVentilateur) et celle de la lumière peuvent-elles fonctionner en parallèle sans conflit ?",
                        "a": "Elles contrôlent des sorties distinctes (relais différents)",
                        "b": "Elles utilisent le même GPIO",
                        "c": "Ce n'est pas possible, il y a forcément un conflit",
                        "d": "Le ventilateur n'existe pas dans ce projet",
                        "bonne": "A",
                        "explication": "Chaque logique pilote une sortie physique différente, donc elles n'entrent jamais en conflit entre elles.",
                    },
                    {
                        "question": "Quels sont des défis bonus proposés pour prolonger ce projet ? (plusieurs réponses possibles)",
                        "a": "Ajouter un capteur de luminosité (LDR)",
                        "b": "Ajouter un minuteur d'extinction automatique",
                        "c": "Remplacer l'ESP32 par un simple interrupteur mural",
                        "d": "Ajouter une notification en cas de présence hors horaires habituels",
                        "bonne": "A,B,D",
                        "plusieurs": True,
                        "explication": "Les trois premières pistes enrichissent le projet ; remplacer l'ESP32 par un simple interrupteur reviendrait à annuler la domotique elle-même.",
                    },
                    {
                        "question": "Quel est l'objectif pédagogique principal de cette dernière leçon ?",
                        "a": "Apprendre un nouveau composant",
                        "b": "Assembler toutes les briques précédentes en un seul système cohérent, avec un ordre de priorité clair",
                        "c": "Revoir uniquement la théorie de sécurité électrique",
                        "d": "Apprendre à souder",
                        "bonne": "B",
                        "explication": "C'est la leçon d'intégration : elle combine tout ce qui précède avec une logique de priorité explicite.",
                    },
                ],
            },
            # ============================================================
            {
                "ordre": 11,
                "titre": "Quiz de synthèse final",
                "resume": "Un dernier passage en revue de tout le parcours Domotique avant l'obtention du certificat.",
                "duree_minutes": 25,
                "blocs": [
                    {"type": "texte", "contenu": (
                        "Dix leçons plus tard, tu as construit un système qui mesure, décide, agit, "
                        "affiche son état, et garde toujours un contrôle manuel de secours. Ce dernier quiz "
                        "vérifie que tu maîtrises l'ensemble — la sécurité électrique, chaque composant "
                        "individuellement, et surtout la façon dont ils s'articulent ensemble dans une "
                        "logique de priorité cohérente.\n\n"
                        "Comme pour le premier parcours, aucun nouveau contenu ici — seulement des "
                        "questions qui recouvrent les dix leçons précédentes, avec un mélange de réponses "
                        "uniques et de réponses multiples. Si une question te bloque, c'est le signal qu'il "
                        "vaut mieux retourner relire la leçon correspondante avant de valider — la "
                        "certification n'a de valeur que si elle reflète une vraie compréhension."
                    )},
                ],
                "quiz": [
                    {
                        "question": "Quel est le rôle de sécurité principal d'un relais dans un montage domotique ?",
                        "a": "Accélérer le Wi-Fi",
                        "b": "Assurer une isolation galvanique entre commande basse tension et charge haute tension",
                        "c": "Remplacer le microcontrôleur",
                        "d": "Afficher l'état sur un écran",
                        "bonne": "B",
                        "explication": "L'isolation galvanique du relais protège l'utilisateur en séparant électriquement les deux circuits.",
                    },
                    {
                        "question": "Que détecte réellement un capteur PIR ?",
                        "a": "Une variation du rayonnement infrarouge liée à un mouvement",
                        "b": "Le son ambiant",
                        "c": "La pression atmosphérique",
                        "d": "La luminosité visible",
                        "bonne": "A",
                        "explication": "Le PIR réagit aux variations de rayonnement infrarouge, pas à la présence statique ni au son ni à la lumière visible.",
                    },
                    {
                        "question": "Quels composants font partie du projet final de ce parcours ? (plusieurs réponses possibles)",
                        "a": "Un module relais",
                        "b": "Un capteur PIR",
                        "c": "Un écran LCD I2C",
                        "d": "Un module GPS",
                        "bonne": "A,B,C",
                        "plusieurs": True,
                        "explication": "Relais, PIR, DHT22, écran LCD et bouton poussoir composent le projet — pas de GPS dans ce parcours.",
                    },
                    {
                        "question": "Pourquoi utilise-t-on deux seuils différents (hystérésis) pour piloter le ventilateur plutôt qu'un seul ?",
                        "a": "Pour éviter le battement (allumage/extinction en rafale) autour d'un seuil unique",
                        "b": "Ça n'a aucune importance",
                        "c": "Pour économiser de la mémoire",
                        "d": "Parce que le DHT22 l'exige techniquement",
                        "bonne": "A",
                        "explication": "L'écart entre les deux seuils stabilise le système et évite l'usure prématurée du relais.",
                    },
                    {
                        "question": "Qu'est-ce que le 'rebond' (bounce) sur un bouton poussoir, et comment le corrige-t-on ?",
                        "a": "Un phénomène mécanique corrigé par un délai de stabilisation (debounce)",
                        "b": "Un bug qui n'a aucune solution",
                        "c": "Un phénomène qui n'existe que sur les capteurs PIR",
                        "d": "Un phénomène corrigé en augmentant la tension d'alimentation",
                        "bonne": "A",
                        "explication": "Le rebond mécanique se corrige logiciellement en n'acceptant un changement d'état que s'il reste stable un certain temps.",
                    },
                    {
                        "question": "Selon la 'règle d'or' de ce parcours, que doit toujours garder un système domotique fiable ?",
                        "a": "Un moyen de contrôle manuel, prioritaire sur l'automatisation",
                        "b": "Une automatisation 100% sans intervention humaine possible",
                        "c": "Un seul capteur au maximum",
                        "d": "Aucune connexion réseau, jamais",
                        "bonne": "A",
                        "explication": "Le contrôle manuel de secours, prioritaire, est le principe central rappelé dès la première leçon.",
                    },
                    {
                        "question": "Quels protocoles/moyens de communication sont utilisés dans ce parcours ? (plusieurs réponses possibles)",
                        "a": "I2C (écran LCD)",
                        "b": "Wi-Fi + HTTP (connexion à l'API Founatek)",
                        "c": "Bluetooth",
                        "d": "Signal numérique simple (PIR, bouton)",
                        "bonne": "A,B,D",
                        "plusieurs": True,
                        "explication": "I2C pour l'écran, Wi-Fi/HTTP pour l'API, et lecture numérique simple pour PIR/bouton — pas de Bluetooth dans ce parcours.",
                    },
                    {
                        "question": "Avec quoi un appareil ESP32 s'authentifie-t-il typiquement auprès de l'API Founatek ?",
                        "a": "Une clé d'API dédiée, distincte du mot de passe personnel",
                        "b": "Le mot de passe du compte utilisateur directement",
                        "c": "Aucune authentification n'est nécessaire",
                        "d": "L'adresse IP du routeur",
                        "bonne": "A",
                        "explication": "Une clé d'API dédiée protège le compte tout en permettant à l'appareil de s'identifier auprès du serveur.",
                    },
                ],
            },
        ]

    def _final_code(self):
        return self._lessons_data()[-2]["blocs"][-2]["code"]
