# Collections personnelles

Le mode Enterprise ajoute `app/personal.py`, `personal_collection.html` et `personal_entry_form.html`.

| URL | Opération |
|---|---|
| GET `/ma-collection` | Liste privée, filtre type/nom, pagination ; appelle `GET /api/v1/collections` avec bearer |
| GET/POST `/ma-collection/ajouter?film_id=<id>` | Sélection d'un film public, type, nom de liste et supports ; `POST /api/v1/collections` |
| GET/POST `/ma-collection/<id>/modifier` | Lecture de sa propre entrée puis `PUT` des attributs autorisés, If-Match |
| POST `/ma-collection/<id>/retirer` | `DELETE` avec If-Match, sans supprimer l'œuvre du catalogue commun |

L'utilisateur doit être connecté ; un membre peut utiliser ces pages sans rôle de gestion. La propriété reste vérifiée côté API, y compris pour un administrateur. Le navigateur ne transmet aucun `owner_id`. Les noms de liste et titres sont échappés ; les réponses utilisent `no-store`, les POST exigent CSRF, les conflits conservent les champs saisis. Les supports personnels ne modifient jamais les exemplaires partagés.

Cinq types : possédés, favoris, vus, à voir et listes personnalisées. Les noms de liste ne sont utilisables que pour le dernier type ; les supports sont réservés aux films possédés. Les données jointes des films sont renvoyées par la même réponse API de liste, afin d'éviter une requête par entrée.

25 tests web Windows/Linux réussis ; API simulée dans ces tests, intégration HTTP réelle distincte de 68 contrôles. Le rendu navigateur des nouveaux écrans privés reste à examiner. Aucun prêt ni réservation n'est fourni par ce jalon.
