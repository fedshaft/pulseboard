import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.api.deps import get_current_source
from app.core.security import hash_api_key
from app.models.source import Source

probe_app = FastAPI()

@probe_app.get("/whoami")
def whoami(source: Source = Depends(get_current_source)) -> dict:
    return {"id": source.id, "name": source.name}

probe = TestClient(probe_app)


@pytest.fixture
def created(admin_client) -> dict:
    r = admin_client.post("/sources", json={"name": "web-01"})
    assert r.status_code == 201, r.text
    return r.json()


def test_admin_creates_source_and_gets_key_once(admin_client, created):
    assert created["name"] == "web-01"
    assert created["api_key"].startswith("pb_live_")
    assert created["key_prefix"] == created["api_key"][:12]
    assert created["revoked_at"] is None

    listed = admin_client.get(f"/sources/{created['id']}").json()
    assert "api_key" not in listed


def test_key_is_stored_hashed_not_raw(created, db):
    stored = db.execute(select(Source.api_key_hash)).scalar_one()
    assert stored == hash_api_key(created["api_key"])
    assert stored != created["api_key"]


def test_viewer_cannot_create_source(viewer_client):
    assert viewer_client.post("/sources", json={"name": "web-01"}).status_code == 403


def test_create_source_without_login_is_401(client):
    assert client.post("/sources", json={"name": "web-01"}).status_code == 401


def test_duplicate_source_name_is_409(admin_client, created):
    assert admin_client.post("/sources", json={"name": "web-01"}).status_code == 409


def test_empty_source_name_is_422(admin_client):
    assert admin_client.post("/sources", json={"name": ""}).status_code == 422


def test_viewer_can_list_sources_without_secrets(created, viewer_client):
    r = viewer_client.get("/sources")
    assert r.status_code == 200
    [source] = r.json()
    assert source["name"] == "web-01"
    assert "api_key" not in source
    assert "api_key_hash" not in source


def test_list_sources_without_login_is_401(client):
    assert client.get("/sources").status_code == 401


def test_get_missing_source_is_404(viewer_client):
    assert viewer_client.get("/sources/999").status_code == 404



def test_admin_revokes_source(admin_client, created):
    r = admin_client.post(f"/sources/{created['id']}/revoke")
    assert r.status_code == 200
    assert r.json()["revoked_at"] is not None


def test_revoking_twice_keeps_original_timestamp(admin_client, created):
    first = admin_client.post(f"/sources/{created['id']}/revoke").json()["revoked_at"]
    second = admin_client.post(f"/sources/{created['id']}/revoke").json()["revoked_at"]
    assert first == second


def test_viewer_cannot_revoke_source(created, viewer_client):
    assert viewer_client.post(f"/sources/{created['id']}/revoke").status_code == 403


def test_revoke_missing_source_is_404(admin_client):
    assert admin_client.post("/sources/999/revoke").status_code == 404


def test_valid_key_identifies_its_source(created):
    r = probe.get("/whoami", headers={"X-API-Key": created["api_key"]})
    assert r.status_code == 200
    assert r.json() == {"id": created["id"], "name": "web-01"}


def test_missing_key_is_401():
    assert probe.get("/whoami").status_code == 401


def test_wrong_key_is_401(created):
    assert probe.get("/whoami", headers={"X-API-Key": "pb_live_not-a-real-key"}).status_code == 401


def test_revoked_key_stops_working(admin_client, created):
    headers = {"X-API-Key": created["api_key"]}
    assert probe.get("/whoami", headers=headers).status_code == 200

    admin_client.post(f"/sources/{created['id']}/revoke")

    assert probe.get("/whoami", headers=headers).status_code == 401
