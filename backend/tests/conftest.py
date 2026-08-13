"""Shared fixtures.

Every test gets a brand-new in-memory database. Nothing here ever touches
trello.db, and no test can see data another test created.
"""

import os

# These two must be set before anything imports app.config, which reads them at
# import time. load_dotenv() does NOT overwrite variables that already exist in
# the environment, so setting them here beats whatever is in backend/.env.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-not-the-production-one")

from dataclasses import dataclass  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlmodel import SQLModel, create_engine  # noqa: E402

from app import auth as auth_module  # noqa: E402
from app import database, ws  # noqa: E402
from app.main import app  # noqa: E402

# bcrypt is deliberately slow — roughly 250ms per hash. That is exactly what you
# want in production and pure waste in tests, where hashing would otherwise be
# the single slowest thing in the suite. 4 rounds is insecure and instant.
auth_module.pwd_context.update(bcrypt__rounds=4)


@dataclass
class Actor:
    """A signed-up, logged-in user plus the two shapes its credentials take."""

    id: int
    email: str
    token: str

    @property
    def headers(self) -> dict:
        """For REST calls — a normal Authorization header."""
        return {"Authorization": f"Bearer {self.token}"}


@pytest.fixture
def client(monkeypatch):
    # "sqlite://" with no path is an in-memory database. StaticPool forces every
    # connection to reuse the SAME one; without it each connection would open a
    # separate empty database and nothing would survive between requests.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    # get_session() looks up database.engine when it runs, so patching the module
    # attribute redirects every HTTP request. ws.py did `from .database import
    # engine`, which copied the reference at import time — that copy needs its
    # own patch or the WebSocket handler would still write to the real file.
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(ws, "engine", engine)

    # the room registry is a module-level singleton and would otherwise carry
    # sockets from one test into the next
    ws.manager.rooms.clear()

    # `with` runs the lifespan, which is what creates the tables
    with TestClient(app) as test_client:
        yield test_client

    engine.dispose()


@pytest.fixture
def make_user(client):
    """Sign up and log in a user, returning an Actor."""

    def _make_user(email: str, password: str = "correct-horse-battery") -> Actor:
        signup = client.post("/auth/signup", json={"email": email, "password": password})
        assert signup.status_code == 201, signup.text
        login = client.post("/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200, login.text
        return Actor(id=signup.json()["id"], email=email, token=login.json()["access_token"])

    return _make_user


@dataclass
class Workspace:
    """The whole object chain most tests need: org -> board -> section -> issue."""

    owner: Actor
    org_id: int
    board_id: int
    section_id: int
    issue_id: int


@pytest.fixture
def workspace(client, make_user) -> Workspace:
    owner = make_user("owner@example.com")
    h = owner.headers

    org = client.post("/orgs", json={"name": "Acme"}, headers=h)
    assert org.status_code == 201, org.text
    org_id = org.json()["id"]

    board = client.post(f"/orgs/{org_id}/boards", json={"title": "Roadmap"}, headers=h)
    assert board.status_code == 201, board.text
    board_id = board.json()["id"]

    section = client.post(f"/boards/{board_id}/sections", json={"title": "To do"}, headers=h)
    assert section.status_code == 201, section.text
    section_id = section.json()["id"]

    issue = client.post(f"/sections/{section_id}/issues", json={"title": "Ship it"}, headers=h)
    assert issue.status_code == 201, issue.text

    return Workspace(
        owner=owner,
        org_id=org_id,
        board_id=board_id,
        section_id=section_id,
        issue_id=issue.json()["id"],
    )
