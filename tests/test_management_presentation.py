"""Management presentation keeps versions, operation keys and source text exact."""

import io
import json
import re
from html import unescape
from unittest.mock import Mock

import pytest

from app import create_app
from app.api_client import APIError

FILM = {
    "id": "film-id",
    "titre": "Film de test",
    "annee": 2026,
    "realisateur": "Créateur",
    "acteurs": ['Nom, "deux"', "Nom\r\ntexte", "Nom\0fin", "🎬"],
    "genres": ["Genre, précis"],
    "synopsis": "Synopsis conservé",
    "copy_count": 1,
    "copies": [],
    "_etag": '"film-v1"',
}


@pytest.fixture
def management():
    api = Mock()
    api.me.return_value = {
        "id": "user-id",
        "username": "gestion",
        "display_name": "Gestionnaire",
        "role": "manager",
        "enabled": True,
    }
    api.get.return_value = FILM.copy()
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "synthetic-management-presentation-key-32plus",
            "ENTERPRISE_ENABLED": True,
            "API_CLIENT": api,
        }
    )
    client = app.test_client()
    client.set_cookie("cinevault_auth", "synthetic-management-bearer-token-12345")
    return client, api


def hidden(page, name):
    return unescape(re.search(r'name="' + name + r'" value="([^"]*)"', page).group(1))


def test_film_form_groups_identity_description_and_preserves_reversible_lists(management):
    client, api = management
    page = client.get("/films/film-id/modifier").get_data(as_text=True)
    assert 'class="management-form movie-editor"' in page
    assert 'aria-labelledby="movie-identity"' in page
    assert 'aria-labelledby="movie-description"' in page
    assert 'href="/films?view=manage"' in page
    assert json.loads(hidden(page, "_original_acteurs")) == FILM["acteurs"]
    assert hidden(page, "version") == FILM["_etag"]
    assert page.count('name="acteurs"') == 4
    assert 'value="add:acteurs"' in page and "formnovalidate" in page


def test_implicit_movie_submission_defaults_to_save_instead_of_list_removal(management):
    client, _ = management
    for route in ("/films/nouveau", "/films/film-id/modifier"):
        page = client.get(route).get_data(as_text=True)
        form = re.search(
            r'<form[^>]*class="management-form movie-editor"[^>]*>(.*?)</form>', page, re.S
        ).group(1)
        first_button = re.search(r"<button\b[^>]*>", form).group()
        assert 'type="submit"' in first_button and 'name="list_action"' not in first_button


def test_edit_conflict_keeps_metadata_link_bound_to_route_film(management):
    client, api = management
    page = client.get("/films/film-id/modifier").get_data(as_text=True)
    api.update.side_effect = APIError(412, "stale")
    response = client.post(
        "/films/film-id/modifier",
        data={
            "csrf_token": hidden(page, "csrf_token"),
            "version": FILM["_etag"],
            "titre": "Titre conservé",
            "realisateur": "Auteur",
            "annee": "2026",
            "acteurs": ["Acteur"],
            "genres": ["Genre"],
            "id": "untrusted-other-film",
        },
    )
    assert response.status_code == 412
    assert 'href="/metadonnees?movie_id=film-id"' in response.get_data(as_text=True)


def test_film_validation_displays_synopsis_error_without_discarding_text(management):
    client, api = management
    page = client.get("/films/nouveau").get_data(as_text=True)
    response = client.post(
        "/films/nouveau",
        data={
            "csrf_token": hidden(page, "csrf_token"),
            "titre": "Titre conservé",
            "realisateur": "Auteur",
            "annee": "2026",
            "support": "dvd",
            "acteurs": ["Acteur"],
            "genres": ["Genre"],
            "synopsis": "x" * 4001,
        },
    )
    text = response.get_data(as_text=True)
    assert response.status_code == 422
    assert 'id="synopsis-error"' in text and 'aria-describedby="synopsis-error"' in text
    assert "Titre conservé" in text and "x" * 4001 in text
    api.create.assert_not_called()


