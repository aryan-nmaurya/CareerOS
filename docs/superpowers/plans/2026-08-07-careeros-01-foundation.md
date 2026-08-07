# CareerOS Plan 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up both halves of CareerOS — a FastAPI + SQLite backend with profile and learning-track management, and a themed React shell with a working onboarding wizard — so that a new user can enter their name, pick a topic, choose an experience level, and land on a dashboard.

**Architecture:** Backend is layered: routers validate and delegate, services own all logic and are the only thing that touches the ORM, models define SQLAlchemy 2.0 tables. Frontend is a Vite SPA with CSS-variable theme tokens swapped by a `dark` class on `<html>`, TanStack Query for all server state, and a typed `api()` fetch wrapper that normalizes the backend's `{detail: {code, message}}` error shape.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2, pytest, React 19, TypeScript, Vite, Tailwind CSS v4, TanStack Query, React Router 7, Framer Motion, Vitest.

**Spec:** `docs/superpowers/specs/2026-08-07-careeros-design.md` (sections 4, 5, 7 profile/tracks, 11)

**Series context:** This is plan 1 of 5.
1. **Foundation** ← you are here
2. AI client + assessment
3. Roadmap SSE generation + viewer + progress + dashboard data
4. Interview core + speech
5. Proctoring + evaluation + reports + polish

No AI calls appear in this plan. `google-genai` is installed but unused until Plan 2.

---

## File Structure

**Backend** (`backend/`)

| File | Responsibility |
|---|---|
| `requirements.txt` | Dependency list |
| `.env.example` | Documented env template (real `.env` is gitignored) |
| `pytest.ini` | Test discovery + `pythonpath` so `from main import app` resolves |
| `config.py` | `Settings` via pydantic-settings; single `settings` instance |
| `main.py` | `create_app()` factory: CORS, `create_all`, router mounting, exception handlers |
| `db/base.py` | `DeclarativeBase` subclass — the metadata registry |
| `db/session.py` | Engine, `SessionLocal`, `get_db` dependency, SQLite PRAGMAs |
| `models/user.py` | `User`, `LearningTrack` |
| `schemas/profile.py` | Pydantic request/response models + shared `Literal` types |
| `services/profile_service.py` | Profile CRUD + track lifecycle incl. single-active invariant |
| `routers/health.py` | Liveness probe |
| `routers/profile.py` | `/api/profile` |
| `routers/tracks.py` | `/api/tracks` |
| `tests/conftest.py` | In-memory DB fixture + `TestClient` with `get_db` overridden |
| `tests/test_profile_service.py` | Service-level logic tests |
| `tests/test_api_smoke.py` | Router-level happy path + error mapping |

**Frontend** (`frontend/`)

| File | Responsibility |
|---|---|
| `package.json`, `vite.config.ts`, `tsconfig*.json` | Build config, `@/*` alias, Vitest setup |
| `src/index.css` | Tailwind v4 `@theme` tokens + light/dark palettes |
| `src/main.tsx` | Root render, QueryClientProvider, BrowserRouter |
| `src/App.tsx` | Route table |
| `src/lib/cn.ts` | `clsx` + `tailwind-merge` helper |
| `src/lib/constants.ts` | The 20 preset topics, experience-level metadata |
| `src/hooks/useTheme.ts` | Theme state + `resolveTheme` pure function |
| `src/hooks/useProfile.ts` | Query/mutation hooks for profile and tracks |
| `src/services/api/client.ts` | `api()` fetch wrapper + `ApiError` |
| `src/services/api/profile.ts` | Typed profile/track calls |
| `src/types/index.ts` | Shared TS types mirroring backend schemas |
| `src/components/ui/{button,card,input}.tsx` | shadcn-pattern primitives |
| `src/components/layout/{AppShell,Sidebar,TopBar,ThemeToggle}.tsx` | Chrome |
| `src/components/onboarding/{NameStep,TopicStep,LevelStep}.tsx` | Wizard steps |
| `src/pages/{OnboardingPage,DashboardPage,SettingsPage}.tsx` | Routed screens |
| `src/test/setup.ts` | jest-dom matchers for Vitest |
| `src/hooks/__tests__/useTheme.test.ts` | `resolveTheme` tests |

---

## Task 1: Backend scaffold and health endpoint

**Files:**
- Create: `backend/requirements.txt`, `backend/.env.example`, `backend/pytest.ini`, `backend/config.py`, `backend/main.py`, `backend/routers/__init__.py`, `backend/routers/health.py`, `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_api_smoke.py`

- [ ] **Step 1: Create the virtualenv and dependency list**

```bash
mkdir -p backend/routers backend/tests
cd backend && python3 -m venv .venv && source .venv/bin/activate
```

Create `backend/requirements.txt`:

```
fastapi>=0.115
uvicorn[standard]>=0.32
pydantic>=2.10
pydantic-settings>=2.7
SQLAlchemy>=2.0.36
python-dotenv>=1.0
google-genai>=1.0
httpx>=0.28
pytest>=8.3
```

Versions are floors, not pins — this is a local-only project and floating to current
patch releases is fine. `google-genai` is installed now but not imported until Plan 2.

- [ ] **Step 2: Install and verify**

Run: `pip install -r requirements.txt`
Expected: `Successfully installed ...` with no build errors.

If SQLAlchemy fails to compile its C extensions on Python 3.14, rerun with
`pip install --no-binary sqlalchemy SQLAlchemy` or create the venv from a
Python 3.12 interpreter (`python3.12 -m venv .venv`). Either is acceptable;
nothing in this project depends on 3.13+ syntax.

- [ ] **Step 3: Write `backend/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment configuration. Values come from backend/.env or the shell."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash"
    DATABASE_URL: str = "sqlite:///./careeros.db"
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
```

- [ ] **Step 4: Write `backend/.env.example`**

```
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash
DATABASE_URL=sqlite:///./careeros.db
CORS_ORIGINS=http://localhost:5173
```

- [ ] **Step 5: Write `backend/pytest.ini`**

```ini
[pytest]
testpaths = tests
pythonpath = .
addopts = -q
```

`pythonpath = .` lets tests do `from main import app` without packaging the backend.

- [ ] **Step 6: Write the failing test**

Create `backend/tests/__init__.py` (empty) and `backend/tests/conftest.py`:

```python
import os

# Point the app at an in-memory database BEFORE importing anything that reads
# settings, otherwise importing main would create a stray careeros.db file.
os.environ["DATABASE_URL"] = "sqlite://"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client
```

Create `backend/tests/test_api_smoke.py`:

```python
def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 7: Run test to verify it fails**

Run: `cd backend && pytest tests/test_api_smoke.py -v`
Expected: FAIL — collection error, `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 8: Write the minimal implementation**

