# Prêts et retours

`app/lending.py`, `loan_list.html` et `loan_approve.html` composent la présentation. L'API décide de toutes les permissions, disponibilités et transitions ; le frontend ne touche jamais le JSON.

| Route | Traitement |
|---|---|
| GET `/emprunts` | Liste du membre, ou vue de gestion pour manager/admin ; statuts et pagination, films et profils nécessaires joints par l'API |
| POST `/films/<id>/emprunter` | Demande pour le compte connecté, sans borrower_id fourni par le navigateur |
| GET/POST `/emprunts/<id>/valider` | Manager/admin ; choix parmi exemplaires libres non abîmés, date de retour, version If-Match |
| POST `/emprunts/<id>/retour` | Manager/admin ; retour effectif atomique |
| POST `/emprunts/<id>/annuler` | Demande en attente seulement, propriétaire ou gestion |

Toutes les mutations ont CSRF et les actions sur une demande existante portent sa version. La liste ne contient aucun bearer ; les erreurs conservent les champs d'approbation quand cela reste possible. Les dates sont affichées en UTC, et l'échéance choisie correspond à la fin de la date UTC. Le serveur API impose l'échéance future et au plus 90 jours. Les comptes désactivés ne peuvent recevoir d'approbation de demande en attente.

La fiche publique affiche la disponibilité calculée via `/api/v1/availability`, sans identité d'emprunteur. Les lectures présentent un état instantané ; l'API revérifie tout au moment d'attribuer. L'historique reste conservé et empêche l'effacement des ressources référencées. Une réponse perdue peut rendre une mutation ambiguë : aucun retry automatique, et les écrans d'indisponibilité demandent de vérifier le résultat avant de répéter une modification. L'idempotence explicite de toutes les créations reste à renforcer et à auditer.

Le premier jalon HTTP réel des prêts a réussi 82 contrôles. Le jalon suivant en compte 112 avec réservations, FIFO et attribution atomique. Le rendu navigateur des nouveaux écrans de prêts n'est pas encore vérifié. La priorité est désormais contrôlée par l'API ; une option d'attribution peut être vide quand les exemplaires libres sont réservés à des membres prioritaires. Voir `reservations.md`.

La fiche authentifiée consulte `GET /api/v1/loans?scope=mine&movie_id=…&status=open&limit=1`. Une demande déjà ouverte ou un prêt actif propose le lien vers son suivi, sans bouton de nouvelle demande/réservation. Le même comportement s’applique aux gestionnaires pour leurs propres prêts. Les contrôles atomiques du backend restent nécessaires si l’état change après le rendu.
