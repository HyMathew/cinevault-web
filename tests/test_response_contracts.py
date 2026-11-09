"""Exercise the native HTTP boundary; no remote API or injected route client."""

from copy import deepcopy

import pytest

from app import create_app
from app.api_client import APIClient, APIError

MOVIE = {
    "id": "synthetic-movie",
    "title": "Synthetic film",
    "year": 2000,
    "director": "Synthetic director",
    "actors": [],
    "synopsis": "",
    "genres": [],
    "_etag": '"synthetic-version"',
    "external_source": None,
}
LEGACY = {
    "id": "synthetic-movie",
    "titre": "Synthetic film",
    "annee": 2000,
    "realisateur": "Synthetic director",
    "acteurs": [],
    "synopsis": "",
    "support": "dvd",
}
PAGE = {"total": 0, "limit": 24, "offset": 0}
MOVIES = {**PAGE, "movies": [], "copy_summaries": {}}
PROFILE = {
    "id": "synthetic-user",
    "username": "synthetic",
    "display_name": "Synthetic member",
    "role": "member",
    "enabled": True,
}
LOAN = {
    "id": "synthetic-loan",
    "movie_id": MOVIE["id"],
    "borrower_id": PROFILE["id"],
    "copy_id": None,
    "status": "pending",
    "requested_at": 1700000000,
    "approved_at": None,
    "due_at": None,
    "returned_at": None,
    "cancelled_at": None,
    "_etag": '"synthetic-version"',
}
METADATA = {
    "film": {
        "id": "Q123",
        "title": "Synthetic film",
        "year": None,
        "director": "",
        "actors": [],
        "genres": [],
        "description": "",
        "poster_filename": None,
        "poster": None,
        "revision": 1,
        "retrieved_at": 1700000000,
        "source_url": "https://www.wikidata.org/wiki/Q123",
        "warnings": [],
    },
    "cache": {"status": "stale", "stored_at": 1700000000, "hit": True},
}
ENTRY = {
    "id": "synthetic-entry",
    "movie_id": MOVIE["id"],
    "kind": "favorite",
    "list_name": "",
    "supports": [],
    "_etag": '"synthetic-version"',
}
RESERVATION = {
    "id": "synthetic-reservation",
    "movie_id": MOVIE["id"],
    "user_id": PROFILE["id"],
    "status": "waiting",
    "created_at": 1700000000,
    "expires_at": 1700000001,
    "_etag": '"synthetic-version"',
}
STATISTICS = {
    "catalogue": {
        "movies": 0,
        "copies": 0,
        "available": 0,
        "held_for_queue": 0,
        "damaged": 0,
        "by_support": {},
        "by_genre": {},
    },
    "personal": {
        "collection_movies": 0,
        "collection_entries": 0,
        "by_kind": {},
        "by_owned_support": {},
        "loans": {},
        "overdue": 0,
        "waiting_reservations": 0,
        "activity_last_7_days": 0,
        "activity_retained": 0,
        "recent_activity": [],
    },
}


def transport(monkeypatch, responses):
    calls = []

    class Response:
        headers = {}

        def __init__(self, status, value):
            self.status_code, self.value = status, value

        def json(self):
            return deepcopy(self.value)

    def send(method, url, **kwargs):
        key = (method, url.removeprefix("http://offline.invalid"))
        calls.append(key)
        status, value = responses[key]
        return Response(status, value)

    monkeypatch.setattr("requests.request", send)
    return calls


def web_client(enterprise=False):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "synthetic-test-key",
            "ENTERPRISE_ENABLED": enterprise,
            "API_CLIENT": APIClient("http://offline.invalid", enterprise=enterprise),
        }
    )
    return app.test_client()


@pytest.mark.parametrize(
    "payload",
    [[], {**MOVIES, "offset": None}, {**MOVIES, "movies": [{"id": "missing-title"}]}],
    ids=["non-object-root", "null-pagination", "missing-movie-field"],
)
def test_malformed_enterprise_catalogue_is_controlled_unavailability(monkeypatch, payload):
    if isinstance(payload, dict) and payload.get("movies"):
        payload = {**payload, "copy_summaries": {"missing-title": {"count": 0, "supports": []}}}
    calls = transport(monkeypatch, {("GET", "/api/v1/movies"): (200, payload)})
    response = web_client(True).get("/films")
    assert response.status_code == 503
    assert "indisponible".encode() in response.data
    assert calls == [("GET", "/api/v1/movies")]