def test_copy_uncertain_result_retains_operation_key_and_values(management):
    client, api = management
    page = client.get("/films/film-id/exemplaires/nouveau").get_data(as_text=True)
    api.create_copy.side_effect = APIError(503, "unconfirmed")
    key = hidden(page, "operation_key")
    response = client.post(
        "/films/film-id/exemplaires/nouveau",
        data={
            "csrf_token": hidden(page, "csrf_token"),
            "operation_key": key,
            "support": "dvd",
            "location": "Rayon conservé",
            "condition": "good",
        },
    )
    text = response.get_data(as_text=True)
    assert response.status_code == 503
    assert 'class="management-form compact-editor"' in text
    assert hidden(text, "operation_key") == key and 'value="Rayon conservé"' in text
    assert "Annuler" in text


def test_admin_rows_keep_individual_labeled_forms_and_empty_state(management):
    client, api = management
    api.me.return_value["role"] = "admin"
    api.users.return_value = {"users": [], "total": 0, "offset": 0, "limit": 24}
    page = client.get("/administration").get_data(as_text=True)
    assert "Aucun compte à afficher." in page
    api.users.return_value = {
        "users": [{**api.me.return_value, "id": "account-id"}],
        "total": 1,
        "offset": 0,
        "limit": 24,
    }
    page = client.get("/administration").get_data(as_text=True)
    assert 'class="member-admin-row"' in page
    assert 'action="/administration/utilisateurs/account-id"' in page
    assert 'for="role-account-id"' in page and 'for="enabled-account-id"' in page


def test_transfer_sections_keep_uncertain_import_key_and_options(management):
    client, api = management
    page = client.get("/transfert").get_data(as_text=True)
    assert 'class="transfer-columns"' in page and 'class="csv-structure"' in page
    key = hidden(page, "operation_key")
    api.import_catalogue.side_effect = APIError(503, "unconfirmed")
    response = client.post(
        "/transfert",
        data={
            "csrf_token": hidden(page, "csrf_token"),
            "operation_key": key,
            "format": "csv",
            "duplicate_policy": "skip",
            "file": (io.BytesIO(b"header"), "fixture.csv"),
        },
    )
    text = response.get_data(as_text=True)
    assert response.status_code == 503 and hidden(text, "operation_key") == key
    assert 'value="csv" selected' in text and 'value="skip" selected' in text


def test_preview_prefill_is_distinguished_from_save_and_stale_remains_visible(management):
    client, api = management
    api.metadata_detail.return_value = {
        "film": {
            "id": "Q123",
            "title": "Proposition",
            "director": "Auteur",
            "year": 2026,
            "actors": ["Acteur"],
            "genres": ["Genre"],
            "description": "Description",
            "poster": None,
            "warnings": [],
            "revision": 1,
        },
        "cache": {"status": "stale"},
    }
    page = client.get("/metadonnees/Q123?movie_id=film-id").get_data(as_text=True)
    assert "Aucune donnée ne sera enregistrée à cette étape." in page
    assert "cache ancien" in page and "Synopsis conservé" not in page
    assert page.index("Préremplir le formulaire") < page.index("Description courte")
    assert "metadata_id=Q123" in page
    api.update.assert_not_called()


def test_discovery_keeps_reason_and_actual_availability(management):
    client, api = management
    api.me.return_value["role"] = "member"
    api.recommendations.return_value = {
        "recommendations": [
            {
                "movie": {"id": "film-id", "title": "Film", "director": "Auteur", "year": 2026},
                "available_copies": 0,
                "score": 5,
                "reasons": [{"label": "Genre choisi", "points": 5}],
            }
        ],
        "personalized": True,
        "total": 1,
        "limit": 12,
    }
    page = client.get("/decouvrir").get_data(as_text=True)
    assert 'class="recommendation-entry"' in page
    assert "Genre choisi" in page and "0 exemplaire" in page
    assert "Voir le film" in page and "Détail du classement" in page
