"""Web boundary tests; real JSON/Mongo receipt semantics belong to API contracts."""

import re

import pytest
import requests
from test_accounts import TOKEN, csrf
from test_accounts import accounts as accounts
from test_enterprise_catalogue import FILM
from test_reservations import fixture as reservations
from werkzeug.datastructures import MultiDict

from app.api_client import APIClient, APIError


def operation_key(page):
    match = re.search(rb'name="operation_key" value="([^"]+)"', page.data)
    assert match, "The rendered form must carry its operation identity"
    return match.group(1).decode()


@pytest.mark.parametrize("available,action", [(1, "emprunter"), (0, "reserver")])
def test_detail_creation_forms_have_fresh_operation_keys(accounts, available, action):
    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    api.get.return_value = {**FILM, "availability": {"available": available}}
    first = client.get("/films/film-id")
    second = client.get("/films/film-id")
    key = operation_key(first)
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", key)
    assert key != operation_key(second)
    assert f'action="/films/film-id/{action}"'.encode() in first.data
    assert first.headers["Cache-Control"] == "no-store"


def test_ready_reservation_loan_form_carries_operation_key(accounts):
    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    reservations(api)
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", operation_key(client.get("/reservations")))


@pytest.mark.parametrize(
    "action,method,list_path",
    [
        ("emprunter", "request_loan", "/emprunts?scope=mine"),
        ("reserver", "request_reservation", "/reservations?scope=mine"),
    ],
)
def test_uncertain_create_keeps_identity_for_one_manual_retry(accounts, action, method, list_path):
    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    token = csrf(client.get("/emprunts"))
    key = "synthetic-operation-key-123456789"
    endpoint = f"/films/film-id/{action}"
    create = getattr(api, method)
    create.side_effect = APIError(503, "private upstream details", retry_after=7)
    body = {"csrf_token": token, "operation_key": key, "user_id": "foreign"}
    response = client.post(endpoint, data=body)
    assert response.status_code == 503
    assert operation_key(response) == key
    assert response.headers["Retry-After"] == "7"
    assert response.headers["Cache-Control"] == "no-store"
    assert list_path.encode() in response.data
    assert "Réessayer la même demande".encode() in response.data
    assert b'http-equiv="refresh"' not in response.data
    assert b"private upstream details" not in response.data and TOKEN.encode() not in response.data
    create.assert_called_once_with(TOKEN, {"movie_id": "film-id"}, operation_key=key)
    create.side_effect = None
    assert (
        client.post(
            endpoint, data={"csrf_token": csrf(response), "operation_key": operation_key(response)}
        ).status_code
        == 303
    )
    assert create.call_count == 2
    assert create.call_args.kwargs == {"operation_key": key}


@pytest.mark.parametrize(
    "action,method", [("emprunter", "request_loan"), ("reserver", "request_reservation")]
)
@pytest.mark.parametrize("key", [None, "", "short", "<invalid-operation-key>"])
def test_missing_or_invalid_operation_identity_never_creates(accounts, action, method, key):
    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    body = {"csrf_token": csrf(client.get("/emprunts"))}
    if key is not None:
        body["operation_key"] = key
    assert client.post(f"/films/film-id/{action}", data=body).status_code == 400
    getattr(api, method).assert_not_called()


@pytest.mark.parametrize(
    "method,path", [("request_loan", "loans"), ("request_reservation", "reservations")]
)
def test_client_relays_operation_header_once_on_timeout(monkeypatch, method, path):
    attempts = []

    def timeout(verb, url, **kwargs):
        attempts.append((verb, url, kwargs))
        raise requests.Timeout()

    monkeypatch.setattr(requests, "request", timeout)
    with pytest.raises(APIError) as failure:
        getattr(APIClient("http://api", enterprise=True), method)(
            TOKEN, {"movie_id": "film-id"}, operation_key="synthetic-operation-key-123456789"
        )
    assert failure.value.status == 503 and len(attempts) == 1
    verb, url, kwargs = attempts[0]
    assert (verb, url) == ("POST", "http://api/api/v1/" + path)
    assert kwargs["headers"] == {
        "Authorization": "Bearer " + TOKEN,
        "Idempotency-Key": "synthetic-operation-key-123456789",
    }
    assert kwargs["json"] == {"movie_id": "film-id"}


@pytest.mark.parametrize(
    "action,method", [("emprunter", "request_loan"), ("reserver", "request_reservation")]
)
def test_duplicate_keys_and_missing_csrf_are_refused_before_creation(accounts, action, method):
    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    token = csrf(client.get("/emprunts"))
    key = "synthetic-operation-key-123456789"
    endpoint = f"/films/film-id/{action}"
    assert client.post(endpoint, data={"operation_key": key}).status_code == 400
    assert (
        client.post(
            endpoint,
            data=MultiDict([("csrf_token", token), ("operation_key", key), ("operation_key", key)]),
        ).status_code
        == 400
    )
    getattr(api, method).assert_not_called()


@pytest.mark.parametrize(
    "action,method", [("emprunter", "request_loan"), ("reserver", "request_reservation")]
)
@pytest.mark.parametrize("status", [401, 403, 409, 422])
def test_confirmed_refusal_never_offers_an_uncertain_retry(accounts, action, method, status):
    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    token = csrf(client.get("/emprunts"))
    getattr(api, method).side_effect = APIError(status, "private details")
    response = client.post(
        f"/films/film-id/{action}",
        data={"csrf_token": token, "operation_key": "synthetic-operation-key-123456789"},
    )
    assert response.status_code == status
    assert "Réessayer la même demande".encode() not in response.data
    assert b"private details" not in response.data


@pytest.mark.parametrize(
    "method,path", [("request_loan", "loans"), ("request_reservation", "reservations")]
)
def test_client_optional_key_preserves_direct_caller_contract(monkeypatch, method, path):
    calls = []
    client = APIClient("http://api", enterprise=True)
    monkeypatch.setattr(client, "request", lambda *args, **kwargs: calls.append((args, kwargs)))
    getattr(client, method)(TOKEN, {"movie_id": "film-id"})
    assert calls == [
        (
            ("POST", "/api/v1/" + path),
            {"headers": {"Authorization": "Bearer " + TOKEN}, "json": {"movie_id": "film-id"}},
        )
    ]