Create `backend/routers/__init__.py` (empty) and `backend/routers/health.py`:

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

Create `backend/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import health


def create_app() -> FastAPI:
    app = FastAPI(title="CareerOS API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    return app


app = create_app()
```

- [ ] **Step 9: Run test to verify it passes**

Run: `cd backend && pytest tests/test_api_smoke.py -v`
Expected: PASS — `1 passed`

- [ ] **Step 10: Commit**

```bash
git add backend/
git commit -m "feat(backend): scaffold FastAPI app with health endpoint"
```

---

## Task 2: Database layer and models

**Files:**
- Create: `backend/db/__init__.py`, `backend/db/base.py`, `backend/db/session.py`, `backend/models/__init__.py`, `backend/models/user.py`
- Modify: `backend/main.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_profile_service.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_profile_service.py`:

```python
from models.user import LearningTrack, User


def test_foreign_keys_are_enforced(db_session):
    """SQLite silently ignores FK constraints unless PRAGMA foreign_keys=ON is set."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    orphan = LearningTrack(user_id=999, topic="Python", experience_level="beginner")
    db_session.add(orphan)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_user_and_track_round_trip(db_session):
    user = User(name="Aryan")
    db_session.add(user)
    db_session.commit()

    track = LearningTrack(user_id=user.id, topic="Python", experience_level="beginner")
    db_session.add(track)
    db_session.commit()

    assert track.id is not None
    assert track.is_active is True
    assert user.tracks == [track]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_profile_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'models'`, and `db_session` fixture undefined.

- [ ] **Step 3: Write `backend/db/base.py`**

Create `backend/db/__init__.py` (empty), then `backend/db/base.py`:

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base. Every model imports from here so that a single
    metadata registry knows about all tables when create_all runs."""
```

- [ ] **Step 4: Write `backend/db/session.py`**

```python
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record) -> None:
    """SQLite ignores foreign key constraints unless explicitly told not to,
    and WAL gives us non-blocking reads while a write is in flight.

    Registered against Engine (not our engine) so test engines get it too.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 5: Write `backend/models/user.py`**

Create `backend/models/__init__.py` (empty), then `backend/models/user.py`:

```python
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class User(Base):
    """The single local user. Kept as a table rather than a config value so that
    tracks, assessments, and interviews all hang off a real foreign key."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    theme: Mapped[str] = mapped_column(String(16), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    tracks: Mapped[list["LearningTrack"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="LearningTrack.created_at.desc()",
    )


class LearningTrack(Base):
    """One topic the user is learning. Exactly one track is active at a time;
    the invariant is enforced in profile_service, not by the schema."""

    __tablename__ = "learning_tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    topic: Mapped[str] = mapped_column(String(120), nullable=False)
    experience_level: Mapped[str] = mapped_column(String(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="tracks")
```

- [ ] **Step 6: Wire `create_all` into `main.py`**

Replace the whole of `backend/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db.base import Base
from db.session import engine
from models import user as _user_models  # noqa: F401  registers tables on Base
from routers import health


def create_app() -> FastAPI:
    app = FastAPI(title="CareerOS API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    Base.metadata.create_all(bind=engine)

    app.include_router(health.router)
    return app


app = create_app()
```

- [ ] **Step 7: Add the `db_session` fixture**

Replace the whole of `backend/tests/conftest.py`:

```python
import os

# Point the app at an in-memory database BEFORE importing anything that reads
# settings, otherwise importing main would create a stray careeros.db file.
os.environ["DATABASE_URL"] = "sqlite://"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from db.base import Base  # noqa: E402
from db.session import get_db  # noqa: E402
from main import app  # noqa: E402
from models import user as _user_models  # noqa: E402,F401  registers tables


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
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd backend && pytest -v`
Expected: PASS — `3 passed` (health + the two model tests)

- [ ] **Step 9: Commit**

```bash
git add backend/
git commit -m "feat(backend): add SQLAlchemy base, session with SQLite pragmas, user and track models"
```

---

## Task 3: Profile service

**Files:**
- Create: `backend/schemas/__init__.py`, `backend/schemas/profile.py`, `backend/services/__init__.py`, `backend/services/profile_service.py`
- Modify: `backend/tests/test_profile_service.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_profile_service.py`:

```python
import pytest

from schemas.profile import ProfileCreate, ProfileUpdate
from services import profile_service
from services.profile_service import ProfileExistsError, ProfileNotFoundError


def test_get_profile_returns_none_when_not_onboarded(db_session):
    assert profile_service.get_profile(db_session) is None


def test_create_profile_trims_whitespace(db_session):
    user = profile_service.create_profile(db_session, ProfileCreate(name="  Aryan  "))

    assert user.name == "Aryan"
    assert user.theme == "system"


def test_create_profile_twice_raises(db_session):
    profile_service.create_profile(db_session, ProfileCreate(name="Aryan"))

    with pytest.raises(ProfileExistsError):
        profile_service.create_profile(db_session, ProfileCreate(name="Someone Else"))


def test_update_profile_changes_name_and_theme(db_session):
    profile_service.create_profile(db_session, ProfileCreate(name="Aryan"))

    updated = profile_service.update_profile(
        db_session, ProfileUpdate(name="Aryan M", theme="dark")
    )

    assert updated.name == "Aryan M"
    assert updated.theme == "dark"


def test_update_profile_leaves_omitted_fields_untouched(db_session):
    profile_service.create_profile(db_session, ProfileCreate(name="Aryan"))

    updated = profile_service.update_profile(db_session, ProfileUpdate(theme="light"))

    assert updated.name == "Aryan"
    assert updated.theme == "light"


def test_update_profile_without_onboarding_raises(db_session):
    with pytest.raises(ProfileNotFoundError):
        profile_service.update_profile(db_session, ProfileUpdate(name="Ghost"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_profile_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'schemas'`

- [ ] **Step 3: Write `backend/schemas/profile.py`**

Create `backend/schemas/__init__.py` (empty), then `backend/schemas/profile.py`:

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ExperienceLevel = Literal["beginner", "intermediate", "advanced"]
Theme = Literal["light", "dark", "system"]


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    theme: Theme | None = None


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    theme: Theme
    created_at: datetime


class TrackCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=120)
    experience_level: ExperienceLevel


class TrackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    topic: str
    experience_level: ExperienceLevel
    is_active: bool
    created_at: datetime
```

- [ ] **Step 4: Write `backend/services/profile_service.py`**

Create `backend/services/__init__.py` (empty), then `backend/services/profile_service.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.user import LearningTrack, User
from schemas.profile import ProfileCreate, ProfileUpdate, TrackCreate


class ProfileExistsError(Exception):
    """A profile already exists; CareerOS is single-user."""


class ProfileNotFoundError(Exception):
    """An operation needed a profile but onboarding has not happened yet."""


