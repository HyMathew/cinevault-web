# Écrans de gestion et d’enrichissement

Le formulaire de film sépare identité, synopsis, interprètes et genres. Les
exemplaires disposent d’un formulaire distinct. Les comptes sont présentés par
membre, avec leur formulaire de rôle et de statut ; import et export occupent
deux sections. La proposition externe présente son action de préremplissage
avant sa description, en précisant qu’elle n’enregistre rien. Les suggestions
gardent leurs disponibilités réelles et une explication du classement dépliable.

Les colonnes se replient sur mobile. Aucun appel API par ligne, dépendance,
JavaScript ou image n’est ajouté. Les listes réversibles, formulaires académiques,
CSRF, versions et clés d’opération restent utilisés.

## Corrections fonctionnelles

La soumission implicite par Entrée dans un champ simple choisit l’enregistrement.
Un premier bouton submit natif masqué évite que le navigateur choisisse le bouton
« Retirer acteur 1 » ; les boutons de liste restent explicitement utilisables sans
JavaScript. Le bouton masqué ne participe pas à la navigation au clavier.

Après un conflit ou une erreur d’édition, le lien vers les métadonnées conserve
l’identifiant du film tiré de la route, sans utiliser un identifiant soumis par
le formulaire. Les champs et l’ancienne version sont conservés pour comparaison.

Les erreurs incertaines d’ajout d’exemplaire ou d’import conservent la clé. Un
réessai reste manuel et réutilise les mêmes données ; l’import demande de choisir
à nouveau le fichier. Sa clé change seulement après confirmation du résultat.

## Vérifications du candidat

Le 11 novembre 2026, Chrome156 a exécuté 140 assertions, produit 58 captures et
contrôlé 17 états avec axe : aucune violation détectée. La campagne utilise le
vrai serveur Flask/Jinja et une API **simulée**, avec des données fictives.
Elle couvre 320, 390, 768 et 1280 pixels, les textes longs et états vides,
Tab/Shift+Tab/Entrée avec observation du contrôle actif, les erreurs 412/503,
le réessai, les rôles, l’import et le préremplissage sans écriture.

Les contrastes des couleurs calculées ont été mesurés pour le texte des champs,
les bordures et le bouton principal. Axe a laissé le contraste de certains champs
indéterminé dans quatre états ; leurs couleurs calculées et fonds hérités ont été
mesurés séparément, au-dessus des seuils retenus. Les neuf tests de présentation couvrent
notamment les deux régressions fonctionnelles corrigées. Ces résultats ne
constituent ni une conformité globale d’accessibilité ni une preuve MongoDB,
de TLS ou de déploiement. Les parcours avec une vraie API restent des campagnes
distinctes, liées à leurs révisions exactes.
