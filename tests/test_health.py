from django.test import Client


def test_health_endpoint_reports_database_and_request_id() -> None:
    response = Client().get("/health/")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"] == "ok"
    assert response.json()["request_id"]
    assert response.headers["X-Request-ID"] == response.json()["request_id"]


def test_health_endpoint_preserves_safe_external_request_id() -> None:
    response = Client().get("/health/", headers={"X-Request-ID": "test-request-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-123"


def test_health_endpoint_replaces_unsafe_request_id() -> None:
    response = Client().get("/health/", headers={"X-Request-ID": "unsafe request id"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != "unsafe request id"
