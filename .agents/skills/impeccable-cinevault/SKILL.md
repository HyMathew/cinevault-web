---
name: impeccable-cinevault
description: Use when auditing or polishing the rendered CineVault Flask/Jinja interface, especially navigation, hierarchy, responsive layout, contrast, focus, and form states. Not for API security audits or a framework migration.
license: Apache-2.0
---

# Impeccable adapté à CineVault

Méthodologie Impeccable adaptée ; moteur natif non exécuté. Cette entrée autonome adapte audit/polish, sans moteur, détecteur, hook, stockage de critique ni téléchargement. [Attribution et modifications](ATTRIBUTION.md) ; [licence](LICENSE) ; [notice amont conservée](NOTICE.md).

## Audit fondé sur les preuves

Lire le design et les conventions existantes, puis observer une vraie page et sa tâche avant de conclure. Conserver rôle, route, filtres, viewport, état de données et version. Distinguer capture applicative et maquette ImageGen ; ne pas créer de films, chiffres, affiches ou états pour embellir une capture.

Examiner hiérarchie et intégrité produit, accessibilité, coût client, tokens et responsive. Pour chaque défaut, donner emplacement, preuve, impact, gravité proportionnée et vérification attendue. Relever aussi les éléments utiles à préserver. Une hypothèse de performance n'est pas une mesure ; une capture seule ne prouve ni clavier ni tactile. Ne produire aucun score global ni déclaration de conformité sans méthode et résultats correspondants.

Utiliser le navigateur disponible pour les interactions, Playwright/axe lorsque pertinents. Faire de vrais Tab/Shift+Tab et observer l'élément actif avant activation ; un appel à `focus()` ne prouve pas l'atteignabilité. Calculer les contrastes des couleurs réellement utilisées, tester zoom, reduced motion et reflow à 320/390/768/1280. La cible produit de 44 px pour les contrôles n'est pas présentée comme le seuil minimal universel WCAG AA.

## Polish dans le périmètre autorisé

Classer la cause : token manquant, composant partagé contourné, erreur de hiérarchie ou défaut local. Corriger au niveau le plus étroit, d'abord tâches bloquées/états trompeurs, puis erreurs et récupération, responsive/hiérarchie, enfin finition. Un audit seul reste en lecture ; une demande de correction autorise les changements réversibles nécessaires sans microconfirmation.

Préserver les deux contextes membre/gestion, routes legacy et Page simple, tous les parcours existants, les états sans affiche et les données exactes. Quantité d'exemplaires n'est pas disponibilité. Ne pas ajouter de requête API par ligne pour inventer un statut de catalogue. Garder CSRF, droits serveur, ETag/version, refus 412/503, import incertain et réessai manuel.

Après correction, parcourir la tâche complète, erreurs et retour compris. Comparer avant/après aux mêmes données et dimensions ; comparer concept et rendu lorsqu'un concept existe. Consigner écarts, corrections, mesures exécutées et limites. Un état sans erreur console ou un axe propre ne remplace pas le contrôle visuel et interactif. Ne pas redessiner silencieusement une autre surface au nom du polish.
