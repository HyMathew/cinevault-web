from test_accounts import TOKEN, csrf
from test_accounts import accounts as accounts
from test_enterprise_catalogue import FILM

from app.api_client import APIError

ENTRY = {
    "id": "entry-id",
    "owner_id": "user-id",
    "movie_id": "film-id",
    "kind": "custom",
    "list_name": "<script>private</script>",
    "supports": [],
    "created_at": 0,
    "_etag": '"entry-version"',
}


def test_personal_pages_require_login_and_escape_private_content(accounts):
    client, api = accounts
    assert client.get("/ma-collection").status_code == 303
    api.collections.assert_not_called()
    client.set_cookie("cinevault_auth", TOKEN)
    api.collections.return_value = {
        "entries": [ENTRY],
        "total": 1,
        "limit": 24,
        "offset": 0,
        "movies": {
            "film-id": {"id": "film-id", "title": "Dune", "director": "Director", "year": 2021}
        },
    }
    response = client.get("/ma-collection?kind=custom")
    assert response.status_code == 200
    assert b"&lt;script&gt;private&lt;/script&gt;" in response.data
    assert b"<script>private</script>" not in response.data
    assert TOKEN.encode() not in response.data
    assert response.headers["Cache-Control"] == "no-store"
    api.collections.assert_called_once_with(TOKEN, kind="custom")


def test_personal_forms_do_not_relay_owner_and_preserve_errors(accounts):
    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    api.get.return_value = FILM
    token = csrf(client.get("/ma-collection/ajouter?film_id=film-id"))
    body = {
        "csrf_token": token,
        "film_id": "film-id",
        "kind": "owned",
        "list_name": "",
        "supports": ["dvd", "blu-ray"],
        "owner_id": "another-user",
    }
    assert client.post("/ma-collection/ajouter", data=body).status_code == 303
    api.create_entry.assert_called_once_with(
        TOKEN,
        {"movie_id": "film-id", "kind": "owned", "list_name": "", "supports": ["dvd", "blu-ray"]},
    )
    api.create_entry.side_effect = APIError(409, "duplicate")
    response = client.post("/ma-collection/ajouter", data=body)
    assert response.status_code == 409
    assert "déjà".encode() in response.data


def test_personal_edit_and_delete_relay_entity_version(accounts):
    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    api.get.return_value = FILM
    api.collection_entry.return_value = ENTRY
    token = csrf(client.get("/ma-collection/entry-id/modifier"))
    body = {"csrf_token": token, "list_name": "Soirées cinéma", "version": '"entry-version"'}
    assert client.post("/ma-collection/entry-id/modifier", data=body).status_code == 303
    api.update_entry.assert_called_once_with(
        TOKEN, "entry-id", {"list_name": "Soirées cinéma", "supports": []}, '"entry-version"'
    )
    assert (
        client.post(
            "/ma-collection/entry-id/retirer",
            data={"csrf_token": token, "version": '"entry-version"'},
        ).status_code
        == 303
    )
    api.delete_entry.assert_called_once_with(TOKEN, "entry-id", '"entry-version"')
    api.collection_entry.side_effect = APIError(404, "unavailable")
    assert client.get("/ma-collection/foreign-entry/modifier").status_code == 404
