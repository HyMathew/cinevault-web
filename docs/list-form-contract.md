# Listes dans les formulaires de films

Les acteurs et genres utilisent des champs texte indépendants : une valeur par champ. Les virgules, guillemets, barres obliques inverses, caractères Unicode et retours à la ligne internes appartiennent à cette valeur. Les boutons Ajouter et Retirer soumettent uniquement une présentation du formulaire, avec les mêmes contrôles de session, de droits et de CSRF ; ils n'enregistrent aucun film.

Une liste contient au plus 30 éléments (120 caractères par acteur, 80 par genre). Un champ laissé vide n'ajoute aucun élément. L'ordre et les doublons sont conservés. Les validations métier du service de données restent applicables. Les formulaires transmettent toujours la version reçue pour la détection des conflits.

Les navigateurs normalisent les retours à la ligne des champs texte. Une copie JSON cachée de chaque liste conserve les originaux : un élément original est réutilisé seulement si son texte normalisé CRLF/CR vers LF correspond exactement au champ soumis normalisé. La comparaison tient aussi compte du remplacement HTML de NUL par U+FFFD, car l'API accepte ce caractère. Sinon, la nouvelle valeur utilise LF. Cette copie n'est pas une preuve d'identité, de version ou de validité ; ses types, limites et encodage sont vérifiés, et les valeurs reconstruites passent les validations habituelles. Une copie absente ou invalide est ignorée. Ajout et retrait reconstruisent d'abord les valeurs, puis renvoient les originaux correspondant aux nouveaux indices.

Les limites sont vérifiées côté serveur en caractères Unicode. Les nouveaux champs n'utilisent pas `maxlength`, qui compterait les unités UTF-16 dans le navigateur et interdirait certains noms valides composés de caractères hors du plan multilingue de base. Les erreurs indiquent la limite métier et conservent le texte saisi.

## Limites de transport

Le formulaire film dispose d'un plafond ciblé de 256 Kio ; le plafond global reste 64 Kio. Au maximum métier Enterprise, titre, réalisateur, acteurs, genres et synopsis totalisent 10 320 caractères. Leur encodage URL peut occuper 123 840 octets ; les 6 000 caractères des listes copiés en JSON ASCII caché ajoutent au plus 96 000 octets encodés URL, plus les noms des champs et séparateurs. Ce majorant reste sous 256 Kio. Un caractère astral peut occuper douze caractères JSON ASCII, et non six ; la borne des originaux en tient compte. Le nombre d'éléments et leurs longueurs sont toujours revalidés.

Les seules mutations de films (`POST`/`PUT` sous `/api/films` et `/api/v1/movies`) transmettent leur JSON en UTF-8, avec le type de contenu JSON explicite et les mêmes en-têtes d'identité/version. Le JSON métier maximal reste sous le plafond API de 65 536 octets ; l'échappement ASCII par défaut aurait pu le dépasser. Les autres appels gardent leur sérialisation existante. Les tests préparent réellement le corps HTTP avec Requests et appliquent le plafond amont ; ils ne remplacent pas une intégration avec le service API réel.

Un champ CSV ou un champ avec une ligne par valeur ne permettrait pas de distinguer les séparateurs des virgules et retours à la ligne légitimes. Une nouvelle lecture de l'API pour reconstruire les originaux introduirait une dépendance supplémentaire et pourrait mélanger deux versions. Le formulaire conserve donc son propre état, sans JavaScript ni nouvelle dépendance.

## Vérification et plan d'exécution

1. Écrire des régressions de lecture, soumission et réaffichage avec des caractères ambigus, CR, LF et CRLF ; constater les échecs avant modification.
2. Lire les champs répétés avant toute conversion en dictionnaire ; reconstruire les originaux bornés et traiter les actions de présentation sans mutation.
3. Partager le rendu accessible des listes entre les formulaires legacy et Enterprise ; conserver les listes des métadonnées sans jointure.
4. Vérifier limites, champs cachés mal formés, droits, CSRF, conflits, erreurs amont et nombre de mutations ; conserver les preuves RED/GREEN sous reports.
5. Adapter uniquement les anciennes fixtures CSV au nouveau contrat (deux champs pour deux valeurs), puis exécuter la suite complète et les contrôles qualité du dépôt. L'intégration avec une vraie API reste une vérification distincte.
