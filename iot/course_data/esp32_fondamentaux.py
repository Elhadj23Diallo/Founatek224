"""Parcours pratique ESP32 utilisant des circuits Wokwi publics et vérifiés."""

from html import escape


WOKWI_GPIO_URL = "https://wokwi.com/projects/480050829243594753"
WOKWI_ADC_PWM_URL = "https://wokwi.com/projects/480051140270148609"

ESPRESSIF_GPIO_URL = (
    "https://docs.espressif.com/projects/esp-faq/en/latest/"
    "hardware-related/hardware-design.html"
)
ESP32_ADC_URL = (
    "https://docs.espressif.com/projects/esp-idf/en/v4.4/esp32/"
    "api-reference/peripherals/adc.html"
)
WOKWI_BUTTON_URL = "https://docs.wokwi.com/parts/wokwi-pushbutton"
WOKWI_LED_URL = "https://docs.wokwi.com/parts/wokwi-led"
WOKWI_RESISTOR_URL = "https://docs.wokwi.com/parts/wokwi-resistor"
WOKWI_POT_URL = "https://docs.wokwi.com/parts/wokwi-potentiometer"


COURSE_IMAGE_BASE = "/static/iot/course_images/"
CC_BY_SA_30_URL = "https://creativecommons.org/licenses/by-sa/3.0/"
CC0_URL = "https://creativecommons.org/publicdomain/zero/1.0/"


def photo_figure(filename, alt, caption, author, source_url, license_name, license_url=None):
    """Créer une figure photo accessible avec crédit, source et licence."""
    license_markup = escape(license_name)
    if license_url:
        license_markup = '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>'.format(
            escape(license_url, quote=True), escape(license_name)
        )
    return (
        '<figure class="course-figure course-photo">'
        '<button type="button" class="course-zoom-trigger" aria-label="Agrandir le visuel : {}">'
        '<img class="course-visual-image" src="{}{}" alt="{}" decoding="async">'
        '<span class="course-zoom-hint" aria-hidden="true"><i class="fas fa-expand"></i> Agrandir</span>'
        '</button>'
        '<figcaption><strong>{}</strong><br><span class="course-image-credit">'
        'Photo : {} · <a href="{}" target="_blank" rel="noopener noreferrer">Source</a> · {}'
        ' · image optimisée pour le Web et convertie en JPEG.</span></figcaption></figure>'
    ).format(
        escape(alt, quote=True),
        COURSE_IMAGE_BASE,
        escape(filename, quote=True),
        escape(alt, quote=True),
        escape(caption),
        escape(author),
        escape(source_url, quote=True),
        license_markup,
    )


def diagram_figure(filename, alt, caption):
    """Créer une figure de schéma original avec un texte alternatif."""
    return (
        '<figure class="course-figure course-schematic">'
        '<button type="button" class="course-zoom-trigger" aria-label="Agrandir le visuel : {}">'
        '<img class="course-visual-image" src="{}{}" alt="{}" decoding="async">'
        '<span class="course-zoom-hint" aria-hidden="true"><i class="fas fa-expand"></i> Agrandir</span>'
        '</button>'
        '<figcaption><strong>{}</strong><br><span class="course-image-credit">'
        'Schéma pédagogique original Founatek Academy; vérifier le brochage de la variante exacte.'
        '</span></figcaption></figure>'
    ).format(
        escape(alt, quote=True),
        COURSE_IMAGE_BASE,
        escape(filename, quote=True),
        escape(alt, quote=True),
        escape(caption),
    )


def resource_block(title, links, visuals=()):
    """Créer une liste de ressources et des figures sûres pour le template."""
    items = "".join(
        '<li><a href="{}" target="_blank" rel="noopener noreferrer">{}</a></li>'.format(
            escape(url, quote=True), escape(label)
        )
        for label, url in links
    )
    visual_markup = ""
    if visuals:
        visual_markup = '<div class="course-visual-grid">{}</div>'.format("".join(visuals))
    return {
        "type": "interactif",
        "language": "html",
        "contenu": None,
        "code": (
            '<div class="course-resources"><strong>{}</strong><ul>{}</ul>{}</div>'.format(
                escape(title), items, visual_markup
            )
        ),
    }


