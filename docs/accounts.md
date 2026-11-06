# Présentation des comptes Enterprise

Mode opt-in `ENTERPRISE_ENABLED=true` ; les routes n'existent pas en mode pédagogique par défaut. L'API doit être configurée avec son document v2 et sa clé privée avant d'activer ce mode côté web. Ce jalon est une intégration de comptes ; les autres fonctions Enterprise restent en développement.

| URL | Méthodes | Fonction / API |
|---|---|---|
| `/inscription` | GET, POST | Formulaire et `POST /api/v1/auth/register` ; rôle membre uniquement |
| `/connexion` | GET, POST | Formulaire et `POST /api/v1/auth/login` |
| `/deconnexion` | POST | Révocation `POST /api/v1/auth/logout` et suppression du cookie |
| `/profil` | GET, POST | `GET /api/v1/me`, `PATCH /api/v1/me` pour le nom affiché |
| `/profil/mot-de-passe` | POST | `PUT /api/v1/me/password`, puis suppression du cookie et nouvelle connexion |
| `/administration` | GET | Liste paginée `GET /api/v1/users`, administrateur seulement |
| `/administration/utilisateurs/<id>` | POST | `PATCH /api/v1/users/<id>` ; rôle/statut seulement |

Templates : `account_auth.html`, `account_profile.html`, `account_admin.html`. Les messages sont échappés par Jinja. Aucun mot de passe ni bearer n'est inséré dans le HTML ou dans les URL. Les erreurs réaffichent l'identifiant mais vident les mots de passe.

Le bearer opaque réside dans un cookie distinct `cinevault_auth`, `HttpOnly`, `SameSite=Lax`, limité à huit heures. Activer `COOKIE_SECURE=true` sous HTTPS. Le frontend relaie ce cookie seulement vers l'URL API fixe configurée, avec `Authorization: Bearer`. Il ne suit aucune redirection HTTP de l'API. Le cookie de session Flask signé contient le jeton CSRF, jamais le bearer. Le secret de signature peut être fourni par `SECRET_KEY_FILE` (fichier privé d'au moins 32 octets), qui prime sur `SECRET_KEY`.

Chaque POST exige un jeton CSRF. Une connexion réussie renouvelle la session CSRF ; déconnexion et changement du secret ferment la session locale. Les permissions et l'expiration restent décidées par l'API, et non par les boutons affichés. Les en-têtes de sécurité sont définis dans la factory Flask. Les réponses des routes de comptes utilisent `Cache-Control: no-store`.

Validation : 18 tests web Windows et Linux. Ces tests simulent l'API ; une preuve distincte de 31 contrôles HTTP via les deux conteneurs réels est conservée dans le dossier d'intégration du workspace. Cette preuve utilise exclusivement des comptes fictifs et HTTP loopback. Les captures et parcours navigateur réels des nouveaux écrans restent à vérifier. Ne pas utiliser cette configuration HTTP pour de véritables comptes sur un réseau non fiable.
