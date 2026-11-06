# Parcours de réservation

- GET `/reservations` : liste personnelle ou de gestion, filtres, position, expiration, indication d'un exemplaire prêt et lien vers une demande déjà ouverte.
- POST `/films/<id>/reserver` : création pour le compte connecté ; pas d'identité ou priorité fournie par le navigateur.
- POST `/reservations/<id>/annuler` : version et CSRF requis ; la décision de propriété et d'état appartient à l'API.

La fiche du film demande à l'API son contexte d'attente propre (`scope=mine`), même pour un gestionnaire. Elle propose soit un prêt disponible, soit une réservation, soit l'attente/demande déjà existante. Une demande en cours est liée plutôt que recréée. Les réponses authentifiées contenant ce contexte sont `no-store`.

Les templates `reservation_list.html` et `reservation_conflict.html` échappent les titres et les noms. Un conflit de création conserve des liens vers les réservations et la disponibilité réelle du film. Les annulations ne suppriment pas l'historique ; une demande de prêt distincte se gère depuis Emprunts.

Les tests web isolés utilisent une API simulée. L'intégration HTTP Compose est distincte et utilise les deux services réels. Aucun rendu navigateur de ces nouveaux écrans n'est encore présenté comme vérifié.
