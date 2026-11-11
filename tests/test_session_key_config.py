"""Session-signing keys have one startup boundary, regardless of their source."""

import pytest
from flask import Flask

from app import create_app


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch):
    # No test reads an operator's key file or uses an inherited secret.
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("SECRET_KEY_FILE", raising=False)
    monkeypatch.delenv("ENTERPRISE_ENABLED", raising=False)


@pytest.mark.parametrize("testing", [False, True])
@pytest.mark.parametrize(
    "key",
    [None, "", b"", "s" * 31, b"s" * 31, "é" * 15 + "a", 1, True, [], {}, bytearray(32)],
    ids=[
        "absent",
        "empty-text",
        "empty-bytes",
        "31-text",
        "31-bytes",
        "31-utf8-bytes",
        "integer",
        "boolean",
        "list",
        "mapping",
        "bytearray",
    ],
)
def test_invalid_direct_key_refuses_startup_even_when_testing(key, testing):
    with pytest.raises(RuntimeError, match="32 octets"):
        create_app({"TESTING": testing, "SECRET_KEY": key})


@pytest.mark.parametrize("key", ["a" * 32, "é" * 16, b"a" * 32, bytes(range(32))])
def test_valid_direct_key_uses_bytes_length_and_keeps_its_value_and_type(key):
    app = create_app({"SECRET_KEY": key})
    assert app.secret_key == key
    assert type(app.secret_key) is type(key)


def test_invalid_unicode_key_fails_without_echoing_value_or_encoding_exception(caplog):
    key = "synthetic-private-key-marker-123456789\ud800"
    with pytest.raises(RuntimeError, match="32 octets") as failure:
        create_app({"SECRET_KEY": key})
    assert "synthetic-private-key-marker" not in str(failure.value)
    assert failure.value.__context__ is None
    assert "synthetic-private-key-marker" not in caplog.text


def test_short_environment_key_is_rejected_and_configuration_can_override_it(monkeypatch):
    key = "synthetic-short-key"
    monkeypatch.setenv("SECRET_KEY", key)
    with pytest.raises(RuntimeError, match="32 octets") as failure:
        create_app()
    assert key not in str(failure.value)
    configured = "synthetic-explicit-config-key-1234567890"
    assert create_app({"SECRET_KEY": configured}).secret_key == configured


def test_environment_accepts_32_utf8_bytes_without_reencoding_stored_key(monkeypatch):
    key = "é" * 16
    monkeypatch.setenv("SECRET_KEY", key)
    assert create_app().secret_key == key


@pytest.mark.parametrize("key", [b"", b"s" * 31])
def test_short_file_key_refuses_startup_without_fallback(tmp_path, key):
    path = tmp_path / "synthetic-key"
    path.write_bytes(key)
    with pytest.raises(RuntimeError, match="32 octets"):
        create_app({"SECRET_KEY_FILE": path, "SECRET_KEY": "valid-unused-fallback-key-1234567890"})


@pytest.mark.parametrize("source", ["configuration", "environment"])
def test_file_key_takes_precedence_without_trimming_or_decoding(tmp_path, monkeypatch, source):
    key = b" \t\n" + bytes(range(32)) + b"\r\n "
    path = tmp_path / "synthetic-key"
    path.write_bytes(key)
    config = {"SECRET_KEY": "short-ignored-key"}
    if source == "configuration":
        config["SECRET_KEY_FILE"] = path
    else:
        monkeypatch.setenv("SECRET_KEY_FILE", str(path))
    app = create_app(config)
    assert app.secret_key == key
    assert type(app.secret_key) is bytes