def test_null_legacy_list_is_controlled_unavailability(monkeypatch):
    transport(monkeypatch, {("GET", "/api/films"): (200, {"films": None})})
    assert web_client().get("/films").status_code == 503


def test_null_genres_is_rejected_before_rendering_movie(monkeypatch):
    transport(
        monkeypatch,
        {
            ("GET", "/api/v1/movies/synthetic-movie"): (200, {**MOVIE, "genres": None}),
            ("GET", "/api/v1/copies"): (200, {"copies": []}),
            ("GET", "/api/v1/availability"): (200, {"available": 0}),
        },
    )
    assert web_client(True).get("/films/synthetic-movie").status_code == 503


def test_malformed_creation_preserves_fields_and_never_replays_post(monkeypatch):
    calls = transport(monkeypatch, {("POST", "/api/films"): (201, {})})
    client = web_client()
    with client.session_transaction() as session:
        session["csrf_token"] = "synthetic-csrf"
    response = client.post(
        "/films/nouveau",
        data={
            "csrf_token": "synthetic-csrf",
            "titre": "Keep my entered film",
            "annee": "2000",
            "realisateur": "Synthetic director",
            "acteurs": "",
            "synopsis": "Keep my entered synopsis",
            "support": "dvd",
        },
    )
    assert response.status_code == 503
    assert b"Keep my entered film" in response.data
    assert b"Keep my entered synopsis" in response.data
    assert "vérifiez le résultat".encode() in response.data
    assert calls == [("POST", "/api/films")]


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/api/films", {"films": [None]}),
        ("/api/films/id", {**LEGACY, "acteurs": "not-a-list"}),
        ("/api/v1/movies", {**MOVIES, "total": True}),
        ("/api/v1/movies", {**MOVIES, "copy_summaries": None}),
        ("/api/v1/movies/id", {**MOVIE, "actors": [None]}),
        ("/api/v1/copies", {"copies": [None]}),
        ("/api/v1/copies/id", {"movie_id": []}),
        ("/api/v1/availability", {"available": None}),
        ("/api/v1/users", {**PAGE, "users": None}),
        ("/api/v1/collections", {**PAGE, "entries": [], "movies": None}),
        ("/api/v1/collections/id", {"movie_id": None}),
        ("/api/v1/loans", {**PAGE, "loans": [], "movies": {}, "borrowers": {}}),
        ("/api/v1/loans/id", {**LOAN, "due_at": "tomorrow"}),
        ("/api/v1/loans/id/options", {"loan_id": "id", "copies": None}),
        ("/api/v1/reservations", {**PAGE, "reservations": None}),
        ("/api/v1/metadata/search", {"items": None, "cache": METADATA["cache"]}),
        ("/api/v1/metadata/Q123", {**METADATA, "film": None}),
        ("/api/v1/metadata/Q123", {**METADATA, "film": {**METADATA["film"], "actors": None}}),
        ("/api/v1/statistics", {"catalogue": {}, "personal": {}}),
        ("/api/v1/recommendations", {"recommendations": None}),
    ],
)
def test_native_consumed_response_shapes_raise_apierror(monkeypatch, path, payload):
    transport(monkeypatch, {("GET", path): (200, payload)})
    with pytest.raises(APIError) as failure:
        APIClient("http://offline.invalid").request("GET", path)
    assert failure.value.status == 503
    assert "invalide" in str(failure.value)


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/api/films", {"films": []}),
        ("/api/films/id", LEGACY),
        ("/api/v1/movies", MOVIES),
        ("/api/v1/movies/id", MOVIE),
        ("/api/v1/copies", {"copies": []}),
        ("/api/v1/loans/id", LOAN),
        ("/api/v1/metadata/Q123", METADATA),
        ("/api/v1/metadata/search", {"items": [], "cache": METADATA["cache"]}),
    ],
)
def test_valid_empty_and_nullable_fields_remain_usable(monkeypatch, path, payload):
    transport(monkeypatch, {("GET", path): (200, payload)})
    assert APIClient("http://offline.invalid").request("GET", path) == payload


