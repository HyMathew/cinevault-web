"""Structural checks for JSON consumed by the native HTTP client and web views.

These deliberately allow extra fields and synthetic identifiers. The API remains
responsible for business validation; optional posters retain their own fallback.
"""

from datetime import datetime, timezone


def _text(value):
    if not isinstance(value, str):
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _integer(value):
    return type(value) is int and value >= 0


def _boolean(value):
    return type(value) is bool


def _nullable(check):
    return lambda value: value is None or check(value)


def _array(check):
    return lambda value: isinstance(value, list) and all(check(item) for item in value)


def _mapping(check):
    return lambda value: (
        isinstance(value, dict) and all(_text(key) and check(item) for key, item in value.items())
    )


def _fields(value, **checks):
    return isinstance(value, dict) and all(
        key in value and check(value[key]) for key, check in checks.items()
    )


def _page(value):
    return _fields(value, total=_integer, limit=_integer, offset=_integer)


def _movie(value):
    return _fields(
        value,
        id=_text,
        title=_text,
        year=_integer,
        director=_text,
        actors=_array(_text),
        synopsis=_text,
        genres=_array(_text),
        _etag=_text,
    ) and (
        "external_source" not in value
        or value["external_source"] is None
        or _fields(value["external_source"], qid=_text, revision=_integer, retrieved_at=_integer)
    )


def _legacy_movie(value):
    return _fields(
        value,
        id=_text,
        titre=_text,
        annee=_integer,
        realisateur=_text,
        acteurs=_array(_text),
        synopsis=_text,
        support=_text,
    )


def _copy(value):
    return _fields(
        value, id=_text, movie_id=_text, support=_text, location=_text, condition=_text, _etag=_text
    )


def _profile(value):
    return _fields(
        value, id=_text, username=_text, display_name=_text, role=_text, enabled=_boolean
    )


def _entry(value):
    return _fields(
        value,
        id=_text,
        movie_id=_text,
        kind=_text,
        list_name=_text,
        supports=_array(_text),
        _etag=_text,
    )


def _loan(value):
    return _fields(
        value,
        id=_text,
        movie_id=_text,
        borrower_id=_text,
        status=_text,
        requested_at=_integer,
        approved_at=_nullable(_integer),
        due_at=_nullable(_integer),
        returned_at=_nullable(_integer),
        _etag=_text,
    )


def _reservation(value):
    return _fields(
        value,
        id=_text,
        movie_id=_text,
        user_id=_text,
        status=_text,
        created_at=_integer,
        expires_at=_integer,
        _etag=_text,
    )


def _movie_list(value):
    return (
        _page(value)
        and _fields(
            value,
            movies=_array(_movie),
            copy_summaries=_mapping(
                lambda item: _fields(item, count=_integer, supports=_array(_text))
            ),
        )
        and all(movie["id"] in value["copy_summaries"] for movie in value["movies"])
    )


def _linked_page(value, name, check, **extra):
    return (
        _page(value)
        and _fields(value, **{name: _array(check)}, movies=_mapping(_movie), **extra)
        and all(item["movie_id"] in value["movies"] for item in value[name])
    )


def _loans(value):
    return _linked_page(
        value, "loans", _loan, borrowers=_mapping(_profile), overdue_ids=_array(_text)
    ) and all(loan["borrower_id"] in value["borrowers"] for loan in value["loans"])


def _reservations(value):
    return _linked_page(
        value,
        "reservations",
        _reservation,
        users=_mapping(_profile),
        positions=_mapping(_integer),
        ready_ids=_array(_text),
        open_loan_ids=_mapping(_text),
    ) and all(item["user_id"] in value["users"] for item in value["reservations"])


def _cache(value):
    return _fields(value, status=_text, stored_at=_integer, hit=_boolean)


def _metadata(value):
    return _fields(
        value,
        id=_text,
        title=_text,
        year=_nullable(_integer),
        director=_text,
        actors=_array(_text),
        genres=_array(_text),
        description=_text,
        revision=_integer,
        warnings=_array(_text),
    )


