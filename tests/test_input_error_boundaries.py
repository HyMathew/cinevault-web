"""Exercise untrusted form/query input and upstream errors through Flask rendering."""

import json
from urllib.parse import urlsplit

import pytest
import requests

from app import create_app
from app.api_client import APIClient

PROFILE = {
    "id": "synthetic-admin",
    "username": "synthetic",
    "display_name": "Synthetic administrator",
    "role": "admin",
    "enabled": True,
}
TOKEN = "synthetic-test-bearer-token-123456789"
FORM = {
    "csrf_token": "synthetic-csrf",
    "titre": "Keep entered title <film>",
    "annee": "2000",
    "realisateur": "Keep entered director",
    "acteurs": "Alice, Bob",
    "support": "dvd",
    "synopsis": "Keep entered synopsis <text>",
    "genres": "Drama",
    "version": '"synthetic-version"',
}


def client_with_transport(monkeypatch, status=422, payload=None, *, enterprise=False, raw=None):
    calls = []

    def send(method, url, **kwargs):
        path = urlsplit(url).path
        calls.append((method, path, kwargs))
        response = requests.Response()
        response.status_code = status
        value = payload
        if path == "/api/v1/me":
            response.status_code, value = 200, PROFILE
        elif path == "/api/v1/users":
            response.status_code = 200
            value = {"users": [PROFILE], "total": 1, "limit": 50, "offset": 0}
        response._content = (
            (raw if raw is not None else json.dumps(value, ensure_ascii=True).encode("utf-8"))
            if path not in ("/api/v1/me", "/api/v1/users")
            else json.dumps(value).encode("utf-8")
        )
        return response

    monkeypatch.setattr(requests, "request", send)
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "synthetic-boundary-session-key-32-bytes-minimum",
            "ENTERPRISE_ENABLED": enterprise,
            "API_CLIENT": APIClient("http://offline.invalid", enterprise=enterprise),
        }
    )
    client = app.test_client()
    with client.session_transaction() as session:
        session["csrf_token"] = FORM["csrf_token"]
    if enterprise:
        client.set_cookie("cinevault_auth", TOKEN)
    return client, calls


@pytest.mark.parametrize("route", ["/films/nouveau", "/films/synthetic-film/modifier"])
@pytest.mark.parametrize(
    "year",
    ["9" * 5000, "00002000", "1887", "2101", "", "+2000", "-2000", "٢٠٠٠", "２０００", "²"],
    ids=[
        "huge",
        "padded",
        "below",
        "above",
        "empty",
        "plus",
        "minus",
        "arabic",
        "fullwidth",
        "superscript",
    ],
)
def test_invalid_year_renders_validation_without_mutating(monkeypatch, route, year):
    client, calls = client_with_transport(monkeypatch)
    response = client.post(route, data=FORM | {"annee": year})
    assert response.status_code == 422
    assert b'aria-describedby="annee-error"' in response.data
    assert b"Keep entered title &lt;film&gt;" in response.data
    assert year.encode() in response.data
    assert calls == []


@pytest.mark.parametrize("year,want", [("1888", 1888), ("2100", 2100), (" 2000 ", 2000)])
def test_valid_year_reaches_api_with_integer_once(monkeypatch, year, want):
    film = {
        key: value for key, value in FORM.items() if key not in ("csrf_token", "genres", "version")
    }
    film.update(id="synthetic-film", annee=want, acteurs=["Alice", "Bob"])
    client, calls = client_with_transport(monkeypatch, 201, film)
    response = client.post("/films/nouveau", data=FORM | {"annee": year})
    assert response.status_code == 303
    assert response.headers["Location"].endswith("/films/synthetic-film")
    assert [(method, path) for method, path, _ in calls] == [("POST", "/api/films")]
    assert json.loads(calls[0][2]["data"])["annee"] == want


@pytest.mark.parametrize(
    "offset",
    ["9" * 5000, "000000", "10001", "", "+1", "-1", " 1", "١", "１", "²"],
    ids=[
        "huge",
        "padded",
        "above",
        "empty",
        "plus",
        "minus",
        "space",
        "arabic",
        "fullwidth",
        "superscript",
    ],
)
def test_invalid_admin_offset_is_rejected_before_listing(monkeypatch, offset):
    client, calls = client_with_transport(monkeypatch, enterprise=True)
    response = client.get("/administration", query_string={"offset": offset})
    assert response.status_code == 422
    assert [(method, path) for method, path, _ in calls] == [("GET", "/api/v1/me")]


@pytest.mark.parametrize("offset,want", [(None, 0), ("0", 0), ("10000", 10000), ("00001", 1)])
def test_valid_admin_offset_reaches_api_as_integer(monkeypatch, offset, want):
    client, calls = client_with_transport(monkeypatch, enterprise=True)
    response = client.get(
        "/administration", query_string={} if offset is None else {"offset": offset}
    )
    assert response.status_code == 200
    assert b"Synthetic administrator" in response.data
    assert calls[-1][1] == "/api/v1/users"
    assert calls[-1][2]["params"] == {"limit": 50, "offset": want}