@pytest.mark.parametrize("status", [401, 403, 404, 409, 412, 422, 428, 429, 503])
def test_http_error_is_not_reclassified_as_invalid_success(monkeypatch, status):
    transport(monkeypatch, {("GET", "/api/films"): (status, {"error": {"message": "Synthetic"}})})
    with pytest.raises(APIError) as failure:
        APIClient("http://offline.invalid").list()
    assert failure.value.status == status


def test_no_content_and_optional_posters_keep_existing_behavior(monkeypatch):
    transport(
        monkeypatch,
        {
            ("DELETE", "/api/films/id"): (204, None),
            ("GET", "/api/v1/posters"): (200, {"posters": {"id": {"image_url": "invalid"}}}),
        },
    )
    client = APIClient("http://offline.invalid")
    assert client.delete("id") is None
    assert client.posters(["id"]) == {}


@pytest.mark.parametrize(
    "route,path,payload",
    [
        (
            "/ma-collection",
            "/api/v1/collections",
            {**PAGE, "total": 1, "entries": [ENTRY], "movies": {MOVIE["id"]: MOVIE}},
        ),
        (
            "/emprunts",
            "/api/v1/loans",
            {
                **PAGE,
                "total": 1,
                "loans": [LOAN],
                "movies": {MOVIE["id"]: MOVIE},
                "borrowers": {PROFILE["id"]: PROFILE},
                "overdue_ids": [],
            },
        ),
        (
            "/reservations",
            "/api/v1/reservations",
            {
                **PAGE,
                "total": 1,
                "reservations": [RESERVATION],
                "movies": {MOVIE["id"]: MOVIE},
                "users": {PROFILE["id"]: PROFILE},
                "positions": {RESERVATION["id"]: 1},
                "ready_ids": [],
                "open_loan_ids": {},
            },
        ),
        ("/mon-espace", "/api/v1/statistics", STATISTICS),
        (
            "/decouvrir",
            "/api/v1/recommendations",
            {"personalized": False, "total": 0, "recommendations": []},
        ),
    ],
)
def test_native_authenticated_views_accept_valid_structures(monkeypatch, route, path, payload):
    transport(monkeypatch, {("GET", "/api/v1/me"): (200, PROFILE), ("GET", path): (200, payload)})
    client = web_client(True)
    client.set_cookie("cinevault_auth", "synthetic-test-bearer-token-123456789")
    response = client.get(route)
    assert response.status_code == 200


def test_native_metadata_preview_accepts_unknown_year_and_no_poster(monkeypatch):
    transport(
        monkeypatch,
        {
            ("GET", "/api/v1/me"): (200, {**PROFILE, "role": "manager"}),
            ("GET", "/api/v1/metadata/Q123"): (200, METADATA),
        },
    )
    client = web_client(True)
    client.set_cookie("cinevault_auth", "synthetic-test-bearer-token-123456789")
    response = client.get("/metadonnees/Q123")
    assert response.status_code == 200
    assert "Année à compléter".encode() in response.data
    assert "cache ancien".encode() in response.data


@pytest.mark.parametrize("timestamp", ["yesterday", 10**100], ids=["noninteger", "overflow"])
def test_unrenderable_activity_date_is_controlled_unavailability(monkeypatch, timestamp):
    payload = deepcopy(STATISTICS)
    payload["personal"]["recent_activity"] = [{"action": "movie.created", "timestamp": timestamp}]
    transport(
        monkeypatch,
        {("GET", "/api/v1/me"): (200, PROFILE), ("GET", "/api/v1/statistics"): (200, payload)},
    )
    client = web_client(True)
    client.set_cookie("cinevault_auth", "synthetic-test-bearer-token-123456789")
    assert client.get("/mon-espace").status_code == 503