class TrackNotFoundError(Exception):
    """The requested learning track does not exist."""


def get_profile(db: Session) -> User | None:
    return db.scalars(select(User).order_by(User.id)).first()


def create_profile(db: Session, payload: ProfileCreate) -> User:
    if get_profile(db) is not None:
        raise ProfileExistsError

    user = User(name=payload.name.strip())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_profile(db: Session, payload: ProfileUpdate) -> User:
    user = get_profile(db)
    if user is None:
        raise ProfileNotFoundError

    if payload.name is not None:
        user.name = payload.name.strip()
    if payload.theme is not None:
        user.theme = payload.theme

    db.commit()
    db.refresh(user)
    return user
```

Track functions land in Task 4 — leave the `TrackCreate` and `LearningTrack`
imports in place; they are used there.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_profile_service.py -v`
Expected: PASS — `8 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/
git commit -m "feat(backend): add profile schemas and service"
```

---

## Task 4: Track lifecycle with the single-active invariant

**Files:**
- Modify: `backend/services/profile_service.py`, `backend/tests/test_profile_service.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_profile_service.py`:

```python
from schemas.profile import TrackCreate
from services.profile_service import TrackNotFoundError


def _onboard(db_session):
    return profile_service.create_profile(db_session, ProfileCreate(name="Aryan"))


def test_create_track_is_active_by_default(db_session):
    _onboard(db_session)

    track = profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level="beginner")
    )

    assert track.is_active is True
    assert profile_service.get_active_track(db_session).id == track.id


def test_creating_a_second_track_deactivates_the_first(db_session):
    _onboard(db_session)
    first = profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level="beginner")
    )

    second = profile_service.create_track(
        db_session, TrackCreate(topic="React", experience_level="intermediate")
    )

    db_session.refresh(first)
    assert first.is_active is False
    assert second.is_active is True
    active = [t for t in profile_service.list_tracks(db_session) if t.is_active]
    assert len(active) == 1


def test_activate_track_switches_the_active_one(db_session):
    _onboard(db_session)
    first = profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level="beginner")
    )
    profile_service.create_track(
        db_session, TrackCreate(topic="React", experience_level="intermediate")
    )

    reactivated = profile_service.activate_track(db_session, first.id)

    assert reactivated.is_active is True
    active = [t for t in profile_service.list_tracks(db_session) if t.is_active]
    assert len(active) == 1
    assert active[0].id == first.id


def test_activate_unknown_track_raises(db_session):
    _onboard(db_session)

    with pytest.raises(TrackNotFoundError):
        profile_service.activate_track(db_session, 4242)


def test_create_track_without_profile_raises(db_session):
    with pytest.raises(ProfileNotFoundError):
        profile_service.create_track(
            db_session, TrackCreate(topic="Python", experience_level="beginner")
        )


def test_get_active_track_returns_none_when_no_tracks(db_session):
    _onboard(db_session)

    assert profile_service.get_active_track(db_session) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_profile_service.py -v`
Expected: FAIL — `AttributeError: module 'services.profile_service' has no attribute 'create_track'`

- [ ] **Step 3: Append the track functions to `backend/services/profile_service.py`**

```python
def list_tracks(db: Session) -> list[LearningTrack]:
    # id as a tiebreak: SQLite's func.now() has second-level resolution, so
    # two tracks created within the same second would otherwise tie and
    # sort unpredictably.
    return list(
        db.scalars(
            select(LearningTrack).order_by(
                LearningTrack.created_at.desc(), LearningTrack.id.desc()
            )
        )
    )


def get_active_track(db: Session) -> LearningTrack | None:
    return db.scalars(
        select(LearningTrack).where(LearningTrack.is_active.is_(True))
    ).first()


def create_track(db: Session, payload: TrackCreate) -> LearningTrack:
    """Creating a track makes it the active one. Exactly one track is active at
    any time — the dashboard and roadmap always render that track."""
    user = get_profile(db)
    if user is None:
        raise ProfileNotFoundError

    for existing in list_tracks(db):
        existing.is_active = False

    track = LearningTrack(
        user_id=user.id,
        topic=payload.topic.strip(),
        experience_level=payload.experience_level,
        is_active=True,
    )
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


def activate_track(db: Session, track_id: int) -> LearningTrack:
    target = db.get(LearningTrack, track_id)
    if target is None:
        raise TrackNotFoundError

    for existing in list_tracks(db):
        existing.is_active = existing.id == track_id

    db.commit()
    db.refresh(target)
    return target
```

A `get_track` lookup is not needed yet — nothing in this plan's API surface
resolves a single track by id (the spec's Plan 1 endpoints only list, create,
and activate). Plan 2 introduces it, driven by its own failing test, when
`POST /api/tracks/{id}/assessment` needs to resolve the track first.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_profile_service.py -v`
Expected: PASS — `14 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/
git commit -m "feat(backend): add learning track lifecycle with single-active invariant"
```

---

## Task 5: Profile and track routers

**Files:**
- Create: `backend/routers/profile.py`, `backend/routers/tracks.py`
- Modify: `backend/main.py`, `backend/tests/test_api_smoke.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_api_smoke.py`:

```python
def test_profile_returns_204_before_onboarding(client):
    response = client.get("/api/profile")

    assert response.status_code == 204


def test_onboarding_happy_path(client):
    created = client.post("/api/profile", json={"name": "Aryan"})
    assert created.status_code == 201
    assert created.json()["name"] == "Aryan"
    assert created.json()["theme"] == "system"

    fetched = client.get("/api/profile")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Aryan"

    track = client.post(
        "/api/tracks", json={"topic": "Python", "experience_level": "beginner"}
    )
    assert track.status_code == 201
    assert track.json()["is_active"] is True

    listed = client.get("/api/tracks")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_creating_a_second_profile_is_rejected(client):
    client.post("/api/profile", json={"name": "Aryan"})

    duplicate = client.post("/api/profile", json={"name": "Someone Else"})

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "profile_exists"


def test_track_before_onboarding_is_rejected(client):
    response = client.post(
        "/api/tracks", json={"topic": "Python", "experience_level": "beginner"}
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "profile_not_found"


def test_activating_unknown_track_returns_404(client):
    client.post("/api/profile", json={"name": "Aryan"})

    response = client.post("/api/tracks/999/activate")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "track_not_found"


def test_invalid_experience_level_is_rejected(client):
    client.post("/api/profile", json={"name": "Aryan"})

    response = client.post(
        "/api/tracks", json={"topic": "Python", "experience_level": "expert"}
    )

    assert response.status_code == 422


def test_patch_profile_updates_theme(client):
    client.post("/api/profile", json={"name": "Aryan"})

    response = client.patch("/api/profile", json={"theme": "dark"})

    assert response.status_code == 200
    assert response.json()["theme"] == "dark"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_api_smoke.py -v`
Expected: FAIL — `assert 404 == 204`, routes do not exist yet.

- [ ] **Step 3: Write `backend/routers/profile.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from db.session import get_db
from schemas.profile import ProfileCreate, ProfileOut, ProfileUpdate
from services import profile_service
from services.profile_service import ProfileExistsError, ProfileNotFoundError

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileOut, responses={204: {"description": "Not onboarded"}})
def read_profile(db: Session = Depends(get_db)):
    user = profile_service.get_profile(db)
    if user is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return user


