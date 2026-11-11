# CineVault Web

Service de présentation Flask/Jinja de CineVault. Il appelle une API HTTP séparée et n'écrit jamais le fichier JSON. Le mode pédagogique legacy est actif par défaut ; `ENTERPRISE_ENABLED=true` active comptes, catalogue partagé, exemplaires, collections privées, prêts et réservations, lorsque le backend est configuré au même mode. TLS et les autres extensions restent à compléter avant la livraison finale.

Documentation : [comptes et transmission de l'identité](docs/accounts.md), [collections privées](docs/collections.md), [prêts et retours](docs/loans.md), [réservations](docs/reservations.md), [import/export](docs/transfer.md), [tableau de bord et découverte](docs/insights.md), [recherche externe et affiches](docs/metadata.md). L'API demeure l'autorité pour les permissions et les règles métier ; le frontend ne transmet aucun rôle ou propriétaire comme preuve d'identité.

## Configuration

- `SECRET_KEY` : obligatoire, valeur aléatoire persistante et confidentielle d'au moins 32 octets UTF-8 ; ne jamais la versionner. La configuration Python accepte aussi des `bytes` d'au moins 32 octets.
- `SECRET_KEY_FILE` : fichier privé d'au moins 32 octets, prioritaire sur `SECRET_KEY` ; utilisé par le mode Compose de test Enterprise.
- `ENTERPRISE_ENABLED=true` : active les routes et écrans Enterprise ; configurer aussi le backend avant activation.
- `API_URL` : URL interne de l'API, `http://cinevault-api:8000` par défaut ; ajuster selon le DNS de la stack.
- `COOKIE_SECURE=true` : à activer lorsque le navigateur accède au service par HTTPS.
- `CLIENT_CONTEXT_KEY_FILE` : clé dédiée partagée avec l'API pour [signer la source du visiteur](docs/client-context.md) ; au moins 32 octets, hors dépôt. L'API exige ce contexte en déploiement avec `CLIENT_CONTEXT_REQUIRED=true`.

La validation de la clé de session est commune à la configuration, à l'environnement et au fichier, y compris en mode test. Les types autres que `str`/`bytes`, clés vides, trop courtes ou textes non encodables en UTF-8 refusent le démarrage sans afficher la valeur. Le fichier est lu comme des octets bruts : aucun espace, saut de ligne ou octet n'est retiré. Une clé valide conserve sa valeur, son type et les signatures de session existantes ; elle n'est ni remplacée ni régénérée. La longueur minimale ne prouve pas l'entropie : générer la clé avec un générateur cryptographiquement sûr et la garder stable hors dépôt.

Si la configuration Python utilise `SECRET_KEY_FALLBACKS` pour une rotation Flask, fournir une liste ou un tuple d'anciennes clés valides, chacune soumise à la même limite de 32 octets. Leur ordre et leurs valeurs sont conservés : les anciens cookies peuvent être lus et les nouveaux restent signés avec la clé courante. `None` ou une séquence vide n'active aucun fallback ; aucune ancienne clé n'est chargée automatiquement.

Le point `GET /health` vérifie uniquement que le processus web répond ; il ne prouve pas la disponibilité de l'API.

## Développement et tests

Créer un environnement virtuel Python 3.13, installer `requirements-dev.txt`, puis définir `SECRET_KEY` et `API_URL`. Lancer `flask --app 'app:create_app()' run --port 5000`. Les tests s'exécutent avec `python -m pytest -q` ; ils utilisent un faux client API pour isoler le service web. Les vérifications interservices et navigateur sont distinctes.

Les formulaires utilisent un jeton CSRF en session et conservent la saisie en cas d'erreur. Les champs sont validés côté interface et revérifiés par l'API, qui reste la source de vérité. Les mutations ne sont pas rejouées automatiquement après un délai dépassé : leur résultat peut être incertain et doit être vérifié avant une nouvelle tentative.

Le concept visuel `concept.png` est une maquette générée ; ses données fictives ne sont pas chargées dans l'application.

Le [catalogue membre et sa navigation contextuelle](docs/member-presentation.md) conservent les formulaires natifs et les permissions existantes. Les rôles de gestion peuvent choisir l'inventaire avec `/films?view=manage` ; ce paramètre de présentation n'est jamais envoyé à l'API.

## Exercices du sujet

- A : `GET /page-simple`, route `app/routes.py`, template `app/templates/simple.html`.
- B : `GET` et `POST /films/nouveau`, validation `app/forms.py`, templates `form.html` et `detail.html` ; le traitement transmet les données à l'API.
- C : `GET /films/<id>`, client `app/api_client.py`, template `detail.html`. Les données viennent du fichier JSON **via l'API** ; le serveur web n'accède pas au fichier.

`tests/test_exercices_pedagogiques.py` teste séparément les trois rendus avec un client API simulé pour B et C. Une vérification interservices avec fichier réel doit être exécutée avec les deux services ; les anciens journaux privés de développement ne sont pas inclus dans ce dépôt et ne constituent pas une preuve publique. Les données des tests sont fictives. Le déploiement complet nécessite aussi le projet d'infrastructure CineVault, qui fournit les configurations Compose et Swarm.

## Qualité et CI

Voir les [commandes, contrôles et limites](docs/quality.md). Les configurations de CI ne constituent pas une preuve d’exécution distante ; aucun badge de succès n’est ajouté avant un résultat GitHub réel.

Le [socle d’exécution spécialisé et ses limites de reconstruction](docs/runtime.md) décrit les deux étapes de construction et les composants conservés.

## Licence et ressources

Le code original et sa documentation sont sous [licence MIT](LICENSE). Les dépendances tierces et les médias référencés conservent leurs propres licences. `concept.png` est une illustration générée pour la conception, avec des contenus fictifs ; elle n'est ni chargée par l'application, ni présentée comme une capture de fonctionnement. Les affiches externes, lorsqu'elles sont activées, affichent leur provenance et leurs conditions séparément.
