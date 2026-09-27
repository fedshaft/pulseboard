import os

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://pulseboard:pulseboard@localhost:5433/pulseboard_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["COOKIE_SECURE"] = "false"  

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal
from app.main import app
from app.models.sessions import UserSession  
from app.models.source import Source 
from app.models.user import User

PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="session", autouse=True)
def test_database():
    url = make_url(TEST_DATABASE_URL)
    admin_dsn = url.set(drivername="postgresql", database="postgres").render_as_string(hide_password=False)
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{url.database}"')

    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture(autouse=True)
def clean_tables():
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with SessionLocal() as db:
        db.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        db.commit()


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def make_user(db):
    def _make_user(email: str, role: str = "viewer") -> User:
        user = User(email=email, password_hash=hash_password(PASSWORD), role=role)
        db.add(user)
        db.commit()
        return user
    return _make_user

def login(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return c

@pytest.fixture
def client() -> TestClient:
    return TestClient(app)

@pytest.fixture
def admin_client(make_user) -> TestClient:
    make_user("admin@example.com", role="admin")
    return login("admin@example.com")

@pytest.fixture
def viewer_client(make_user) -> TestClient:
    make_user("viewer@example.com", role="viewer")
    return login("viewer@example.com")

@pytest.fixture
def cookie_name() -> str:
    return settings.session_cookie_name