@router.post("", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
def create_profile(payload: ProfileCreate, db: Session = Depends(get_db)):
    try:
        return profile_service.create_profile(db, payload)
    except ProfileExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "profile_exists", "message": "A profile already exists."},
        )


@router.patch("", response_model=ProfileOut)
def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db)):
    try:
        return profile_service.update_profile(db, payload)
    except ProfileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "profile_not_found", "message": "No profile yet."},
        )
```

- [ ] **Step 4: Write `backend/routers/tracks.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db.session import get_db
from schemas.profile import TrackCreate, TrackOut
from services import profile_service
from services.profile_service import ProfileNotFoundError, TrackNotFoundError

router = APIRouter(prefix="/api/tracks", tags=["tracks"])

_PROFILE_MISSING = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "profile_not_found", "message": "No profile yet."},
)
_TRACK_MISSING = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "track_not_found", "message": "That learning track does not exist."},
)


@router.get("", response_model=list[TrackOut])
def list_tracks(db: Session = Depends(get_db)):
    return profile_service.list_tracks(db)


@router.post("", response_model=TrackOut, status_code=status.HTTP_201_CREATED)
def create_track(payload: TrackCreate, db: Session = Depends(get_db)):
    try:
        return profile_service.create_track(db, payload)
    except ProfileNotFoundError:
        raise _PROFILE_MISSING


@router.post("/{track_id}/activate", response_model=TrackOut)
def activate_track(track_id: int, db: Session = Depends(get_db)):
    try:
        return profile_service.activate_track(db, track_id)
    except TrackNotFoundError:
        raise _TRACK_MISSING
```

- [ ] **Step 5: Mount the routers in `backend/main.py`**

Change the import line and the mounting block:

```python
from routers import health, profile, tracks
```

```python
    app.include_router(health.router)
    app.include_router(profile.router)
    app.include_router(tracks.router)
    return app
```

- [ ] **Step 6: Run the whole suite**

Run: `cd backend && pytest -v`
Expected: PASS — `22 passed`

- [ ] **Step 7: Verify the server actually boots**

Run: `cd backend && uvicorn main:app --port 8000 &  sleep 3 && curl -s localhost:8000/health && kill %1`
Expected: `{"status":"ok"}`

Also open `http://localhost:8000/docs` once to confirm all seven routes appear.

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "feat(backend): add profile and track routers with structured error codes"
```

---

## Task 6: Frontend scaffold with Tailwind v4 theme tokens

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.app.json`, `frontend/tsconfig.node.json`, `frontend/index.html`, `frontend/.env`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/index.css`, `frontend/src/vite-env.d.ts`, `frontend/src/lib/cn.ts`, `frontend/src/test/setup.ts`

- [ ] **Step 1: Create the project directory and `package.json`**

```bash
mkdir -p frontend/src/{lib,hooks,types,test,pages,services/api} \
         frontend/src/components/{ui,layout,onboarding}
```

Create `frontend/package.json`:

```json
{
  "name": "careeros-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.62.0",
    "clsx": "^2.1.1",
    "framer-motion": "^12.0.0",
    "lucide-react": "^0.468.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^7.1.0",
    "tailwind-merge": "^2.6.0"
  },
  "devDependencies": {
    "@tailwindcss/vite": "^4.0.0",
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.1.0",
    "@types/node": "^22.10.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.4",
    "jsdom": "^25.0.1",
    "tailwindcss": "^4.0.0",
    "typescript": "~5.7.2",
    "vite": "^6.0.0",
    "vitest": "^2.1.8"
  }
}
```

- [ ] **Step 2: Install**

Run: `cd frontend && npm install`
Expected: `added N packages` with no `ERESOLVE` errors.

- [ ] **Step 3: Write the build config**

`frontend/vite.config.ts`:

```ts
/// <reference types="vitest/config" />
import path from "node:path";
import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(dirname, "./src") },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
```

`frontend/tsconfig.json`:

```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ]
}
```

`frontend/tsconfig.app.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "noEmit": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "verbatimModuleSyntax": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"],
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src"]
}
```

`frontend/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2023"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "types": ["node"]
  },
  "include": ["vite.config.ts"]
}
```

`frontend/src/vite-env.d.ts`:

```ts
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
```

`frontend/.env`:

```
VITE_API_BASE_URL=http://localhost:8000
```

`frontend/src/test/setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 4: Write the theme tokens**

`frontend/src/index.css`:

```css
@import "tailwindcss";

@custom-variant dark (&:is(.dark *));

/* Tokens are indirected through var(--x) so toggling `.dark` on <html>
   repaints the entire palette without a rebuild. */
@theme {
  --color-bg: var(--bg);
  --color-surface: var(--surface);
  --color-surface-hover: var(--surface-hover);
  --color-line: var(--line);
  --color-text-primary: var(--text-primary);
  --color-text-secondary: var(--text-secondary);
  --color-text-muted: var(--text-muted);
  --color-accent: var(--accent);
  --color-accent-hover: var(--accent-hover);
  --color-accent-soft: var(--accent-soft);
  --color-on-accent: var(--on-accent);
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-danger: #ef4444;

  --font-sans: "Inter", ui-sans-serif, system-ui, sans-serif;

  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;

  --duration-fast: 120ms;
  --duration-base: 200ms;
}

/* Light is the default palette. */
:root {
  --bg: #fafafa;
  --surface: #ffffff;
  --surface-hover: #f4f4f5;
  --line: #e4e4e7;
  --text-primary: #18181b;
  --text-secondary: #52525b;
  --text-muted: #a1a1aa;
  --accent: #6366f1;
  --accent-hover: #4f46e5;
  --accent-soft: rgba(99, 102, 241, 0.1);
  --on-accent: #ffffff;

  color-scheme: light;
}

.dark {
  --bg: #09090b;
  --surface: #131316;
  --surface-hover: #1a1a1f;
  --line: #27272a;
  --text-primary: #fafafa;
  --text-secondary: #a1a1aa;
  --text-muted: #52525b;
  --accent: #818cf8;
  --accent-hover: #a5b4fc;
  --accent-soft: rgba(129, 140, 248, 0.12);
  --on-accent: #09090b;

  color-scheme: dark;
}

* {
  border-color: var(--line);
}

body {
  background-color: var(--bg);
  color: var(--text-primary);
  font-family: var(--font-sans);
  -webkit-font-smoothing: antialiased;
}
```

