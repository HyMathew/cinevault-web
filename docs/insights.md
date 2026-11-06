# Votre espace et découverte

En mode Enterprise, le lien « Mon espace » donne accès à `/mon-espace`. L'utilisateur retrouve son profil, sa collection et ses emprunts, les totaux réels du catalogue et ses indicateurs personnels. La « Vue de gestion » est explicitement réservée aux gestionnaires/administrateurs. Les agrégats personnels restent ceux du compte connecté dans cette vue, sans sélecteur d'un autre utilisateur. L'API revérifie les droits.

La page `/decouvrir` montre les recommandations, disponibilités et contributions au score. Un formulaire GET permet un choix temporaire de genre ; aucune préférence n'est écrite dans le compte. Les favoris, vus et prêts retournés donnent les références propres ; la liste à voir ajoute un signal direct. L'interface affiche le fonctionnement, les points, l'état vide et l'absence de personnalisation au démarrage. Les collections des autres utilisateurs ne sont pas employées.

Le serveur web interroge exclusivement les routes JSON `/api/v1/statistics` et `/api/v1/recommendations` avec bearer. Aucune lecture du stockage, aucun calcul de score dans le template. Toutes les pages de ce parcours authentifié sont `no-store` ; les libellés de films, genres et raisons sont échappés par Jinja. Les erreurs d'API suivent les pages d'erreur communes sans répétition automatique.

Les tests web isolent l'API pour contrôler l'accès, la portée, les paramètres, les valeurs affichées et XSS. L'intégration HTTP Compose distincte couvre les vrais favoris, les agrégats d'un autre compte sans ses données privées, le choix de genre, le démarrage sans historique et la reprise après redémarrage. Le contrôle visuel navigateur, les dimensions et l'audit complet d'accessibilité restent à réaliser sur ces écrans.
