from __future__ import annotations

import re
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


class RequestContextMiddleware:
    """Attach a safe request identifier without logging request bodies or PII."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        supplied_request_id = request.headers.get("X-Request-ID", "")
        if _REQUEST_ID_PATTERN.fullmatch(supplied_request_id):
            request_id = supplied_request_id
        else:
            request_id = uuid.uuid4().hex

        request.request_id = request_id
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response
