import os

# Point the app at an in-memory database BEFORE importing anything that reads
# settings, otherwise importing main would create a stray careeros.db file.
os.environ["DATABASE_URL"] = "sqlite://"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from ai.client import FakeAIClient, get_ai_client  # noqa: E402
from db.base import Base  # noqa: E402
from db.session import get_db  # noqa: E402
from main import app  # noqa: E402
from models import assessment as _assessment_models  # noqa: E402,F401
from models import roadmap as _roadmap_models  # noqa: E402,F401
from models import user as _user_models  # noqa: E402,F401


@pytest.fixture()
def db_session():
    """A fresh in-memory database per test.

    StaticPool keeps every connection pointed at the same :memory: database —
    without it each new connection would get its own empty one.
    """
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        test_engine.dispose()


@pytest.fixture()
def fake_ai():
    return FakeAIClient()


@pytest.fixture()
def client(db_session, fake_ai):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_ai_client] = lambda: fake_ai
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
