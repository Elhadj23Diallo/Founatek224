# Founatek Academy — Livre 1 : intégration progressive

## Décision produit
- **Partie 00** : gratuite.
- **Parties 01–11** : un seul achat définitif du pack à **9,99 EUR**.
- Prestataires visés : Stripe et PayPal **déjà intégrés pour les recharges/abonnements**, mais pas encore pour l'achat d'un cours.
- Aucune publication automatique, aucun débit réel, aucun cours factice.

## Architecture constatée
`iot.Parcours` → `iot.Lecon` → `iot.BlocPedagogique`, `iot.Quiz` et `iot.Progression`.
Les cours sont ordonnés par `Lecon.ordre`. `Parcours.is_published` masque les brouillons du catalogue.
`iot.utils.pedagogy.lecon_est_debloquee` vérifie **seulement** la progression pédagogique, pas le paiement.
Le `Parcours.prix` existant n'impose **aucun contrôle d'accès** : ne pas l'utiliser comme verrou de sécurité.

## Contrat de sécurité avant activation
1. Introduire une table `CourseEntitlement` unique par utilisateur et pack, avec référence de paiement,
   statut, dates et journal d'audit. Ne jamais se baser sur le seul retour navigateur.
2. Ajouter des transactions de cours distinctes des recharges du wallet. Stripe : confirmer
   l'événement signé, le montant **999 centimes**, la devise EUR, l'identifiant du pack et le compte.
   PayPal : vérifier côté serveur la capture `COMPLETED`, son bénéficiaire, son montant, sa devise
   et sa référence. Vérifier l'idempotence et traiter remboursements/contestations.
3. Bloquer les accès **dans la vue et les API**, pas seulement masquer des boutons.
   La partie 00 reste accessible sans achat ; le reste requiert un droit confirmé,
   puis respecte les prérequis de progression.
4. Ne pas réutiliser `seed_electronique_embarquee` : il efface les leçons existantes.
   Écrire un import idempotent basé sur des identifiants stables des fiches, qui
   ne supprime jamais les progressions, quiz ou travaux des apprenants.
5. Conserver les 12 parties dans l'ordre du livre ; ne pas importer les pages modèles
   « diode » comme si elles étaient des cours finis. Faire valider les fiches techniques,
   les schémas et les codes avant de publier les parties 01–11.
6. Tests : accès anonyme, utilisateur gratuit, acheteur, échec de paiement, webhook rejoué,
   montant erroné, remboursement, changement de compte, leçon directe et API.
7. Déploiement : sauvegarde base, `python manage.py check`, `python manage.py migrate`,
   tests ciblés, rechargement PythonAnywhere, vérification en mode test Stripe/PayPal.

## État
Ce commit prépare **uniquement** la configuration ordonnée et le cahier de sécurité.
Il **n'active pas** les paiements, ne publie pas de cours et ne modifie aucune donnée.
Ne pas promettre qu'un simple `git pull` active l'offre tant que les étapes ci-dessus
ne sont pas réalisées et testées.