def test_empty_success_cannot_replace_enterprise_catalogue_json(monkeypatch):
    transport(monkeypatch, {("GET", "/api/v1/movies"): (204, None)})
    assert web_client(True).get("/films").status_code == 503


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/films"),
        ("GET", "/api/v1/movies/id"),
        ("GET", "/api/v1/metadata/Q123"),
        ("POST", "/api/films"),
        ("POST", "/api/v1/movies"),
        ("PUT", "/api/v1/movies/id"),
        ("DELETE", "/api/v1/unknown/id"),
    ],
)
def test_unexpected_no_content_is_controlled_apierror(monkeypatch, method, path):
    transport(monkeypatch, {(method, path): (204, None)})
    with pytest.raises(APIError) as failure:
        APIClient("http://offline.invalid").request(method, path)
    assert failure.value.status == 503


@pytest.mark.parametrize(
    "method,path",
    [
        ("DELETE", "/api/films/id"),
        ("DELETE", "/api/v1/movies/id"),
        ("DELETE", "/api/v1/copies/id"),
        ("DELETE", "/api/v1/collections/id"),
        ("POST", "/api/v1/auth/logout"),
        ("PUT", "/api/v1/me/password"),
    ],
)
def test_documented_no_content_operations_remain_valid(monkeypatch, method, path):
    transport(monkeypatch, {(method, path): (204, None)})
    assert APIClient("http://offline.invalid").request(method, path) is None


@pytest.mark.parametrize("title", ["\ud800", "\udfff"], ids=["high-surrogate", "low-surrogate"])
def test_unencodable_movie_text_is_controlled_unavailability(monkeypatch, title):
    transport(monkeypatch, {("GET", "/api/films"): (200, {"films": [{**LEGACY, "titre": title}]})})
    assert web_client().get("/films").status_code == 503


def test_unencodable_mapping_key_is_controlled_unavailability(monkeypatch):
    payload = deepcopy(STATISTICS)
    payload["catalogue"]["by_genre"] = {"\ud800": 1}
    transport(
        monkeypatch,
        {("GET", "/api/v1/me"): (200, PROFILE), ("GET", "/api/v1/statistics"): (200, payload)},
    )
    client = web_client(True)
    client.set_cookie("cinevault_auth", "synthetic-test-bearer-token-123456789")
    assert client.get("/mon-espace").status_code == 503


def test_unencodable_profile_is_rejected_before_template_rendering(monkeypatch):
    transport(monkeypatch, {("GET", "/api/v1/me"): (200, {**PROFILE, "display_name": "\ud800"})})
    client = web_client(True)
    client.set_cookie("cinevault_auth", "synthetic-test-bearer-token-123456789")
    assert client.get("/profil").status_code == 503


@pytest.mark.parametrize("content", ["\ud800", {"movies": [{"title": "\ud800"}]}])
def test_unencodable_export_content_is_rejected_at_native_boundary(monkeypatch, content):
    payload = {"format": "csv" if isinstance(content, str) else "json", "content": content}
    transport(monkeypatch, {("GET", "/api/v1/catalogue/export"): (200, payload)})
    with pytest.raises(APIError) as failure:
        APIClient("http://offline.invalid").export_catalogue("synthetic-token", payload["format"])
    assert failure.value.status == 503


def test_unencodable_optional_poster_is_discarded(monkeypatch):
    poster = {
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Synthetic.jpg",
        "source_url": "https://commons.wikimedia.org/wiki/File:Synthetic.jpg",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "artist": "\ud800",
        "license": "CC BY 4.0",
    }
    transport(monkeypatch, {("GET", "/api/v1/posters"): (200, {"posters": {"id": poster}})})
    assert APIClient("http://offline.invalid").posters(["id"]) == {}


def test_ordinary_unicode_text_and_dictionary_keys_remain_renderable(monkeypatch):
    title = "Été à Reykjavík 🎬"
    transport(monkeypatch, {("GET", "/api/films"): (200, {"films": [{**LEGACY, "titre": title}]})})
    response = web_client().get("/films")
    assert response.status_code == 200
    assert title.encode("utf-8") in response.data
    payload = deepcopy(STATISTICS)
    payload["catalogue"]["by_genre"] = {"Comédie 🎬": 1}
    transport(monkeypatch, {("GET", "/api/v1/statistics"): (200, payload)})
    assert APIClient("http://offline.invalid").statistics("synthetic-token") == payload