- [ ] **Step 5: Write the entry points**

`frontend/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>CareerOS</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`frontend/src/lib/cn.ts`:

```ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

`frontend/src/App.tsx`:

```tsx
export default function App() {
  return (
    <main className="grid min-h-dvh place-items-center">
      <h1 className="text-3xl font-semibold text-accent">CareerOS</h1>
    </main>
  );
}
```

`frontend/src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

- [ ] **Step 6: Verify the build and dev server**

Run: `cd frontend && npm run build`
Expected: `✓ built in ...` with no TypeScript errors.

Run: `cd frontend && npm run dev`
Expected: server on `http://localhost:5173`; the page shows "CareerOS" in indigo on a near-white background. Stop it with Ctrl-C.

- [ ] **Step 7: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold Vite React app with Tailwind v4 theme tokens"
```

---

## Task 7: Theme system

**Files:**
- Create: `frontend/src/hooks/useTheme.ts`, `frontend/src/hooks/__tests__/useTheme.test.ts`, `frontend/src/components/layout/ThemeToggle.tsx`

- [ ] **Step 1: Write the failing test**

```bash
mkdir -p frontend/src/hooks/__tests__
```

`frontend/src/hooks/__tests__/useTheme.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { resolveTheme } from "@/hooks/useTheme";

