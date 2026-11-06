"""Client HTTP du service de données ; aucune mutation n'est rejouée."""
from urllib.parse import quote

import requests


class APIError(Exception):
    def __init__(self, status, message, fields=None):
        super().__init__(message)
        self.status = status
        self.fields = fields or {}


class APIClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')

    def request(self, method, path, **kwargs):
        try:
            response = requests.request(method, self.base_url + path, timeout=(2, 5), allow_redirects=False, **kwargs)
        except requests.RequestException as exc:
            raise APIError(503, "Le service de données est indisponible.") from exc
        if 300 <= response.status_code < 400:
            raise APIError(503, 'Redirection inattendue du service de données.')
        if response.status_code >= 400:
            try:
                error = response.json().get('error', {})
            except (ValueError, AttributeError):
                error = {}
            if not isinstance(error, dict):
                error = {}
            raise APIError(response.status_code, error.get('message', 'Une erreur est survenue.'), error.get('fields'))
        if response.status_code == 204:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise APIError(503, "Réponse invalide du service de données.") from exc

    def list(self, q='', support=''):
        result = self.request('GET', '/api/films', params={'q': q, 'support': support})
        try:
            return result['films']
        except (KeyError, TypeError) as exc:
            raise APIError(503, 'Réponse invalide du service de données.') from exc

    def get(self, film_id):
        try:
            return self.request('GET', '/api/films/' + quote(film_id, safe=''))
        except APIError as exc:
            if exc.status == 404:
                return None
            raise

    def create(self, data):
        return self.request('POST', '/api/films', json=data)

    def update(self, film_id, data):
        return self.request('PUT', '/api/films/' + quote(film_id, safe=''), json=data)

    def delete(self, film_id):
        return self.request('DELETE', '/api/films/' + quote(film_id, safe=''))

    def register(self, data):
        return self.request('POST', '/api/v1/auth/register', json=data)

    def login(self, data):
        return self.request('POST', '/api/v1/auth/login', json=data)

    def account_request(self, token, method, path, **kwargs):
        return self.request(method, '/api/v1' + path, headers={'Authorization':'Bearer ' + token}, **kwargs)

    def me(self, token):
        profile = self.account_request(token, 'GET', '/me')
        if not isinstance(profile, dict) or set(profile) != {'id','username','display_name','role','enabled'} or any(not isinstance(profile[k], str) for k in ('id','username','display_name','role')) or profile['role'] not in ('member','manager','admin') or profile['enabled'] is not True:
            raise APIError(503, 'Profil invalide du service de données.')
        return profile

    def logout(self, token):
        return self.account_request(token, 'POST', '/auth/logout')

    def update_profile(self, token, data):
        return self.account_request(token, 'PATCH', '/me', json=data)

    def change_password(self, token, data):
        return self.account_request(token, 'PUT', '/me/password', json=data)

    def users(self, token, offset=0):
        return self.account_request(token, 'GET', '/users', params={'limit':50,'offset':offset})

    def update_user(self, token, user_id, data):
        return self.account_request(token, 'PATCH', '/users/' + quote(user_id, safe=''), json=data)
