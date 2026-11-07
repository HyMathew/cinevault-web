import io
import re

from test_accounts import PROFILE, TOKEN, csrf
from test_accounts import accounts as accounts

from app.api_client import APIError


def test_transfer_is_manager_only_and_csrf_protected(accounts):
    client, api = accounts
    assert client.get("/transfert").status_code == 303
    client.set_cookie("cinevault_auth", TOKEN)
    assert client.get("/transfert").status_code == 403
    api.me.return_value = {**PROFILE, "role": "manager"}
    assert client.get("/transfert").status_code == 200
    assert client.post("/transfert", data={}).status_code == 400
    api.import_catalogue.assert_not_called()


def test_upload_json_carrier_retains_key_after_failure(accounts):
    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    api.me.return_value = {**PROFILE, "role": "manager"}
    page = client.get("/transfert")
    key = re.search(rb'name="operation_key" value="([^"]+)"', page.data).group(1).decode()
    api.import_catalogue.side_effect = APIError(503, "unavailable")
    response = client.post(
        "/transfert",
        data={
            "csrf_token": csrf(page),
            "operation_key": key,
            "format": "json",
            "duplicate_policy": "skip",
            "file": (io.BytesIO(b'{"format_version":1,"movies":[]}'), "private-name.json"),
        },
    )
    assert response.status_code == 503
    assert key.encode() in response.data and b"private-name" not in response.data
    api.import_catalogue.assert_called_once_with(
        TOKEN,
        {
            "format": "json",
            "content": '{"format_version":1,"movies":[]}',
            "duplicate_policy": "skip",
        },
        key,
    )
    api.import_catalogue.side_effect = None
    api.import_catalogue.return_value = {
        "operation_id": "operation",
        "created_movies": 1,
        "created_copies": 2,
        "skipped_movies": 0,
        "skipped_copies": 0,
    }
    response = client.post(
        "/transfert",
        data={
            "csrf_token": csrf(page),
            "operation_key": key,
            "format": "csv",
            "duplicate_policy": "reject",
            "file": (io.BytesIO(b"header"), "file.csv"),
        },
    )
    assert response.status_code == 200 and b"Import termin" in response.data


def test_download_and_bad_upload(accounts):
    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    api.me.return_value = {**PROFILE, "role": "admin"}
    page = client.get("/transfert")
    key = re.search(rb'name="operation_key" value="([^"]+)"', page.data).group(1).decode()
    response = client.post(
        "/transfert",
        data={
            "csrf_token": csrf(page),
            "operation_key": key,
            "format": "json",
            "duplicate_policy": "reject",
            "file": (io.BytesIO(b"\xff"), "bad.json"),
        },
    )
    assert response.status_code == 422
    api.import_catalogue.assert_not_called()
    api.export_catalogue.return_value = {
        "format": "json",
        "content": {"format_version": 1, "movies": []},
        "filename": "ignored.json",
    }
    response = client.get("/transfert/export?format=json")
    assert response.status_code == 200 and response.is_json
    assert response.json == {"format_version": 1, "movies": []}
    assert (
        response.headers["Content-Disposition"] == 'attachment; filename="cinevault-catalogue.json"'
    )
    assert response.headers["Cache-Control"] == "no-store"


def test_transfer_upload_file_bound_is_independent_of_ordinary_form_bound(accounts):
    client, api = accounts
    client.set_cookie("cinevault_auth", TOKEN)
    api.me.return_value = {**PROFILE, "role": "manager"}
    page = client.get("/transfert")
    token = csrf(page)
    key = re.search(rb'name="operation_key" value="([^"]+)"', page.data).group(1).decode()
    fields = {
        "csrf_token": token,
        "operation_key": key,
        "format": "json",
        "duplicate_policy": "reject",
    }
    api.import_catalogue.return_value = {
        "operation_id": "operation",
        "created_movies": 0,
        "created_copies": 0,
        "skipped_movies": 0,
        "skipped_copies": 0,
    }
    assert (
        client.post(
            "/transfert", data={**fields, "file": (io.BytesIO(b" " * 70000), "large.json")}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/transfert", data={**fields, "file": (io.BytesIO(b" " * 1048577), "too-large.json")}
        ).status_code
        == 422
    )
    assert api.import_catalogue.call_count == 1
    assert (
        client.post("/profil", data={"csrf_token": token, "display_name": "a" * 70000}).status_code
        == 413
    )
