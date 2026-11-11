"""Browser-like form round trips; only the upstream HTTP transport is replaced."""

import json
from copy import deepcopy
from html.parser import HTMLParser
from itertools import product
from urllib.parse import urlsplit

import pytest
import requests
from werkzeug.datastructures import MultiDict

from app import create_app
from app.api_client import APIClient
from app.forms import list_values

VALUES = [
    "Doe, Jane",
    'A "quoted" name',
    "Élodie 李 🎬",
    "back\\slash",
    "first\nlast",
    "first\rlast",
    "first\r\nlast",
]
PROFILE = {
    "id": "admin",
    "username": "admin",
    "display_name": "Admin",
    "role": "admin",
    "enabled": True,
}
FILM = {
    "id": "film-id",
    "titre": "Film",
    "annee": 2000,
    "realisateur": "Director",
    "acteurs": VALUES,
    "genres": VALUES,
    "synopsis": "Keep synopsis",
    "support": "dvd",
    "_etag": '"old-version"',
}
TOKEN = "synthetic-test-bearer-token-123456789"


def lf(value):
    return value.replace("\r\n", "\n").replace("\r", "\n")


class BrowserForm(HTMLParser):
    """Model HTML newline normalization and successful text/hidden controls."""

    def __init__(self, response):
        super().__init__(convert_charrefs=True)
        self.data = MultiDict()
        self.textarea = None
        self.text = ""
        self.controls = []
        self.labels = {}
        self.feed(lf(response.get_data(as_text=True)).replace("\x00", "\ufffd"))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.controls.append((tag, attrs))
        if tag == "input" and attrs.get("name") and attrs.get("type") != "checkbox":
            self.data.add(attrs["name"], attrs.get("value", ""))
        if tag == "textarea":
            self.textarea, self.text = attrs.get("name"), ""
        if tag == "option" and "selected" in attrs:
            self.data.add("support", attrs["value"])

    def handle_data(self, data):
        if self.textarea:
            self.text += data

    def handle_endtag(self, tag):
        if tag == "textarea" and self.textarea:
            # HTML ignores one immediately leading newline in a textarea.
            text = self.text[1:] if self.text.startswith("\n") else self.text
            self.data.add(self.textarea, text.replace("\n", "\r\n"))
            self.textarea = None


def native_client(monkeypatch, enterprise, film=None):
    film = deepcopy(film or FILM)
    calls = []
    state = {
        "status": 200,
        "error": {
            "error": {
                "code": "validation_error",
                "message": "Refusé",
                "fields": {"titre": "Titre refusé"},
            }
        },
    }

    def send(method, url, **kwargs):
        path = urlsplit(url).path
        calls.append((method, path, kwargs))
        response = requests.Response()
        response.status_code = 200
        movie = {
            "id": film["id"],
            "title": film["titre"],
            "year": film["annee"],
            "director": film["realisateur"],
            "actors": film["acteurs"],
            "genres": film["genres"],
            "synopsis": film["synopsis"],
            "_etag": film["_etag"],
        }
        if method != "GET":
            response.status_code = state["status"]
            value = state["error"] if response.status_code >= 400 else movie if enterprise else film
            wire = (
                requests.Request(
                    method,
                    url,
                    headers=kwargs.get("headers"),
                    json=kwargs.get("json"),
                    data=kwargs.get("data"),
                )
                .prepare()
                .body
            )
            state.setdefault("wire_bodies", []).append(wire)
            if state.get("enforce_api_limit") and len(wire) > 65536:
                response.status_code = 413
                value = {"error": {"code": "too_large", "message": "Request exceeds API limit"}}
        else:
            value = {
                "/api/v1/me": PROFILE,
                "/api/v1/copies": {"copies": []},
                "/api/v1/availability": {"available": 0},
                "/api/v1/movies/film-id": movie,
                "/api/films/film-id": film,
            }.get(path)
            if path == "/api/v1/metadata/Q123":
                value = {
                    "film": {
                        "id": "Q123",
                        "title": "Proposed film",
                        "year": 2001,
                        "director": "Proposed director",
                        "actors": film["acteurs"],
                        "genres": film["genres"],
                        "description": "Proposal",
                        "poster_filename": None,
                        "poster": None,
                        "revision": 1,
                        "retrieved_at": 1700000000,
                        "source_url": "https://www.wikidata.org/wiki/Q123",
                        "warnings": [],
                    },
                    "cache": {"status": "fresh", "stored_at": 1700000000, "hit": True},
                }
        response._content = json.dumps(value).encode()
        return response

    monkeypatch.setattr(requests, "request", send)
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "synthetic-list-session-key-32-bytes-minimum",
            "ENTERPRISE_ENABLED": enterprise,
            "API_CLIENT": APIClient("http://offline.invalid", enterprise=enterprise),
        }
    )
    client = app.test_client()
    if enterprise:
        client.set_cookie("cinevault_auth", TOKEN)
    return client, calls, state


