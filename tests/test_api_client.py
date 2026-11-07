import pytest
import requests

from app.api_client import APIClient, APIError


def test_timeout_causes_explicit_unavailability_without_retry(monkeypatch):
    attempts = []

    def fail(method, url, **kwargs):
        attempts.append((method, kwargs["timeout"]))
        raise requests.Timeout()

    monkeypatch.setattr(requests, "request", fail)
    with pytest.raises(APIError) as failure:
        APIClient("http://api").create({"titre": "Film"})
    assert failure.value.status == 503
    assert attempts == [("POST", (2, 5))]


def test_http_validation_error_is_exposed_to_form(monkeypatch):
    class Response:
        status_code = 422

        def json(self):
            return {"error": {"message": "Titre invalide", "fields": {"titre": "Trop long"}}}

    monkeypatch.setattr(requests, "request", lambda *a, **k: Response())
    with pytest.raises(APIError) as failure:
        APIClient("http://api").create({"titre": "x"})
    assert failure.value.status == 422
    assert failure.value.fields == {"titre": "Trop long"}


def test_absent_film_maps_404_to_none(monkeypatch):
    class Response:
        status_code = 404

        def json(self):
            return {"error": {"message": "Absent"}}

    monkeypatch.setattr(requests, "request", lambda *a, **k: Response())
    assert APIClient("http://api").get("abc") is None
