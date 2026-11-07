# Parcours ESP32 avec Wokwi

Le module `esp32_fondamentaux.py` contient le parcours « Atelier ESP32 : GPIO, ADC et PWM avec Wokwi », ses six leçons, ses quiz, ses extraits Arduino et les liens documentaires. Les deux schémas sont des projets Wokwi publics :

- Bouton + LED : <https://wokwi.com/projects/480050829243594753>
- Potentiomètre + LED PWM : <https://wokwi.com/projects/480051140270148609>

Les deux sketches ont été compilés dans Wokwi. Le projet ADC/PWM produit au point médian environ `ADC=2050 PWM=127`. Les simulateurs Wokwi sont des aides pédagogiques et ne reproduisent pas toutes les limites électriques du matériel.

Après le déploiement des fichiers, exécuter depuis la racine Django :

```bash
python manage.py seed_esp32_wokwi
```

La commande `seed_esp32_wokwi` peut être relancée. Elle utilise le compte `elhadj` par défaut; changer ce nom avec `--username nom_du_compte` ou `FOUNATEK_SEED_USERNAME`. Elle crée le parcours publié la première fois, puis préserve son propriétaire et son état de publication. Les leçons, blocs, quiz et projets sont rapprochés par clés stables. La commande n’efface ni progression apprenant, ni média, ni contenu hors seed, et toute l’opération s’exécute dans une transaction atomique. Les données de cours sont versionnées dans Git, séparées de la commande.

Les liens de ressources sont ajoutés par HTML statique versionné et échappé dans le module de données; ils ouvrent les pages Wokwi et Espressif dans un nouvel onglet. Aucun iframe Wokwi non officiellement pris en charge n’est utilisé.
