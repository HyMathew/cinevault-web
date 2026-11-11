"""Personal task hierarchy and context preserve the existing API boundary."""

import re
from html import unescape

from test_accounts import PROFILE, TOKEN
from test_accounts import accounts as accounts
from test_personal import ENTRY


def stats():
    return {
        "catalogue": {
            "movies": 1,
            "copies": 3,
            "available": 1,
            "held_for_queue": 1,
            "damaged": 1,
            "by_support": {"dvd": 3},
            "by_genre": {"Drame": 1},
        },
        "personal": {
            "collection_movies": 1,
            "collection_entries": 5,
            "by_kind": {},
            "by_owned_support": {},
            "loans": {"pending": 2, "active": 1},
            "overdue": 1,
            "waiting_reservations": 3,
            "activity_retained": 0,
            "activity_last_7_days": 0,
            "recent_activity": [],
        },
    }


def test_dashboard_prioritizes_personal_actions_and_scopes_links(accounts):
    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    api.me.return_value = {**PROFILE, "role": "manager"}
    api.statistics.return_value = stats()
    page = client.get("/mon-espace").get_data(as_text=True)
    assert page.index("Vos emprunts et réservations") < page.index("Le catalogue partagé")
    assert 'href="/emprunts?scope=mine' in page
    assert 'href="/reservations?scope=mine' in page
    assert 'aria-label="Votre activité personnelle"' in page
    assert 'aria-label="Voir mes prêts en cours : 1"' in page
    assert 'aria-label="Voir mes demandes en attente : 2"' in page
    assert 'aria-label="Voir mes réservations en attente : 3"' in page
    api.statistics.assert_called_once_with(TOKEN, "mine")


def test_profile_names_the_settings_task_and_keeps_secret_fields(accounts):
    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    page = client.get("/profil").get_data(as_text=True)
    assert "<h1>Mon profil</h1>" in page
    assert "&lt;script&gt;Alice&lt;/script&gt;" in page
    assert "MON ESPACE" not in page
    for field in ("current_password", "new_password", "password_confirmation"):
        assert re.search(r'<input[^>]+name="' + field + r'"[^>]+autocomplete=', page)
    assert 'action="/profil/mot-de-passe"' in page
    assert 'name="csrf_token"' in page


def test_auth_heading_names_the_task_without_echoing_secrets(accounts):
    client, api = accounts
    assert "<h1>Connexion</h1>" in client.get("/connexion").get_data(as_text=True)
    assert "<h1>Créer un compte</h1>" in client.get("/inscription").get_data(as_text=True)


def test_collection_distinguishes_filtered_empty_from_unfiltered_empty(accounts):
    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    api.collections.return_value = {
        "entries": [],
        "movies": {},
        "total": 0,
        "offset": 0,
        "limit": 24,
    }
    page = client.get("/ma-collection?kind=custom&list_name=Soirées").get_data(as_text=True)
    assert "Aucune entrée pour ces filtres." in page
    assert "Une place pour vos coups de cœur." not in page
    assert 'href="/ma-collection"' in page
    api.collections.assert_called_once_with(TOKEN, kind="custom", list_name="Soirées")
    assert "Une place pour vos coups de cœur." in client.get("/ma-collection").get_data(
        as_text=True
    )


def test_reservation_personal_context_agrees_for_manager_and_preserves_filters(accounts):
    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    api.me.return_value = {**PROFILE, "role": "manager"}
    page = client.get("/reservations?scope=mine&movie_id=film-id&limit=12").get_data(as_text=True)
    assert "<h1>Vos réservations.</h1>" in page
    assert "GESTION DE LA VIDÉOTHÈQUE" not in page
    assert 'name="movie_id" value="film-id"' in page
    assert 'name="limit" value="12"' in page
    api.reservations.assert_called_once_with(TOKEN, scope="mine", movie_id="film-id", limit="12")


def test_collection_entries_keep_exact_private_text_and_version(accounts):
    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    api.collections.return_value = {
        "entries": [ENTRY],
        "movies": {
            "film-id": {
                "id": "film-id",
                "title": "Film <script> privé",
                "director": "Auteur",
                "year": 2026,
            }
        },
        "total": 1,
        "offset": 0,
        "limit": 24,
    }
    page = client.get("/ma-collection").get_data(as_text=True)
    assert 'class="collection-entry"' in page
    assert "Film &lt;script&gt; privé" in page
    assert unescape(re.search(r'name="version" value="([^"]+)"', page).group(1)) == ENTRY["_etag"]
    assert 'action="/ma-collection/entry-id/retirer"' in page


def test_auth_pattern_escapes_hyphen_for_browser_unicode_sets(accounts):
    client, api = accounts
    for route in ("/connexion", "/inscription"):
        page = client.get(route).get_data(as_text=True)
        assert r'pattern="[a-z0-9][a-z0-9._\-]{2,31}"' in page
