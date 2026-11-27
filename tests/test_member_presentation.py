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
    assert "Disponibilité à vérifier sur la fiche" in page
    assert "Aucun exemplaire libre hors réservations" not in page
    assert re.search(r'<a[^>]+aria-label="Voir le film : Dune"', page)
    assert 'action="/films#catalogue-results"' in page
    assert 'id="catalogue-results" tabindex="-1" role="status"' in page
    assert len(re.findall(r'href="/films/film-id\?return_to=[^"]+"', page)) == 1
    api.search.assert_called_once_with(include_posters=True, include_availability=True)


def test_catalogue_displays_public_availability_in_both_views(accounts):
    client, api = accounts
    setup_catalogue(api)
    zero = {**FILM, "id": "zero", "titre": "Autre film", "available_count": 0}
    api.search.return_value = {
        "films": [{**FILM, "available_count": 1}, zero],
        "total": 2,
        "limit": 24,
        "offset": 0,
    }
    api.me.return_value = {**PROFILE, "role": "manager"}
    client.set_cookie("cinevault_auth", TOKEN)
    for view in ("member", "manage"):
        page = client.get("/films", query_string={"view": view})
        assert page.status_code == 200
        assert "1 disponible hors réservations" in page.text
        assert "Aucun exemplaire libre hors réservations" in page.text
        assert 'href="/films/zero?' in page.text
        assert "Disponibilité à vérifier" not in page.text
    api.loans.assert_not_called()
    api.reservations.assert_not_called()


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
    api.search.assert_called_once_with(
        include_posters=True, include_availability=True, genre="Drame", sort="-year"
    )
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


def test_film_detail_displays_stock_and_keeps_collection_out_of_lending(accounts):
    client, api = accounts
    setup_catalogue(api)
    api.get.return_value = {**FILM, "availability": {"available": 1}}
    client.set_cookie("cinevault_auth", TOKEN)

    page = client.get("/films/film-id").text
    borrowing = page.split('aria-labelledby="borrowing-title"', 1)[1].split("</section>", 1)[0]
    assert "1 exemplaire · Blu-ray" in borrowing
    assert "1 disponible hors réservations." in borrowing
    assert "Demander un prêt" in borrowing
    assert "Ajouter à ma collection" not in borrowing
    assert page.index("Demander un prêt") < page.index('class="detail-artwork"')
    assert "Ajouter à ma collection" in page
    api.get.assert_called_once_with("film-id", include_related=True)


def test_film_without_inventory_can_still_join_the_reservation_queue(accounts):
    client, api = accounts
    setup_catalogue(api)
    api.get.return_value = {**FILM, "copy_count": 0, "copies": [], "copy_supports": []}
    client.set_cookie("cinevault_auth", TOKEN)
    page = client.get("/films/film-id").text
    assert "Aucun exemplaire enregistré. Une réservation vous place dans la file d’attente." in page
    assert "Réserver ce film" in page
    assert "Demander un prêt" not in page


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
    legacy = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "synthetic-legacy-session-key-32-bytes-minimum",
            "API_CLIENT": api,
        }
    )
    api.list.return_value = []
    page = legacy.test_client().get("/films").get_data(as_text=True)
    assert 'href="/page-simple"' in page
    assert legacy.test_client().get("/page-simple").status_code == 200
