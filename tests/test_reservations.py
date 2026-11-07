import pytest
from test_accounts import PROFILE, TOKEN, csrf
from test_accounts import accounts as accounts

from app.api_client import APIError

RESERVATION = {
    "id": "reservation-id",
    "movie_id": "film-id",
    "user_id": "user-id",
    "status": "waiting",
    "sequence": 3,
    "created_at": 1700000000,
    "expires_at": 1701209600,
    "closed_at": None,
    "loan_id": None,
    "_etag": '"reservation-version"',
}


def fixture(api, pending=None):
    api.reservations.return_value = {
        "reservations": [RESERVATION],
        "total": 1,
        "limit": 24,
        "offset": 0,
        "movies": {"film-id": {"id": "film-id", "title": "<script>Film</script>", "year": 2021}},
        "users": {"user-id": PROFILE},
        "positions": {"reservation-id": 1},
        "ready_ids": ["reservation-id"],
        "open_loan_ids": pending or {},
    }


def test_reservation_pages_require_login_and_mutations_require_csrf(accounts):
    client, api = accounts
    assert client.get("/reservations").status_code == 303
    api.reservations.assert_not_called()
    assert client.post("/films/film-id/reserver").status_code == 400
    assert client.post("/reservations/reservation-id/annuler").status_code == 400


def test_own_reservation_list_is_private_and_escapes_titles(accounts):
    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    fixture(api)
    page = client.get("/reservations?status=waiting")
    assert page.status_code == 200 and page.headers["Cache-Control"] == "no-store"
    assert b"&lt;script&gt;Film&lt;/script&gt;" in page.data
    assert b"<script>Film</script>" not in page.data and TOKEN.encode() not in page.data
    assert "Demander un prêt".encode() in page.data
    api.reservations.assert_called_once_with(TOKEN, status="waiting")
    token = csrf(page)
    assert (
        client.post(
            "/films/film-id/reserver", data={"csrf_token": token, "user_id": "other"}
        ).status_code
        == 303
    )
    api.request_reservation.assert_called_once_with(TOKEN, {"movie_id": "film-id"})
    assert (
        client.post(
            "/reservations/reservation-id/annuler",
            data={"csrf_token": token, "version": '"reservation-version"'},
        ).status_code
        == 303
    )
    api.cancel_reservation.assert_called_once_with(TOKEN, "reservation-id", '"reservation-version"')


def test_existing_pending_loan_is_linked_instead_of_requested_again(accounts):
    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    fixture(api, {"reservation-id": "loan-id"})
    page = client.get("/reservations")
    assert page.status_code == 200
    assert b"Voir ma demande" in page.data
    assert "Demander un prêt".encode() not in page.data


def test_foreign_or_stale_cancellation_preserves_api_status(accounts):
    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    fixture(api)
    token = csrf(client.get("/reservations"))
    for status in (404, 412):
        api.cancel_reservation.side_effect = APIError(status, "unavailable")
        assert (
            client.post(
                "/reservations/foreign/annuler", data={"csrf_token": token, "version": '"old"'}
            ).status_code
            == status
        )


def test_film_detail_uses_own_queue_context_without_cache(accounts):
    from test_enterprise_catalogue import FILM

    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    fixture(api)
    api.get.return_value = {**FILM, "availability": {"available": 0}}
    page = client.get("/films/film-id")
    assert page.status_code == 200 and page.headers["Cache-Control"] == "no-store"
    api.reservations.assert_called_once_with(
        TOKEN, status="waiting", scope="mine", movie_id="film-id"
    )
    assert "Un exemplaire est disponible pour vous.".encode() in page.data
    assert "Réserver ce film".encode() not in page.data


@pytest.mark.parametrize("role", ["member", "manager", "admin"])
@pytest.mark.parametrize(
    "status,label", [("pending", "Voir ma demande de prêt"), ("active", "Voir mon prêt en cours")]
)
def test_film_detail_links_existing_own_loan_even_without_reservation(
    accounts, role, status, label
):
    from test_enterprise_catalogue import FILM

    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    api.me.return_value = {**PROFILE, "role": role}
    api.get.return_value = {**FILM, "availability": {"available": 0 if status == "active" else 2}}
    api.loans.return_value = {"loans": [{"id": "own-loan", "status": status}], "total": 1}
    page = client.get("/films/film-id")
    assert page.status_code == 200 and page.headers["Cache-Control"] == "no-store"
    api.loans.assert_called_once_with(
        TOKEN, scope="mine", movie_id="film-id", status="open", limit=1
    )
    assert label.encode() in page.data
    assert "Demander un prêt".encode() not in page.data
    assert "Réserver ce film".encode() not in page.data