def mutations(calls):
    return [
        (method, path, {**kwargs, "json": json.loads(kwargs["data"])})
        for method, path, kwargs in calls
        if method != "GET"
    ]


@pytest.mark.parametrize("enterprise", [False, True])
def test_unchanged_lists_round_trip_exactly_through_browser_and_api(monkeypatch, enterprise):
    client, calls, _ = native_client(monkeypatch, enterprise)
    form = BrowserForm(client.get("/films/film-id/modifier"))
    assert form.data.getlist("acteurs") == [lf(value).replace("\n", "\r\n") for value in VALUES]
    page = client.post("/films/film-id/modifier", data=form.data)
    assert page.status_code == 303
    sent = mutations(calls)
    assert len(sent) == 1
    assert sent[0][2]["json"]["actors" if enterprise else "acteurs"] == VALUES
    if enterprise:
        assert sent[0][2]["json"]["genres"] == VALUES
        assert sent[0][2]["headers"]["If-Match"] == '"old-version"'


@pytest.mark.parametrize("enterprise", [False, True])
@pytest.mark.parametrize("status", [422, 503, 412])
def test_error_render_and_second_submit_preserve_exact_lists_and_version(
    monkeypatch, enterprise, status
):
    client, calls, state = native_client(monkeypatch, enterprise)
    original = BrowserForm(client.get("/films/film-id/modifier"))
    original.data["titre"] = "My changed title"
    state["status"] = status
    failed = client.post("/films/film-id/modifier", data=original.data)
    assert failed.status_code == (status if enterprise or status != 412 else 503)
    assert b"My changed title" in failed.data
    again = BrowserForm(failed)
    state["status"] = 200
    assert client.post("/films/film-id/modifier", data=again.data).status_code == 303
    sent = mutations(calls)
    assert len(sent) == 2
    for _, _, kwargs in sent:
        assert kwargs["json"]["actors" if enterprise else "acteurs"] == VALUES
        if enterprise:
            assert kwargs["json"]["genres"] == VALUES
            assert kwargs["headers"]["If-Match"] == '"old-version"'


@pytest.mark.parametrize("enterprise", [False, True])
def test_add_remove_without_javascript_preserves_indices_and_never_mutates(monkeypatch, enterprise):
    client, calls, _ = native_client(monkeypatch, enterprise)
    form = BrowserForm(client.get("/films/film-id/modifier"))
    form.data["titre"] = "Keep changed title"
    form.data["list_action"] = "add:acteurs"
    added = client.post("/films/film-id/modifier", data=form.data)
    assert added.status_code == 200
    form = BrowserForm(added)
    assert len(form.data.getlist("acteurs")) == len(VALUES) + 1
    form.data["list_action"] = "remove:acteurs:1"
    removed = client.post("/films/film-id/modifier", data=form.data)
    assert removed.status_code == 200
    assert mutations(calls) == []
    form = BrowserForm(removed)
    assert b"Keep changed title" in removed.data
    assert client.post("/films/film-id/modifier", data=form.data).status_code == 303
    expected = VALUES[:1] + VALUES[2:]
    assert mutations(calls)[0][2]["json"]["actors" if enterprise else "acteurs"] == expected


