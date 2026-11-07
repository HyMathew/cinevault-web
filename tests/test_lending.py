from datetime import date, timedelta

from test_accounts import PROFILE, TOKEN, csrf
from test_accounts import accounts as accounts

LOAN = {
    "id": "loan-id",
    "movie_id": "film-id",
    "borrower_id": "user-id",
    "copy_id": None,
    "status": "pending",
    "requested_at": 1700000000,
    "approved_at": None,
    "due_at": None,
    "returned_at": None,
    "cancelled_at": None,
    "_etag": '"loan-version"',
}


def fixture(api):
    api.loans.return_value = {
        "loans": [LOAN],
        "total": 1,
        "limit": 24,
        "offset": 0,
        "overdue_ids": [],
        "movies": {"film-id": {"id": "film-id", "title": "Dune", "year": 2021}},
        "borrowers": {"user-id": PROFILE},
    }
    api.loan.return_value = LOAN
    api.loan_options.return_value = {
        "loan_id": "loan-id",
        "copies": [
            {
                "id": "copy-id",
                "support": "dvd",
                "location": "A",
                "condition": "good",
                "_etag": '"copy-version"',
            }
        ],
    }


def test_member_requests_and_cancels_own_pending_loan_with_csrf(accounts):
    client, api = accounts
    assert client.get("/emprunts").status_code == 303
    client.set_cookie("cinevault_auth", TOKEN)
    fixture(api)
    page = client.get("/emprunts")
    assert page.status_code == 200
    assert response_private(page)
    token = csrf(page)
    assert client.post("/films/film-id/emprunter", data={"csrf_token": token}).status_code == 303
    api.request_loan.assert_called_once_with(TOKEN, {"movie_id": "film-id"})
    assert (
        client.post(
            "/emprunts/loan-id/annuler", data={"csrf_token": token, "version": '"loan-version"'}
        ).status_code
        == 303
    )
    api.loan_action.assert_called_once_with(TOKEN, "loan-id", "cancel", '"loan-version"')
    assert (
        client.post(
            "/emprunts/loan-id/retour", data={"csrf_token": token, "version": '"loan-version"'}
        ).status_code
        == 403
    )
    assert client.get("/emprunts/loan-id/valider").status_code == 403


def response_private(response):
    return (
        response.headers.get("Cache-Control") == "no-store" and TOKEN.encode() not in response.data
    )


def test_open_loan_followup_preserves_movie_and_own_scope_when_filtering(accounts):
    client, api = accounts
    fixture(api)
    api.me.return_value = {**PROFILE, "role": "manager"}
    client.set_cookie("cinevault_auth", TOKEN)
    page = client.get("/emprunts?scope=mine&movie_id=film-id&status=open")
    assert page.status_code == 200 and response_private(page)
    assert b'name="scope" value="mine"' in page.data
    assert b'name="movie_id" value="film-id"' in page.data
    assert b'<option value="open" selected>' in page.data
    assert b"Vos emprunts." in page.data


def test_manager_approval_parses_date_and_relays_copy_and_version(accounts):
    client, api = accounts
    fixture(api)
    api.me.return_value = {**PROFILE, "role": "manager"}
    client.set_cookie("cinevault_auth", TOKEN)
    token = csrf(client.get("/emprunts/loan-id/valider"))
    tomorrow = (date.today() + timedelta(days=2)).isoformat()
    response = client.post(
        "/emprunts/loan-id/valider",
        data={
            "csrf_token": token,
            "version": '"loan-version"',
            "copy_id": "copy-id",
            "due_date": tomorrow,
        },
    )
    assert response.status_code == 303
    args = api.loan_action.call_args.args
    assert args[:4] == (TOKEN, "loan-id", "approve", '"loan-version"')
    assert args[4]["copy_id"] == "copy-id" and type(args[4]["due_at"]) is int
    assert (
        client.post(
            "/emprunts/loan-id/valider",
            data={
                "csrf_token": token,
                "version": '"loan-version"',
                "copy_id": "copy-id",
                "due_date": "not-a-date",
            },
        ).status_code
        == 422
    )
