import os
import secrets
import hmac
from pathlib import Path

from flask import Flask, abort, request, session

from .api_client import APIClient, APIError
from .forms import SUPPORTS


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY'), API_URL=os.environ.get('API_URL', 'http://cinevault-api:8000'), SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE', '').lower() == 'true', MAX_CONTENT_LENGTH=64 * 1024)
    if config:
        app.config.update(config)
    app.config.setdefault('ENTERPRISE_ENABLED', os.environ.get('ENTERPRISE_ENABLED', '').lower() == 'true')
    secret_file = app.config.get('SECRET_KEY_FILE') or os.environ.get('SECRET_KEY_FILE')
    if secret_file:
        app.config['SECRET_KEY'] = Path(secret_file).read_bytes()
        if len(app.config['SECRET_KEY']) < 32:
            raise RuntimeError('Le fichier de clé de session doit contenir au moins 32 octets.')
    if not app.config['SECRET_KEY']:
        raise RuntimeError('SECRET_KEY doit être défini avant le démarrage.')
    app.extensions['cinevault_api'] = app.config.get('API_CLIENT') or APIClient(app.config['API_URL'])

    @app.context_processor
    def context():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_urlsafe(32)
        return {'csrf_token': session['csrf_token'], 'supports': SUPPORTS}

    @app.before_request
    def verify_csrf():
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            expected = session.get('csrf_token', '')
            received = request.form.get('csrf_token', '')
            if not expected or not received.isascii() or not hmac.compare_digest(expected, received):
                abort(400, description='Formulaire expiré ou jeton de sécurité invalide.')

    from .routes import pages
    app.register_blueprint(pages)
    if app.config['ENTERPRISE_ENABLED'] is True:
        from .accounts import install_accounts
        install_accounts(app)

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        return response

    @app.errorhandler(APIError)
    def api_error(error):
        from flask import render_template
        app.logger.warning('Erreur du service de données : statut %s', error.status)
        status = 404 if error.status == 404 else 503
        return render_template('error.html', title='Film introuvable' if status == 404 else 'Service indisponible', message='Le film demandé est introuvable.' if status == 404 else 'Le service de données est indisponible. Réessayez plus tard.'), status

    @app.errorhandler(404)
    def not_found(error):
        from flask import render_template
        return render_template('error.html', title='Page introuvable', message='Cette page ou ce film est introuvable.'), 404

    return app
