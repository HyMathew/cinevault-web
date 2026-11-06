# Transfert du catalogue

Mode Enterprise uniquement. La page `/transfert` exige une session de gestionnaire ou administrateur. Les membres ordinaires reçoivent 403 ; une session absente est dirigée vers la connexion. L'API revérifie indépendamment les droits courants sous verrou.

Le navigateur transmet un fichier multipart au serveur web. Celui-ci lit au plus 1 Mio + 1 octet, vérifie UTF-8, puis transmet le contenu **dans un corps JSON** à l'API. Le web n'accède jamais au document de persistance. Les noms de fichiers reçus ne sont ni utilisés comme chemins, ni journalisés, ni affichés.

Le formulaire présente le format JSON/CSV et la politique de doublons. Le champ fichier est associé à une aide sur les limites ; les erreurs sont annoncées par `role=alert`, le résultat par `role=status`. Les formulaires utilisent la même protection CSRF que les autres mutations. Un succès donne les quatre nombres créés/ignorés et la référence d'opération ; une nouvelle clé est alors proposée pour le prochain import.

Une indisponibilité conserve la clé et les options. Le navigateur interdit de préremplir un champ fichier : l'utilisateur doit sélectionner le même fichier s'il répète un envoi incertain. Aucun retry automatique. L'API mémorise le résultat initial pendant 24 h ; changer le fichier ou les options avec la même clé entraîne 409. Après expiration, un nouvel import peut ajouter des exemplaires selon la politique choisie.

`GET /transfert/export?format=json|csv` obtient une enveloppe JSON de l'API et renvoie un téléchargement de nom fixe avec le type approprié et `Cache-Control: no-store`. Les en-têtes transmis par l'API ne sont pas recopiés arbitrairement. Aucun compte, collection privée, prêt ou secret dans ces transferts.

Les tests web utilisent une API simulée ; ils contrôlent rôle, CSRF, contenu transmis, clé conservée, encodage et téléchargement. La preuve d'intégration Compose vérifie séparément le parcours multipart → web → JSON API → document, le double envoi, le CSV, les erreurs sans ajout partiel et le redémarrage. Le contrôle visuel navigateur de cette nouvelle page reste à mener dans l'audit d'interface complet.
