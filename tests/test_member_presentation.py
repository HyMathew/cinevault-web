"""Presentation choices preserve API queries and role boundaries."""

import re

from test_accounts import PROFILE, TOKEN
from test_accounts import accounts as accounts
from test_enterprise_catalogue import FILM, setup_catalogue

from app import create_app


def test_member_catalogue_has_film_links_and_explicit_stock(accounts):
    client, api = accounts
    setup_catalogue(api)
    page = client.get("/films").get_data(as_text=True)
    assert "Voir le film" in page
    assert "Affiche non disponible" in page
    assert "1 exemplaire" in page
    assert "disponible pour un prêt" not in page
    assert re.search(r'<a[^>]+aria-label="Voir le film : Dune"', page)
    api.search.assert_called_once_with(include_posters=True)


def test_management_view_is_authorized_and_never_sent_to_api(accounts):
    client, api = accounts
    setup_catalogue(api)
    assert client.get("/films?view=manage").status_code == 403
    client.set_cookie("cinevault_auth", TOKEN)
    assert client.get("/films?view=manage").status_code == 403
    api.me.return_value = {**PROFILE, "role": "manager"}
    page = client.get("/films?view=manage&genre=Drame&sort=-year")
    assert page.status_code == 200
    assert b"Inventaire" in page.data and b"view=manage" in page.data
    assert b"<table" in page.data
    assert re.search(
        r'href="[^"]*view=manage[^"]*genre=Drame[^"]*offset=24"[^>]*>Suivant',
        page.get_data(as_text=True),
    )
    api.search.assert_called_once_with(include_posters=True, genre="Drame", sort="-year")
    assert client.get("/films?view=unknown").status_code == 422
    assert client.get("/films?view=manage&view=manage").status_code == 422


def test_navigation_distinguishes_profile_and_personal_space(accounts):
    client, api = accounts
    setup_catalogue(api)
    client.set_cookie("cinevault_auth", TOKEN)
    page = client.get("/films").get_data(as_text=True)
    assert re.search(r'<a[^>]+href="/mon-espace"[^>]*>Mon espace</a>', page)
    assert re.search(r'<a[^>]+href="/profil"[^>]*>Mon profil</a>', page)
    assert re.search(r'<a[^>]+href="/films"[^>]+aria-current="page"', page)
    assert "<summary>Menu</summary>" in page


def test_film_primary_action_precedes_synopsis_and_management(accounts):
    client, api = accounts
    setup_catalogue(api)
    api.get.return_value = {**FILM, "availability": {"available": 1}}
    client.set_cookie("cinevault_auth", TOKEN)
    api.me.return_value = {**PROFILE, "role": "manager"}
    page = client.get("/films/film-id").get_data(as_text=True)
    assert page.index("Demander un prêt") < page.index("Synopsis")
    assert page.index("Demander un prêt") < page.index("Modifier le film")
    assert 'name="csrf_token"' in page


def test_filtered_catalogue_return_stays_local(accounts):
    client, api = accounts
    setup_catalogue(api)
    page = client.get("/films?q=atelier&genre=Drame&sort=-year&limit=12").get_data(as_text=True)
    assert 'name="limit" value="12"' in page
    assert "return_to=" in page
    returned = client.get("/films/film-id?return_to=%2Ffilms%3Fq%3Datelier%26genre%3DDrame")
    assert b'href="/films?q=atelier&amp;genre=Drame"' in returned.data
    for external in (
        "https://example.invalid",
        "//example.invalid",
        "/films-other",
        "/films?unexpected=1",
        "/films?q=a&q=b",
        "/films?q=a#fragment",
        "/films?view=external",
    ):
        returned = client.get("/films/film-id", query_string={"return_to": external})
        assert b'<div class="back"><a href="/films">' in returned.data
    returned = client.get(
        "/films/film-id", query_string={"return_to": '/films?q="><script>alert(1)</script>'}
    )
    assert b"<script>" not in returned.data
    assert b"&lt;script&gt;" in returned.data


def test_manager_default_lending_context_agrees_with_scope(accounts):
    client, api = accounts
    setup_catalogue(api)
    api.me.return_value = {**PROFILE, "role": "manager"}
    client.set_cookie("cinevault_auth", TOKEN)
    for path in ("/emprunts", "/emprunts?scope=all"):
        page = client.get(path).get_data(as_text=True)
        assert 'class="management-context"' in page
    page = client.get("/emprunts?scope=mine").get_data(as_text=True)
    assert 'class="member-context"' in page


def test_catalogue_refusals_keep_recovery_and_french_context(accounts):
    client, api = accounts
    setup_catalogue(api)
    for path, title, status in (
        ("/films?view=manage", "Accès interdit", 403),
        ("/films?unknown=1", "Données invalides", 422),
    ):
        response = client.get(path)
        assert response.status_code == status
        page = response.get_data(as_text=True)
        assert title in page
        assert "Retour au catalogue" in page
        assert '<html lang="fr">' in page


def test_enterprise_footer_keeps_legacy_route_out_of_member_navigation(accounts):
    client, api = accounts
    setup_catalogue(api)
    page = client.get("/films").get_data(as_text=True)
    assert 'href="/page-simple"' not in page
    assert "Vidéothèque collaborative" in page
    legacy = create_app({"TESTING": True, "SECRET_KEY": "synthetic-legacy-test", "API_CLIENT": api})
    api.list.return_value = []
    page = legacy.test_client().get("/films").get_data(as_text=True)
    assert 'href="/page-simple"' in page
    assert legacy.test_client().get("/page-simple").status_code == 200