INVALID_ERRORS = [
    [],
    None,
    {},
    {"error": []},
    {"error": None},
    {"error": "invalid"},
    {"error": {}},
    {"error": {"message": None}},
    {"error": {"message": []}},
    {"error": {"message": {}}},
    {"error": {"message": 42}},
    {"error": {"message": True}},
    {"error": {"message": "\ud800"}},
] + [
    {"error": {"message": "Invalid fields", "fields": fields}}
    for fields in (
        [],
        ["wrong-shape"],
        None,
        "titre",
        42,
        True,
        {"titre": []},
        {"titre": None},
        {"titre": {}},
        {"titre": False},
        {"titre": 42},
        {"titre": "\ud800"},
        {"\ud800": "Invalid"},
    )
]


@pytest.mark.parametrize("enterprise", [False, True], ids=["legacy", "enterprise"])
@pytest.mark.parametrize("route", ["/films/nouveau", "/films/synthetic-film/modifier"])
@pytest.mark.parametrize("payload", INVALID_ERRORS)
def test_malformed_error_is_503_preserving_form_without_replay(
    monkeypatch, enterprise, route, payload
):
    client, calls = client_with_transport(monkeypatch, payload=payload, enterprise=enterprise)
    response = client.post(route, data=FORM)
    assert response.status_code == 503
    assert b"Keep entered title &lt;film&gt;" in response.data
    assert b"Keep entered synopsis &lt;text&gt;" in response.data
    assert b"Alice, Bob" in response.data
    assert "vérifiez le résultat".encode() in response.data
    mutations = [(method, path) for method, path, _ in calls if method != "GET"]
    method = "PUT" if route.endswith("/modifier") else "POST"
    path = "/api/v1/movies" if enterprise else "/api/films"
    if method == "PUT":
        path += "/synthetic-film"
    assert mutations == [(method, path)]
    if enterprise:
        assert b"Drama" in response.data
        if method == "PUT":
            assert b"&#34;synthetic-version&#34;" in response.data


@pytest.mark.parametrize("raw", [b"not JSON", b"<html>upstream failure</html>", b""])
def test_non_json_error_is_503_and_preserves_submitted_values(monkeypatch, raw):
    client, calls = client_with_transport(monkeypatch, raw=raw)
    response = client.post("/films/nouveau", data=FORM)
    assert response.status_code == 503
    assert b"Keep entered title &lt;film&gt;" in response.data
    assert [(method, path) for method, path, _ in calls] == [("POST", "/api/films")]


@pytest.mark.parametrize("fields", [{}, {"titre": "Titre refusé <unsafe>", "autre": "Information"}])
@pytest.mark.parametrize("enterprise", [False, True])
def test_valid_validation_error_remains_422_and_escapes_message(monkeypatch, fields, enterprise):
    payload = {
        "error": {
            "code": "validation_error",
            "message": "Données invalides <unsafe>",
            "fields": fields,
        }
    }
    client, calls = client_with_transport(monkeypatch, payload=payload, enterprise=enterprise)
    response = client.post("/films/nouveau", data=FORM)
    assert response.status_code == 422
    assert "Données invalides &lt;unsafe&gt;".encode() in response.data
    assert b"Keep entered title &lt;film&gt;" in response.data
    if fields:
        assert "Titre refusé &lt;unsafe&gt;".encode() in response.data
    assert len([call for call in calls if call[0] == "POST"]) == 1


def test_validation_error_without_optional_fields_remains_422(monkeypatch):
    client, calls = client_with_transport(
        monkeypatch, payload={"error": {"message": "Rule violated"}}
    )
    response = client.post("/films/nouveau", data=FORM)
    assert response.status_code == 422
    assert b"Rule violated" in response.data
    assert len(calls) == 1


@pytest.mark.parametrize("status", [422, 200], ids=["error-body", "success-body"])
def test_deep_json_is_controlled_unavailability_without_replaying_mutation(monkeypatch, status):
    raw = b'{"error":{"message":"Invalid","fields":' + b"[" * 5000 + b"0" + b"]" * 5000 + b"}}"
    client, calls = client_with_transport(monkeypatch, status=status, raw=raw)
    response = client.post("/films/nouveau", data=FORM)
    assert response.status_code == 503
    assert b"Keep entered title &lt;film&gt;" in response.data
    assert b"Keep entered synopsis &lt;text&gt;" in response.data
    assert "vérifiez le résultat".encode() in response.data
    assert [(method, path) for method, path, _ in calls] == [("POST", "/api/films")]
