"""Bounded HTTP access events for the web service."""

import json
import logging
import re
from time import perf_counter_ns
from uuid import uuid4

from flask import g, has_request_context, request
from flask.logging import wsgi_errors_stream

_HTTP_METHODS = frozenset(
    {"CONNECT", "DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"}
)
_REQUEST_ID = "X-Request-ID"
_UUID4_HEX = re.compile(r"[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}")
_MAX_API_REQUEST_IDS = 8
_ACCESS_LOG = logging.Logger("cinevault.web.access", logging.INFO)
_ACCESS_LOG.addHandler(logging.StreamHandler(wsgi_errors_stream))


def record_api_request_id(value):
    if not has_request_context() or not isinstance(value, str):
        return
    ids = g.get("cinevault_api_request_ids")
    if ids is None or len(ids) >= _MAX_API_REQUEST_IDS:
        return
    if _UUID4_HEX.fullmatch(value) and value not in ids:
        ids.append(value)


def install_request_telemetry(app):
    @app.before_request
    def start_access_event():
        g.cinevault_access_start = perf_counter_ns()
        g.cinevault_request_id = uuid4().hex
        g.cinevault_api_request_ids = []

    @app.after_request
    def finish_access_event(response):
        request_id = g.cinevault_request_id
        response.headers[_REQUEST_ID] = request_id
        event = {
            "service": "web",
            "request_id": request_id,
            "method": request.method if request.method in _HTTP_METHODS else "OTHER",
            "route": request.url_rule.rule if request.url_rule is not None else "unmatched",
            "status": response.status_code,
            "duration_ms": round((perf_counter_ns() - g.cinevault_access_start) / 1_000_000, 3),
        }
        if g.cinevault_api_request_ids:
            event["api_request_ids"] = g.cinevault_api_request_ids
        _ACCESS_LOG.info(json.dumps(event, separators=(",", ":")))
        return response