def test_metadata_proposal_keeps_full_lists_and_original_newlines(monkeypatch):
    client, calls, _ = native_client(monkeypatch, True)
    form = BrowserForm(client.get("/films/nouveau?metadata_id=Q123"))
    form.data["support"] = "dvd"
    assert client.post("/films/nouveau", data=form.data).status_code == 303
    body = mutations(calls)[0][2]["json"]
    assert body["actors"] == VALUES
    assert body["genres"] == VALUES
    assert body["external_id"] == "Q123"


@pytest.mark.parametrize(
    "original",
    [
        "not JSON",
        "null",
        "{}",
        '"text"',
        "[true]",
        "[null]",
        '[["nested"]]',
        '["\\ud800"]',
        json.dumps(["x" * 121]),
        json.dumps(["x"] * 31),
        "[" * 1500,
    ],
)
def test_invalid_hidden_original_falls_back_without_overriding_text(monkeypatch, original):
    client, calls, _ = native_client(monkeypatch, False)
    form = BrowserForm(client.get("/films/film-id/modifier"))
    form.data.setlist("acteurs", ["User\r\nvalue"])
    form.data["_original_acteurs"] = original
    assert client.post("/films/film-id/modifier", data=form.data).status_code == 303
    assert mutations(calls)[0][2]["json"]["acteurs"] == ["User\nvalue"]


def test_changed_field_wins_over_hidden_original_and_other_originals_stay_exact(monkeypatch):
    client, calls, _ = native_client(monkeypatch, False)
    form = BrowserForm(client.get("/films/film-id/modifier"))
    entered = form.data.getlist("acteurs")
    entered[0] = "Changed, name\r\nwith lines"
    form.data.setlist("acteurs", entered)
    assert client.post("/films/film-id/modifier", data=form.data).status_code == 303
    assert mutations(calls)[0][2]["json"]["acteurs"] == ["Changed, name\nwith lines"] + VALUES[1:]


@pytest.mark.parametrize(
    "action",
    [
        "remove:acteurs:99",
        "remove:acteurs:-1",
        "remove:acteurs:١",
        "remove:acteurs:" + "9" * 5000,
        "add:unknown",
        "delete",
        "remove:genres:99",
    ],
)
def test_invalid_presentation_action_never_saves_a_film(monkeypatch, action):
    client, calls, _ = native_client(monkeypatch, True)
    form = BrowserForm(client.get("/films/film-id/modifier"))
    form.data["list_action"] = action
    response = client.post("/films/film-id/modifier", data=form.data)
    assert response.status_code == 422
    assert mutations(calls) == []


def test_remove_last_element_and_add_to_empty_list(monkeypatch):
    client, calls, _ = native_client(monkeypatch, False, FILM | {"acteurs": ["Only name"]})
    form = BrowserForm(client.get("/films/film-id/modifier"))
    form.data["list_action"] = "remove:acteurs:0"
    form = BrowserForm(client.post("/films/film-id/modifier", data=form.data))
    assert form.data.getlist("acteurs") == []
    form.data["list_action"] = "add:acteurs"
    form = BrowserForm(client.post("/films/film-id/modifier", data=form.data))
    assert form.data.getlist("acteurs") == [""]
    assert mutations(calls) == []


@pytest.mark.parametrize("count,length,status", [(30, 120, 303), (31, 1, 422), (1, 121, 422)])
def test_actor_limits_are_checked_for_repeated_fields(monkeypatch, count, length, status):
    client, calls, _ = native_client(monkeypatch, False)
    form = BrowserForm(client.get("/films/film-id/modifier"))
    form.data.setlist("acteurs", ["x" * length] * count)
    assert client.post("/films/film-id/modifier", data=form.data).status_code == status
    assert len(mutations(calls)) == (1 if status == 303 else 0)
    if status == 303:
        assert mutations(calls)[0][2]["json"]["acteurs"] == ["x" * length] * count


@pytest.mark.parametrize("count,length,status", [(30, 80, 303), (31, 1, 422), (1, 81, 422)])
def test_genre_limits_are_checked_for_repeated_fields(monkeypatch, count, length, status):
    client, calls, _ = native_client(monkeypatch, True)
    form = BrowserForm(client.get("/films/film-id/modifier"))
    form.data.setlist("genres", ["x" * length] * count)
    assert client.post("/films/film-id/modifier", data=form.data).status_code == status
    assert len(mutations(calls)) == (1 if status == 303 else 0)
    if status == 303:
        assert mutations(calls)[0][2]["json"]["genres"] == ["x" * length] * count