def _statistics(value):
    counts = _mapping(_integer)
    return _fields(
        value,
        catalogue=lambda item: _fields(
            item,
            movies=_integer,
            copies=_integer,
            available=_integer,
            held_for_queue=_integer,
            damaged=_integer,
            by_support=counts,
            by_genre=counts,
        ),
        personal=lambda item: _fields(
            item,
            collection_movies=_integer,
            collection_entries=_integer,
            by_kind=counts,
            by_owned_support=counts,
            loans=counts,
            overdue=_integer,
            waiting_reservations=_integer,
            activity_last_7_days=_integer,
            activity_retained=_integer,
            recent_activity=_array(
                lambda event: _fields(event, action=_text, timestamp=_activity_timestamp)
            ),
        ),
    ) and (
        "operations" not in value
        or _fields(
            value["operations"],
            loans=counts,
            overdue=_integer,
            waiting_reservations=_integer,
            activity_last_7_days=counts,
        )
    )


def _activity_timestamp(value):
    # The dashboard date filter has no fallback for unrepresentable timestamps.
    if not _integer(value):
        return False
    try:
        datetime.fromtimestamp(value, timezone.utc)
    except (ValueError, OverflowError, OSError):
        return False
    return True


def _recommendations(value):
    return _fields(
        value,
        personalized=_boolean,
        total=_integer,
        recommendations=_array(
            lambda item: _fields(
                item,
                movie=_movie,
                available_copies=_integer,
                score=_integer,
                reasons=_array(lambda reason: _fields(reason, label=_text, points=_integer)),
            )
        ),
    )


def allows_no_content(method, path):
    """Only these native operations have a documented empty success response."""
    if (method, path) in (
        ("POST", "/api/v1/auth/logout"),
        ("PUT", "/api/v1/me/password"),
    ):
        return True
    parts = path.strip("/").split("/")
    return method == "DELETE" and (
        (len(parts) == 3 and parts[:2] == ["api", "films"] and bool(parts[2]))
        or (
            len(parts) == 4
            and parts[:2] == ["api", "v1"]
            and parts[2] in ("movies", "copies", "collections")
            and bool(parts[3])
        )
    )


def _export_text(value):
    # Every key and value in this carrier is emitted by json.dumps(ensure_ascii=False).
    if isinstance(value, str):
        return _text(value)
    if isinstance(value, dict):
        return _mapping(_export_text)(value)
    if isinstance(value, list):
        return _array(_export_text)(value)
    return True


def valid_response(method, path, value):
    """Check only fields that callers consume, before indexing or rendering them."""
    if not isinstance(value, dict):
        return False
    parts = path.strip("/").split("/")
    if parts[:2] == ["api", "films"]:
        if method == "GET" and len(parts) == 2:
            return _fields(value, films=_array(_legacy_movie))
        if method in ("GET", "POST", "PUT"):
            return _legacy_movie(value)
    if parts[:2] != ["api", "v1"]:
        return True
    resource = parts[2:]
    if not resource:
        return True
    if resource[0] == "movies" and method in ("GET", "POST", "PUT"):
        return _movie_list(value) if method == "GET" and len(resource) == 1 else _movie(value)
    if method != "GET":
        if resource == ["catalogue", "import"]:
            return _fields(
                value,
                operation_id=_text,
                created_movies=_integer,
                created_copies=_integer,
                skipped_movies=_integer,
                skipped_copies=_integer,
            )
        return True
    if resource[0] == "copies":
        return _fields(value, copies=_array(_copy)) if len(resource) == 1 else _copy(value)
    if resource == ["availability"]:
        return _fields(value, available=_integer)
    if resource == ["users"]:
        return _page(value) and _fields(value, users=_array(_profile))
    if resource == ["me"]:
        return _profile(value)
    if resource == ["catalogue", "export"]:
        return _fields(value, format=_text) and (
            (value["format"] == "csv" and _fields(value, content=_text))
            or (
                value["format"] == "json"
                and isinstance(value.get("content"), dict)
                and _export_text(value["content"])
            )
        )
    if resource[0] == "collections":
        return _linked_page(value, "entries", _entry) if len(resource) == 1 else _entry(value)
    if resource[0] == "loans":
        if len(resource) == 1:
            return _loans(value)
        return _fields(value, copies=_array(_copy)) if resource[-1] == "options" else _loan(value)
    if resource == ["reservations"]:
        return _reservations(value)
    if resource[0] == "metadata":
        if resource[-1] == "search":
            return _fields(
                value,
                items=_array(lambda item: _fields(item, id=_text, title=_text, description=_text)),
                cache=_cache,
            )
        return _fields(value, film=_metadata, cache=_cache)
    if resource == ["statistics"]:
        return _statistics(value)
    if resource == ["recommendations"]:
        return _recommendations(value)
    return True