COURSE = {
    "slug": "atelier-esp32-gpio-adc-pwm-wokwi",
    "titre": "Atelier ESP32 : GPIO, ADC et PWM avec Wokwi",
    "niveau": "Débutant",
    "prix": "0.00",
    "certifiant": True,
    "description": (
        "Un parcours progressif pour programmer une carte ESP32 et comprendre ses entrées et sorties. "
        "On commence par les règles électriques essentielles, puis on pilote une LED, lit un bouton, "
        "mesure un potentiomètre avec l’ADC et règle une LED en PWM. Chaque montage est disponible "
        "dans Wokwi; le matériel réel reste facultatif pour suivre les exercices. Les limites de tension "
        "et les différences entre variantes d’ESP32 sont signalées avant les travaux pratiques."
    ),
    "materiel_requis": (
        "Simulation Wokwi (suffit pour suivre le parcours)\n"
        "Pour les essais physiques : carte ESP32 DevKit compatible, breadboard, LED, résistance 220–330 Ω,\n"
        "bouton-poussoir, potentiomètre linéaire 10 kΩ, fils Dupont et câble USB.\n"
        "Alimenter les potentiomètres depuis 3,3 V et ne jamais appliquer 5 V directement à une broche GPIO."
    ),
    "lessons": [
        {
            "ordre": 1,
            "titre": "Préparer le banc d’essai : carte, broches et sécurité",
            "resume": "Repérer GPIO, 3V3 et GND, comprendre le simulateur et poser des règles simples avant le câblage.",
            "duree_minutes": 18,
            "blocs": [
                {
                    "type": "texte",
                    "contenu": (
                        "Dans ce parcours, la carte choisie est une **ESP32 DevKit classique**. Un microcontrôleur lit des entrées, exécute un programme et commande des sorties. Une broche **GPIO** peut être utilisée comme entrée ou sortie numérique; certaines broches ont aussi une fonction analogique ou PWM. Le nom inscrit sur une carte peut différer du numéro GPIO utilisé dans le code : vérifie toujours le brochage exact de ta carte.\n\n"
                        "**Trois règles avant d’alimenter un montage :**\n"
                        "1. Débranche l’USB avant de déplacer les fils.\n"
                        "2. Relie les masses (GND) des composants et de la carte quand le montage l’exige.\n"
                        "3. Les GPIO de l’ESP32 fonctionnent en logique 3,3 V : ne leur applique pas directement 5 V. La tolérance exacte dépend du composant et de la variante; consulte sa fiche technique.\n\n"
                        "Le simulateur Wokwi aide à vérifier la logique et le câblage, mais ne reproduit pas parfaitement les tolérances, le bruit ni les défauts électriques. Une simulation réussie ne remplace donc pas les vérifications matérielles."
                    ),
                },
                resource_block("Documents de référence", [
                    ("Recommandations matérielles Espressif", ESPRESSIF_GPIO_URL),
                    ("Format des schémas Wokwi", "https://docs.wokwi.com/diagram-format"),
                ], visuals=[
                    photo_figure(
                        "esp32-devkit-cc0.jpg",
                        "Photo réelle d’une carte ESP32 DevKit avec module ESP-WROOM-32",
                        "Carte ESP32 DevKit classique",
                        "Ubahnverleih",
                        "https://commons.wikimedia.org/wiki/File:ESP32_Espressif_ESP-WROOM-32_Dev_Board_(2).jpg",
                        "CC0 1.0",
                        CC0_URL,
                    ),
                    photo_figure(
                        "breadboard.jpg",
                        "Photo réelle d’une breadboard blanche sans soudure",
                        "Breadboard sans soudure",
                        "Evan-Amos",
                        "https://commons.wikimedia.org/wiki/File:Electronics-White-Breadboard.jpg",
                        "Domaine public (PD-self)",
                    ),
                ]),
            ],
            "quiz": [
                {
                    "question": "Quelle tension logique faut-il utiliser comme référence pour les GPIO de l’ESP32 classique ?",
                    "a": "3,3 V; il ne faut pas envoyer directement 5 V sur une GPIO",
                    "b": "12 V",
                    "c": "La tension secteur",
                    "d": "La broche VIN est toujours une entrée GPIO",
                    "bonne": "A",
                    "explication": "Les GPIO ne sont pas des entrées 5 V tolérantes. Il faut vérifier la documentation du modèle exact et rester dans ses limites électriques.",
                },
                {
                    "question": "Que faut-il faire avant de déplacer un fil sur un montage réel ?",
                    "a": "Augmenter la tension d’alimentation",
                    "b": "Débrancher l’alimentation USB du montage",
                    "c": "Toucher les deux broches avec un tournevis",
                    "d": "Court-circuiter 3V3 et GND",
                    "bonne": "B",
                    "explication": "Couper l’alimentation avant de recâbler réduit les risques de court-circuit et de dommage.",
                },
            ],
        },
        {
            "ordre": 2,
            "titre": "Sortie numérique : allumer une LED sans la griller",
            "resume": "Configurer une GPIO en sortie, comprendre HIGH/LOW et dimensionner une résistance en série.",
            "duree_minutes": 22,
            "blocs": [
                {
                    "type": "texte",
                    "contenu": (
                        "Une sortie numérique prend deux états : **HIGH** ou **LOW**. Pour commander une LED, on place une résistance en série afin de limiter le courant. La LED est polarisée : son anode A va du côté de la sortie, sa cathode C vers GND.\n\n"
                        "Exemple indicatif : avec 3,3 V, une LED dont la chute de tension est proche de 2,0 V et une résistance de 220 Ω, le courant vaut environ (3,3 − 2,0) / 220 = **5,9 mA**. La chute réelle dépend de la LED; la résistance en série reste indispensable.\n\n"
                        "Le sketch ci-dessous fait clignoter la LED sur GPIO23. Utilise le lien Wokwi pour consulter le schéma. La simulation contient aussi un bouton, qui sera exploité à la leçon suivante."
                    ),
                },
                {
                    "type": "code",
                    "language": "cpp",
                    "code": (
                        "const int LED_PIN = 23;\n\n"
                        "void setup() {\n"
                        "  pinMode(LED_PIN, OUTPUT);\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  digitalWrite(LED_PIN, HIGH);\n"
                        "  delay(500);\n"
                        "  digitalWrite(LED_PIN, LOW);\n"
                        "  delay(500);\n"
                        "}\n"
                    ),
                },
                resource_block("Schéma et fiches de composants", [
                    ("Ouvrir le circuit bouton + LED dans Wokwi", WOKWI_GPIO_URL),
                    ("Fiche LED Wokwi : anode A et cathode C", WOKWI_LED_URL),
                    ("Fiche résistance Wokwi", WOKWI_RESISTOR_URL),
                ], visuals=[
                    photo_figure(
                        "red-led.jpg",
                        "Photo réelle d’une LED rouge traversante à deux pattes",
                        "LED rouge traversante",
                        "Evan-Amos",
                        "https://commons.wikimedia.org/wiki/File:Electronic-Component-Red-LED.jpg",
                        "Domaine public (PD-self)",
                    ),
                    photo_figure(
                        "resistors.jpg",
                        "Photo de résistances traversantes réelles avec plusieurs codes couleur",
                        "Résistances traversantes",
                        "FDominec",
                        "https://commons.wikimedia.org/wiki/File:Electronic_component_resistors.jpg",
                        "CC BY-SA 3.0",
                        CC_BY_SA_30_URL,
                    ),
                    diagram_figure(
                        "schema-esp32-bouton-led.png",
                        "Schéma : GPIO23 vers une résistance de 220 ohms, anode de la LED, cathode vers GND; bouton entre GPIO18 et 3V3",
                        "Schéma bouton + LED sur ESP32",
                    ),
                ]),
            ],
            "quiz": [
                {
                    "question": "Pourquoi met-on une résistance en série avec une LED commandée par GPIO23 ?",
                    "a": "Pour limiter le courant qui traverse la LED",
                    "b": "Pour convertir GND en Wi-Fi",
                    "c": "Pour inverser le programme",
                    "d": "Pour augmenter la tension du GPIO à 5 V",
                    "bonne": "A",
                    "explication": "La résistance en série limite le courant et protège la LED ainsi que la sortie.",
                },
                {
                    "question": "Dans digitalWrite(LED_PIN, LOW), que demande-t-on à la sortie ?",
                    "a": "Un niveau bas logique",
                    "b": "Une lecture ADC",
                    "c": "Une connexion Wi-Fi",
                    "d": "Un niveau analogique calibré",
                    "bonne": "A",
                    "explication": "LOW correspond à un niveau logique bas; la tension mesurée exacte dépend du circuit et de la charge.",
                },
            ],
        },
        {
            "ordre": 3,
            "titre": "Entrée numérique : lire un bouton et éviter les faux appuis",
            "resume": "Utiliser INPUT_PULLDOWN, câbler un bouton vers 3V3 et comprendre le rebond mécanique.",
            "duree_minutes": 25,
            "blocs": [
                {
                    "type": "texte",
                    "contenu": (
                        "Une entrée laissée en l’air peut capter du bruit et changer d’état sans appui. On la maintient à un état connu avec une résistance de rappel. Dans l’exemple, `INPUT_PULLDOWN` maintient GPIO18 à LOW; l’appui relie la broche à 3V3 et produit HIGH. Le bouton et la LED partagent la masse du circuit.\n\n"
                        "Un vrai bouton peut rebondir : pendant quelques millisecondes, ses contacts alternent rapidement entre ouvert et fermé. Le programme attend donc que la lecture reste stable pendant 35 ms avant de changer l’état de la LED. Le bouton Wokwi de la simulation est réglé sans rebond, mais le filtrage reste utile sur le matériel réel.\n\n"
                        "Dans le projet lié, lance la simulation et clique sur le bouton vert. Le moniteur série du sketch de démonstration affiche aussi l’état lu."
                    ),
                },
                {
                    "type": "code",
                    "language": "cpp",
                    "code": (
                        "const int BUTTON_PIN = 18;\n"
                        "const int LED_PIN = 23;\n"
                        "const unsigned long DEBOUNCE_MS = 35;\n"
                        "int stableState = LOW;\n"
                        "int lastReading = LOW;\n"
                        "unsigned long lastChangeMs = 0;\n\n"
                        "void setup() {\n"
                        "  pinMode(BUTTON_PIN, INPUT_PULLDOWN);\n"
                        "  pinMode(LED_PIN, OUTPUT);\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  int reading = digitalRead(BUTTON_PIN);\n"
                        "  if (reading != lastReading) {\n"
                        "    lastChangeMs = millis();\n"
                        "    lastReading = reading;\n"
                        "  }\n"
                        "  if (millis() - lastChangeMs >= DEBOUNCE_MS) {\n"
                        "    stableState = reading;\n"
                        "  }\n"
                        "  digitalWrite(LED_PIN, stableState);\n"
                        "  delay(2);\n"
                        "}\n"
                    ),
                },
                resource_block("Essayer et approfondir", [
                    ("Ouvrir le circuit bouton + LED dans Wokwi", WOKWI_GPIO_URL),
                    ("Brochage et rebond des boutons Wokwi", WOKWI_BUTTON_URL),
                ], visuals=[
                    photo_figure(
                        "tactile-switches.jpg",
                        "Photo réelle de trois boutons tactiles à quatre pattes, avec règle de comparaison",
                        "Boutons-poussoirs tactiles",
                        "Scwerllguy",
                        "https://commons.wikimedia.org/wiki/File:Tactile_switches.jpg",
                        "CC BY-SA 3.0",
                        CC_BY_SA_30_URL,
                    ),
                    diagram_figure(
                        "schema-esp32-bouton-led.png",
                        "Schéma du bouton relié entre GPIO18 avec INPUT_PULLDOWN et 3V3, plus la LED sur GPIO23 avec résistance série",
                        "Câblage de l’entrée bouton et de la sortie LED",
                    ),
                ]),
            ],
            "quiz": [
                {
                    "question": "Avec INPUT_PULLDOWN, à quel état la broche est-elle maintenue au repos dans ce circuit ?",
                    "a": "LOW; l’appui la relie à 3V3 et donne HIGH",
                    "b": "Toujours HIGH, même sans fil",
                    "c": "À 5 V",
                    "d": "À une valeur ADC aléatoire par conception",
                    "bonne": "A",
                    "explication": "La résistance interne de rappel maintient l’entrée à LOW jusqu’à ce que le bouton la relie à 3V3.",
                },
                {
                    "question": "À quoi sert l’anti-rebond logiciel ?",
                    "a": "À stabiliser une lecture perturbée par les contacts mécaniques du bouton",
                    "b": "À augmenter la tension de l’alimentation",
                    "c": "À empêcher l’ESP32 de démarrer",
                    "d": "À transformer GPIO18 en sortie analogique",
                    "bonne": "A",
                    "explication": "Le filtrage ignore les transitions très courtes dues au rebond des contacts.",
                },
            ],
        },
        {
            "ordre": 4,
            "titre": "Mesure analogique : lire un potentiomètre avec l’ADC",
            "resume": "Convertir une tension en nombre, choisir une broche ADC1 et interpréter les valeurs avec prudence.",
            "duree_minutes": 24,
            "blocs": [
                {
                    "type": "texte",
                    "contenu": (
                        "Un ADC (convertisseur analogique-numérique) traduit une tension en nombre. Sur l’ESP32 classique, la lecture Arduino par défaut est généralement sur 12 bits, soit des codes de 0 à 4095. Ce nombre n’est pas une mesure de tension parfaitement linéaire ou étalonnée : la plage utile et la précision varient selon la puce, l’atténuation et la carte.\n\n"
                        "Le potentiomètre se câble avec ses extrémités vers 3V3 et GND, puis le curseur SIG vers GPIO34. Sur l’ESP32 classique, GPIO34 est une entrée seule et appartient à ADC1. Les broches ADC1 sont utiles lorsque le Wi-Fi sera ajouté, car ADC2 peut être indisponible pendant l’utilisation du Wi-Fi sur cette famille de puces.\n\n"
                        "**Sécurité :** un potentiomètre alimenté en 5 V peut envoyer une tension trop élevée au curseur. Dans cet exercice, alimente-le en 3,3 V. Le potentiomètre Wokwi agit comme un curseur numérique; son modèle analogique est simplifié."
                    ),
                },
                {
                    "type": "code",
                    "language": "cpp",
                    "code": (
                        "const int POT_PIN = 34;\n\n"
                        "void setup() {\n"
                        "  Serial.begin(115200);\n"
                        "  analogReadResolution(12);\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  int raw = analogRead(POT_PIN);\n"
                        "  float voltsApprox = raw * 3.3f / 4095.0f;\n"
                        "  Serial.print(\"ADC=\");\n"
                        "  Serial.print(raw);\n"
                        "  Serial.print(\"; V approx=\");\n"
                        "  Serial.println(voltsApprox, 2);\n"
                        "  delay(200);\n"
                        "}\n"
                    ),
                },
                resource_block("Simulation et documentation", [
                    ("Ouvrir le circuit potentiomètre + LED dans Wokwi", WOKWI_ADC_PWM_URL),
                    ("Fiche du potentiomètre Wokwi", WOKWI_POT_URL),
                    ("Référence ADC Espressif pour ESP32 classique", ESP32_ADC_URL),
                ], visuals=[
                    photo_figure(
                        "potentiometer.jpg",
                        "Photo réelle d’un potentiomètre rotatif traversant avec trois broches",
                        "Potentiomètre rotatif à trois bornes",
                        "Evan-Amos",
                        "https://commons.wikimedia.org/wiki/File:Electronic-Component-Potentiometer.jpg",
                        "Domaine public (PD-self)",
                    ),
                    diagram_figure(
                        "schema-esp32-potentiometre-pwm.png",
                        "Schéma : potentiomètre 10 kilo-ohms entre 3V3 et GND, curseur sur GPIO34 ADC1; GPIO23 commande une LED via 220 ohms",
                        "Schéma ADC1 + LED protégée sur ESP32",
                    ),
                ]),
            ],
            "quiz": [
                {
                    "question": "Dans le montage de cette leçon, quelle broche lit le curseur du potentiomètre ?",
                    "a": "GPIO34, une entrée ADC1 sur l’ESP32 classique",
                    "b": "GND",
                    "c": "La broche TX du port série",
                    "d": "Le port USB directement",
                    "bonne": "A",
                    "explication": "GPIO34 est une entrée ADC1 couramment utilisée sur l’ESP32 classique; vérifie toujours le brochage de ta variante.",
                },
                {
                    "question": "Pourquoi alimente-t-on le potentiomètre en 3,3 V dans cet exercice ?",
                    "a": "Pour que sa sortie reste dans une plage adaptée aux GPIO de l’ESP32",
                    "b": "Pour forcer une lecture toujours égale à 4095",
                    "c": "Pour remplacer le GND",
                    "d": "Parce que l’ADC ne fonctionne qu’avec du 5 V",
                    "bonne": "A",
                    "explication": "Le curseur peut atteindre la tension d’alimentation du potentiomètre; 5 V directement sur une GPIO peut endommager l’ESP32.",
                },
            ],
        },
        {
            "ordre": 5,
            "titre": "PWM : régler la luminosité d’une LED",
            "resume": "Comprendre le rapport cyclique et transformer une lecture analogique en commande de sortie.",
            "duree_minutes": 22,
            "blocs": [
                {
                    "type": "texte",
                    "contenu": (
                        "Une GPIO numérique ne fournit pas une tension analogique variable. Le **PWM** (modulation de largeur d’impulsion) commute rapidement la sortie entre LOW et HIGH. Le rapport cyclique décrit la part du temps passée à HIGH : 0 correspond à presque éteint, 255 à la commande maximale dans cet exemple 8 bits. L’œil perçoit une luminosité moyenne.\n\n"
                        "On lit le potentiomètre sur une plage de 0 à 4095 puis `map()` convertit cette plage en 0 à 255. `analogWrite()` règle la sortie PWM sur GPIO23 dans le cœur Arduino ESP32 utilisé par Wokwi. La LED garde sa résistance série de 220 Ω. Pour un moteur ou une charge puissante, ne branche jamais la charge directement sur une GPIO : utilise un étage de puissance approprié."
                    ),
                },
                {
                    "type": "code",
                    "language": "cpp",
                    "code": (
                        "const int POT_PIN = 34;\n"
                        "const int LED_PIN = 23;\n\n"
                        "void setup() {\n"
                        "  Serial.begin(115200);\n"
                        "  pinMode(POT_PIN, INPUT);\n"
                        "  pinMode(LED_PIN, OUTPUT);\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  int raw = analogRead(POT_PIN);\n"
                        "  int duty = map(raw, 0, 4095, 0, 255);\n"
                        "  analogWrite(LED_PIN, duty);\n"
                        "  Serial.print(\"ADC=\"); Serial.print(raw);\n"
                        "  Serial.print(\" PWM=\"); Serial.println(duty);\n"
                        "  delay(100);\n"
                        "}\n"
                    ),
                },
                resource_block("Observer la conversion en direct", [
                    ("Ouvrir le circuit ADC → PWM dans Wokwi", WOKWI_ADC_PWM_URL),
                    ("Documentation du potentiomètre Wokwi", WOKWI_POT_URL),
                ], visuals=[
                    photo_figure(
                        "resistors.jpg",
                        "Photo de résistances réelles dont des composants traversants à code couleur",
                        "Résistance série : un composant réel à identifier",
                        "FDominec",
                        "https://commons.wikimedia.org/wiki/File:Electronic_component_resistors.jpg",
                        "CC BY-SA 3.0",
                        CC_BY_SA_30_URL,
                    ),
                    diagram_figure(
                        "schema-esp32-potentiometre-pwm.png",
                        "Schéma du potentiomètre sur GPIO34 ADC1 et de la LED protégée commandée en PWM par GPIO23",
                        "Chemin de mesure ADC vers commande PWM",
                    ),
                ]),
            ],
            "quiz": [
                {
                    "question": "Que représente la valeur `duty = 128` dans ce programme PWM 8 bits ?",
                    "a": "Un rapport cyclique d’environ 50 %",
                    "b": "128 volts appliqués à la LED",
                    "c": "Une lecture de 128 capteurs",
                    "d": "Une sortie forcément à 5 V",
                    "bonne": "A",
                    "explication": "La plage 0–255 représente 256 niveaux de commande; 128 est proche de la moitié de la plage.",
                },
                {
                    "question": "Pourquoi une résistance série reste-t-elle nécessaire avec le PWM ?",
                    "a": "Le PWM ne limite pas à lui seul le courant instantané traversant la LED",
                    "b": "Parce que PWM signifie alimentation 5 V",
                    "c": "Pour convertir la LED en entrée",
                    "d": "Pour empêcher `analogRead()` de fonctionner",
                    "bonne": "A",
                    "explication": "Le PWM commute la sortie, mais chaque impulsion HIGH peut encore fournir trop de courant sans limitation adaptée.",
                },
            ],
        },
        {
            "ordre": 6,
            "titre": "Mini-projet : variateur ESP32 piloté par potentiomètre",
            "resume": "Assembler ADC, PWM et diagnostic série, puis proposer une extension mesurable.",
            "duree_minutes": 30,
            "blocs": [
                {
                    "type": "texte",
                    "contenu": (
                        "Le mini-projet relie trois étapes d’un système embarqué : **mesurer** le curseur du potentiomètre sur GPIO34, **transformer** la valeur en rapport cyclique, puis **agir** sur la luminosité de la LED via GPIO23. Le moniteur série permet de comparer le nombre ADC au rapport PWM.\n\n"
                        "Dans Wokwi, démarre la simulation, clique sur le potentiomètre et déplace son curseur. Observe la variation simultanée de `ADC` et `PWM`. Au milieu, tu devrais voir des valeurs proches de la moitié de chaque plage; la simulation de potentiomètre n’est pas une mesure électrique réelle.\n\n"
                        "**Défi :** ajoute un seuil qui éteint la LED sous une valeur choisie; ensuite, affiche un pourcentage plutôt qu’un nombre brut. Note les limites observées. Sur une vraie carte, mesure la tension avec un multimètre si tu en as un et consulte la documentation du modèle exact avant toute connexion."
                    ),
                },
                {
                    "type": "code",
                    "language": "cpp",
                    "code": (
                        "const int POT_PIN = 34;\n"
                        "const int LED_PIN = 23;\n\n"
                        "void setup() {\n"
                        "  Serial.begin(115200);\n"
                        "  analogReadResolution(12);\n"
                        "  pinMode(POT_PIN, INPUT);\n"
                        "  pinMode(LED_PIN, OUTPUT);\n"
                        "}\n\n"
                        "void loop() {\n"
                        "  int raw = analogRead(POT_PIN);\n"
                        "  int duty = map(raw, 0, 4095, 0, 255);\n"
                        "  analogWrite(LED_PIN, duty);\n"
                        "  int percent = map(duty, 0, 255, 0, 100);\n"
                        "  Serial.print(\"ADC=\"); Serial.print(raw);\n"
                        "  Serial.print(\" PWM=\"); Serial.print(duty);\n"
                        "  Serial.print(\" Luminosite=\"); Serial.print(percent);\n"
                        "  Serial.println(\"%\");\n"
                        "  delay(100);\n"
                        "}\n"
                    ),
                },
                resource_block("Ouvrir le montage complet", [
                    ("Variante bouton + LED", WOKWI_GPIO_URL),
                    ("Mini-projet potentiomètre + PWM", WOKWI_ADC_PWM_URL),
                    ("Précautions GPIO Espressif", ESPRESSIF_GPIO_URL),
                ], visuals=[
                    photo_figure(
                        "esp32-devkit-cc0.jpg",
                        "Photo réelle d’une carte de développement ESP32 DevKit",
                        "Carte de calcul du mini-projet",
                        "Ubahnverleih",
                        "https://commons.wikimedia.org/wiki/File:ESP32_Espressif_ESP-WROOM-32_Dev_Board_(2).jpg",
                        "CC0 1.0",
                        CC0_URL,
                    ),
                    photo_figure(
                        "breadboard.jpg",
                        "Photo d’une breadboard sans soudure pour prototyper le montage",
                        "Support de prototypage physique",
                        "Evan-Amos",
                        "https://commons.wikimedia.org/wiki/File:Electronics-White-Breadboard.jpg",
                        "Domaine public (PD-self)",
                    ),
                    diagram_figure(
                        "schema-esp32-potentiometre-pwm.png",
                        "Schéma complet du mini-projet : potentiomètre 10 kilo-ohms vers ADC1 GPIO34 et LED via résistance commandée par PWM GPIO23",
                        "Montage complet du variateur PWM",
                    ),
                ]),
            ],
            "quiz": [
                {
                    "question": "Quel ordre décrit correctement le mini-projet ?",
                    "a": "Lire le potentiomètre, convertir la lecture, commander la LED en PWM",
                    "b": "Envoyer 5 V dans GPIO34, puis ignorer la valeur",
                    "c": "Écrire sur GND puis lire la LED comme un réseau Wi-Fi",
                    "d": "Utiliser le bouton pour remplacer l’ADC",
                    "bonne": "A",
                    "explication": "Le montage suit la chaîne entrée analogique → traitement logiciel → sortie PWM.",
                },
                {
                    "question": "Pourquoi faut-il rester prudent même si le projet fonctionne dans Wokwi ?",
                    "a": "Le simulateur ne reproduit pas toutes les contraintes, le bruit ni les limites électriques du matériel réel",
                    "b": "Parce que Wokwi convertit les GPIO en broches secteur",
                    "c": "Parce qu’une simulation n’utilise jamais de programme",
                    "d": "Il n’y a aucune différence entre simulation et matériel réel",
                    "bonne": "A",
                    "explication": "Une simulation valide la logique, pas toutes les conditions électriques d’une carte physique.",
                },
            ],
        },
    ],
    "project": {
        "titre": "Variateur PWM commandé par potentiomètre",
        "ordre": 1,
        "language": "cpp",
        "description": (
            "Lire le potentiomètre sur GPIO34, convertir sa valeur ADC en rapport cyclique PWM et régler la "
            "luminosité d’une LED protégée par une résistance de 220 Ω sur GPIO23. Les apprenants peuvent "
            "tester la simulation Wokwi depuis la leçon 6, puis reproduire le montage sur une carte compatible."
        ),
        "code": (
            "const int POT_PIN = 34;\n"
            "const int LED_PIN = 23;\n\n"
            "void setup() {\n"
            "  Serial.begin(115200);\n"
            "  analogReadResolution(12);\n"
            "  pinMode(POT_PIN, INPUT);\n"
            "  pinMode(LED_PIN, OUTPUT);\n"
            "}\n\n"
            "void loop() {\n"
            "  int raw = analogRead(POT_PIN);\n"
            "  int duty = map(raw, 0, 4095, 0, 255);\n"
            "  analogWrite(LED_PIN, duty);\n"
            "  Serial.print(\"ADC=\"); Serial.print(raw);\n"
            "  Serial.print(\" PWM=\"); Serial.println(duty);\n"
            "  delay(100);\n"
            "}\n"
        ),
    },
}
