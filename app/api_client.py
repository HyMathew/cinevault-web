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
            response = requests.request(method, self.base_url + path, timeout=(2, 5), **kwargs)
        except requests.RequestException as exc:
            raise APIError(503, "Le service de données est indisponible.") from exc
        if response.status_code >= 400:
            try:
                error = response.json().get('error', {})
            except (ValueError, AttributeError):
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
