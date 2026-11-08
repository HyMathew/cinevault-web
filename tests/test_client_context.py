"""A browser's forwarding headers never select the API's rate-limit identity."""

import hashlib
import hmac
import json
import time

import pytest
from test_accounts import accounts as accounts
from test_accounts import csrf

from app import create_app
from app.api_client import APIClient, APIError

KEY = b"synthetic-client-context-key-1234567890"


@pytest.mark.parametrize(
    "operation,path", [("login", "/api/v1/auth/login"), ("register", "/api/v1/auth/register")]
)
def test_auth_client_signs_observed_peer_and_exact_request_body(monkeypatch, operation, path):
    calls = []

    class Response:
        status_code = 200

        def json(self):
            return {"synthetic": True}

    def send(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return Response()

    monkeypatch.setattr("requests.request", send)
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "synthetic-cookie-key",
            "ENTERPRISE_ENABLED": True,
            "CLIENT_CONTEXT_KEY": KEY,
        }
    )
    data = {"username": "synthetic-visitor", "password": "synthetic passphrase été"}
    with app.test_request_context(
        "/connexion",
        environ_base={"REMOTE_ADDR": "198.51.100.10"},
        headers={"X-Forwarded-For": "198.51.100.99"},
    ):
        assert getattr(app.extensions["cinevault_api"], operation)(data) == {"synthetic": True}
    assert len(calls) == 1
    method, url, options = calls[0]
    assert method == "POST" and url.endswith(path)
    headers = options["headers"]
    assert headers["X-CineVault-Client-IP"] == "198.51.100.10"
    assert abs(int(headers["X-CineVault-Client-Time"]) - int(time.time())) <= 1
    assert json.loads(options["data"]) == data
    message = "\n".join(
        (
            "cinevault-client-v1",
            headers["X-CineVault-Client-Time"],
            "198.51.100.10",
            method,
            path,
            hashlib.sha256(options["data"]).hexdigest(),
        )
    )
    assert hmac.compare_digest(
        headers["X-CineVault-Client-Signature"],
        hmac.new(KEY, message.encode("ascii"), hashlib.sha256).hexdigest(),
    )
    assert options["allow_redirects"] is False


def test_client_context_key_file_is_loaded_and_invalid_key_fails(tmp_path):
    keyfile = tmp_path / "context-key"
    keyfile.write_bytes(KEY)
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "synthetic-cookie-key",
            "ENTERPRISE_ENABLED": True,
            "CLIENT_CONTEXT_KEY_FILE": str(keyfile),
        }
    )
    assert app.extensions["cinevault_api"].client_context_key == KEY
    with pytest.raises(RuntimeError):
        create_app({"SECRET_KEY": "synthetic-cookie-key", "CLIENT_CONTEXT_KEY": b"short"})


@pytest.mark.parametrize("value,expected", [("60", 60), ("invalid", None), ("99999", None)])
def test_api_client_keeps_only_bounded_retry_after(monkeypatch, value, expected):
    class Response:
        status_code = 429
        headers = {"Retry-After": value}

        def json(self):
            return {"error": {"message": "Synthetic rate limit"}}

    monkeypatch.setattr("requests.request", lambda *args, **kwargs: Response())
    with pytest.raises(APIError) as failure:
        APIClient("http://api").login({"username": "synthetic", "password": "synthetic"})
    assert failure.value.retry_after == expected


@pytest.mark.parametrize("route,operation", [("/connexion", "login"), ("/inscription", "register")])
def test_account_error_preserves_retry_after_for_browser(accounts, route, operation):
    client, api = accounts
    getattr(api, operation).side_effect = APIError(429, "Synthetic limit", retry_after=60)
    token = csrf(client.get(route))
    response = client.post(
        route,
        data={
            "csrf_token": token,
            "username": "synthetic",
            "display_name": "Synthetic",
            "password": "synthetic passphrase",
            "password_confirmation": "synthetic passphrase",
        },
    )
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
