from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from test_accounts import PROFILE, TOKEN
from test_accounts import accounts as accounts

from app import create_app


def test_suggestions_use_public_catalogue_and_project_a_bounded_response(accounts):
    client, api = accounts
    api.search.return_value = {
        "films": [
            {
                "id": f"film-{i}",
                "titre": "Étoiles",
                "annee": 2025,
                "realisateur": "Artiste",
                "copies": [{"location": "Réserve"}],
            }
            for i in range(6)
        ],
        "total": 12,
    }

    response = client.get("/recherche/films", query_string={"q": "  Étoiles  "})
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json["total"] == 12 and len(response.json["films"]) == 5
    first = response.json["films"][0]
    assert first == {
        "title": "Étoiles",
        "year": 2025,
        "director": "Artiste",
        "url": first["url"],
    }
    target = urlsplit(first["url"])
    assert target.path == "/films/film-0"
    catalogue = urlsplit(parse_qs(target.query)["return_to"][0])
    assert catalogue.path == "/films" and parse_qs(catalogue.query) == {"q": ["Étoiles"]}
    api.search.assert_called_once_with(q="Étoiles", limit=5)
    api.me.assert_not_called()
    api.loans.assert_not_called()
    api.reservations.assert_not_called()


@pytest.mark.parametrize(
    "query", ["", "?q=x", "?q=%20%20", "?q=du&q=ne", "?q=du&scope=all", "?q=" + "é" * 201]
)
def test_invalid_suggestions_do_not_query_api(accounts, query):
    client, api = accounts
    assert client.get("/recherche/films" + query).status_code == 422
    api.search.assert_not_called()


@pytest.mark.parametrize("role", [None, "member", "manager", "admin"])
def test_destinations_are_rendered_for_the_current_server_role(accounts, role):
    client, api = accounts
    api.search.return_value = {"films": [], "total": 0, "limit": 5, "offset": 0}
    if role:
        client.set_cookie("cinevault_auth", TOKEN)
        api.me.return_value = {**PROFILE, "role": role}

    page = client.get("/").get_data(as_text=True)
    dialog = page.split('<dialog id="quick-search"', 1)[1].split("</dialog>", 1)[0]
    assert 'href="/films"' in dialog
    assert ('href="/ma-collection"' in dialog) is bool(role)
    assert ('href="/emprunts?scope=mine"' in dialog) is bool(role)
    assert ('href="/reservations?scope=mine"' in dialog) is bool(role)
    assert ('href="/decouvrir"' in dialog) is bool(role)
    assert ('href="/films?view=manage"' in dialog) is (role in {"manager", "admin"})
    assert ('href="/films/nouveau"' in dialog) is (role in {"manager", "admin"})
    assert ('href="/reservations?scope=all"' in dialog) is (role in {"manager", "admin"})
    assert ('href="/administration"' in dialog) is (role == "admin")
    assert ('href="/connexion"' in dialog) is (role is None)


def test_academic_web_does_not_load_or_register_search_behavior():
    api = Mock()
    api.list.return_value = []
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "synthetic-unit-test-session-key-32-bytes-minimum",
            "ENTERPRISE_ENABLED": False,
            "API_CLIENT": api,
        }
    )
    client = app.test_client()
    page = client.get("/").get_data(as_text=True)
    assert "quick-search" not in page
    assert client.get("/recherche/films?q=du").status_code == 404
    api.search.assert_not_called()
