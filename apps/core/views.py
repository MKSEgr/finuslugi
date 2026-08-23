from __future__ import annotations

from django.db import connection
from django.http import HttpRequest, JsonResponse


def health_check(request: HttpRequest) -> JsonResponse:
    """Return a shallow application and database health signal."""

    database_status = "ok"
    http_status = 200
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # noqa: BLE001 - health endpoint must convert infrastructure errors
        database_status = "unavailable"
        http_status = 503

    return JsonResponse(
        {
            "status": "ok" if http_status == 200 else "degraded",
            "database": database_status,
            "request_id": getattr(request, "request_id", ""),
        },
        status=http_status,
    )
