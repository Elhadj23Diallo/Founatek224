# Parcours ESP32 avec Wokwi

Le module `esp32_fondamentaux.py` contient le parcours « Atelier ESP32 : GPIO, ADC et PWM avec Wokwi », ses six leçons, ses quiz, ses extraits Arduino et les liens documentaires. Les deux circuits de simulation Wokwi sont publics :

- Bouton + LED : <https://wokwi.com/projects/480050829243594753>
- Potentiomètre + LED PWM : <https://wokwi.com/projects/480051140270148609>

Les deux sketches ont été compilés dans Wokwi. Le projet ADC/PWM produit au point médian environ `ADC=2050 PWM=127`. Les simulateurs Wokwi sont des aides pédagogiques et ne reproduisent pas toutes les limites électriques du matériel.

Après le déploiement des fichiers, exécuter depuis la racine Django :

```bash
python manage.py seed_esp32_wokwi
```

La commande `seed_esp32_wokwi` peut être relancée. Elle utilise le compte `elhadj` par défaut; changer ce nom avec `--username nom_du_compte` ou `FOUNATEK_SEED_USERNAME`. Elle crée le parcours publié la première fois, puis préserve son propriétaire et son état de publication. Les leçons, blocs, quiz et projets sont rapprochés par clés stables. La commande n’efface ni progression apprenant, ni média, ni contenu hors seed, et toute l’opération s’exécute dans une transaction atomique. Les données de cours sont versionnées dans Git, séparées de la commande.

Les liens de ressources sont ajoutés par HTML statique versionné et échappé dans le module de données; ils ouvrent les pages Wokwi et Espressif dans un nouvel onglet. Aucun iframe Wokwi non officiellement pris en charge n’est utilisé.


## Photos réelles et schémas

Les leçons affichent des photos réelles sous licences ouvertes (carte ESP32, breadboard, LED, résistances, bouton tactile et potentiomètre), ainsi que deux schémas de câblage originaux. Les crédits visibles et les licences sont détaillés dans [`ASSETS.md`](ASSETS.md). Les sources Mermaid des schémas sont dans `schemas/`; leurs PNG statiques sont dans `iot/static/iot/course_images/`. Les liens vers les circuits Wokwi restent disponibles pour lancer les simulations dans un nouvel onglet.

Après le pull sur PythonAnywhere, activer le virtualenv puis lancer `python manage.py collectstatic --noinput` pour installer les nouveaux fichiers statiques; ensuite exécuter `python manage.py seed_esp32_wokwi` afin d’actualiser les blocs pédagogiques en base, puis recharger l’application Web avec le bouton **Reload**. Aucune migration n’est requise.