describe("resolveTheme", () => {
  it("returns the explicit choice regardless of system preference", () => {
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });

  it("follows the system preference when set to system", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL — `Failed to resolve import "@/hooks/useTheme"`

- [ ] **Step 3: Write `frontend/src/hooks/useTheme.ts`**

```ts
import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

const STORAGE_KEY = "careeros.theme";

/** Pure: what the page should actually render, given the choice and the OS. */
export function resolveTheme(theme: Theme, prefersDark: boolean): ResolvedTheme {
  if (theme === "system") return prefersDark ? "dark" : "light";
  return theme;
}

function readStoredTheme(): Theme {
  const raw = localStorage.getItem(STORAGE_KEY);
  return raw === "light" || raw === "dark" || raw === "system" ? raw : "system";
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(readStoredTheme);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");

    const apply = () => {
      const resolved = resolveTheme(theme, media.matches);
      document.documentElement.classList.toggle("dark", resolved === "dark");
    };

    apply();
    // Only "system" needs to react to the OS flipping mid-session.
    if (theme !== "system") return;

    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [theme]);

  const setTheme = useCallback((next: Theme) => {
    localStorage.setItem(STORAGE_KEY, next);
    setThemeState(next);
  }, []);

  return { theme, setTheme };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test`
Expected: PASS — `2 passed`

- [ ] **Step 5: Write `frontend/src/components/layout/ThemeToggle.tsx`**

```tsx
import { Monitor, Moon, Sun } from "lucide-react";

import { useTheme, type Theme } from "@/hooks/useTheme";
import { cn } from "@/lib/cn";

const OPTIONS: { value: Theme; icon: typeof Sun; label: string }[] = [
  { value: "light", icon: Sun, label: "Light" },
  { value: "dark", icon: Moon, label: "Dark" },
  { value: "system", icon: Monitor, label: "System" },
];

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="flex items-center gap-0.5 rounded-lg border border-line bg-surface p-0.5">
      {OPTIONS.map(({ value, icon: Icon, label }) => (
        <button
          key={value}
          type="button"
          aria-label={label}
          aria-pressed={theme === value}
          onClick={() => setTheme(value)}
          className={cn(
            "grid size-7 place-items-center rounded-md transition-colors duration-fast",
            theme === value
              ? "bg-accent-soft text-accent"
              : "text-text-muted hover:text-text-secondary",
          )}
        >
          <Icon className="size-4" />
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): add theme system with light, dark, and system modes"
```

---

## Task 8: UI primitives and app shell

**Files:**
- Create: `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/card.tsx`, `frontend/src/components/ui/input.tsx`, `frontend/src/components/layout/Sidebar.tsx`, `frontend/src/components/layout/TopBar.tsx`, `frontend/src/components/layout/AppShell.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/main.tsx`

These are presentational; they are verified by the build and by eye rather than by
unit tests. Component behaviour that matters (theme resolution, progress math,
warning escalation) is tested where the logic lives.

- [ ] **Step 1: Write `frontend/src/components/ui/button.tsx`**

```tsx
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

type Variant = "primary" | "secondary" | "ghost";
type Size = "sm" | "md" | "lg";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-on-accent hover:bg-accent-hover",
  secondary: "border border-line bg-surface text-text-primary hover:bg-surface-hover",
  ghost: "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-sm",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-6 text-base",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export function Button({
  variant = "primary",
  size = "md",
  className,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium",
        "transition-colors duration-fast",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
        "disabled:pointer-events-none disabled:opacity-50",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    />
  );
}
```

- [ ] **Step 2: Write `frontend/src/components/ui/card.tsx`**

```tsx
import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-xl border border-line bg-surface p-5", className)}
      {...props}
    />
  );
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2
      className={cn("text-base font-semibold text-text-primary", className)}
      {...props}
    />
  );
}

export function CardDescription({
  className,
  ...props
}: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-sm text-text-secondary", className)} {...props} />;
}
```

- [ ] **Step 3: Write `frontend/src/components/ui/input.tsx`**

```tsx
import type { InputHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export function Input({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-11 w-full rounded-lg border border-line bg-surface px-3.5 text-sm",
        "text-text-primary placeholder:text-text-muted",
        "transition-colors duration-fast",
        "focus:border-accent focus:outline-none",
        className,
      )}
      {...props}
    />
  );
}
```

- [ ] **Step 4: Write `frontend/src/components/layout/Sidebar.tsx`**

```tsx
import { LayoutDashboard, Map, MessageSquare, Settings } from "lucide-react";
import { NavLink } from "react-router-dom";

import { cn } from "@/lib/cn";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/roadmap", label: "Roadmap", icon: Map },
  { to: "/interview", label: "Interviews", icon: MessageSquare },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  return (
    <nav
      aria-label="Main"
      className={cn(
        "flex shrink-0 gap-1 border-line bg-surface",
        // Bottom bar on small screens, rail on md and up.
        "fixed inset-x-0 bottom-0 z-20 justify-around border-t p-2",
        "md:static md:h-dvh md:w-56 md:flex-col md:justify-start md:border-r md:border-t-0 md:p-3",
      )}
    >
      <div className="hidden px-2 pb-4 pt-2 md:block">
        <span className="text-lg font-semibold tracking-tight text-text-primary">
          Career<span className="text-accent">OS</span>
        </span>
      </div>

      {NAV.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/"}
          className={({ isActive }) =>
            cn(
              "flex flex-1 flex-col items-center gap-1 rounded-lg px-3 py-2 text-xs font-medium",
              "transition-colors duration-fast",
              "md:w-full md:flex-none md:flex-row md:gap-2.5 md:text-sm",
              isActive
                ? "bg-accent-soft text-accent"
                : "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
            )
          }
        >
          <Icon className="size-[18px]" />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
```

- [ ] **Step 5: Write `frontend/src/components/layout/TopBar.tsx`**

```tsx
import { ThemeToggle } from "@/components/layout/ThemeToggle";

interface TopBarProps {
  title: string;
  subtitle?: string;
}

export function TopBar({ title, subtitle }: TopBarProps) {
  return (
    <header className="flex items-start justify-between gap-4 pb-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-text-primary">
          {title}
        </h1>
        {subtitle && <p className="mt-1 text-sm text-text-secondary">{subtitle}</p>}
      </div>
      <ThemeToggle />
    </header>
  );
}
```

- [ ] **Step 6: Write `frontend/src/components/layout/AppShell.tsx`**

```tsx
import type { ReactNode } from "react";

import { Sidebar } from "@/components/layout/Sidebar";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh bg-bg">
      <Sidebar />
      {/* pb-24 clears the fixed bottom nav on mobile. */}
      <main className="mx-auto w-full max-w-5xl px-5 pb-24 pt-8 md:px-8 md:pb-8">
        {children}
      </main>
    </div>
  );
}
```

- [ ] **Step 7: Wire routing in `frontend/src/App.tsx`**

```tsx
import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";

function Placeholder({ title }: { title: string }) {
  return (
    <AppShell>
      <TopBar title={title} subtitle="Coming in a later plan." />
    </AppShell>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Placeholder title="Dashboard" />} />
      <Route path="/roadmap" element={<Placeholder title="Roadmap" />} />
      <Route path="/interview" element={<Placeholder title="Interviews" />} />
      <Route path="/settings" element={<Placeholder title="Settings" />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
```

- [ ] **Step 8: Wire providers in `frontend/src/main.tsx`**

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 30_000 },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
```

- [ ] **Step 9: Verify**

Run: `cd frontend && npm run build && npm test`
Expected: build succeeds, `2 passed`.

Run `npm run dev` and confirm: the sidebar navigates between four routes, the
theme toggle switches all three modes, and at a narrow window width the sidebar
becomes a bottom bar.

- [ ] **Step 10: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): add UI primitives, app shell, and routing"
```

---

## Task 9: Typed API client and data hooks

**Files:**
- Create: `frontend/src/types/index.ts`, `frontend/src/services/api/client.ts`, `frontend/src/services/api/profile.ts`, `frontend/src/hooks/useProfile.ts`

- [ ] **Step 1: Write `frontend/src/types/index.ts`**

```ts
export type ExperienceLevel = "beginner" | "intermediate" | "advanced";
export type Theme = "light" | "dark" | "system";

export interface Profile {
  id: number;
  name: string;
  theme: Theme;
  created_at: string;
}

export interface Track {
  id: number;
  topic: string;
  experience_level: ExperienceLevel;
  is_active: boolean;
  created_at: string;
}
```

- [ ] **Step 2: Write `frontend/src/services/api/client.ts`**

```ts
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Thin fetch wrapper. Normalizes the backend's {detail: {code, message}} shape
 * into ApiError so callers can branch on `code` rather than parsing strings,
 * and maps 204 to null (the "not onboarded yet" signal from GET /api/profile).
 */
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });

  if (response.status === 204) return null as T;

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = body?.detail;
    const isStructured = detail !== null && typeof detail === "object";
    throw new ApiError(
      response.status,
      isStructured && typeof detail.code === "string" ? detail.code : "unknown_error",
      isStructured && typeof detail.message === "string"
        ? detail.message
        : response.statusText,
    );
  }

  return body as T;
}
```

- [ ] **Step 3: Write `frontend/src/services/api/profile.ts`**

```ts
import { api } from "@/services/api/client";
import type { ExperienceLevel, Profile, Theme, Track } from "@/types";

export const getProfile = () => api<Profile | null>("/api/profile");

export const createProfile = (name: string) =>
  api<Profile>("/api/profile", { method: "POST", body: JSON.stringify({ name }) });

export const updateProfile = (payload: { name?: string; theme?: Theme }) =>
  api<Profile>("/api/profile", { method: "PATCH", body: JSON.stringify(payload) });

export const listTracks = () => api<Track[]>("/api/tracks");

export const createTrack = (topic: string, experienceLevel: ExperienceLevel) =>
  api<Track>("/api/tracks", {
    method: "POST",
    body: JSON.stringify({ topic, experience_level: experienceLevel }),
  });
```

The backend's `POST /api/tracks/{id}/activate` is built and tested in Task 4/5
because the spec lists it, but no UI in this plan switches between tracks, so
a client wrapper for it would have zero callers. Add it alongside whichever
future plan builds a track switcher.

- [ ] **Step 4: Write `frontend/src/hooks/useProfile.ts`**

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createProfile,
  createTrack,
  getProfile,
  listTracks,
  updateProfile,
} from "@/services/api/profile";
import type { ExperienceLevel } from "@/types";

export const profileKey = ["profile"] as const;
export const tracksKey = ["tracks"] as const;

export function useProfile() {
  return useQuery({ queryKey: profileKey, queryFn: getProfile });
}

export function useTracks() {
  return useQuery({ queryKey: tracksKey, queryFn: listTracks });
}

export function useActiveTrack() {
  const { data, ...rest } = useTracks();
  return { data: data?.find((track) => track.is_active) ?? null, ...rest };
}

export function useCreateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => createProfile(name),
    onSuccess: (profile) => queryClient.setQueryData(profileKey, profile),
  });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateProfile,
    onSuccess: (profile) => queryClient.setQueryData(profileKey, profile),
  });
}

export function useCreateTrack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      topic,
      experienceLevel,
    }: {
      topic: string;
      experienceLevel: ExperienceLevel;
    }) => createTrack(topic, experienceLevel),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: tracksKey }),
  });
}
```

- [ ] **Step 5: Verify it compiles**

Run: `cd frontend && npm run build`
Expected: `✓ built in ...`

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): add typed API client and profile data hooks"
```

---

## Task 10: Onboarding wizard

**Files:**
- Create: `frontend/src/lib/constants.ts`, `frontend/src/components/onboarding/NameStep.tsx`, `frontend/src/components/onboarding/TopicStep.tsx`, `frontend/src/components/onboarding/LevelStep.tsx`, `frontend/src/pages/OnboardingPage.tsx`

