# Présentation membre et navigation

Le catalogue Enterprise présente les films sous forme de lignes média : affiche autorisée lorsqu'elle est fournie par le client existant, sinon visuel typographique local. Le titre complet, le réalisateur, l'année, le nombre total d'exemplaires et les supports proviennent des données API. Le nombre d'exemplaires ne devient jamais une disponibilité déduite.

La direction conserve le fond noir chaud, les titres Georgia ivoire et l'action ambre. Les contrôles utilisent Arial/Helvetica ; aucune police distante, bibliothèque de composants ou dépendance JavaScript de production n'est ajoutée. La référence de conception est `member-catalogue-concept-v2.png`, conservée dans les documents de design du projet d'infrastructure. Le système de présentation de ce projet précise les différences intentionnelles avec cette maquette : contenu limité à 1184 px, H1 de 44 px, visuel de 160 × 240 px et contrôles explicites de 44 px minimum. La navigation secondaire et le bouton « Trier » sont nécessaires pour garder les destinations et la soumission sans JavaScript.

## Navigation et permissions

Le visiteur conserve Accueil, Catalogue et Connexion. Le membre accède à Catalogue, Ma collection, Mon espace, Mon profil ainsi qu'à Découvrir, Emprunts, Réservations et Déconnexion dans Menu. Mon profil désigne les réglages ; Mon espace désigne le tableau de bord.

Les gestionnaires et administrateurs disposent d'un lien Gestion vers `/films?view=manage`. Ce choix de présentation est validé côté web : seuls ces deux rôles peuvent afficher l'inventaire. La valeur `view` est contrôlée et retirée avant l'appel API. Les filtres et la pagination gardent cette valeur. L'API reste l'autorité pour toutes les permissions et mutations.

Le contexte gestion présente Inventaire, Emprunts, Réservations, Statistiques, Import / export et Administration pour l'administrateur. Le lien Espace membre restitue le catalogue membre. Pour les écrans de circulation existants, l'absence de `scope` conserve leur contexte de gestion pour les rôles autorisés ; `scope=mine` restitue le contexte personnel.

Menu est un `details` natif fermé au départ. Les destinations principales visibles sur ordinateur sont masquées sur petit écran ; leurs variantes mobiles n'entrent dans la navigation au clavier qu'une fois Menu ouvert. Aucun élément fermé n'est forcé visible par CSS. Le menu se déploie dans le flux, sans overlay ni piège de focus. Les liens actifs visibles sont soulignés et portent `aria-current`. Les variantes masquées ne sont pas des doublons atteignables au clavier.

Le pied de page Enterprise porte « Vidéothèque collaborative » sans lien vers le parcours pédagogique. Le mode académique conserve le lien Page simple, sa route et ses exercices. Les deux présentations ne proposent donc pas au membre un changement implicite vers le parcours legacy.

## Recherche et fiche

La recherche, les filtres et le tri restent un formulaire GET. Les filtres secondaires actifs restent ouverts. Rechercher, Appliquer les filtres et Trier sont des soumissions explicites ; une nouvelle recherche repart au début des résultats et garde la limite demandée. Les liens de fiche transmettent un retour vers les critères du catalogue. Ce retour est limité au chemin local `/films` et à sa chaîne de paramètres ; aucune destination externe n'est acceptée.

La fiche place la disponibilité réelle, le prêt ou la réservation, et l'accès à la collection avant le synopsis. Les branches existantes restent distinctes : visiteur, demande en attente, prêt actif, réservation en attente ou prête, aucun exemplaire disponible. Les actions de gestion viennent ensuite. CSRF, versions d'exemplaires, autorisations et soumissions serveur restent inchangés.

Le titre principal et le titre de résultat ne sont jamais tronqués. Seul le titre décoratif répété dans le visuel de remplacement est limité en lignes pour garder son ratio 2:3 ; ce doublon est exclu de l'arbre accessible. À 320 px, le visuel et le texte s'empilent. Les libellés mobiles de l'inventaire sont du texte HTML réel, en complément des en-têtes du tableau.

## Vérification et portée

Les tests `tests/test_member_presentation.py` vérifient les frontières de rôle, les paramètres transmis à l'API, le retour local filtré, la cohérence des contextes et l'ordre de l'action de fiche. Ils complètent la suite existante de contrats, CSRF, collections, circulation et mode pédagogique.

La passe navigateur locale du 10 novembre 2026 utilise Playwright 1.64.1 et un profil Chrome isolé. Les données et réponses API sont des fixtures synthétiques ; il s'agit d'une validation réelle du rendu web, pas d'une validation interservices ou de production. Les captures avant/après utilisent le même film fictif et les mêmes dimensions. Les preuves détaillées, mesures, contrôles axe-core 4.11.0, parcours Tab/Shift+Tab et empreintes sont conservés dans le dossier de travail de la mission, hors source applicative. Aucun compte réel ni secret n'y est enregistré.

La passe couvre 320, 390, 768, 1280 et 1402 px, menu et filtres ouverts/fermés, titres longs, vide réel, recherche sans résultat, erreur 503 et les rôles membre/gestionnaire/administrateur. Le reflow à 640 et 320 px est distinct d'un zoom natif complet du navigateur. Une passe axe sans violation ne certifie pas WCAG ; lecteur d'écran, autres moteurs de navigateur, affiches externes et validation interservices restent des contrôles séparés.

Les parcours du tableau de bord, des collections, de la circulation personnelle et du compte sont détaillés dans [Parcours personnels](workspace-presentation.md).
