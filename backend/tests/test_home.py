"""Tests for health and assignment endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_root(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "lmh-rag-backend"
    assert payload["endpoints"]["chats"] == "/api/v1/chats"
    assert payload["endpoints"]["documents"] == "/api/v1/documents"
    assert payload["endpoints"]["usage"] == "/api/v1/usage"


def test_health_v1(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_assignment_html(client: TestClient) -> None:
    response = client.get("/api/v1/assignment")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Last Mile Health" in response.text
    assert "Retrieval-Augmented Generation" in response.text


def test_legacy_assignment_path_is_gone(client: TestClient) -> None:
    assert client.get("/assignment").status_code == 404


def test_openapi_docs_available(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    paths = openapi.json()["paths"]
    assert "/api/v1/chats" in paths
    assert "/api/v1/documents" in paths
    assert "/api/v1/usage" in paths
