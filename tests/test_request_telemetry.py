import io
import json
import re
from types import SimpleNamespace
from uuid import UUID

import pytest
import requests

from app import create_app

CLIENT_ID = "aaaaaaaaaaaa4aaa8aaaaaaaaaaaaaaa"


def application(**settings):
    return create_app(
        {"SECRET_KEY": "synthetic-test-session-secret" * 2, "API_URL": "http://api", **settings}
    )


def events(stream):
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.startswith("{")]


def assert_access_event(event, response, method, route, **extra):
    request_id = response.headers["X-Request-ID"]
    assert re.fullmatch(r"[0-9a-f]{32}", request_id)
    assert UUID(request_id).version == 4
    assert request_id != CLIENT_ID
    duration = event["duration_ms"]
    assert type(duration) in (float, int) and duration >= 0
    assert event == {
        "service": "web",
        "request_id": request_id,
        "method": method,
        "route": route,
        "status": response.status_code,
        "duration_ms": duration,
        **extra,
    }


def test_health_logs_server_ids_without_request_values():
    client = application(TESTING=True).test_client()
    stream = io.StringIO()
    client.set_cookie("private-cookie-canary", "private-cookie-value")
    headers = {"X-Request-ID": CLIENT_ID, "Authorization": "Bearer private-bearer-canary"}

    first = client.get(
        "/health?q=private-search-canary",
        headers=headers,
        environ_overrides={"wsgi.errors": stream},
    )
    second = client.get("/health", headers=headers, environ_overrides={"wsgi.errors": stream})

    assert first.status_code == second.status_code == 200
    assert first.get_json() == second.get_json() == {"status": "ok"}
    assert first.headers["X-Content-Type-Options"] == "nosniff"
    first_event, second_event = events(stream)
    assert_access_event(first_event, first, "GET", "/health")
    assert_access_event(second_event, second, "GET", "/health")
    assert first_event["request_id"] != second_event["request_id"]
    assert "private-" not in stream.getvalue()
    assert CLIENT_ID not in stream.getvalue()


@pytest.mark.parametrize(
    ("method", "path", "logged_method", "status"),
    [
        ("GET", "/private-missing-path?q=private-query", "GET", 404),
        ("PRIVATE-METHOD", "/health", "OTHER", 405),
    ],
)
def test_routing_failures_use_fixed_route_and_method_values(method, path, logged_method, status):
    stream = io.StringIO()
    response = (
        application(TESTING=True)
        .test_client()
        .open(path, method=method, environ_overrides={"wsgi.errors": stream})
    )

    assert response.status_code == status
    (event,) = events(stream)
    assert_access_event(event, response, logged_method, "unmatched")
    assert "private" not in stream.getvalue().lower()


def test_api_response_correlations_are_canonical_bounded_and_per_request(monkeypatch):
    app = application(TESTING=True)
    ids = [f"{index:012x}40008000000000000000" for index in range(10)]
    response_ids = [
        "private-response-header",
        CLIENT_ID.upper(),
        "1" * 32,
        ids[0],
        ids[0],
        *ids[1:],
    ]
    remaining_ids = iter(response_ids)
    observed = []

    def request_api(method, url, **kwargs):
        observed.append(kwargs.get("headers", {}))
        return SimpleNamespace(
            status_code=200,
            headers={"X-Request-ID": next(remaining_ids)},
            json=lambda: {"films": []},
        )

    monkeypatch.setattr(requests, "request", request_api)

    @app.get("/test-linked/<film_id>")
    def linked(film_id):
        for _ in response_ids:
            app.extensions["cinevault_api"].list(q=film_id)
        return "OK"

    stream = io.StringIO()
    client = app.test_client()
    response = client.get(
        "/test-linked/private-film-id",
        headers={"X-Request-ID": CLIENT_ID},
        environ_overrides={"wsgi.errors": stream},
    )
    health = client.get("/health", environ_overrides={"wsgi.errors": stream})

    assert response.status_code == 200 and response.get_data() == b"OK"
    assert observed == [{}] * len(response_ids)
    linked_event, health_event = events(stream)
    assert_access_event(
        linked_event, response, "GET", "/test-linked/<film_id>", api_request_ids=ids[:8]
    )
    assert_access_event(health_event, health, "GET", "/health")
    assert "private-" not in stream.getvalue()


def test_unhandled_error_does_not_log_path_or_exception_data(caplog):
    app = application()

    @app.get("/test-error/<value>")
    def raise_error(value):
        raise RuntimeError("private-exception-header-value")

    stream = io.StringIO()
    response = app.test_client().get(
        "/test-error/private-path-fragment", environ_overrides={"wsgi.errors": stream}
    )

    assert response.status_code == 500
    (event,) = events(stream)
    assert_access_event(event, response, "GET", "/test-error/<value>")
    assert "private-" not in stream.getvalue() + caplog.text
    assert "Traceback" not in stream.getvalue() + caplog.text