- [ ] **Step 1: Write `frontend/src/lib/constants.ts`**

```ts
import type { ExperienceLevel } from "@/types";

export const PRESET_TOPICS = [
  "Python",
  "JavaScript",
  "TypeScript",
  "Git & GitHub",
  "React",
  "Node.js",
  "Express.js",
  "Full Stack Development",
  "Software Development",
  "AI",
  "Machine Learning",
  "Deep Learning",
  "MLOps",
  "DevOps",
  "SQL",
  "PostgreSQL",
  "Docker",
  "Kubernetes",
  "Cloud Computing",
  "Data Structures & Algorithms",
] as const;

export const EXPERIENCE_LEVELS: {
  value: ExperienceLevel;
  label: string;
  description: string;
}[] = [
  {
    value: "beginner",
    label: "Beginner",
    description:
      "New to this. We skip the assessment and build a roadmap from the fundamentals up.",
  },
  {
    value: "intermediate",
    label: "Intermediate",
    description:
      "You know some of it. A short assessment finds your gaps, then the roadmap targets them.",
  },
  {
    value: "advanced",
    label: "Advanced (Revision)",
    description:
      "You want to sharpen up. A harder assessment drives a roadmap of weak spots, advanced projects, and interview prep.",
  },
];
```

- [ ] **Step 2: Write `frontend/src/components/onboarding/NameStep.tsx`**

```tsx
import { ArrowRight } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function NameStep({ onNext }: { onNext: (name: string) => void }) {
  const [name, setName] = useState("");
  const trimmed = name.trim();

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (trimmed) onNext(trimmed);
      }}
      className="space-y-6"
    >
      <div className="space-y-2">
        <h2 className="text-3xl font-semibold tracking-tight">
          What should we call you?
        </h2>
        <p className="text-text-secondary">
          CareerOS builds a plan around you, so let's start with a name.
        </p>
      </div>

      <Input
        autoFocus
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="Your name"
        maxLength={120}
        aria-label="Your name"
      />

      <Button type="submit" size="lg" disabled={!trimmed}>
        Continue <ArrowRight className="size-4" />
      </Button>
    </form>
  );
}
```

- [ ] **Step 3: Write `frontend/src/components/onboarding/TopicStep.tsx`**

```tsx
import { ArrowRight } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PRESET_TOPICS } from "@/lib/constants";
import { cn } from "@/lib/cn";

export function TopicStep({ onNext }: { onNext: (topic: string) => void }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [custom, setCustom] = useState("");

  const topic = (custom.trim() || selected) ?? "";

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (topic) onNext(topic);
      }}
      className="space-y-6"
    >
      <div className="space-y-2">
        <h2 className="text-3xl font-semibold tracking-tight">
          What do you want to learn?
        </h2>
        <p className="text-text-secondary">
          Pick one, or type anything else you have in mind.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {PRESET_TOPICS.map((preset) => (
          <button
            key={preset}
            type="button"
            aria-pressed={selected === preset && !custom.trim()}
            onClick={() => {
              setSelected(preset);
              setCustom("");
            }}
            className={cn(
              "rounded-full border px-3.5 py-1.5 text-sm transition-colors duration-fast",
              selected === preset && !custom.trim()
                ? "border-accent bg-accent-soft text-accent"
                : "border-line bg-surface text-text-secondary hover:bg-surface-hover hover:text-text-primary",
            )}
          >
            {preset}
          </button>
        ))}
      </div>

      <Input
        value={custom}
        onChange={(event) => setCustom(event.target.value)}
        placeholder="Or something else — e.g. Rust, Systems Design"
        maxLength={120}
        aria-label="Custom topic"
      />

      <Button type="submit" size="lg" disabled={!topic}>
        Continue <ArrowRight className="size-4" />
      </Button>
    </form>
  );
}
```

- [ ] **Step 4: Write `frontend/src/components/onboarding/LevelStep.tsx`**

```tsx
import { Loader2 } from "lucide-react";

import { EXPERIENCE_LEVELS } from "@/lib/constants";
import { cn } from "@/lib/cn";
import type { ExperienceLevel } from "@/types";

interface LevelStepProps {
  topic: string;
  pending: boolean;
  onSelect: (level: ExperienceLevel) => void;
}

export function LevelStep({ topic, pending, onSelect }: LevelStepProps) {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-3xl font-semibold tracking-tight">
          How much {topic} do you already know?
        </h2>
        <p className="text-text-secondary">
          This decides whether we assess you first or go straight to the roadmap.
        </p>
      </div>

      <div className="grid gap-3">
        {EXPERIENCE_LEVELS.map(({ value, label, description }) => (
          <button
            key={value}
            type="button"
            disabled={pending}
            onClick={() => onSelect(value)}
            className={cn(
              "rounded-xl border border-line bg-surface p-5 text-left",
              "transition-colors duration-fast",
              "hover:border-accent hover:bg-accent-soft",
              "disabled:pointer-events-none disabled:opacity-60",
            )}
          >
            <span className="block font-semibold text-text-primary">{label}</span>
            <span className="mt-1 block text-sm text-text-secondary">
              {description}
            </span>
          </button>
        ))}
      </div>

      {pending && (
        <p className="flex items-center gap-2 text-sm text-text-secondary">
          <Loader2 className="size-4 animate-spin" /> Setting up your track…
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Write `frontend/src/pages/OnboardingPage.tsx`**

```tsx
import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { LevelStep } from "@/components/onboarding/LevelStep";
import { NameStep } from "@/components/onboarding/NameStep";
import { TopicStep } from "@/components/onboarding/TopicStep";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { useCreateProfile, useCreateTrack, useProfile } from "@/hooks/useProfile";
import { cn } from "@/lib/cn";
import type { ExperienceLevel } from "@/types";

