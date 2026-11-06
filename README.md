# CineVault Web

Service de présentation Flask/Jinja de la vidéothèque CineVault. Il appelle une API HTTP séparée, n'écrit pas le fichier JSON et ne comprend aucune authentification utilisateur. À réserver à un réseau de confiance ou protéger par un contrôle d'accès adapté avant toute exposition publique.

## Configuration

- `SECRET_KEY` : obligatoire, valeur aléatoire persistante et confidentielle ; ne jamais la versionner.
- `API_URL` : URL interne de l'API, `http://cinevault-api:8000` par défaut ; ajuster selon le DNS de la stack.
- `COOKIE_SECURE=true` : à activer lorsque le navigateur accède au service par HTTPS.

Le point `GET /health` vérifie uniquement que le processus web répond ; il ne prouve pas la disponibilité de l'API.

## Développement et tests

Créer un environnement virtuel Python 3.13, installer `requirements-dev.txt`, puis définir `SECRET_KEY` et `API_URL`. Lancer `flask --app 'app:create_app()' run --port 5000`. Les tests s'exécutent avec `python -m pytest -q` ; ils utilisent un faux client API pour isoler le service web. Les vérifications interservices et navigateur sont distinctes.

Les formulaires utilisent un jeton CSRF en session et conservent la saisie en cas d'erreur. Les champs sont validés côté interface et revérifiés par l'API, qui reste la source de vérité. Les mutations ne sont pas rejouées automatiquement après un délai dépassé : leur résultat peut être incertain et doit être vérifié avant une nouvelle tentative.

Le concept visuel `concept.png` est une maquette générée ; ses données fictives ne sont pas chargées dans l'application.

## Exercices du sujet

- A : `GET /page-simple`, route `app/routes.py`, template `app/templates/simple.html`.
- B : `GET` et `POST /films/nouveau`, validation `app/forms.py`, templates `form.html` et `detail.html` ; le traitement transmet les données à l'API.
- C : `GET /films/<id>`, client `app/api_client.py`, template `detail.html`. Les données viennent du fichier JSON **via l'API** ; le serveur web n'accède pas au fichier.

`tests/test_exercices_pedagogiques.py` teste séparément les trois rendus avec un client API simulé pour B et C. La preuve interservices avec fichier réel est distincte des tests simulés et doit être exécutée avec les deux services ; voir l'index des preuves dans le dossier de travail du projet. Les données des tests sont fictives.
