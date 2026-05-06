import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_via_docs(client):
    r = client.get("/docs")
    assert r.status_code == 200


def test_create_then_list(client):
    r = client.post("/api/todos", json={"title": "API経由で追加"})
    assert r.status_code == 201
    body = r.json()
    new_id = body["id"]
    assert body["title"] == "API経由で追加"
    assert body["done"] is False

    r = client.get("/api/todos", params={"filter": "open"})
    assert r.status_code == 200
    assert any(t["id"] == new_id for t in r.json())


def test_toggle_changes_done(client):
    new = client.post("/api/todos", json={"title": "切替テスト"}).json()
    assert new["done"] is False
    r = client.post(f"/api/todos/{new['id']}/toggle")
    assert r.status_code == 200
    assert r.json()["done"] is True


def test_patch_clears_due_on(client):
    new = client.post(
        "/api/todos",
        json={"title": "PATCHで期限消す", "due_on": "2026-06-15"},
    ).json()
    assert new["due_on"] == "2026-06-15"

    r = client.patch(f"/api/todos/{new['id']}", json={"due_on": None})
    assert r.status_code == 200
    assert r.json()["due_on"] is None


def test_validation_fails_on_empty_title(client):
    r = client.post("/api/todos", json={"title": ""})
    assert r.status_code == 422


def test_validation_fails_on_bad_priority(client):
    r = client.post("/api/todos", json={"title": "x", "priority": 5})
    assert r.status_code == 422


def test_404_on_unknown_id(client):
    r = client.patch("/api/todos/9999999", json={"title": "no-op"})
    assert r.status_code == 404


def test_delete_removes(client):
    new = client.post("/api/todos", json={"title": "消す"}).json()
    r = client.delete(f"/api/todos/{new['id']}")
    assert r.status_code == 204
    r2 = client.get(f"/api/todos/{new['id']}")
    assert r2.status_code == 404
