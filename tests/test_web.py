import re

import pytest

from app import create_app
from app.api_client import APIError


FILM = {"id": "abc", "titre": "<script>alert(1)</script>", "annee": 2001, "realisateur": "A. Martin", "acteurs": [], "support": "dvd", "synopsis": "Un récit."}


class FakeAPI:
    def __init__(self):
        self.films = [FILM.copy()]
        self.unavailable = False

    def list(self, q="", support=""):
        if self.unavailable:
            raise APIError(503, "Service indisponible")
        return [f for f in self.films if q.lower() in f["titre"].lower() and (not support or f["support"] == support)]

    def get(self, film_id):
        if self.unavailable:
            raise APIError(503, 'Service indisponible')
        return next((f for f in self.films if f["id"] == film_id), None)

    def create(self, data):
        film = dict(data, id="new")
        self.films.append(film)
        return film

    def update(self, film_id, data):
        if self.unavailable:
            raise APIError(503, 'Service indisponible')
        if not any(f['id'] == film_id for f in self.films):
            raise APIError(404, 'Absent')
        self.films = [dict(data, id=film_id) if f["id"] == film_id else f for f in self.films]
        return dict(data, id=film_id)

    def delete(self, film_id):
        self.films = [f for f in self.films if f["id"] != film_id]


@pytest.fixture
def setup():
    api = FakeAPI()
    app = create_app({"TESTING": True, "SECRET_KEY": "test-only-key", "API_CLIENT": api})
    return app.test_client(), api


def csrf(response):
    return re.search(rb'name="csrf_token" value="([^"]+)"', response.data).group(1).decode()


def valid(token):
    return {"csrf_token": token, "titre": "Nouveau film", "annee": "2000", "realisateur": "Martin", "acteurs": "A, B", "support": "dvd", "synopsis": "Résumé"}


def test_catalogue_escapes_user_content_and_filters(setup):
    client, _ = setup
    response = client.get('/films?q=script&support=dvd')
    assert response.status_code == 200
    assert b'&lt;script&gt;' in response.data
    assert b'<script>alert' not in response.data
    assert 'Réalisateur'.encode() in response.data


def test_create_validates_csrf_and_data_then_redirects(setup):
    client, api = setup
    assert client.post('/films/nouveau', data={}).status_code == 400
    token = csrf(client.get('/films/nouveau'))
    invalid = valid(token) | {"titre": "", "annee": "1890x"}
    response = client.post('/films/nouveau', data=invalid)
    assert response.status_code == 422
    assert 'Martin'.encode() in response.data
    response = client.post('/films/nouveau', data=valid(token))
    assert response.status_code == 303
    assert response.headers['Location'].endswith('/films/new')
    assert api.films[-1]['acteurs'] == ['A', 'B']


def test_edit_and_delete_are_post_with_csrf(setup):
    client, api = setup
    token = csrf(client.get('/films/abc/modifier'))
    response = client.post('/films/abc/modifier', data=valid(token))
    assert response.status_code == 303
    assert api.get('abc')['titre'] == 'Nouveau film'
    assert client.get('/films/abc/supprimer').status_code == 200
    assert client.post('/films/abc/supprimer').status_code == 400
    assert client.post('/films/abc/supprimer', data={'csrf_token': token}).status_code == 303
    assert api.get('abc') is None


def test_missing_film_and_unavailable_api_are_truthful(setup):
    client, api = setup
    assert client.get('/films/inconnu').status_code == 404
    api.unavailable = True
    response = client.get('/films')
    assert response.status_code == 503
    assert 'indisponible'.encode() in response.data.lower()


def test_edit_preserves_entered_values_if_api_is_unavailable(setup):
    client, api = setup
    token = csrf(client.get('/films/abc/modifier'))
    api.unavailable = True
    response = client.post('/films/abc/modifier', data=valid(token))
    assert response.status_code == 503
    assert b'Nouveau film' in response.data


def test_edit_deleted_film_returns_404(setup):
    client, api = setup
    token = csrf(client.get('/films/abc/modifier'))
    api.films.clear()
    assert client.post('/films/abc/modifier', data=valid(token)).status_code == 404
