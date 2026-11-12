# Design de CineVault

Référence canonique pour les prochains lots de présentation. État décrit : WEB
`7d602d3`, 12 novembre 2026. Ce fichier conserve les choix acceptés ; les
[styles](app/static/style.css), [templates](app/templates/base.html) et contrats
serveur restent les preuves de l'implémentation. Toute évolution acceptée doit
garder ce document cohérent avec le produit, sans changer silencieusement sa
direction ni ses règles métier.

## Identité et densité

**Archive cinématographique contemporaine** : noir chaud, ivoire, ambre,
titres éditoriaux et contrôles sobres. Le contenu et les tâches structurent
l'écran ; pas de nouvelle identité, de décoration sans fonction ou de promesse
de lecture vidéo. La vidéothèque organise des œuvres et leurs exemplaires.

La [vue membre du catalogue](app/templates/enterprise_catalogue.html) privilégie
des lignes avec affiche, titre lisible et accès à la fiche. La vue de gestion
`view=manage`, réservée aux rôles autorisés, utilise un inventaire plus dense
avec réalisateur, année et exemplaires. Le rôle ne force pas toute navigation
dans la vue de gestion : les parcours personnels gardent `scope=mine`.

L'espace membre présente d'abord prêts, réservations et collection ; les
répartitions secondaires utilisent `details`. Les écrans de gestion regroupent
les champs par tâche : film et synopsis, exemplaire et état, attribution et
échéance, compte et permissions. Import et export restent distincts. Une
proposition de métadonnées préremplit un formulaire ; elle n'enregistre rien à
elle seule. Les recommandations montrent leurs raisons et les points reçus.

## Valeurs effectives

La cascade CSS contient des règles historiques puis les blocs CineVault 2.
Lire les dernières règles applicables avant de réutiliser une valeur.

| Jeton | Valeur | Usage |
|---|---|---|
| `--bg` | `#111011` | Fond et texte des boutons ambre/danger |
| `--surface` | `#1b1919` | Champs et surfaces secondaires |
| `--text` | `#f5eee5` | Texte principal |
| `--muted` | `#c9beb5` | Texte secondaire et placeholders opaques |
| `--accent` | `#f2a838` | Action principale, repères et focus |
| `--line` | `#48413d` | Séparateurs |
| `--control-border` | `#887b70` | Bordures de contrôles |
| `--danger` | `#ffb4ab` | Action de danger |
| `--success` | `#a9d6b0` | Jeton déclaré ; ne présume pas son emploi partout |

Corps et contrôles : Arial/Helvetica, 16 px, interligne 1,5. Titres et marque :
Georgia/Times. H1 courant : 44 px, ramené à 32 px sous 600 px ; certains
templates conservent une taille propre. Conteneur principal : 1184 px maximum,
marges adaptées par media queries. Les espacements récurrents sont 8, 12, 16,
24, 32 et 40 px ; ils sont des valeurs CSS existantes, pas une nouvelle échelle
de variables. Boutons et contrôles courants visent 44 px de hauteur minimale.

Le descriptif d'infrastructure v1, référencé au commit `f3d10cb`, précède cet
état. Ses tailles et mesures de contraste datées ne décrivent pas automatiquement
la présentation v2 et ne doivent pas être recopiées comme mesures actuelles.

## Composants et adaptation

Conserver liens pour naviguer, boutons pour agir, labels associés aux champs,
`fieldset`/`legend` pour les groupes, listes et tableaux avec leurs intitulés.
Le [socle commun](app/templates/base.html) fournit langue française, lien
d'évitement, navigation et contenu principal ; `aria-current` situe la page.
Menus, filtres secondaires et explications reposent sur `details`/`summary`.
Les [champs répétés](app/templates/_list_fields.html) sont des formulaires
serveur : préserver leurs valeurs originales et leur cycle ajouter/retirer.
Aucun JavaScript frontend supplémentaire n'est nécessaire pour ces parcours.

Garder l'ordre du document cohérent avec Tab/Shift+Tab/Entrée, le focus visible
de 3 px décalé de 3 px, les libellés d'action explicites et les messages proches
des champs. La couleur seule ne doit pas porter un état. Vérifier réellement le
clavier ; placer le focus par programme ne prouve pas qu'un contrôle est atteint.

Les grilles utilisent `minmax(0,1fr)` et le retour à la ligne pour les titres,
noms et références longs. Sous 850 px, plusieurs grilles deviennent une colonne
et la navigation passe par le menu natif ; sous 600 px, les formulaires se
réorganisent ; sous 350 px, affiche et contenu du catalogue se superposent.
Le tableau de gestion est réorganisé sur petit écran avec libellés visibles.
Contrôler 320, 390, 768 et 1280 px, textes longs, états vides et erreurs : ces
largeurs sont des points de vérification, pas une garantie universelle de reflow.
Conserver la règle `prefers-reduced-motion: reduce` existante.

## États métier et médias

Distinguer catalogue vide, filtres sans résultat, refus confirmé et résultat
incertain. Une réponse 503 après création peut suivre une écriture réussie :
la [reprise de prêt/réservation](docs/lending-recovery.md) conserve film, action
et même clé d'opération, propose de consulter son espace puis un réessai manuel.
Aucun succès, nouvel envoi ou rafraîchissement automatique. Les refus confirmés
conservent leur traitement ; une version ETag périmée demande comparaison et
rechargement volontaire, jamais une version fraîche réinjectée automatiquement.

Les formulaires gardent le CSRF, les versions et clés cachées nécessaires.
La clé de création est aléatoire et distincte du CSRF ; le compte vient de
l'identité authentifiée. Les droits sont contrôlés côté serveur, indépendamment
des boutons. La conservation de la clé par le web ne prouve pas le rejeu API :
celui-ci dépend des reçus du backend, limités à 24 h, et de sa validation réelle.

Afficher uniquement les médias validés par le [client API](app/api_client.py).
Une [affiche](app/templates/poster.html) garde auteur, licence et source,
dimensions réservées, chargement différé et absence de référent. Le navigateur
charge l'image Wikimedia directement. Sans affiche disponible, utiliser le
[repli typographique](app/templates/_poster_fallback.html), sans image inventée ;
le titre complet reste accessible dans le contenu de la fiche ou du catalogue.

## Vérification d'un prochain lot

Suivre les [contrôles qualité](docs/quality.md), puis inspecter les parcours
touchés, clavier, reflow et états d'erreur. Dater les captures et préciser si
l'API est simulée ou réelle. Ce document ne certifie ni performance mesurée,
pertinence des recommandations, conformité globale d'accessibilité, transport
TLS ou fonctionnement distribué. Une validation documentaire ne remplace pas
les tests d'interaction et les contrôles du backend.
