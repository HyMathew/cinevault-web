# Créations de prêts et réservations après un résultat incertain

Les formulaires natifs de création portent une clé d'opération aléatoire neuve
par rendu, distincte du jeton CSRF. Le POST web exige une seule clé ASCII URL-safe
de 16 à 128 caractères ; un ancien formulaire sans clé doit être rouvert. Le
compte provient de la session authentifiée, jamais d'un champ user_id soumis.
Le client HTTP transmet la clé dans Idempotency-Key pour ces deux créations.
Ses appels directs restent compatibles sans cet argument optionnel.

Sur une réponse503, le site conserve film, action et même clé dans une page de
reprise. Il propose d'abord de consulter ses emprunts ou réservations et la
disponibilité du film, puis de réessayer manuellement la même demande. Un éventuel
Retry-After est conservé. Aucun nouvel envoi, rafraîchissement ou succès n'est
déclenché automatiquement. La page est privée et no-store ; elle n'affiche ni
jeton d'authentification ni message technique du service amont.

Les refus confirmés gardent leurs statuts et traitements existants, dont le conflit
de réservation409. Les transitions de prêt/réservation conservent leurs ETag ; ce
lot n'ajoute ni reçu de transition ni relecture automatique d'une version fraîche.

L'API candidate C4 fournit des reçus de création limités à24h, par acteur et clé.
Ce raccord web dépend de cette API pour le rejeu réel : conserver une clé dans
un test web simulé ne prouve pas l'atomicité du backend. Un rechargement de la fiche
crée une nouvelle intention, et aucune idempotence indéfinie n'est garantie après
expiration des reçus. Les parcours réels avec C4 doivent être qualifiés séparément
avant une livraison commune.

La validation web comprend27nouveaux tests, les parcours existants et une revue
indépendante. La campagne de rendu utilise réellement Flask/Jinja et Chrome,
avec API explicitement simulée : comparaison avant/après à320/390/768/1280px,
reflow, huit scans axe, vrais Tab/Shift+Tab/Enter et vérification des appels après
réessai manuel. Elle ne constitue pas une preuve MongoDB, TLS, de tous navigateurs
ou de conformité globale d'accessibilité.