export default function OnboardingPage() {
  const navigate = useNavigate();
  const { data: profile } = useProfile();
  const createProfile = useCreateProfile();
  const createTrack = useCreateTrack();

  // If a profile already exists we are here to add a track, not to re-onboard.
  const [step, setStep] = useState(profile ? 1 : 0);
  const [topic, setTopic] = useState("");

  const handleName = async (name: string) => {
    await createProfile.mutateAsync(name);
    setStep(1);
  };

  const handleTopic = (chosen: string) => {
    setTopic(chosen);
    setStep(2);
  };

  const handleLevel = async (level: ExperienceLevel) => {
    await createTrack.mutateAsync({ topic, experienceLevel: level });
    navigate("/", { replace: true });
  };

  return (
    <div className="min-h-dvh bg-bg">
      <div className="mx-auto flex w-full max-w-xl flex-col gap-10 px-5 py-16">
        <div className="flex items-center justify-between">
          <span className="text-lg font-semibold tracking-tight">
            Career<span className="text-accent">OS</span>
          </span>
          <ThemeToggle />
        </div>

        <div className="flex gap-1.5" aria-hidden>
          {[0, 1, 2].map((index) => (
            <span
              key={index}
              className={cn(
                "h-1 flex-1 rounded-full transition-colors duration-base",
                index <= step ? "bg-accent" : "bg-line",
              )}
            />
          ))}
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -16 }}
            transition={{ duration: 0.2 }}
          >
            {step === 0 && <NameStep onNext={handleName} />}
            {step === 1 && <TopicStep onNext={handleTopic} />}
            {step === 2 && (
              <LevelStep
                topic={topic}
                pending={createTrack.isPending}
                onSelect={handleLevel}
              />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Verify it compiles**

Run: `cd frontend && npm run build`
Expected: `✓ built in ...`

- [ ] **Step 7: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): add three-step onboarding wizard"
```

---

## Task 11: Dashboard, settings, and onboarding gate

**Files:**
- Create: `frontend/src/pages/DashboardPage.tsx`, `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write `frontend/src/pages/DashboardPage.tsx`**

```tsx
import { Plus } from "lucide-react";
import { Link } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { useActiveTrack, useProfile } from "@/hooks/useProfile";

export default function DashboardPage() {
  const { data: profile } = useProfile();
  const { data: track } = useActiveTrack();

  return (
    <AppShell>
      <TopBar
        title={`Welcome back, ${profile?.name ?? "there"}`}
        subtitle={
          track
            ? `You're learning ${track.topic} at ${track.experience_level} level.`
            : "Pick something to learn to get started."
        }
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardTitle>Current track</CardTitle>
          <CardDescription className="mt-1">
            {track ? track.topic : "No active track yet."}
          </CardDescription>
          <Link to="/onboarding" className="mt-4 inline-block">
            <Button variant="secondary" size="sm">
              <Plus className="size-4" /> New track
            </Button>
          </Link>
        </Card>

        <Card>
          <CardTitle>Roadmap</CardTitle>
          <CardDescription className="mt-1">
            Your personalized roadmap arrives in the next build stage.
          </CardDescription>
        </Card>
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 2: Write `frontend/src/pages/SettingsPage.tsx`**

```tsx
import { useEffect, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useProfile, useUpdateProfile } from "@/hooks/useProfile";

export default function SettingsPage() {
  const { data: profile } = useProfile();
  const updateProfile = useUpdateProfile();
  const [name, setName] = useState("");

  useEffect(() => {
    if (profile) setName(profile.name);
  }, [profile]);

  const trimmed = name.trim();
  const dirty = Boolean(trimmed) && trimmed !== profile?.name;

  return (
    <AppShell>
      <TopBar title="Settings" subtitle="Your profile and appearance." />

      <Card className="max-w-md">
        <CardTitle>Your name</CardTitle>
        <CardDescription className="mt-1">
          Used across your dashboard and reports.
        </CardDescription>

        <div className="mt-4 flex gap-2">
          <Input
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={120}
            aria-label="Your name"
          />
          <Button
            disabled={!dirty || updateProfile.isPending}
            onClick={() => updateProfile.mutate({ name: trimmed })}
          >
            Save
          </Button>
        </div>
      </Card>
    </AppShell>
  );
}
```

- [ ] **Step 3: Add the onboarding gate to `frontend/src/App.tsx`**

Replace the whole file:

```tsx
import { Loader2 } from "lucide-react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";
import { useProfile } from "@/hooks/useProfile";
import DashboardPage from "@/pages/DashboardPage";
import OnboardingPage from "@/pages/OnboardingPage";
import SettingsPage from "@/pages/SettingsPage";

function Placeholder({ title }: { title: string }) {
  return (
    <AppShell>
      <TopBar title={title} subtitle="Coming in a later plan." />
    </AppShell>
  );
}

export default function App() {
  const { data: profile, isPending } = useProfile();
  const location = useLocation();

  if (isPending) {
    return (
      <div className="grid min-h-dvh place-items-center bg-bg">
        <Loader2 className="size-6 animate-spin text-text-muted" />
      </div>
    );
  }

  // No profile means onboarding is the only reachable screen.
  if (!profile && location.pathname !== "/onboarding") {
    return <Navigate to="/onboarding" replace />;
  }

  return (
    <Routes>
      <Route path="/onboarding" element={<OnboardingPage />} />
      <Route path="/" element={<DashboardPage />} />
      <Route path="/roadmap" element={<Placeholder title="Roadmap" />} />
      <Route path="/interview" element={<Placeholder title="Interviews" />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
```

- [ ] **Step 4: Full verification**

Run: `cd backend && pytest -v`
Expected: `22 passed`

Run: `cd frontend && npm run build && npm test`
Expected: build succeeds, `2 passed`

Now run both servers and walk the flow end to end:

```bash
cd backend && rm -f careeros.db && uvicorn main:app --reload
```

```bash
cd frontend && npm run dev
```

Open `http://localhost:5173` and confirm:
1. It redirects to `/onboarding`.
2. Entering a name advances to the topic step.
3. Picking "Python" (or typing a custom topic) advances to the level step.
4. Choosing a level lands on the dashboard, which greets you by name and shows
   the topic.
5. Reloading goes straight to the dashboard — no re-onboarding.
6. `/settings` renames you and the dashboard greeting updates.
7. The theme toggle works in all three modes, and "System" follows an OS theme
   change.
8. Narrowing the window turns the sidebar into a bottom bar.

- [ ] **Step 5: Write `README.md` at the repo root**

````markdown
# CareerOS

An AI Career Mentor: personalized learning roadmaps and AI-proctored mock
interviews. University mini project.

**Stack:** React 19 + TypeScript + Vite + Tailwind v4 · FastAPI + SQLAlchemy +
SQLite · Google Gemini · MediaPipe (in-browser proctoring) · Web Speech API.

## Running it

Backend:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # add your GEMINI_API_KEY
uvicorn main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. API docs at http://localhost:8000/docs.

## Tests

```bash
cd backend && pytest
cd frontend && npm test
```

## Design docs

- Spec: `docs/superpowers/specs/2026-08-07-careeros-design.md`
- Plans: `docs/superpowers/plans/`
````

- [ ] **Step 6: Commit**

```bash
git add frontend/ README.md
git commit -m "feat(frontend): add dashboard, settings, and onboarding gate"
```

---

## Done when

- `cd backend && pytest` → 22 passed
- `cd frontend && npm run build && npm test` → build clean, 2 passed
- A fresh `careeros.db` walks name → topic → level → dashboard without errors
- All three theme modes work and persist across reload
- The layout is usable at 375px and at 1440px

**Next:** Plan 2 — AI client, `FakeAIClient`, assessment generation, autosave,
grading, and the assessment UI.
