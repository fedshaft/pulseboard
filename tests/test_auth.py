from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update

from app.core.bootstrap import ensure_bootstrap_admin
from app.core.config import settings
from app.core.security import hash_session_token
from app.models.sessions import UserSession
from app.models.user import User
from tests.conftest import PASSWORD, login

NEW_USER = {"email": "new@example.com", "password": PASSWORD}
def test_register_without_login_is_401(client):
    assert client.post("/auth/register", json=NEW_USER).status_code == 401

def test_viewer_cannot_register_users(viewer_client):
    assert viewer_client.post("/auth/register", json=NEW_USER).status_code == 403

def test_admin_registers_a_viewer(admin_client):
    r = admin_client.post("/auth/register", json=NEW_USER)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "new@example.com"
    assert body["role"] == "viewer"
    assert "password_hash" not in body

def test_register_duplicate_email_is_409(admin_client):
    admin_client.post("/auth/register", json=NEW_USER)
    assert admin_client.post("/auth/register", json=NEW_USER).status_code == 409

def test_register_short_password_is_422(admin_client):
    r = admin_client.post("/auth/register", json={"email": "new@example.com", "password": "short"})
    assert r.status_code == 422

def test_login_sets_httponly_session_cookie(client, make_user, cookie_name):
    make_user("viewer@example.com")
    r = client.post("/auth/login", json={"email": "viewer@example.com", "password": PASSWORD})
    assert r.status_code == 200
    set_cookie = r.headers["set-cookie"]
    assert set_cookie.startswith(f"{cookie_name}=")
    assert "HttpOnly" in set_cookie

def test_wrong_password_and_unknown_email_look_identical(client, make_user):
    make_user("viewer@example.com")
    wrong_pw = client.post("/auth/login", json={"email": "viewer@example.com", "password": "wrong-password"})
    unknown = client.post("/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()

def test_me_returns_the_logged_in_user(viewer_client):
    r = viewer_client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "viewer@example.com"

def test_me_without_cookie_is_401(client):
    assert client.get("/auth/me").status_code == 401

def test_forged_token_is_401(client, cookie_name):
    client.cookies.set(cookie_name, "not-a-real-token")
    assert client.get("/auth/me").status_code == 401

def test_session_is_stored_hashed_not_raw(viewer_client, db, cookie_name):
    token = viewer_client.cookies[cookie_name]
    stored = db.execute(select(UserSession.session_id)).scalar_one()
    assert stored == hash_session_token(token)
    assert stored != token

def test_expired_session_is_401(viewer_client, db):
    db.execute(update(UserSession).values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
    db.commit()
    assert viewer_client.get("/auth/me").status_code == 401

def test_logout_revokes_the_session_server_side(viewer_client, cookie_name):
    token = viewer_client.cookies[cookie_name]
    assert viewer_client.post("/auth/logout").status_code == 204
    viewer_client.cookies.set(cookie_name, token)
    assert viewer_client.get("/auth/me").status_code == 401


def test_bootstrap_creates_one_admin_even_when_run_twice(db, monkeypatch):
    monkeypatch.setattr(settings, "bootstrap_admin_email", "boot@example.com")
    monkeypatch.setattr(settings, "bootstrap_admin_password", PASSWORD)

    ensure_bootstrap_admin()
    ensure_bootstrap_admin()

    admins = db.execute(select(func.count()).select_from(User).where(User.role == "admin")).scalar_one()
    assert admins == 1
    login("boot@example.com")


def test_bootstrap_does_nothing_when_unset(db, monkeypatch):
    monkeypatch.setattr(settings, "bootstrap_admin_email", None)
    monkeypatch.setattr(settings, "bootstrap_admin_password", None)
    ensure_bootstrap_admin()
    assert db.execute(select(func.count()).select_from(User)).scalar_one() == 0