def test_controls_have_unique_labels_and_do_not_limit_unicode_to_utf16_units(monkeypatch):
    client, _, _ = native_client(monkeypatch, True)
    form = BrowserForm(client.get("/films/film-id/modifier"))
    fields = [
        attrs
        for tag, attrs in form.controls
        if tag == "textarea" and attrs.get("name") in ("acteurs", "genres")
    ]
    labels = {attrs.get("for") for tag, attrs in form.controls if tag == "label"}
    assert len(fields) == len(VALUES) * 2
    identities = [attrs["id"] for attrs in fields]
    assert len(set(identities)) == len(identities)
    assert set(identities) <= labels
    assert all("maxlength" not in attrs for attrs in fields)


def test_api_unicode_and_html_characters_survive_browser_normalization(monkeypatch):
    names = ["A\x00B", "<textarea>&'\"</textarea>", "🎬" * 120]
    client, calls, _ = native_client(monkeypatch, False, FILM | {"acteurs": names})
    form = BrowserForm(client.get("/films/film-id/modifier"))
    assert form.data.getlist("acteurs")[0] == "A\ufffdB"
    assert client.post("/films/film-id/modifier", data=form.data).status_code == 303
    assert mutations(calls)[0][2]["json"]["acteurs"] == names


def test_presentation_actions_keep_csrf_and_manager_checks(monkeypatch):
    client, calls, _ = native_client(monkeypatch, True)
    form = BrowserForm(client.get("/films/film-id/modifier"))
    form.data["list_action"] = "add:genres"
    csrf = form.data.pop("csrf_token")
    assert client.post("/films/film-id/modifier", data=form.data).status_code == 400
    form.data["csrf_token"] = csrf
    client.delete_cookie("cinevault_auth")
    assert client.post("/films/film-id/modifier", data=form.data).status_code == 403
    assert mutations(calls) == []


def test_genre_presentation_changes_preserve_other_fields_without_validating_or_saving(monkeypatch):
    client, calls, _ = native_client(monkeypatch, True)
    form = BrowserForm(client.get("/films/film-id/modifier"))
    form.data["titre"] = ""
    form.data["list_action"] = "remove:genres:0"
    response = client.post("/films/film-id/modifier", data=form.data)
    assert response.status_code == 200
    form = BrowserForm(response)
    assert form.data["titre"] == ""
    form.data["list_action"] = "add:genres"
    form = BrowserForm(client.post("/films/film-id/modifier", data=form.data))
    assert len(form.data.getlist("genres")) == len(VALUES)
    assert mutations(calls) == []
    form.data["titre"] = "Now valid"
    assert client.post("/films/film-id/modifier", data=form.data).status_code == 303
    assert mutations(calls)[0][2]["json"]["genres"] == VALUES[1:]
    assert mutations(calls)[0][2]["json"]["actors"] == VALUES


def test_duplicate_actions_are_rejected_and_duplicate_originals_do_not_override_input(monkeypatch):
    client, calls, _ = native_client(monkeypatch, False)
    form = BrowserForm(client.get("/films/film-id/modifier"))
    form.data.setlist("list_action", ["add:acteurs", "remove:acteurs:0"])
    assert client.post("/films/film-id/modifier", data=form.data).status_code == 422
    assert mutations(calls) == []
    form.data.poplist("list_action")
    form.data.setlist("acteurs", ["Entered\r\nvalue"])
    form.data.setlist("_original_acteurs", [json.dumps(["Entered\rvalue"])] * 2)
    assert client.post("/films/film-id/modifier", data=form.data).status_code == 303
    assert mutations(calls)[0][2]["json"]["acteurs"] == ["Entered\nvalue"]