@pytest.mark.parametrize("file_source", [False, True])
def test_valid_key_preserves_preexisting_flask_cookie_signature(tmp_path, file_source):
    key = b" \tsynthetic-cookie-compatibility-key-1234567890\r\n"
    old = Flask("pre_validation_application")
    old.secret_key = key
    old_serializer = old.session_interface.get_signing_serializer(old)
    payload = {"csrf_token": "synthetic-csrf-token", "compatibility_marker": "preserved"}
    cookie = old_serializer.dumps(payload)
    if file_source:
        path = tmp_path / "synthetic-key"
        path.write_bytes(key)
        new = create_app({"SECRET_KEY_FILE": path})
    else:
        new = create_app({"SECRET_KEY": key})
    new_serializer = new.session_interface.get_signing_serializer(new)
    assert new_serializer.loads(cookie) == payload
    assert old_serializer.loads(new_serializer.dumps(payload)) == payload
    client = new.test_client()
    client.set_cookie(new.config["SESSION_COOKIE_NAME"], cookie)
    with client.session_transaction() as session:
        assert session["csrf_token"] == payload["csrf_token"]
        assert session["compatibility_marker"] == "preserved"


@pytest.mark.parametrize(
    "fallbacks",
    [
        ["short"],
        [b"s" * 31],
        ["é" * 15],
        [None],
        ["synthetic-valid-previous-key-1234567890", "short"],
        ["s" * 32 + "\ud800"],
    ],
    ids=[
        "short-text",
        "short-bytes",
        "short-utf8",
        "invalid-type",
        "second-key-short",
        "invalid-unicode",
    ],
)
def test_weak_or_invalid_fallback_key_also_refuses_startup(fallbacks):
    with pytest.raises(RuntimeError, match="32 octets"):
        create_app(
            {
                "SECRET_KEY": "synthetic-current-key-123456789012345",
                "SECRET_KEY_FALLBACKS": fallbacks,
            }
        )


@pytest.mark.parametrize("fallbacks", ["s" * 32, b"s" * 32, 0, False, {"s" * 32: "value"}])
def test_fallbacks_require_an_explicit_key_sequence(fallbacks):
    with pytest.raises(RuntimeError, match="anciennes clés"):
        create_app(
            {
                "SECRET_KEY": "synthetic-current-key-123456789012345",
                "SECRET_KEY_FALLBACKS": fallbacks,
            }
        )


@pytest.mark.parametrize("as_tuple", [False, True])
def test_valid_fallbacks_keep_order_values_and_flask_rotation_compatibility(as_tuple):
    old_keys = [
        "synthetic-previous-key-123456789012345",
        b" \tprevious-binary-key-123456789012345\r\n",
    ]
    fallbacks = tuple(old_keys) if as_tuple else old_keys
    current = "synthetic-current-key-123456789012345"
    new = create_app({"SECRET_KEY": current, "SECRET_KEY_FALLBACKS": fallbacks})
    assert new.config["SECRET_KEY_FALLBACKS"] is fallbacks
    assert list(new.config["SECRET_KEY_FALLBACKS"]) == old_keys
    serializer = new.session_interface.get_signing_serializer(new)
    payload = {"csrf_token": "synthetic-csrf-from-before-rotation"}
    for key in old_keys:
        previous = Flask("previous_application")
        previous.secret_key = key
        assert (
            serializer.loads(
                previous.session_interface.get_signing_serializer(previous).dumps(payload)
            )
            == payload
        )
    # Newly emitted cookies must use the current key, not either fallback.
    current_only = Flask("current_application")
    current_only.secret_key = current
    assert (
        current_only.session_interface.get_signing_serializer(current_only).loads(
            serializer.dumps(payload)
        )
        == payload
    )


@pytest.mark.parametrize("fallbacks", [None, [], ()])
def test_fallbacks_remain_optional(fallbacks):
    app = create_app(
        {"SECRET_KEY": "synthetic-current-key-123456789012345", "SECRET_KEY_FALLBACKS": fallbacks}
    )
    assert app.config["SECRET_KEY_FALLBACKS"] is fallbacks


def test_configured_key_file_keeps_precedence_over_environment_file(tmp_path, monkeypatch):
    configured, ignored = tmp_path / "configured-key", tmp_path / "ignored-key"
    key = b"synthetic-configured-file-key-1234567890\n"
    configured.write_bytes(key)
    ignored.write_bytes(b"short")
    monkeypatch.setenv("SECRET_KEY_FILE", str(ignored))
    assert create_app({"SECRET_KEY_FILE": configured}).secret_key == key
