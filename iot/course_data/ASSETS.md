# Crédits des visuels — parcours ESP32

Les photos sont des photographies de composants physiques publiées sur Wikimedia Commons. Les crédits et liens de source/licence sont également affichés sous les images dans les leçons. Les fichiers ont été optimisés pour le Web, redimensionnés lorsque nécessaire en conservant leur ratio, puis convertis en WebP; aucun contenu ni annotation n’a été ajouté.

| Fichier | Crédit et licence | Source |
|---|---|---|
| `esp32-devkit-cc0.webp` | Ubahnverleih, CC0 1.0; redimensionnée et convertie en WebP | [ESP32 Espressif ESP-WROOM-32 Dev Board (2).jpg](https://commons.wikimedia.org/wiki/File:ESP32_Espressif_ESP-WROOM-32_Dev_Board_(2).jpg) · [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) |
| `breadboard.webp` | Evan-Amos, domaine public (PD-self); redimensionnée et convertie en WebP | [Electronics-White-Breadboard.jpg](https://commons.wikimedia.org/wiki/File:Electronics-White-Breadboard.jpg) |
| `red-led.webp` | Evan-Amos, domaine public (PD-self); redimensionnée et convertie en WebP | [Electronic-Component-Red-LED.jpg](https://commons.wikimedia.org/wiki/File:Electronic-Component-Red-LED.jpg) |
| `resistors.webp` | FDominec, CC BY-SA 3.0; redimensionnée et convertie en WebP | [Electronic component resistors.jpg](https://commons.wikimedia.org/wiki/File:Electronic_component_resistors.jpg) · [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) |
| `tactile-switches.webp` | Scwerllguy, CC BY-SA 3.0; convertie en WebP | [Tactile switches.jpg](https://commons.wikimedia.org/wiki/File:Tactile_switches.jpg) · [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) |
| `potentiometer.webp` | Evan-Amos, domaine public (PD-self); redimensionnée et convertie en WebP | [Electronic-Component-Potentiometer.jpg](https://commons.wikimedia.org/wiki/File:Electronic-Component-Potentiometer.jpg) |

Les adaptations issues des fichiers CC BY-SA restent créditées et publiées sous la licence correspondante; cela ne prétend pas appliquer ces licences aux autres contenus du cours.

Les schémas `esp32-bouton-led.mmd` et `esp32-potentiometre-pwm.mmd` sont des schémas pédagogiques originaux, conservés en Mermaid dans `iot/course_data/schemas/` et rendus en PNG dans `iot/static/iot/course_images/`. Les liens de projet Wokwi intégrés au cours ouvrent les simulations interactives; aucun iframe Wokwi n’est utilisé.

## Mise en ligne des visuels

Après le pull du commit sur PythonAnywhere, activer le virtualenv puis exécuter `python manage.py collectstatic --noinput` pour copier les images vers `STATIC_ROOT`, puis `python manage.py seed_esp32_wokwi` pour mettre à jour les blocs du parcours. Enfin, utiliser le bouton **Reload** de l’application Web PythonAnywhere. Aucune migration de schéma n’est nécessaire.