def test_oversized_original_is_ignored_and_does_not_override_changed_input(monkeypatch):
    client, calls, _ = native_client(monkeypatch, False)
    form = BrowserForm(client.get("/films/film-id/modifier"))
    form.data.setlist("acteurs", ["Entered\r\nvalue"])
    form.data["_original_acteurs"] = " " * 50000 + json.dumps(["Entered\rvalue"])
    assert client.post("/films/film-id/modifier", data=form.data).status_code == 303
    assert mutations(calls)[0][2]["json"]["acteurs"] == ["Entered\nvalue"]


def test_add_at_limit_preserves_all_thirty_values_without_saving(monkeypatch):
    values = [str(index) for index in range(30)]
    client, calls, _ = native_client(monkeypatch, False, FILM | {"acteurs": values})
    form = BrowserForm(client.get("/films/film-id/modifier"))
    form.data["list_action"] = "add:acteurs"
    response = client.post("/films/film-id/modifier", data=form.data)
    assert response.status_code == 422
    assert BrowserForm(response).data.getlist("acteurs") == values
    assert mutations(calls) == []


@pytest.mark.parametrize("enterprise", [False, True])
def test_delimiter_combinations_round_trip_as_individual_values(monkeypatch, enterprise):
    delimiters = [",", '"', "\\", "\n", "\r", "\r\n", "é李"]
    # Deterministic generated corpus, including duplicates and all delimiter pairs.
    corpus = ["A" + first + "B" + second + "C" for first, second in product(delimiters, repeat=2)]
    for start in range(0, len(corpus), 20):
        values = corpus[start : start + 20] + [corpus[start]]
        client, calls, _ = native_client(
            monkeypatch, enterprise, FILM | {"acteurs": values, "genres": values}
        )
        form = BrowserForm(client.get("/films/film-id/modifier"))
        assert client.post("/films/film-id/modifier", data=form.data).status_code == 303
        assert mutations(calls)[0][2]["json"]["actors" if enterprise else "acteurs"] == values


@pytest.mark.parametrize("name,limit", [("acteurs", 120), ("genres", 80)])
def test_maximal_ascii_escaped_original_preserves_cr_in_all_thirty_elements(name, limit):
    original = "🎬" * (limit - 2) + "\rX"
    data = MultiDict([(name, lf(original))] * 30)
    data["_original_" + name] = json.dumps([original] * 30)
    assert list_values(data, name, limit) == [original] * 30


@pytest.mark.parametrize("enterprise", [False, True])
def test_maximal_unicode_movie_fits_targeted_form_and_api_limits(monkeypatch, enterprise):
    from urllib.parse import urlencode

    actor = "🎬" * 118 + "\rX"
    genre = "🎬" * 78 + "\rX"
    film = FILM | {
        "titre": "🎬" * 200,
        "realisateur": "🎬" * 120,
        "synopsis": "🎬" * 4000,
        "acteurs": [actor] * 30,
        "genres": [genre] * 30,
    }
    client, calls, state = native_client(monkeypatch, enterprise, film)
    state["enforce_api_limit"] = True
    form = BrowserForm(client.get("/films/film-id/modifier"))
    encoded_form = urlencode(list(form.data.items(multi=True))).encode("ascii")
    assert 65536 < len(encoded_form) < 256 * 1024
    assert (
        client.post(
            "/films/film-id/modifier",
            data=encoded_form,
            content_type="application/x-www-form-urlencoded",
        ).status_code
        == 303
    )
    assert len(mutations(calls)) == 1
    body = state["wire_bodies"][0]
    assert len(body) <= 65536
    decoded = json.loads(body)
    assert decoded["actors" if enterprise else "acteurs"] == [actor] * 30
    assert decoded["synopsis"] == "🎬" * 4000
    if enterprise:
        assert decoded["genres"] == [genre] * 30


def test_enlarged_body_limit_applies_only_to_movie_forms(monkeypatch):
    client, calls, _ = native_client(monkeypatch, True)
    form = BrowserForm(client.get("/films/film-id/modifier"))
    body = MultiDict(
        [(key, value) for key, value in form.data.items(multi=True) if key == "csrf_token"]
    )
    body["extra"] = "a" * 70000
    assert client.post("/profil", data=body).status_code == 413
    assert mutations(calls) == []
