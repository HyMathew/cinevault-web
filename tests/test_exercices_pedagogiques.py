"""Exercices A/B/C isolés. La chaîne JSON réelle est vérifiée séparément en intégration."""

import re

from app import create_app


class StubAPI:
    def __init__(self):
        self.data = None

    def create(self, data):
        self.data = {**data, "id": "exercice"}
        return self.data

    def get(self, film_id):
        return self.data if film_id == "exercice" else None


def make_client(api):
    return create_app(
        {"TESTING": True, "SECRET_KEY": "test-seulement", "API_CLIENT": api}
    ).test_client()


def test_exercice_a_page_html_simple_servie_sans_appel_api():
    client = make_client(object())
    response = client.get("/page-simple")
    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "<h1>Bienvenue dans CineVault</h1>" in response.get_data(as_text=True)


def test_exercice_b_formulaire_traitement_et_rendu_jinja():
    api = StubAPI()
    client = make_client(api)
    page = client.get("/films/nouveau")
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)
    response = client.post(
        "/films/nouveau",
        data={
            "csrf_token": token,
            "titre": "Les étoiles",
            "realisateur": "A. Martin",
            "annee": "2004",
            "acteurs": ["Alice", "Bob"],
            "support": "dvd",
            "synopsis": "Une fiction.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "<h1>Les étoiles</h1>" in response.get_data(as_text=True)
    assert api.data["annee"] == 2004
    assert api.data["acteurs"] == ["Alice", "Bob"]


def test_exercice_c_template_rend_et_echappe_donnees_de_reponse_api_simulee():
    api = StubAPI()
    api.data = {
        "id": "exercice",
        "titre": "Film <script>",
        "realisateur": "L. Martin",
        "annee": 2001,
        "acteurs": ["Camille"],
        "support": "dvd",
        "synopsis": "Texte JSON.",
    }
    response = make_client(api).get("/films/exercice")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "<h1>Film &lt;script&gt;</h1>" in html
    assert "Texte JSON." in html and "Camille" in html
