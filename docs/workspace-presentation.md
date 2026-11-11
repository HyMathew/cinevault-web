# Parcours personnels : activité, collection et compte

Cette présentation prolonge les tokens et composants natifs du
[catalogue membre](member-presentation.md), sans nouvelle dépendance ni image
de production. Les titres désignent la tâche : Mon profil pour les réglages,
Connexion et Créer un compte pour l’accès, Ma collection pour les entrées privées.
Les routes et la destination du parcours de connexion sont conservées.

## Priorités de lecture

Le tableau de bord ouvre par les prêts en cours, les demandes et les réservations
personnelles. Chaque valeur vient de la réponse statistique de l’API. Les liens
vers les emprunts et réservations transmettent `scope=mine`, y compris pour un
gestionnaire consultant son activité personnelle. Une échéance en retard n’est
signalée que lorsque l’API en compte réellement. Les totaux retournés et annulés,
la collection, l’activité retenue et le catalogue restent accessibles ; les
répartitions secondaires utilisent `details` natif.

Les listes de collection présentent le type, le titre complet et les opérations
existantes dans une même ligne sur ordinateur, puis dans le flux sur mobile.
Un filtre sans résultat se distingue d’une collection sans entrée. Les titres,
noms de liste et noms affichés longs restent lisibles et échappés par Jinja.
Les versions d’entrée, jetons CSRF et permissions de l’API restent les autorités
pour chaque mutation. Le formulaire ne transforme pas un conflit de version en
écrasement automatique.

Les emprunts regroupent les dates sans déplacer les actions hors du document.
Les réservations distinguent les contextes personnel et de gestion, conservent
le film et la limite lors d’un filtrage et n’affichent une disponibilité
prioritaire que lorsque la réponse API la fournit. Ces changements n’ajoutent
aucune requête API par ligne.

## Formulaires et accès

Le profil sépare les informations du compte du changement de mot de passe.
La fermeture de toutes les sessions reste annoncée avant la soumission. Les
attributs d’autocomplétion et les limites existantes sont conservés ; les secrets
ne sont jamais recopiés dans les champs après une erreur.

Le tiret littéral du motif HTML d’identifiant est échappé pour la compilation
avec le drapeau `v` définie par le
[standard HTML, attribut pattern](https://html.spec.whatwg.org/multipage/input.html#the-pattern-attribute).
Le motif précédent provoquait une erreur de compilation dans Chrome et cessait
de filtrer les identifiants côté navigateur. La politique serveur n’est pas
modifiée : la validation de formulaire reste une aide, jamais une autorisation.

## Portée des vérifications

`tests/test_workspace_presentation.py` vérifie l’ordre des informations, les
contextes et paramètres transmis, l’échappement, les versions et les champs
sensibles. La suite existante conserve les contrats API, le CSRF, les conflits,
la circulation et les routes pédagogiques.

La passe navigateur locale utilise de vrais écrans Flask/Jinja et une API
simulée avec des données fictives. Elle couvre 320, 390, 768 et 1280 px, les
transitions des formulaires, les annulations, les erreurs, les textes longs,
les états vides, Tab/Shift+Tab, les contrôles axe et les contrastes calculés.
Le reflow à 640 px est distingué d’un zoom natif complet. Cette preuve de
présentation ne démontre ni un déploiement, ni le backend Mongo, ni une
certification d’accessibilité. Les captures et reçus horodatés restent dans
le dossier de travail de la mission, hors code applicatif.
