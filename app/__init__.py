import hmac
import os
import secrets
from pathlib import Path

from flask import Flask, abort, request, session

from .api_client import APIClient, APIError
from .forms import SUPPORTS


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        API_URL=os.environ.get("API_URL", "http://cinevault-api:8000"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "").lower() == "true",
        MAX_CONTENT_LENGTH=64 * 1024,
    )
    if config:
        app.config.update(config)
    app.config.setdefault(
        "ENTERPRISE_ENABLED", os.environ.get("ENTERPRISE_ENABLED", "").lower() == "true"
    )
    secret_file = app.config.get("SECRET_KEY_FILE") or os.environ.get("SECRET_KEY_FILE")
    if secret_file:
        app.config["SECRET_KEY"] = Path(secret_file).read_bytes()
        if len(app.config["SECRET_KEY"]) < 32:
            raise RuntimeError("Le fichier de clé de session doit contenir au moins 32 octets.")
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("SECRET_KEY doit être défini avant le démarrage.")
    app.extensions["cinevault_api"] = app.config.get("API_CLIENT") or APIClient(
        app.config["API_URL"], enterprise=app.config["ENTERPRISE_ENABLED"] is True
    )

    @app.context_processor
    def context():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        from flask import g

        manager = not app.config["ENTERPRISE_ENABLED"] or bool(
            g.get("user") and g.user["role"] in ("manager", "admin")
        )
        return {"csrf_token": session["csrf_token"], "supports": SUPPORTS, "can_manage": manager}

    @app.before_request
    def verify_csrf():
        if request.endpoint == "transfer.catalogue":
            request.max_content_length = 2 * 1024 * 1024
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            expected = session.get("csrf_token", "")
            received = request.form.get("csrf_token", "")
            if (
                not expected
                or not received.isascii()
                or not hmac.compare_digest(expected, received)
            ):
                abort(400, description="Formulaire expiré ou jeton de sécurité invalide.")

    from .routes import pages

    app.register_blueprint(pages)
    if app.config["ENTERPRISE_ENABLED"] is True:
        from .accounts import install_accounts

        install_accounts(app)
        from .personal import bp as personal_bp

        app.register_blueprint(personal_bp)
        from .lending import bp as lending_bp

        app.register_blueprint(lending_bp)
        from .transfer import bp as transfer_bp

        app.register_blueprint(transfer_bp)
        from .insights import bp as insights_bp

        app.register_blueprint(insights_bp)
        from .metadata_views import bp as metadata_bp

        app.register_blueprint(metadata_bp)

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' https://upload.wikimedia.org https://thumb.wikimedia.org; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        return response

    @app.errorhandler(APIError)
    def api_error(error):
        from flask import render_template

        app.logger.warning("Erreur du service de données : statut %s", error.status)
        status = error.status if error.status in (401, 403, 404, 409, 412, 422, 428, 429) else 503
        title, message = {
            401: ("Connexion requise", "Votre session a expiré. Connectez-vous à nouveau."),
            403: ("Accès interdit", "Votre rôle ne permet pas cette action."),
            404: (
                "Élément introuvable",
                "L’élément demandé est introuvable ou n’est pas accessible.",
            ),
            409: ("Opération impossible", "Des données liées empêchent cette opération."),
            412: (
                "Données modifiées",
                "Rechargez la ressource et vérifiez les changements avant de réessayer.",
            ),
            422: ("Données invalides", "Vérifiez les champs ou les filtres utilisés."),
            428: ("Version requise", "Rechargez le formulaire avant de réessayer."),
            429: ("Trop de tentatives", "Réessayez dans quelques minutes."),
            503: (
                "Service indisponible",
                "Le service de données est indisponible. Avant de répéter une modification, vérifiez son résultat lorsque le service revient.",
            ),
        }[status]
        return render_template("error.html", title=title, message=message), status

    @app.errorhandler(404)
    def not_found(error):
        from flask import render_template

        return render_template(
            "error.html", title="Page introuvable", message="Cette page ou ce film est introuvable."
        ), 404

    return app
