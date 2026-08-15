from django.contrib.auth.models import User
from iot.models import Parcours, Lecon, BlocPedagogique, Quiz, Project, Organisation

# ─── 1. Récupérer le formateur et l'organisation ───────────────
try:
    user_elhadj = User.objects.get(username='elhadj')
    formateur   = user_elhadj.formateur_profile
    org         = formateur.organisation
    print(f"✅ Formateur : {user_elhadj.username} | Org : {org.nom}")
except Exception as e:
    print(f"❌ Erreur : {e}")
    exit()

# ─── 2. Créer le Parcours ──────────────────────────────────────
# Champs obligatoires du modèle :
#   organisation (FK) ✅
#   created_by   (FK User) ✅  ← manquait dans ton script original !
#   titre        ✅
#   description  ✅
#   niveau       ✅
#   prix         ✅
#   certifiant   ✅
#   is_published ✅
#   slug         → auto-généré par save() si vide ✅

parcours, created = Parcours.objects.get_or_create(
    slug="arduino-programmation-embarquee",
    defaults={
        'titre':        "Arduino & Programmation Embarquée",
        'description':  "Maîtrisez Arduino, les capteurs IoT et la programmation C/C++ pour créer des projets connectés. Du débutant à avancé.",
        'niveau':       "Débutant",
        'prix':         49.99,
        'certifiant':   True,
        'is_published': True,
        'organisation': org,
        'created_by':   user_elhadj,   # ← champ obligatoire corrigé
    }
)

if created:
    print(f"✅ Parcours créé : {parcours.titre} (ID: {parcours.id})")
else:
    print(f"ℹ️  Parcours déjà existant : {parcours.titre} (ID: {parcours.id})")

# ─── 3. Créer les Leçons ───────────────────────────────────────
lecons_data = [
    (1, "Introduction à Arduino",          "Découvrir la carte Arduino Uno et l'IDE."),
    (2, "Les variables et types de données","Comprendre int, float, String en C++."),
    (3, "Entrées/Sorties numériques",       "Contrôler des LEDs et lire des boutons."),
    (4, "Entrées analogiques",              "Lire des potentiomètres et capteurs analogiques."),
    (5, "Le capteur DHT22",                 "Mesurer température et humidité en temps réel."),
    (6, "Le capteur MQ135",                 "Mesurer la qualité de l'air et les gaz."),
    (7, "Communication WiFi avec ESP32",    "Connecter l'ESP32 à un réseau WiFi."),
    (8, "Envoyer des données à Founatek",   "Intégrer ESP32 à la plateforme IoT Founatek."),
]

lecons_creees = []
for ordre, titre, resume in lecons_data:
    lecon, lc = Lecon.objects.get_or_create(
        parcours=parcours,
        ordre=ordre,
        defaults={'titre': titre, 'resume': resume}
    )
    lecons_creees.append(lecon)
    print(f"  {'✅ Créée' if lc else 'ℹ️  Existe'} → Leçon {ordre}: {titre}")

# ─── 4. Ajouter des blocs pédagogiques sur la leçon 1 ─────────
l1 = lecons_creees[0]
blocs_l1 = [
    {'ordre': 1, 'type': 'texte', 'contenu': "Arduino est une plateforme open-source d'électronique. La carte Arduino Uno utilise un microcontrôleur ATmega328P cadencé à 16 MHz avec 14 broches numériques et 6 broches analogiques."},
    {'ordre': 2, 'type': 'code',  'contenu': "// Premier programme Arduino", 'language': 'cpp', 'code': "void setup() {\n  pinMode(13, OUTPUT); // LED intégrée\n}\n\nvoid loop() {\n  digitalWrite(13, HIGH); // Allumer\n  delay(1000);             // Attendre 1s\n  digitalWrite(13, LOW);  // Éteindre\n  delay(1000);\n}"},
    {'ordre': 3, 'type': 'texte', 'contenu': "La fonction setup() s'exécute une seule fois au démarrage. La fonction loop() s'exécute en boucle infinie. C'est la base de tout programme Arduino."},
]
for b in blocs_l1:
    BlocPedagogique.objects.get_or_create(
        lecon=l1, ordre=b['ordre'],
        defaults={k: v for k, v in b.items() if k != 'ordre'}
    )
print(f"✅ {len(blocs_l1)} blocs ajoutés à la leçon 1")

# ─── 5. Ajouter un Quiz sur la leçon 1 ────────────────────────
quiz, qc = Quiz.objects.get_or_create(
    lecon=l1,
    question="Quelle fonction s'exécute en boucle infinie dans un programme Arduino ?",
    defaults={
        'choix_a':       'setup()',
        'choix_b':       'loop()',
        'choix_c':       'main()',
        'choix_d':       'run()',
        'bonne_reponse': 'B',
        'explication':   'loop() est appelée indéfiniment après setup(). C\'est le cœur du programme Arduino.',
    }
)
print(f"  {'✅ Quiz créé' if qc else 'ℹ️  Quiz existant'} sur leçon 1")

# ─── 6. Ajouter un Projet au parcours ─────────────────────────
projet, pc = Project.objects.get_or_create(
    parcours=parcours,
    titre="Station météo connectée ESP32",
    defaults={
        'description': "Construire une station météo avec DHT22 + MQ135 qui envoie les données à Founatek IoT en temps réel.",
        'ordre':    1,
        'language': 'cpp',
        'code':     '// Code complet dans le cours',
    }
)
print(f"  {'✅ Projet créé' if pc else 'ℹ️  Projet existant'} : {projet.titre}")

# ─── Résumé final ──────────────────────────────────────────────
print("\n" + "="*50)
print(f"📚 Parcours  : {parcours.titre}")
print(f"🏢 Org       : {org.nom}")
print(f"📖 Leçons    : {parcours.lecons.count()}")
print(f"🏆 Certifiant: {'Oui' if parcours.certifiant else 'Non'}")
print(f"💰 Prix      : {parcours.prix} EUR")
print(f"🌐 Publié    : {'Oui' if parcours.is_published else 'Non'}")
print("="*50)
print("✅ Script terminé avec succès !")