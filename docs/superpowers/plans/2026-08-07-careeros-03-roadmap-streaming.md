# CareerOS Plan 3 — Roadmap Streaming, Progress, and Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the streaming roadmap generator — phases materializing live over SSE as Gemini writes them — plus the module-completion progress model, the timeline viewer UI, and the real dashboard aggregate. By the end, finishing onboarding (Beginner, or Intermediate/Advanced after a scored assessment) lands the learner on a real, AI-generated, phase-by-phase roadmap they can track progress through.

**Architecture:** `PhaseStreamParser` is a pure incremental scanner (no I/O) that turns raw Gemini text deltas into `(event, data)` tuples the moment each phase's closing brace arrives. `roadmap_service.stream_roadmap` is a generator that drives the parser, persists phases inside one uncommitted transaction as they arrive, and yields SSE-ready tuples; the router formats those as `text/event-stream` text. The frontend consumes it with `fetch` + `ReadableStream` (not `EventSource`, which cannot POST) through a small `sse.ts` helper, animating each phase in with Framer Motion as it lands. Progress math (module/phase/roadmap completion, phase unlock, current phase) is pure and implemented twice — `progress_service.py` and `lib/progress.ts` — tested against the identical fixtures on both sides so they can never silently drift.

**Tech Stack:** `google-genai` 2.x (streaming), FastAPI `StreamingResponse`, SQLAlchemy, pytest (backend); React 19, TanStack Query, Framer Motion, `fetch`/`ReadableStream` (frontend).

**Spec:** `docs/superpowers/specs/2026-08-07-careeros-design.md` (sections 5 roadmap tables, 6 derived progress logic, 7 roadmap + dashboard API, 8 streaming roadmap, 11 `/roadmap` and `/dashboard` pages)

**Series context:** Plan 3 of 5.
1. Foundation (done)
2. AI client + assessment (done)
3. **Roadmap SSE generation + viewer + progress + dashboard data** ← you are here
4. Interview core + speech
5. Proctoring + evaluation + reports + polish

**Verified before writing this plan**, against the live API and a real local FastAPI/uvicorn stack (not assumed from documentation):
- `generate_content_stream(...)` yields chunks whose `.text` is a **delta**, not a cumulative snapshot — concatenating chunks in arrival order reproduces the exact final JSON. Confirmed with a real 2-phase roadmap generation (8 chunks, final text parsed cleanly).
- Chunk boundaries fall at **arbitrary byte positions with zero regard for JSON structure** — a real chunk boundary landed mid-word inside a string value. Any parser that treats each chunk as its own JSON object is wrong; the parser must be a stateful scanner across the accumulated buffer.
- With `phases` declared as the schema's last property, Gemini's structured output reliably emits it last — confirmed via `list(parsed.keys())[-1] == "phases"` on real output.
- A hand-built prototype scanner (brace-depth + string/escape tracking) was run against the real captured delta chunks above, plus synthetic cases with literal `{`/`}` inside string values and multiple phases closing within a single chunk. All cases produced correct, individually-parseable phase objects. This exact design is what Task 1 implements.
- `StreamingResponse` wrapping a plain sync generator streams **progressively** through real uvicorn, not buffered — a 4-tick generator with `time.sleep(1)` between yields delivered each tick to a real `httpx` streaming client roughly 1 second apart, not all at once at the end.
- A `Depends(get_db)`-style yield dependency **stays open for the full duration** of a `StreamingResponse` — verified with a 3-second real generator that used the injected session on every tick; the session closed only after the stream fully completed. This is what makes "persist phases as they arrive, commit once at the end" safe.

---

## File Structure

**Backend** (`backend/`)

| File | Responsibility |
|---|---|
| `ai/stream_parser.py` | `PhaseStreamParser` — pure incremental scanner, no I/O |
| `ai/client.py` | + `generate_json_stream` on the `AIClient` Protocol and `FakeAIClient` |
| `ai/gemini_client.py` | + `GeminiClient.generate_json_stream` |
| `ai/prompts/roadmap.py` | `build_roadmap_prompt` — pure, beginner/intermediate/advanced variants |
| `models/roadmap.py` | `Roadmap`, `RoadmapPhase`, `RoadmapModule` |
| `schemas/roadmap.py` | `RoadmapOut`, `RoadmapPhaseOut`, `RoadmapModuleOut`, `ProgressOut` |
| `schemas/dashboard.py` | `DashboardOut` |
| `services/progress_service.py` | pure: `is_module_complete`, `phase_completion`, `roadmap_completion`, `is_phase_unlocked`, `current_phase_index`, `build_progress` |
| `services/roadmap_service.py` | `stream_roadmap` (generator), `get_roadmap`, `toggle_module` |
| `services/assessment_service.py` | + `get_latest_completed_assessment` (roadmap needs the learner's estimated level/strengths/weaknesses) |
| `services/dashboard_service.py` | `get_dashboard` — aggregates profile, track, roadmap, progress, recent interviews |
| `routers/roadmap.py` | SSE stream route, `GET roadmap`, `PATCH module`, `GET progress` |
| `routers/dashboard.py` | `GET /api/dashboard` |
| `main.py` | + roadmap/dashboard model imports and router wiring |
| `tests/test_stream_parser.py` | phase emission, nested objects, braces inside strings, backslash escapes, truncated stream |
| `tests/test_roadmap_prompts.py` | prompt builder is a correct pure function |
| `tests/test_progress_service.py` | phase/roadmap completion, 80% unlock rule, current-phase detection, all-complete edge |
| `tests/test_roadmap_service.py` | stream orchestration against `FakeAIClient`, transaction rollback on failure |
| `tests/test_roadmap_api.py` | router-level SSE consumption, module toggle, progress endpoint |
| `tests/test_dashboard_api.py` | dashboard aggregate shape, empty-state before any track exists |

**Frontend** (`frontend/src/`)

| File | Responsibility |
|---|---|
| `services/api/sse.ts` | `sseFetch` — `fetch` + `ReadableStream` SSE parser (not `EventSource`, which can't POST) |
| `services/api/roadmap.ts` | typed roadmap calls |
| `services/api/dashboard.ts` | typed dashboard call |
| `hooks/useRoadmapStream.ts` | drives `sseFetch`, accumulates phases into local state as they arrive |
| `hooks/useRoadmap.ts` | `useRoadmap`, `useToggleModule`, `useProgress` (post-generation reads) |
| `hooks/useDashboard.ts` | dashboard query |
| `lib/progress.ts` | pure mirror of `progress_service.py`, tested against the same fixtures |
| `components/roadmap/PhaseCard.tsx` | expandable phase with lock badge, completion bar |
| `components/roadmap/ModuleRow.tsx` | module row with completion checkbox, kind badge |
| `components/roadmap/ProgressRing.tsx` | SVG ring, reused on roadmap + dashboard |
| `components/roadmap/GeneratingRoadmap.tsx` | live streaming view — phases stagger in as SSE events arrive |
| `pages/RoadmapPage.tsx` | orchestrates streaming-vs-persisted view, timeline render |
| `pages/DashboardPage.tsx` | replaced: real greeting, progress ring, current phase, next module, Continue Learning |
| `pages/OnboardingPage.tsx` | modified: Beginner and post-assessment-submit both trigger roadmap generation, land on `/roadmap` |
| `App.tsx` | `/roadmap` now renders `RoadmapPage` instead of the placeholder |

---

## Task 1: PhaseStreamParser

**Files:**
- Create: `backend/ai/stream_parser.py`
- Test: `backend/tests/test_stream_parser.py`

This is the piece verified against real Gemini output before writing this plan (see header). The tests below encode those exact verified cases, plus the ones spec section 12 calls for (truncated stream, backslash escapes).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_stream_parser.py`:

```python
from ai.stream_parser import PhaseStreamParser


def _feed_all(parser: PhaseStreamParser, chunks: list[str]):
    events = []
    for chunk in chunks:
        events.extend(parser.feed(chunk))
    return events


def test_emits_meta_once_scalars_and_phases_key_are_seen():
    parser = PhaseStreamParser()
    events = _feed_all(
        parser,
        [
            '{"title": "T", "summary": "S", "total_weeks": 4, "weekly_hours": 8, ',
            '"weekly_goals": [{"week": 1, "goal": "G", "phase_order": 0}], ',
            '"final_project": {"title": "F", "description": "D", "skills_demonstrated": ["x"]}, ',
            '"phases": [',
        ],
    )
    assert len(events) == 1
    event, data = events[0]
    assert event == "meta"
    assert data["title"] == "T"
    assert data["total_weeks"] == 4
    assert data["weekly_goals"] == [{"week": 1, "goal": "G", "phase_order": 0}]
    assert data["final_project"]["title"] == "F"


def test_emits_one_phase_event_per_completed_phase_object():
    parser = PhaseStreamParser()
    chunks = [
        '{"title": "T", "summary": "S", "total_weeks": 1, "weekly_hours": 5, ',
        '"weekly_goals": [], "final_project": {"title": "F", "description": "D", "skills_demonstrated": []}, ',
        '"phases": [',
        '{"title": "Phase 1: Fundamentals & Syntax", "goal": "Master the core building blocks of Python, incl',
        'uding variables and loops.", "modules": []},',
        '{"title": "Phase 2: Functions, Data Structures & Basic Projects", "goal": "Learn to',
        ' organize code using functions and collections.", "modules": []}',
        ']}',
    ]
    events = _feed_all(parser, chunks)

    assert [e for e, _ in events] == ["meta", "phase", "phase"]
    _, phase1 = events[1]
    _, phase2 = events[2]
    assert phase1["title"] == "Phase 1: Fundamentals & Syntax"
    assert phase2["title"] == "Phase 2: Functions, Data Structures & Basic Projects"


def test_handles_nested_module_objects_inside_a_phase():
    parser = PhaseStreamParser()
    chunks = [
        '{"title": "T", "summary": "S", "total_weeks": 1, "weekly_hours": 5, ',
        '"weekly_goals": [], "final_project": {"title": "F", "description": "D", "skills_demonstrated": []}, ',
        '"phases": [',
        '{"title": "P1", "goal": "G1", "modules": [',
        '{"title": "M1", "description": "D1", "lessons": ["l1"], "exercises": [], "project": null, ',
        '"estimated_hours": 2, "kind": "module"}',
        ']}',
        ']}',
    ]
    events = _feed_all(parser, chunks)

    assert [e for e, _ in events] == ["meta", "phase"]
    _, phase = events[1]
    assert len(phase["modules"]) == 1
    assert phase["modules"][0]["title"] == "M1"


def test_literal_braces_inside_string_values_do_not_confuse_depth_tracking():
    parser = PhaseStreamParser()
    chunks = [
        '{"title": "T", "summary": "S", "total_weeks": 1, "weekly_hours": 5, ',
        '"weekly_goals": [], "final_project": {"title": "F", "description": "D", "skills_demonstrated": []}, ',
        '"phases": [',
        '{"title": "Uses {curly} braces", "goal": "explain dict literals like {\\"a\\": 1}", "modules": []}',
        ']}',
    ]
    events = _feed_all(parser, chunks)

    assert [e for e, _ in events] == ["meta", "phase"]
    _, phase = events[1]
    assert phase["title"] == "Uses {curly} braces"
    assert phase["goal"] == 'explain dict literals like {"a": 1}'


def test_multiple_phases_closing_within_a_single_chunk_all_emit():
    parser = PhaseStreamParser()
    chunks = [
        '{"title": "T", "summary": "S", "total_weeks": 1, "weekly_hours": 5, ',
        '"weekly_goals": [], "final_project": {"title": "F", "description": "D", "skills_demonstrated": []}, ',
        '"phases": [',
        '{"title": "P1", "goal": "G1", "modules": []},{"title": "P2", "goal": "G2", "modules": []}',
        ']}',
    ]
    events = _feed_all(parser, chunks)

    assert [e for e, _ in events] == ["meta", "phase", "phase"]


def test_truncated_stream_emits_only_completed_phases_no_crash():
    parser = PhaseStreamParser()
    chunks = [
        '{"title": "T", "summary": "S", "total_weeks": 1, "weekly_hours": 5, ',
        '"weekly_goals": [], "final_project": {"title": "F", "description": "D", "skills_demonstrated": []}, ',
        '"phases": [',
        '{"title": "P1", "goal": "G1", "modules": []},',
        '{"title": "P2 is cut off mid',
        # stream ends here — no crash, no partial "phase" event for P2
    ]
    events = _feed_all(parser, chunks)

    assert [e for e, _ in events] == ["meta", "phase"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_stream_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai.stream_parser'`

- [ ] **Step 3: Write `backend/ai/stream_parser.py`**

```python
from __future__ import annotations

import json

Event = tuple[str, dict]


class PhaseStreamParser:
    """Incrementally scans accumulating JSON text from a streaming roadmap
    generation and yields (event, data) tuples the instant enough text has
    arrived to know the answer:

      ("meta", {...})   once, as soon as every scalar field plus weekly_goals
                        and final_project are complete (i.e. the moment the
                        "phases" array opens — this is why the roadmap schema
                        requires "phases" to be the last property)
      ("phase", {...})  once per phase, the instant that phase object's
                        closing brace arrives

    Pure — no I/O, no network, no DB. Chunk boundaries are assumed to fall
    at arbitrary byte positions with no regard for JSON structure (verified
    against real Gemini streaming output before this was written), so this
    tracks brace depth char-by-char across the whole accumulated buffer
    rather than trying to parse each chunk in isolation.
    """

    def __init__(self) -> None:
        self._buffer = ""
        self._depth = 0
        self._in_string = False
        self._escaped = False
        self._phases_started = False
        self._meta_emitted = False
        self._phase_start: int | None = None

    def feed(self, chunk: str) -> list[Event]:
        events: list[Event] = []
        for ch in chunk:
            self._buffer += ch

            if self._escaped:
                self._escaped = False
                continue
            if ch == "\\" and self._in_string:
                self._escaped = True
                continue
            if ch == '"':
                self._in_string = not self._in_string
                continue
            if self._in_string:
                continue

            if ch == "{":
                if self._depth == 1 and self._phases_started and self._phase_start is None:
                    self._phase_start = len(self._buffer) - 1
                self._depth += 1
            elif ch == "}":
                self._depth -= 1
                if self._depth == 1 and self._phases_started and self._phase_start is not None:
                    raw = self._buffer[self._phase_start :]
                    self._phase_start = None
                    try:
                        events.append(("phase", json.loads(raw)))
                    except json.JSONDecodeError:
                        pass
            elif ch == "[" and self._depth == 1 and not self._phases_started:
                prefix = self._buffer[: len(self._buffer) - 1].rstrip()
                if prefix.endswith('"phases":') or prefix.endswith('"phases" :'):
                    self._phases_started = True
                    if not self._meta_emitted:
                        meta_raw = self._buffer[: self._buffer.rfind('"phases"')]
                        meta_raw = meta_raw.rstrip().rstrip(",") + "}"
                        try:
                            events.append(("meta", json.loads(meta_raw)))
                        except json.JSONDecodeError:
                            pass
                        self._meta_emitted = True

        return events
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_stream_parser.py -v`
Expected: PASS — `6 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/ai/stream_parser.py backend/tests/test_stream_parser.py
git commit -m "feat(backend): add PhaseStreamParser, verified against real Gemini streaming output"
```

---

## Task 2: Roadmap models

**Files:**
- Create: `backend/models/roadmap.py`
- Test: `backend/tests/test_roadmap_models.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_roadmap_models.py`:

```python
from models.roadmap import Roadmap, RoadmapModule, RoadmapPhase
from models.user import LearningTrack
from schemas.profile import ProfileCreate, TrackCreate
from services import profile_service


def _track(db_session):
    profile_service.create_profile(db_session, ProfileCreate(name="Aryan"))
    return profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level="beginner")
    )


def test_roadmap_phase_module_round_trip(db_session):
    track = _track(db_session)

    roadmap = Roadmap(
        track_id=track.id,
        title="Python Roadmap",
        summary="From zero to functional scripts.",
        total_weeks=8,
        weekly_hours=6,
        weekly_goals=[{"week": 1, "goal": "Learn syntax", "phase_order": 0}],
        final_project={"title": "CLI tool", "description": "...", "skills_demonstrated": ["cli"]},
    )
    db_session.add(roadmap)
    db_session.commit()

    phase = RoadmapPhase(
        roadmap_id=roadmap.id,
        order_index=0,
        title="Foundations",
        description="The basics.",
        goal="Write and run simple scripts.",
        estimated_hours=10,
    )
    db_session.add(phase)
    db_session.commit()

    module = RoadmapModule(
        phase_id=phase.id,
        order_index=0,
        title="Variables & Types",
        description="...",
        lessons=["Numbers", "Strings"],
        exercises=["Write a temperature converter"],
        project=None,
        estimated_hours=3,
        kind="module",
    )
    db_session.add(module)
    db_session.commit()

    assert roadmap.phases == [phase]
    assert phase.roadmap is roadmap
    assert phase.modules == [module]
    assert module.completed_at is None
    assert roadmap.track.id == track.id


def test_deleting_track_cascades_to_roadmap_phases_and_modules(db_session):
    track = _track(db_session)
    roadmap = Roadmap(track_id=track.id, title="T", summary="S", total_weeks=1, weekly_hours=1)
    db_session.add(roadmap)
    db_session.commit()
    phase = RoadmapPhase(roadmap_id=roadmap.id, order_index=0, title="P", description="", goal="G", estimated_hours=1)
    db_session.add(phase)
    db_session.commit()
    module = RoadmapModule(
        phase_id=phase.id, order_index=0, title="M", description="", lessons=[], exercises=[],
        project=None, estimated_hours=1, kind="module",
    )
    db_session.add(module)
    db_session.commit()
    roadmap_id, phase_id, module_id = roadmap.id, phase.id, module.id

    db_session.delete(db_session.get(LearningTrack, track.id))
    db_session.commit()

    assert db_session.get(Roadmap, roadmap_id) is None
    assert db_session.get(RoadmapPhase, phase_id) is None
    assert db_session.get(RoadmapModule, module_id) is None


def test_module_kind_and_completion_fields(db_session):
    track = _track(db_session)
    roadmap = Roadmap(track_id=track.id, title="T", summary="S", total_weeks=1, weekly_hours=1)
    db_session.add(roadmap)
    db_session.commit()
    phase = RoadmapPhase(roadmap_id=roadmap.id, order_index=0, title="P", description="", goal="G", estimated_hours=1)
    db_session.add(phase)
    db_session.commit()

    milestone = RoadmapModule(
        phase_id=phase.id, order_index=0, title="Capstone check-in", description="",
        lessons=[], exercises=[], project={"title": "Mini project", "description": "..."},
        estimated_hours=4, kind="milestone",
    )
    db_session.add(milestone)
    db_session.commit()

    assert milestone.kind == "milestone"
    assert milestone.project["title"] == "Mini project"
    assert milestone.started_at is None
    assert milestone.completed_at is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_roadmap_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'models.roadmap'`

- [ ] **Step 3: Write `backend/models/roadmap.py`**

```python
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from models.user import LearningTrack


class Roadmap(Base):
    """The generated learning path for a track. At most one roadmap matters
    at a time in the UI (the active track's), but nothing here prevents a
    track from accumulating several over time if regenerated."""

    __tablename__ = "roadmaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("learning_tracks.id", ondelete="CASCADE"))
    assessment_id: Mapped[int | None] = mapped_column(
        ForeignKey("assessments.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    total_weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    weekly_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    weekly_goals: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    final_project: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    track: Mapped["LearningTrack"] = relationship()
    phases: Mapped[list["RoadmapPhase"]] = relationship(
        back_populates="roadmap",
        cascade="all, delete-orphan",
        order_by="RoadmapPhase.order_index",
    )


class RoadmapPhase(Base):
    __tablename__ = "roadmap_phases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    roadmap_id: Mapped[int] = mapped_column(ForeignKey("roadmaps.id", ondelete="CASCADE"))
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    roadmap: Mapped["Roadmap"] = relationship(back_populates="phases")
    modules: Mapped[list["RoadmapModule"]] = relationship(
        back_populates="phase",
        cascade="all, delete-orphan",
        order_by="RoadmapModule.order_index",
    )


class RoadmapModule(Base):
    """`kind` distinguishes plain modules from revision checkpoints,
    phase-capping milestones, and mini-projects — the timeline renders each
    differently, but they're all completed the same way (`completed_at`)."""

    __tablename__ = "roadmap_modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phase_id: Mapped[int] = mapped_column(ForeignKey("roadmap_phases.id", ondelete="CASCADE"))
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    lessons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    exercises: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    project: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    estimated_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="module")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    phase: Mapped["RoadmapPhase"] = relationship(back_populates="modules")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_roadmap_models.py -v`
Expected: PASS — `3 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/models/roadmap.py backend/tests/test_roadmap_models.py
git commit -m "feat(backend): add Roadmap, RoadmapPhase, RoadmapModule models"
```

---

## Task 3: Progress service — pure completion, unlock, and current-phase logic

**Files:**
- Create: `backend/services/progress_service.py`
- Test: `backend/tests/test_progress_service.py`

Genuinely pure functions — no DB, no I/O. Tests use `SimpleNamespace` stand-ins
(just the attributes each function actually reads) rather than real ORM rows, so
the "pure" claim is verified by construction, not just by convention. This is
the exact logic `lib/progress.ts` mirrors later in this plan; the frontend tests
reuse these same numeric cases.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_progress_service.py`:

```python
from datetime import datetime
from types import SimpleNamespace

import pytest

from services.progress_service import (
    build_progress,
    current_phase_index,
    is_module_complete,
    is_phase_unlocked,
    phase_completion,
    roadmap_completion,
)


def _module(completed: bool):
    return SimpleNamespace(completed_at=datetime(2026, 1, 1) if completed else None)


def _phase(order_index: int, modules: list):
    return SimpleNamespace(order_index=order_index, title=f"Phase {order_index}", modules=modules)


def test_is_module_complete_checks_completed_at():
    assert is_module_complete(_module(True)) is True
    assert is_module_complete(_module(False)) is False


def test_phase_completion_is_the_completed_fraction():
    modules = [_module(True), _module(True), _module(False)]
    assert phase_completion(modules) == pytest.approx(2 / 3)


def test_phase_completion_of_empty_phase_is_zero_not_a_crash():
    assert phase_completion([]) == 0.0


def test_roadmap_completion_spans_all_phases():
    phases = [
        _phase(0, [_module(True), _module(True)]),
        _phase(1, [_module(True), _module(False)]),
    ]
    # 3 of 4 modules complete overall
    assert roadmap_completion(phases) == pytest.approx(3 / 4)


def test_first_phase_is_always_unlocked():
    phases = [_phase(0, [_module(False)])]
    assert is_phase_unlocked(0, phases) is True


def test_phase_unlocked_at_exactly_80_percent_previous_completion():
    # 4 of 5 = exactly 0.8 — the spec's threshold is inclusive
    previous = _phase(0, [_module(True)] * 4 + [_module(False)])
    phases = [previous, _phase(1, [_module(False)])]
    assert is_phase_unlocked(1, phases) is True


def test_phase_locked_just_under_80_percent_previous_completion():
    # 3 of 4 = 0.75 — below the threshold
    previous = _phase(0, [_module(True)] * 3 + [_module(False)])
    phases = [previous, _phase(1, [_module(False)])]
    assert is_phase_unlocked(1, phases) is False


def test_current_phase_is_the_first_incomplete_one():
    phases = [
        _phase(0, [_module(True)]),
        _phase(1, [_module(False)]),
        _phase(2, [_module(False)]),
    ]
    assert current_phase_index(phases) == 1


def test_current_phase_when_everything_is_complete_is_the_last_one():
    phases = [_phase(0, [_module(True)]), _phase(1, [_module(True)])]
    assert current_phase_index(phases) == 1


def test_build_progress_summarizes_everything_in_one_shape():
    phases = [
        _phase(0, [_module(True), _module(True)]),
        _phase(1, [_module(False)]),
    ]

    progress = build_progress(phases)

    assert progress["completed_modules"] == 2
    assert progress["total_modules"] == 3
    assert progress["completion_pct"] == pytest.approx(66.7, abs=0.1)
    assert progress["current_phase_index"] == 1
    assert progress["phases"][0]["unlocked"] is True
    assert progress["phases"][1]["unlocked"] is True  # phase 0 is 100% >= 80%
    assert progress["phases"][1]["completion_pct"] == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_progress_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.progress_service'`

- [ ] **Step 3: Write `backend/services/progress_service.py`**

```python
from __future__ import annotations

from typing import Any, Protocol


class _HasCompletedAt(Protocol):
    completed_at: object


class _HasModules(Protocol):
    order_index: int
    title: str
    modules: list[_HasCompletedAt]


def is_module_complete(module: _HasCompletedAt) -> bool:
    return module.completed_at is not None


def phase_completion(modules: list[_HasCompletedAt]) -> float:
    if not modules:
        return 0.0
    completed = sum(1 for m in modules if is_module_complete(m))
    return completed / len(modules)


def roadmap_completion(phases: list[_HasModules]) -> float:
    all_modules = [m for p in phases for m in p.modules]
    if not all_modules:
        return 0.0
    completed = sum(1 for m in all_modules if is_module_complete(m))
    return completed / len(all_modules)


def is_phase_unlocked(phase_index: int, phases: list[_HasModules]) -> bool:
    if phase_index == 0:
        return True
    return phase_completion(phases[phase_index - 1].modules) >= 0.8


def current_phase_index(phases: list[_HasModules]) -> int:
    for i, phase in enumerate(phases):
        if phase_completion(phase.modules) < 1.0:
            return i
    return len(phases) - 1 if phases else 0


def build_progress(phases: list[_HasModules]) -> dict[str, Any]:
    """The full progress summary the roadmap and dashboard endpoints share."""
    total_modules = sum(len(p.modules) for p in phases)
    completed_modules = sum(1 for p in phases for m in p.modules if is_module_complete(m))
    current = current_phase_index(phases)

    return {
        "completion_pct": round(roadmap_completion(phases) * 100, 1),
        "completed_modules": completed_modules,
        "total_modules": total_modules,
        "current_phase_index": current,
        "current_phase_title": phases[current].title if phases else None,
        "phases": [
            {
                "order_index": phase.order_index,
                "completion_pct": round(phase_completion(phase.modules) * 100, 1),
                "unlocked": is_phase_unlocked(i, phases),
            }
            for i, phase in enumerate(phases)
        ],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_progress_service.py -v`
Expected: PASS — `10 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/services/progress_service.py backend/tests/test_progress_service.py
git commit -m "feat(backend): add pure progress service (completion, unlock, current phase)"
```

---

## Task 4: Roadmap generation prompt

**Files:**
- Create: `backend/ai/prompts/roadmap.py`
- Test: `backend/tests/test_roadmap_prompts.py`

Pure function, no client, no DB — the assessment's strengths/weaknesses are
passed in as a lightweight duck-typed object so this file never needs to import
the ORM.

**A real finding baked into the schema below:** the full combined
`_ROADMAP_SCHEMA` was tested live against the API while writing this plan (see
Task 5's smoke test) and came back `400 INVALID_ARGUMENT`. Bisecting field by
field, every individual top-level property validated fine in isolation
(`title`, `summary`, `weekly_goals`, `final_project` all OK alone) — the
difference is the nested `project` field inside each module: a `nullable`
object that also carried its own `required: ["title", "description"]`, four
levels deep (root → phases → modules → project). Two narrower live tests each
passed individually — `nullable` + `required` together at one level deep, and
plain four-level nesting without that combination — but the exact combination
of both at that depth was never itself tested before the full schema failed,
which makes it the leading suspect. The schema below drops `required` from
that nested object as the fix (Gemini still reliably fills in both fields when
it includes a project, guided by the prompt text, without a hard schema
constraint forcing it).

**This fix is not yet re-confirmed live** — the API's free-tier quota was
exhausted by the bisection testing itself before a clean re-run could happen.
Whoever executes Task 5's live smoke test is the one actually proving this;
if it still 400s, bisect further from here rather than assuming this was the
only issue.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_roadmap_prompts.py`:

```python
from types import SimpleNamespace

from ai.prompts.roadmap import build_roadmap_prompt


def test_beginner_prompt_assumes_zero_knowledge():
    prompt = build_roadmap_prompt("Python", "beginner")

    assert "zero prior knowledge" in prompt.user_content.lower()


def test_advanced_prompt_includes_strengths_weaknesses_and_skips_fundamentals():
    assessment = SimpleNamespace(strengths=["loops"], weaknesses=["oop"])

    prompt = build_roadmap_prompt("Python", "advanced", assessment)

    assert "skip fundamentals" in prompt.user_content.lower()
    assert "loops" in prompt.user_content
    assert "oop" in prompt.user_content
    assert "interview" in prompt.user_content.lower()


def test_intermediate_prompt_weights_toward_weaknesses():
    assessment = SimpleNamespace(strengths=["loops"], weaknesses=["oop"])

    prompt = build_roadmap_prompt("Python", "intermediate", assessment)

    assert "loops" in prompt.user_content
    assert "oop" in prompt.user_content


def test_schema_requires_phases_last_and_bounds_phase_count():
    prompt = build_roadmap_prompt("Python", "beginner")

    keys = list(prompt.response_schema["properties"].keys())
    assert keys[-1] == "phases"
    phases_schema = prompt.response_schema["properties"]["phases"]
    assert phases_schema["min_items"] == 4
    assert phases_schema["max_items"] == 10


def test_module_schema_includes_kind_enum():
    prompt = build_roadmap_prompt("Python", "beginner")

    module_schema = prompt.response_schema["properties"]["phases"]["items"]["properties"]["modules"]["items"]
    assert set(module_schema["properties"]["kind"]["enum"]) == {
        "module",
        "checkpoint",
        "milestone",
        "project",
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_roadmap_prompts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai.prompts.roadmap'`

- [ ] **Step 3: Write `backend/ai/prompts/roadmap.py`**

```python
from __future__ import annotations

from typing import Protocol

from ai.client import Prompt


class _HasStrengthsWeaknesses(Protocol):
    strengths: list[str]
    weaknesses: list[str]


_MODULE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING"},
        "description": {"type": "STRING"},
        "lessons": {"type": "ARRAY", "items": {"type": "STRING"}},
        "exercises": {"type": "ARRAY", "items": {"type": "STRING"}},
        "project": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING"},
                "description": {"type": "STRING"},
            },
            "nullable": True,
        },
        "estimated_hours": {"type": "INTEGER"},
        "kind": {"type": "STRING", "enum": ["module", "checkpoint", "milestone", "project"]},
    },
    "required": ["title", "description", "lessons", "exercises", "estimated_hours", "kind"],
}

_PHASE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING"},
        "description": {"type": "STRING"},
        "goal": {"type": "STRING"},
        "estimated_hours": {"type": "INTEGER"},
        "modules": {"type": "ARRAY", "min_items": 2, "max_items": 8, "items": _MODULE_SCHEMA},
    },
    "required": ["title", "goal", "modules"],
}

_ROADMAP_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING"},
        "summary": {"type": "STRING"},
        "total_weeks": {"type": "INTEGER"},
        "weekly_hours": {"type": "INTEGER"},
        "weekly_goals": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "week": {"type": "INTEGER"},
                    "goal": {"type": "STRING"},
                    "phase_order": {"type": "INTEGER"},
                },
                "required": ["week", "goal", "phase_order"],
            },
        },
        "final_project": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING"},
                "description": {"type": "STRING"},
                "skills_demonstrated": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["title", "description", "skills_demonstrated"],
        },
        # Last on purpose: Gemini reliably follows schema property order, and
        # this lets the SSE parser emit `meta` with complete data before the
        # first phase arrives. Verified against a live streaming call before
        # this schema was written — see this plan's header.
        "phases": {"type": "ARRAY", "min_items": 4, "max_items": 10, "items": _PHASE_SCHEMA},
    },
    "required": [
        "title",
        "summary",
        "total_weeks",
        "weekly_hours",
        "weekly_goals",
        "final_project",
        "phases",
    ],
}

_SYSTEM = (
    "You are a curriculum designer for CareerOS, an AI career mentor. Output "
    "only valid JSON matching the schema. Every phase needs 2-8 modules; every "
    "module needs lessons, exercises, an estimated_hours, and a kind. Include "
    "at least one checkpoint and one milestone somewhere in the roadmap."
)


def build_roadmap_prompt(
    topic: str, level: str, assessment: _HasStrengthsWeaknesses | None = None
) -> Prompt:
    if level == "beginner":
        guidance = (
            "Assume zero prior knowledge. Start from absolute fundamentals and "
            "build up gradually. Include a gentle on-ramp phase before anything else."
        )
    else:
        strengths = ", ".join(assessment.strengths) if assessment and assessment.strengths else "none identified"
        weaknesses = (
            ", ".join(assessment.weaknesses) if assessment and assessment.weaknesses else "none identified"
        )
        if level == "advanced":
            guidance = (
                "This is a revision roadmap — skip fundamentals entirely. The "
                f"learner's assessed strengths are: {strengths}. Their weaknesses "
                f"are: {weaknesses}. Weight phases and modules toward the "
                "weaknesses, include advanced projects, and end with "
                "interview-focused revision for this topic."
            )
        else:
            guidance = (
                "Build the roadmap from the learner's actual assessed level, not "
                f"from scratch. Their strengths are: {strengths} — cover these "
                f"lightly as review. Their weaknesses are: {weaknesses} — give "
                "these real depth and practice."
            )

    user_content = (
        f"Topic: {topic}\n"
        f"Declared/assessed level: {level}\n"
        f"{guidance}\n\n"
        "Design a complete, personalized learning roadmap:\n"
        "- 4-10 learning phases, each with a clear goal and 2-8 modules\n"
        "- weekly_goals spanning total_weeks, each tagged with its phase_order\n"
        "- final_project: one capstone spanning skills from multiple phases, "
        "distinct from any single module's mini project"
    )

    return Prompt(
        system_instruction=_SYSTEM,
        user_content=user_content,
        response_schema=_ROADMAP_SCHEMA,
        temperature=0.7,
        max_output_tokens=8192,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_roadmap_prompts.py -v`
Expected: PASS — `5 passed`

- [ ] **Step 5: Live smoke test against the real API**

```bash
cd backend && .venv/bin/python -c "
from ai.client import get_ai_client
from ai.prompts.roadmap import build_roadmap_prompt
from ai.stream_parser import PhaseStreamParser

client = get_ai_client()
prompt = build_roadmap_prompt('Python', 'beginner')

parser = PhaseStreamParser()
events = []
for chunk in client.generate_json_stream(prompt):
    events.extend(parser.feed(chunk))

kinds = [e for e, _ in events]
print('event sequence:', kinds)
meta = next(d for e, d in events if e == 'meta')
print('title:', meta['title'])
print('total_weeks:', meta['total_weeks'])
print('phase count:', kinds.count('phase'))
"
```

Expected: `event sequence` starts with `meta` followed by 4-10 `phase` entries, a
real title, a real `total_weeks`, and a phase count matching. This won't
actually pass yet — `generate_json_stream` doesn't exist on `AIClient` until
Task 5. Come back to this once Task 5 is done; it's the same "verify against
the real API before trusting the design" step this plan's own header describes,
now applied end-to-end through the real parser.

- [ ] **Step 6: Commit**

```bash
git add backend/ai/prompts/roadmap.py backend/tests/test_roadmap_prompts.py
git commit -m "feat(backend): add roadmap generation prompt with level-aware guidance"
```

---

## Task 5: Streaming support on the AI client

**Files:**
- Modify: `backend/ai/client.py`, `backend/ai/gemini_client.py`, `backend/tests/test_ai_client.py`

`generate_json_stream` joins `generate_json` on the `AIClient` Protocol. `FakeAIClient`
gets a parallel `queue_stream`/`stream_calls` pair so streaming and non-streaming
calls in the same test never get confused with each other.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_ai_client.py`:

```python
def test_fake_client_streams_queued_chunks_in_order():
    client = FakeAIClient()
    client.queue_stream(['{"a":', " 1}"])

    chunks = list(client.generate_json_stream(_prompt()))

    assert chunks == ['{"a":', " 1}"]


def test_fake_client_records_stream_calls_separately_from_json_calls():
    client = FakeAIClient()
    client.queue_response({"a": 1})
    client.queue_stream(["chunk"])

    client.generate_json(_prompt("json call"))
    list(client.generate_json_stream(_prompt("stream call")))

    assert len(client.calls) == 1
    assert client.calls[0].user_content == "json call"
    assert len(client.stream_calls) == 1
    assert client.stream_calls[0].user_content == "stream call"


def test_fake_client_raises_when_stream_queue_is_empty():
    client = FakeAIClient()

    with pytest.raises(AssertionError):
        list(client.generate_json_stream(_prompt()))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_ai_client.py -v`
Expected: FAIL — `AttributeError: 'FakeAIClient' object has no attribute 'queue_stream'`

- [ ] **Step 3: Extend `backend/ai/client.py`**

Replace the whole file:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Protocol


@dataclass(frozen=True)
class Prompt:
    system_instruction: str
    user_content: str
    response_schema: dict[str, Any]
    temperature: float = 0.4
    max_output_tokens: int = 4096


class AIClient(Protocol):
    def generate_json(self, prompt: Prompt) -> dict[str, Any]: ...
    def generate_json_stream(self, prompt: Prompt) -> Iterator[str]: ...


class FakeAIClient:
    """Test double. Queue non-streaming responses with queue_response() and
    streaming ones with queue_stream(); each call pops the next one, in
    order, for its own method. Raises AssertionError if the relevant queue
    runs dry, so an under-specified test fails loudly instead of hanging.
    """

    def __init__(self) -> None:
        self._queue: list[dict[str, Any]] = []
        self._stream_queue: list[list[str]] = []
        self.calls: list[Prompt] = []
        self.stream_calls: list[Prompt] = []

    def queue_response(self, response: dict[str, Any]) -> None:
        self._queue.append(response)

    def queue_stream(self, chunks: list[str]) -> None:
        self._stream_queue.append(chunks)

    def generate_json(self, prompt: Prompt) -> dict[str, Any]:
        self.calls.append(prompt)
        if not self._queue:
            raise AssertionError("FakeAIClient: no queued response left")
        return self._queue.pop(0)

    def generate_json_stream(self, prompt: Prompt) -> Iterator[str]:
        self.stream_calls.append(prompt)
        if not self._stream_queue:
            raise AssertionError("FakeAIClient: no queued stream left")
        return iter(self._stream_queue.pop(0))


_client: AIClient | None = None


def get_ai_client() -> AIClient:
    """FastAPI dependency. Lazily constructs a singleton GeminiClient.

    The import is local (not at module top) because gemini_client.py imports
    Prompt and AIClient from this module — a top-level import here would be
    circular.
    """
    global _client
    if _client is None:
        from ai.gemini_client import GeminiClient

        _client = GeminiClient()
    return _client
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_ai_client.py -v`
Expected: PASS — `6 passed`

- [ ] **Step 5: Add `generate_json_stream` to `backend/ai/gemini_client.py`**

Append to the end of the `GeminiClient` class (same indentation as `generate_json`):

```python
    def generate_json_stream(self, prompt: Prompt) -> Iterator[str]:
        def call():
            return self._client.models.generate_content_stream(
                model=settings.GEMINI_MODEL,
                contents=prompt.user_content,
                config=types.GenerateContentConfig(
                    system_instruction=prompt.system_instruction,
                    response_mime_type="application/json",
                    response_schema=prompt.response_schema,
                    temperature=prompt.temperature,
                    max_output_tokens=prompt.max_output_tokens,
                    # Thinking stays enabled here, unlike generate_json — the
                    # spec calls for it on roadmap generation specifically,
                    # since it's a much harder generation task than a single
                    # assessment-grading extraction.
                ),
            )

        try:
            stream = call_with_retries(call, is_retryable=_is_retryable)
            for chunk in stream:
                if chunk.text:
                    yield chunk.text
        except errors.APIError as exc:
            log.warning("Gemini streaming error: %s", exc)
            raise AIUnavailable(str(exc)) from exc
```

Add `Iterator` to the existing `from typing import ...` import if it isn't already
there (it wasn't needed in this file before this task).

- [ ] **Step 6: Live smoke test (retry Task 4's Step 5 now that the method exists)**

```bash
cd backend && .venv/bin/python -c "
from ai.client import get_ai_client
from ai.prompts.roadmap import build_roadmap_prompt
from ai.stream_parser import PhaseStreamParser

client = get_ai_client()
prompt = build_roadmap_prompt('Python', 'beginner')

parser = PhaseStreamParser()
events = []
for chunk in client.generate_json_stream(prompt):
    events.extend(parser.feed(chunk))

kinds = [e for e, _ in events]
print('event sequence:', kinds)
meta = next(d for e, d in events if e == 'meta')
print('title:', meta['title'])
print('total_weeks:', meta['total_weeks'])
print('phase count:', kinds.count('phase'))
first_phase = next(d for e, d in events if e == 'phase')
print('first phase modules:', len(first_phase['modules']))
"
```

Expected: a real title, a real `total_weeks`, `phase count` between 4 and 10, and
a non-empty module list for the first phase — proving the full chain (prompt →
streaming client → parser) works against the live API before it's wired into a
route.

**Status: attempted twice on 2026-08-08, both `429 RESOURCE_EXHAUSTED`.** The
violation detail is `GenerateRequestsPerDayPerProjectPerModel-FreeTier`,
`quotaValue: 20` — a genuine per-day cap, not a short rate window, so the
`retryDelay` the API suggests (~30-60s) is misleading for this specific
exhaustion; retrying inside that window fails again with the same code, only
the countdown changes. Confirmed by waiting out one full suggested delay and
retrying once for real, which still 429'd. **Do not loop-retry this** — it
won't succeed until the daily quota window resets (unknown exact time; likely
midnight in whatever timezone Google's free-tier meter uses). Whoever has
quota available next is the one who actually discharges this step and Task
4's schema-fix caveat together in one run.

- [ ] **Step 7: Commit**

```bash
git add backend/ai/client.py backend/ai/gemini_client.py backend/tests/test_ai_client.py
git commit -m "feat(backend): add streaming support to the AI client"
```

---

## Task 6: Roadmap service — stream orchestration

**Files:**
- Create: `backend/services/roadmap_service.py`
- Modify: `backend/services/assessment_service.py` (add `get_latest_completed_assessment`)
- Test: `backend/tests/test_roadmap_service.py`
- Modify: `backend/tests/test_assessment_service.py` (2 tests for the new lookup)

`stream_roadmap` is the generator the router will iterate to produce SSE.
Entirely testable against `FakeAIClient.queue_stream` — no live API needed,
which matters right now since Task 5's live check is blocked on quota. It
persists `Roadmap`/`RoadmapPhase`/`RoadmapModule` rows via `db.add()` +
`db.flush()` as each event arrives (assigning ids for FKs without committing),
then commits exactly once at the end — or rolls back the whole thing if the
stream fails, comes back with zero phases, or a phase somehow arrives before
the roadmap's own meta record (unreachable given the schema, per Task 4's
note that `phases` is always last, but guarded rather than left to crash).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_roadmap_service.py`:

```python
from datetime import datetime

from ai.errors import AIUnavailable
from models.assessment import Assessment
from models.roadmap import Roadmap
from schemas.profile import ProfileCreate, TrackCreate
from services import profile_service
from services.roadmap_service import stream_roadmap

_HAPPY_CHUNKS = [
    '{"title": "Python Roadmap", "summary": "From zero to functional scripts.", ',
    '"total_weeks": 4, "weekly_hours": 5, ',
    '"weekly_goals": [{"week": 1, "goal": "Learn syntax", "phase_order": 0}], ',
    '"final_project": {"title": "CLI Tool", "description": "Build a CLI", "skills_demonstrated": ["cli"]}, ',
    '"phases": [',
    '{"title": "Foundations", "description": "The basics.", "goal": "Write simple scripts.", '
    '"estimated_hours": 10, "modules": [',
    '{"title": "Variables", "description": "Learn variables.", "lessons": ["l1"], "exercises": ["e1"], ',
    '"project": null, "estimated_hours": 3, "kind": "module"}',
    ']}',
    ']}',
]


def _track(db_session, level="beginner"):
    profile_service.create_profile(db_session, ProfileCreate(name="Aryan"))
    return profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level=level)
    )


def _raising_stream(chunks, exc):
    yield from chunks
    raise exc


def test_stream_roadmap_persists_meta_and_phases_and_yields_matching_events(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_stream(_HAPPY_CHUNKS)

    events = list(stream_roadmap(db_session, fake_ai, track.id))

    assert [e for e, _ in events] == ["meta", "phase", "done"]
    roadmap = db_session.query(Roadmap).filter_by(track_id=track.id).one()
    assert roadmap.title == "Python Roadmap"
    assert roadmap.assessment_id is None
    assert len(roadmap.phases) == 1
    assert roadmap.phases[0].title == "Foundations"
    assert len(roadmap.phases[0].modules) == 1
    assert roadmap.phases[0].modules[0].title == "Variables"
    assert roadmap.phases[0].modules[0].kind == "module"
    _, done_data = events[2]
    assert done_data["roadmap_id"] == roadmap.id


def test_stream_roadmap_beginner_path_skips_assessment_lookup(db_session, fake_ai):
    track = _track(db_session, level="beginner")
    fake_ai.queue_stream(_HAPPY_CHUNKS)

    list(stream_roadmap(db_session, fake_ai, track.id))

    assert "zero prior knowledge" in fake_ai.stream_calls[0].user_content.lower()


def test_stream_roadmap_intermediate_path_uses_latest_completed_assessment(db_session, fake_ai):
    track = _track(db_session, level="intermediate")
    assessment = Assessment(
        track_id=track.id,
        level="intermediate",
        status="completed",
        completed_at=datetime(2026, 1, 1),
        strengths=["loops"],
        weaknesses=["oop"],
    )
    db_session.add(assessment)
    db_session.commit()
    fake_ai.queue_stream(_HAPPY_CHUNKS)

    list(stream_roadmap(db_session, fake_ai, track.id))

    assert "loops" in fake_ai.stream_calls[0].user_content
    assert "oop" in fake_ai.stream_calls[0].user_content
    roadmap = db_session.query(Roadmap).filter_by(track_id=track.id).one()
    assert roadmap.assessment_id == assessment.id


def test_stream_roadmap_unknown_track_yields_error_and_makes_no_ai_call(db_session, fake_ai):
    events = list(stream_roadmap(db_session, fake_ai, 999))

    assert len(events) == 1
    event, data = events[0]
    assert event == "error"
    assert data["code"] == "track_not_found"
    assert fake_ai.stream_calls == []


def test_stream_roadmap_rejects_stream_with_no_phases_and_rolls_back(db_session, fake_ai):
    track = _track(db_session)
    no_phase_chunks = [
        '{"title": "T", "summary": "S", "total_weeks": 1, "weekly_hours": 1, ',
        '"weekly_goals": [], "final_project": {"title": "F", "description": "D", "skills_demonstrated": []}, ',
        '"phases": []}',
    ]
    fake_ai.queue_stream(no_phase_chunks)

    events = list(stream_roadmap(db_session, fake_ai, track.id))

    assert [e for e, _ in events] == ["meta", "error"]
    assert events[1][1]["code"] == "ai_invalid_response"
    assert db_session.query(Roadmap).filter_by(track_id=track.id).count() == 0


def test_stream_roadmap_rolls_back_everything_on_mid_stream_ai_failure(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_stream(_raising_stream(_HAPPY_CHUNKS[:9], AIUnavailable("boom")))

    events = list(stream_roadmap(db_session, fake_ai, track.id))

    assert [e for e, _ in events] == ["meta", "phase", "error"]
    assert events[2][1]["code"] == "ai_unavailable"
    assert db_session.query(Roadmap).filter_by(track_id=track.id).count() == 0
```

Append to `backend/tests/test_assessment_service.py`:

```python
def test_get_latest_completed_assessment_returns_most_recent(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(8))
    older = assessment_service.start_assessment(db_session, fake_ai, track.id)
    older.status = "completed"
    older.completed_at = None
    db_session.commit()

    fake_ai.queue_response(_generation_response(8))
    newer = assessment_service.start_assessment(db_session, fake_ai, track.id)
    newer.status = "completed"
    db_session.commit()

    latest = assessment_service.get_latest_completed_assessment(db_session, track.id)

    assert latest.id == newer.id


def test_get_latest_completed_assessment_ignores_in_progress_and_returns_none(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(8))
    assessment_service.start_assessment(db_session, fake_ai, track.id)  # stays in_progress

    latest = assessment_service.get_latest_completed_assessment(db_session, track.id)

    assert latest is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_roadmap_service.py tests/test_assessment_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.roadmap_service'`

- [ ] **Step 3: Add `get_latest_completed_assessment` to `backend/services/assessment_service.py`**

Add near `list_assessments`:

```python
def get_latest_completed_assessment(db: Session, track_id: int) -> Assessment | None:
    return db.scalars(
        select(Assessment)
        .where(Assessment.track_id == track_id, Assessment.status == "completed")
        .order_by(Assessment.started_at.desc(), Assessment.id.desc())
    ).first()
```

- [ ] **Step 4: Write `backend/services/roadmap_service.py`**

```python
from __future__ import annotations

from typing import Iterator

from sqlalchemy.orm import Session

from ai.client import AIClient
from ai.errors import AIInvalidResponse, AIUnavailable
from ai.prompts.roadmap import build_roadmap_prompt
from ai.stream_parser import PhaseStreamParser
from models.roadmap import Roadmap, RoadmapModule, RoadmapPhase
from services import assessment_service, profile_service
from services.profile_service import TrackNotFoundError

StreamEvent = tuple[str, dict]


def stream_roadmap(db: Session, ai_client: AIClient, track_id: int) -> Iterator[StreamEvent]:
    """Drives PhaseStreamParser over a live Gemini stream, persisting
    Roadmap/RoadmapPhase/RoadmapModule rows as events arrive inside one
    uncommitted transaction. Commits once, only if at least one phase
    actually arrived; rolls back on any AI failure or an empty result.
    Yields SSE-ready (event, data) tuples — the router owns HTTP framing.
    """
    try:
        track = profile_service.get_track(db, track_id)
    except TrackNotFoundError:
        yield ("error", {"code": "track_not_found", "message": "That learning track does not exist."})
        return

    assessment = None
    if track.experience_level != "beginner":
        assessment = assessment_service.get_latest_completed_assessment(db, track.id)

    prompt = build_roadmap_prompt(track.topic, track.experience_level, assessment)
    parser = PhaseStreamParser()
    roadmap: Roadmap | None = None
    phase_count = 0

    try:
        for chunk in ai_client.generate_json_stream(prompt):
            for event, data in parser.feed(chunk):
                if event == "meta":
                    roadmap = Roadmap(
                        track_id=track.id,
                        assessment_id=assessment.id if assessment else None,
                        title=data["title"],
                        summary=data["summary"],
                        total_weeks=data["total_weeks"],
                        weekly_hours=data["weekly_hours"],
                        weekly_goals=data.get("weekly_goals", []),
                        final_project=data.get("final_project"),
                    )
                    db.add(roadmap)
                    db.flush()
                    yield ("meta", data)
                elif event == "phase":
                    if roadmap is None:
                        db.rollback()
                        yield (
                            "error",
                            {
                                "code": "ai_invalid_response",
                                "message": "Phase arrived before roadmap metadata.",
                            },
                        )
                        return
                    phase = RoadmapPhase(
                        roadmap_id=roadmap.id,
                        order_index=phase_count,
                        title=data["title"],
                        description=data.get("description", ""),
                        goal=data["goal"],
                        estimated_hours=data.get("estimated_hours", 0),
                    )
                    db.add(phase)
                    db.flush()
                    for m_index, module in enumerate(data.get("modules", [])):
                        db.add(
                            RoadmapModule(
                                phase_id=phase.id,
                                order_index=m_index,
                                title=module["title"],
                                description=module.get("description", ""),
                                lessons=module.get("lessons", []),
                                exercises=module.get("exercises", []),
                                project=module.get("project"),
                                estimated_hours=module.get("estimated_hours", 0),
                                kind=module.get("kind", "module"),
                            )
                        )
                    phase_count += 1
                    yield (
                        "phase",
                        {
                            "order_index": phase.order_index,
                            "title": phase.title,
                            "modules": data.get("modules", []),
                        },
                    )
    except AIUnavailable as exc:
        db.rollback()
        yield ("error", {"code": "ai_unavailable", "message": str(exc)})
        return
    except AIInvalidResponse as exc:
        db.rollback()
        yield ("error", {"code": "ai_invalid_response", "message": str(exc)})
        return

    if roadmap is None or phase_count == 0:
        db.rollback()
        yield ("error", {"code": "ai_invalid_response", "message": "No phases were generated."})
        return

    db.commit()
    yield ("done", {"roadmap_id": roadmap.id})
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_roadmap_service.py tests/test_assessment_service.py -v`
Expected: PASS — `6 passed` (roadmap_service) and `2 passed` (assessment_service additions)

- [ ] **Step 6: Run the full backend suite**

Run: `cd backend && .venv/bin/pytest -v`
Expected: PASS — `104 passed` (96 before this task + 6 + 2)

- [ ] **Step 7: Commit**

```bash
git add backend/services/roadmap_service.py backend/services/assessment_service.py backend/tests/test_roadmap_service.py backend/tests/test_assessment_service.py
git commit -m "feat(backend): add roadmap service with streaming persistence and rollback"
```

---

## Task 7: Roadmap schemas and router

**Files:**
- Create: `backend/schemas/roadmap.py`
- Modify: `backend/services/roadmap_service.py` (read/toggle functions + output builders)
- Create: `backend/routers/roadmap.py`
- Modify: `backend/main.py` (model import + router wiring)
- Modify: `backend/tests/conftest.py` (defensive `models.roadmap` import, matching the existing pattern for `models.assessment`/`models.user` — needed so `Base.metadata.create_all` sees the roadmap tables even if a test file is run in isolation from ones that happen to import `models.roadmap` first)
- Test: `backend/tests/test_roadmap_api.py`

Output builders follow the same explicit, field-by-field pattern as
`assessment_service.to_assessment_out` — no bare `model_validate(orm_obj)`
relied on for nested shapes, so there is one obvious place that decides what
a client sees.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_roadmap_api.py`:

```python
import json

_HAPPY_CHUNKS = [
    '{"title": "Python Roadmap", "summary": "From zero to functional scripts.", ',
    '"total_weeks": 4, "weekly_hours": 5, ',
    '"weekly_goals": [{"week": 1, "goal": "Learn syntax", "phase_order": 0}], ',
    '"final_project": {"title": "CLI Tool", "description": "Build a CLI", "skills_demonstrated": ["cli"]}, ',
    '"phases": [',
    '{"title": "Foundations", "description": "The basics.", "goal": "Write simple scripts.", '
    '"estimated_hours": 10, "modules": [',
    '{"title": "Variables", "description": "Learn variables.", "lessons": ["l1"], "exercises": ["e1"], ',
    '"project": null, "estimated_hours": 3, "kind": "module"}',
    ']}',
    ']}',
]


def _onboard_and_track(client, level="beginner"):
    client.post("/api/profile", json={"name": "Aryan"})
    track = client.post(
        "/api/tracks", json={"topic": "Python", "experience_level": level}
    )
    return track.json()["id"]


def _parse_sse(text):
    events = []
    for block in text.strip().split("\n\n"):
        if not block:
            continue
        lines = block.splitlines()
        event = next(l.split(": ", 1)[1] for l in lines if l.startswith("event: "))
        data = next(l.split(": ", 1)[1] for l in lines if l.startswith("data: "))
        events.append((event, json.loads(data)))
    return events


def test_generate_roadmap_streams_meta_phase_and_done(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_stream(_HAPPY_CHUNKS)

    response = client.post(f"/api/tracks/{track_id}/roadmap/stream")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(response.text)
    assert [e for e, _ in events] == ["meta", "phase", "done"]
    assert events[0][1]["title"] == "Python Roadmap"


def test_generate_roadmap_unknown_track_streams_error_event(client, fake_ai):
    response = client.post("/api/tracks/999/roadmap/stream")

    events = _parse_sse(response.text)
    assert events == [("error", {"code": "track_not_found", "message": "That learning track does not exist."})]
    assert fake_ai.stream_calls == []


def test_get_roadmap_returns_full_shape_with_progress(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_stream(_HAPPY_CHUNKS)
    client.post(f"/api/tracks/{track_id}/roadmap/stream")

    response = client.get(f"/api/tracks/{track_id}/roadmap")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Python Roadmap"
    assert len(body["phases"]) == 1
    assert len(body["phases"][0]["modules"]) == 1
    assert body["phases"][0]["modules"][0]["title"] == "Variables"
    assert body["progress"]["total_modules"] == 1
    assert body["progress"]["completed_modules"] == 0


def test_get_roadmap_before_generation_returns_404(client):
    track_id = _onboard_and_track(client)

    response = client.get(f"/api/tracks/{track_id}/roadmap")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "roadmap_not_found"


def test_patch_module_toggles_completion_both_ways(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_stream(_HAPPY_CHUNKS)
    client.post(f"/api/tracks/{track_id}/roadmap/stream")
    module_id = client.get(f"/api/tracks/{track_id}/roadmap").json()["phases"][0]["modules"][0]["id"]

    completed = client.patch(f"/api/modules/{module_id}", json={"completed": True})
    assert completed.status_code == 200
    completed_body = completed.json()
    assert completed_body["module"]["completed_at"] is not None
    assert completed_body["progress"]["completed_modules"] == 1
    assert completed_body["progress"]["completion_pct"] == 100.0

    uncompleted = client.patch(f"/api/modules/{module_id}", json={"completed": False})
    uncompleted_body = uncompleted.json()
    assert uncompleted_body["module"]["completed_at"] is None
    assert uncompleted_body["progress"]["completed_modules"] == 0


def test_patch_module_unknown_returns_404(client):
    response = client.patch("/api/modules/999", json={"completed": True})

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "module_not_found"


def test_get_progress_before_roadmap_returns_404(client):
    track_id = _onboard_and_track(client)

    response = client.get(f"/api/tracks/{track_id}/progress")

    assert response.status_code == 404


def test_get_progress_matches_roadmap_progress(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_stream(_HAPPY_CHUNKS)
    client.post(f"/api/tracks/{track_id}/roadmap/stream")

    response = client.get(f"/api/tracks/{track_id}/progress")

    assert response.status_code == 200
    assert response.json()["total_modules"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_roadmap_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'schemas.roadmap'`

- [ ] **Step 3: Write `backend/schemas/roadmap.py`**

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RoadmapModuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_index: int
    title: str
    description: str
    lessons: list[str]
    exercises: list[str]
    project: dict | None
    estimated_hours: int
    kind: str
    started_at: datetime | None
    completed_at: datetime | None


class RoadmapPhaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_index: int
    title: str
    description: str
    goal: str
    estimated_hours: int
    modules: list[RoadmapModuleOut]


class PhaseProgressOut(BaseModel):
    order_index: int
    completion_pct: float
    unlocked: bool


class ProgressOut(BaseModel):
    completion_pct: float
    completed_modules: int
    total_modules: int
    current_phase_index: int
    current_phase_title: str | None
    phases: list[PhaseProgressOut]


class RoadmapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    track_id: int
    title: str
    summary: str
    total_weeks: int
    weekly_hours: int
    weekly_goals: list[dict]
    final_project: dict | None
    created_at: datetime
    phases: list[RoadmapPhaseOut]
    progress: ProgressOut


class ModuleToggle(BaseModel):
    completed: bool


class ModuleToggleOut(BaseModel):
    module: RoadmapModuleOut
    progress: ProgressOut
```

- [ ] **Step 4: Add read/toggle functions and output builders to `backend/services/roadmap_service.py`**

Add `from datetime import UTC, datetime` and `from sqlalchemy import select` to the
imports, add `from schemas.roadmap import (ModuleToggleOut, ProgressOut, RoadmapModuleOut, RoadmapOut, RoadmapPhaseOut)`
and `from services.progress_service import build_progress`, then append:

```python
class RoadmapNotFoundError(Exception):
    pass


class ModuleNotFoundError(Exception):
    pass


def get_roadmap_by_track(db: Session, track_id: int) -> Roadmap:
    roadmap = db.scalars(
        select(Roadmap)
        .where(Roadmap.track_id == track_id)
        .order_by(Roadmap.created_at.desc(), Roadmap.id.desc())
    ).first()
    if roadmap is None:
        raise RoadmapNotFoundError
    return roadmap


def get_module(db: Session, module_id: int) -> RoadmapModule:
    module = db.get(RoadmapModule, module_id)
    if module is None:
        raise ModuleNotFoundError
    return module


def toggle_module(db: Session, module_id: int, completed: bool) -> RoadmapModule:
    module = get_module(db, module_id)
    if completed:
        if module.completed_at is None:
            now = datetime.now(UTC).replace(tzinfo=None)
            module.completed_at = now
            if module.started_at is None:
                module.started_at = now
    else:
        # started_at is left alone on purpose — un-completing shouldn't erase
        # that the learner did start it at some point.
        module.completed_at = None
    db.commit()
    db.refresh(module)
    return module


def to_module_out(module: RoadmapModule) -> RoadmapModuleOut:
    return RoadmapModuleOut(
        id=module.id,
        order_index=module.order_index,
        title=module.title,
        description=module.description,
        lessons=module.lessons,
        exercises=module.exercises,
        project=module.project,
        estimated_hours=module.estimated_hours,
        kind=module.kind,
        started_at=module.started_at,
        completed_at=module.completed_at,
    )


def to_phase_out(phase: RoadmapPhase) -> RoadmapPhaseOut:
    return RoadmapPhaseOut(
        id=phase.id,
        order_index=phase.order_index,
        title=phase.title,
        description=phase.description,
        goal=phase.goal,
        estimated_hours=phase.estimated_hours,
        modules=[to_module_out(m) for m in phase.modules],
    )


def to_roadmap_out(roadmap: Roadmap) -> RoadmapOut:
    return RoadmapOut(
        id=roadmap.id,
        track_id=roadmap.track_id,
        title=roadmap.title,
        summary=roadmap.summary,
        total_weeks=roadmap.total_weeks,
        weekly_hours=roadmap.weekly_hours,
        weekly_goals=roadmap.weekly_goals,
        final_project=roadmap.final_project,
        created_at=roadmap.created_at,
        phases=[to_phase_out(p) for p in roadmap.phases],
        progress=ProgressOut(**build_progress(roadmap.phases)),
    )


def to_module_toggle_out(module: RoadmapModule) -> ModuleToggleOut:
    progress = build_progress(module.phase.roadmap.phases)
    return ModuleToggleOut(module=to_module_out(module), progress=ProgressOut(**progress))
```

- [ ] **Step 5: Write `backend/routers/roadmap.py`**

```python
import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ai.client import AIClient, get_ai_client
from db.session import get_db
from schemas.roadmap import ModuleToggle, ModuleToggleOut, ProgressOut, RoadmapOut
from services import roadmap_service
from services.progress_service import build_progress
from services.roadmap_service import ModuleNotFoundError, RoadmapNotFoundError

router = APIRouter(tags=["roadmap"])

_ROADMAP_MISSING = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "roadmap_not_found", "message": "No roadmap exists for that track yet."},
)
_MODULE_MISSING = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "module_not_found", "message": "That module does not exist."},
)


def _format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/api/tracks/{track_id}/roadmap/stream")
def generate_roadmap(
    track_id: int,
    db: Session = Depends(get_db),
    ai_client: AIClient = Depends(get_ai_client),
):
    def event_stream():
        for event, data in roadmap_service.stream_roadmap(db, ai_client, track_id):
            yield _format_sse(event, data)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/api/tracks/{track_id}/roadmap", response_model=RoadmapOut)
def get_roadmap(track_id: int, db: Session = Depends(get_db)):
    try:
        roadmap = roadmap_service.get_roadmap_by_track(db, track_id)
    except RoadmapNotFoundError:
        raise _ROADMAP_MISSING
    return roadmap_service.to_roadmap_out(roadmap)


@router.patch("/api/modules/{module_id}", response_model=ModuleToggleOut)
def patch_module(module_id: int, payload: ModuleToggle, db: Session = Depends(get_db)):
    try:
        module = roadmap_service.toggle_module(db, module_id, payload.completed)
    except ModuleNotFoundError:
        raise _MODULE_MISSING
    return roadmap_service.to_module_toggle_out(module)


@router.get("/api/tracks/{track_id}/progress", response_model=ProgressOut)
def get_progress(track_id: int, db: Session = Depends(get_db)):
    try:
        roadmap = roadmap_service.get_roadmap_by_track(db, track_id)
    except RoadmapNotFoundError:
        raise _ROADMAP_MISSING
    return ProgressOut(**build_progress(roadmap.phases))
```

- [ ] **Step 6: Wire `backend/main.py`**

Add `from models import roadmap as _roadmap_models  # noqa: F401` next to the
other model imports, add `roadmap` to the `from routers import ...` line, and
add `app.include_router(roadmap.router)` next to the other `include_router` calls.

- [ ] **Step 7: Add the defensive model import to `backend/tests/conftest.py`**

Add next to the existing `models.assessment`/`models.user` imports:

```python
from models import roadmap as _roadmap_models  # noqa: E402,F401
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_roadmap_api.py -v`
Expected: PASS — `8 passed`

- [ ] **Step 9: Run the full backend suite**

Run: `cd backend && .venv/bin/pytest -v`
Expected: PASS — `112 passed` (104 before this task + 8)

- [ ] **Step 10: Commit**

```bash
git add backend/schemas/roadmap.py backend/services/roadmap_service.py backend/routers/roadmap.py backend/main.py backend/tests/conftest.py backend/tests/test_roadmap_api.py
git commit -m "feat(backend): add roadmap schemas, router, and progress/toggle endpoints"
```

---

## Task 8: Dashboard aggregate

**Files:**
- Create: `backend/schemas/dashboard.py`
- Create: `backend/services/dashboard_service.py`
- Create: `backend/routers/dashboard.py`
- Modify: `backend/main.py` (router wiring — no new model, dashboard has no table)
- Test: `backend/tests/test_dashboard_api.py`

One read-only aggregate: profile, active track, roadmap summary, current
phase, module counts, next module to work on, recent interviews. Every piece
already exists (`profile_service`, `roadmap_service`, `progress_service`) —
this just composes them and degrades gracefully at each stage nothing exists
yet (no profile → no track → no roadmap), which is exactly the sequence a
brand-new install walks through. `recent_interviews` is always `[]` for
now — Plan 4 introduces the model that actually fills it in.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_dashboard_api.py`:

```python
_HAPPY_CHUNKS = [
    '{"title": "Python Roadmap", "summary": "From zero to functional scripts.", ',
    '"total_weeks": 4, "weekly_hours": 5, ',
    '"weekly_goals": [{"week": 1, "goal": "Learn syntax", "phase_order": 0}], ',
    '"final_project": {"title": "CLI Tool", "description": "Build a CLI", "skills_demonstrated": ["cli"]}, ',
    '"phases": [',
    '{"title": "Foundations", "description": "The basics.", "goal": "Write simple scripts.", '
    '"estimated_hours": 10, "modules": [',
    '{"title": "Variables", "description": "Learn variables.", "lessons": ["l1"], "exercises": ["e1"], ',
    '"project": null, "estimated_hours": 3, "kind": "module"}',
    ']}',
    ']}',
]


def test_dashboard_before_any_profile_returns_empty_shape(client):
    response = client.get("/api/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["profile"] is None
    assert body["active_track"] is None
    assert body["completed_modules"] == 0
    assert body["remaining_modules"] == 0
    assert body["completion_pct"] == 0.0
    assert body["next_module"] is None
    assert body["recent_interviews"] == []


def test_dashboard_with_profile_but_no_active_track_returns_partial_shape(client):
    client.post("/api/profile", json={"name": "Aryan"})

    response = client.get("/api/dashboard")

    body = response.json()
    assert body["profile"]["name"] == "Aryan"
    assert body["active_track"] is None
    assert body["roadmap_summary"] is None


def test_dashboard_with_track_but_no_roadmap_returns_partial_shape(client):
    client.post("/api/profile", json={"name": "Aryan"})
    client.post("/api/tracks", json={"topic": "Python", "experience_level": "beginner"})

    response = client.get("/api/dashboard")

    body = response.json()
    assert body["active_track"]["topic"] == "Python"
    assert body["roadmap_summary"] is None
    assert body["current_phase"] is None
    assert body["next_module"] is None


def test_dashboard_reflects_roadmap_progress_and_updates_after_module_completion(client, fake_ai):
    client.post("/api/profile", json={"name": "Aryan"})
    track_id = client.post(
        "/api/tracks", json={"topic": "Python", "experience_level": "beginner"}
    ).json()["id"]
    fake_ai.queue_stream(_HAPPY_CHUNKS)
    client.post(f"/api/tracks/{track_id}/roadmap/stream")

    before = client.get("/api/dashboard").json()
    assert before["roadmap_summary"] == "From zero to functional scripts."
    assert before["current_phase"] == "Foundations"
    assert before["completed_modules"] == 0
    assert before["remaining_modules"] == 1
    assert before["completion_pct"] == 0.0
    assert before["next_module"]["title"] == "Variables"
    assert before["next_module"]["kind"] == "module"

    module_id = before["next_module"]["id"]
    client.patch(f"/api/modules/{module_id}", json={"completed": True})

    after = client.get("/api/dashboard").json()
    assert after["completed_modules"] == 1
    assert after["remaining_modules"] == 0
    assert after["completion_pct"] == 100.0
    assert after["next_module"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_dashboard_api.py -v`
Expected: FAIL — `404` on `/api/dashboard` (route doesn't exist yet)

- [ ] **Step 3: Write `backend/schemas/dashboard.py`**

```python
from pydantic import BaseModel

from schemas.profile import ProfileOut, TrackOut


class NextModuleOut(BaseModel):
    id: int
    title: str
    kind: str
    phase_title: str


class DashboardOut(BaseModel):
    profile: ProfileOut | None
    active_track: TrackOut | None
    roadmap_summary: str | None
    current_phase: str | None
    completed_modules: int
    remaining_modules: int
    completion_pct: float
    next_module: NextModuleOut | None
    recent_interviews: list = []
```

- [ ] **Step 4: Write `backend/services/dashboard_service.py`**

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from schemas.dashboard import DashboardOut, NextModuleOut
from schemas.profile import ProfileOut, TrackOut
from services import profile_service, roadmap_service
from services.progress_service import current_phase_index, build_progress
from services.roadmap_service import RoadmapNotFoundError

_EMPTY = dict(
    roadmap_summary=None,
    current_phase=None,
    completed_modules=0,
    remaining_modules=0,
    completion_pct=0.0,
    next_module=None,
    recent_interviews=[],
)


def _find_next_module(phases) -> NextModuleOut | None:
    if not phases:
        return None
    phase = phases[current_phase_index(phases)]
    for module in phase.modules:
        if module.completed_at is None:
            return NextModuleOut(
                id=module.id, title=module.title, kind=module.kind, phase_title=phase.title
            )
    return None


def get_dashboard(db: Session) -> DashboardOut:
    user = profile_service.get_profile(db)
    if user is None:
        return DashboardOut(profile=None, active_track=None, **_EMPTY)

    profile_out = ProfileOut.model_validate(user)
    active_track = profile_service.get_active_track(db)
    if active_track is None:
        return DashboardOut(profile=profile_out, active_track=None, **_EMPTY)

    track_out = TrackOut.model_validate(active_track)
    try:
        roadmap = roadmap_service.get_roadmap_by_track(db, active_track.id)
    except RoadmapNotFoundError:
        return DashboardOut(profile=profile_out, active_track=track_out, **_EMPTY)

    progress = build_progress(roadmap.phases)
    return DashboardOut(
        profile=profile_out,
        active_track=track_out,
        roadmap_summary=roadmap.summary,
        current_phase=progress["current_phase_title"],
        completed_modules=progress["completed_modules"],
        remaining_modules=progress["total_modules"] - progress["completed_modules"],
        completion_pct=progress["completion_pct"],
        next_module=_find_next_module(roadmap.phases),
        recent_interviews=[],
    )
```

- [ ] **Step 5: Write `backend/routers/dashboard.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.session import get_db
from schemas.dashboard import DashboardOut
from services import dashboard_service

router = APIRouter(tags=["dashboard"])


@router.get("/api/dashboard", response_model=DashboardOut)
def get_dashboard(db: Session = Depends(get_db)):
    return dashboard_service.get_dashboard(db)
```

- [ ] **Step 6: Wire `backend/main.py`**

Add `dashboard` to the `from routers import ...` line and add
`app.include_router(dashboard.router)` next to the other `include_router` calls.
No model import needed — the dashboard has no table of its own.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_dashboard_api.py -v`
Expected: PASS — `4 passed`

- [ ] **Step 8: Run the full backend suite**

Run: `cd backend && .venv/bin/pytest -v`
Expected: PASS — `116 passed` (112 before this task + 4)

- [ ] **Step 9: Commit**

```bash
git add backend/schemas/dashboard.py backend/services/dashboard_service.py backend/routers/dashboard.py backend/main.py backend/tests/test_dashboard_api.py
git commit -m "feat(backend): add dashboard aggregate endpoint"
```

---

## Task 9: Frontend SSE client, roadmap/dashboard API, hooks, and the progress mirror

**Files:**
- Modify: `frontend/src/types/index.ts` (+ roadmap/dashboard/progress/stream types)
- Modify: `frontend/src/services/api/client.ts` (export `BASE_URL` so `sse.ts` doesn't duplicate it)
- Create: `frontend/src/services/api/sse.ts`, `roadmap.ts`, `dashboard.ts`
- Create: `frontend/src/hooks/useRoadmapStream.ts`, `useRoadmap.ts`, `useDashboard.ts`
- Create: `frontend/src/lib/progress.ts`
- Test: `frontend/src/services/api/__tests__/sse.test.ts`, `frontend/src/lib/__tests__/progress.test.ts`

**Verified live before writing this task:** jsdom (the project's Vitest
`environment`) *does* correctly support constructing a real `Response` with a
`ReadableStream` body and reading it with `response.body.getReader()`, and
`global.fetch` can be overridden to return one — checked with a throwaway
probe test (two cases: direct `Response`, then through an overridden
`fetch`), both passed, then deleted. This means `sse.ts` is testable exactly
like the backend's `PhaseStreamParser` — a fake stream, no real network.

`lib/progress.ts` mirrors `services/progress_service.py` function-for-function
and its test fixtures are the *same 10 cases*, not just "similar" — this is
what makes the "implemented twice, tested identically" claim in this plan's
architecture line actually true rather than aspirational.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/lib/__tests__/progress.test.ts`:

```typescript
import { describe, expect, it } from "vitest";

import {
  buildProgress,
  currentPhaseIndex,
  isModuleComplete,
  isPhaseUnlocked,
  phaseCompletion,
  roadmapCompletion,
} from "@/lib/progress";

function mod(completed: boolean) {
  return { completed_at: completed ? "2026-01-01T00:00:00" : null };
}

function phase(orderIndex: number, modules: { completed_at: string | null }[]) {
  return { order_index: orderIndex, title: `Phase ${orderIndex}`, modules };
}

describe("isModuleComplete", () => {
  it("checks completed_at", () => {
    expect(isModuleComplete(mod(true))).toBe(true);
    expect(isModuleComplete(mod(false))).toBe(false);
  });
});

describe("phaseCompletion", () => {
  it("is the completed fraction", () => {
    expect(phaseCompletion([mod(true), mod(true), mod(false)])).toBeCloseTo(2 / 3);
  });

  it("is zero for an empty phase, not a crash", () => {
    expect(phaseCompletion([])).toBe(0);
  });
});

describe("roadmapCompletion", () => {
  it("spans all phases", () => {
    const phases = [phase(0, [mod(true), mod(true)]), phase(1, [mod(true), mod(false)])];
    expect(roadmapCompletion(phases)).toBeCloseTo(3 / 4);
  });
});

describe("isPhaseUnlocked", () => {
  it("the first phase is always unlocked", () => {
    expect(isPhaseUnlocked(0, [phase(0, [mod(false)])])).toBe(true);
  });

  it("unlocks at exactly 80% previous completion", () => {
    const previous = phase(0, [mod(true), mod(true), mod(true), mod(true), mod(false)]);
    expect(isPhaseUnlocked(1, [previous, phase(1, [mod(false)])])).toBe(true);
  });

  it("stays locked just under 80% previous completion", () => {
    const previous = phase(0, [mod(true), mod(true), mod(true), mod(false)]);
    expect(isPhaseUnlocked(1, [previous, phase(1, [mod(false)])])).toBe(false);
  });
});

describe("currentPhaseIndex", () => {
  it("is the first incomplete phase", () => {
    const phases = [phase(0, [mod(true)]), phase(1, [mod(false)]), phase(2, [mod(false)])];
    expect(currentPhaseIndex(phases)).toBe(1);
  });

  it("is the last phase when everything is complete", () => {
    expect(currentPhaseIndex([phase(0, [mod(true)]), phase(1, [mod(true)])])).toBe(1);
  });
});

describe("buildProgress", () => {
  it("summarizes everything in one shape", () => {
    const phases = [phase(0, [mod(true), mod(true)]), phase(1, [mod(false)])];
    const progress = buildProgress(phases);

    expect(progress.completed_modules).toBe(2);
    expect(progress.total_modules).toBe(3);
    expect(progress.completion_pct).toBeCloseTo(66.7, 1);
    expect(progress.current_phase_index).toBe(1);
    expect(progress.phases[0].unlocked).toBe(true);
    expect(progress.phases[1].unlocked).toBe(true);
    expect(progress.phases[1].completion_pct).toBe(0);
  });
});
```

Create `frontend/src/services/api/__tests__/sse.test.ts`:

```typescript
import { afterEach, describe, expect, it, vi } from "vitest";

import { sseFetch } from "@/services/api/sse";

function streamFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let i = 0;
  return new ReadableStream({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(encoder.encode(chunks[i]));
        i += 1;
      } else {
        controller.close();
      }
    },
  });
}

function mockFetchReturning(chunks: string[]) {
  return vi.fn(async () => new Response(streamFromChunks(chunks), { status: 200 }));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

async function collect(path: string) {
  const events = [];
  for await (const event of sseFetch(path)) events.push(event);
  return events;
}

describe("sseFetch", () => {
  it("parses a single complete event", async () => {
    vi.stubGlobal("fetch", mockFetchReturning(['event: meta\ndata: {"title":"T"}\n\n']));

    expect(await collect("/x")).toEqual([{ event: "meta", data: { title: "T" } }]);
  });

  it("reassembles an event split across multiple read chunks", async () => {
    vi.stubGlobal("fetch", mockFetchReturning(['event: meta\ndata: {"tit', 'le":"T"}\n\n']));

    expect(await collect("/x")).toEqual([{ event: "meta", data: { title: "T" } }]);
  });

  it("emits multiple events in arrival order, one per block", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchReturning([
        'event: meta\ndata: {"a":1}\n\n',
        'event: phase\ndata: {"b":2}\n\nevent: done\ndata: {"c":3}\n\n',
      ]),
    );

    const events = await collect("/x");
    expect(events.map((e) => e.event)).toEqual(["meta", "phase", "done"]);
    expect(events.map((e) => e.data)).toEqual([{ a: 1 }, { b: 2 }, { c: 3 }]);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/lib/__tests__/progress.test.ts src/services/api/__tests__/sse.test.ts`
Expected: FAIL — `Cannot find module '@/lib/progress'` and `Cannot find module '@/services/api/sse'`

- [ ] **Step 3: Add roadmap/dashboard/stream types to `frontend/src/types/index.ts`**

Append:

```typescript
export type ModuleKind = "module" | "checkpoint" | "milestone" | "project";

export interface RoadmapModule {
  id: number;
  order_index: number;
  title: string;
  description: string;
  lessons: string[];
  exercises: string[];
  project: { title: string; description: string } | null;
  estimated_hours: number;
  kind: ModuleKind;
  started_at: string | null;
  completed_at: string | null;
}

export interface RoadmapPhase {
  id: number;
  order_index: number;
  title: string;
  description: string;
  goal: string;
  estimated_hours: number;
  modules: RoadmapModule[];
}

export interface WeeklyGoal {
  week: number;
  goal: string;
  phase_order: number;
}

export interface FinalProject {
  title: string;
  description: string;
  skills_demonstrated: string[];
}

export interface PhaseProgress {
  order_index: number;
  completion_pct: number;
  unlocked: boolean;
}

export interface Progress {
  completion_pct: number;
  completed_modules: number;
  total_modules: number;
  current_phase_index: number;
  current_phase_title: string | null;
  phases: PhaseProgress[];
}

export interface Roadmap {
  id: number;
  track_id: number;
  title: string;
  summary: string;
  total_weeks: number;
  weekly_hours: number;
  weekly_goals: WeeklyGoal[];
  final_project: FinalProject | null;
  created_at: string;
  phases: RoadmapPhase[];
  progress: Progress;
}

export interface NextModule {
  id: number;
  title: string;
  kind: ModuleKind;
  phase_title: string;
}

export interface Dashboard {
  profile: Profile | null;
  active_track: Track | null;
  roadmap_summary: string | null;
  current_phase: string | null;
  completed_modules: number;
  remaining_modules: number;
  completion_pct: number;
  next_module: NextModule | null;
  recent_interviews: unknown[];
}

// Streamed phase/module data has no id yet — it isn't persisted-and-fetched
// until generation finishes; only the real GET /roadmap response (above) has
// ids. This is why RoadmapPage switches from the stream view to a real
// useRoadmap() query once the "done" event arrives, rather than trying to
// make the streamed data itself interactive.
export interface StreamModule {
  title: string;
  description: string;
  lessons: string[];
  exercises: string[];
  project: { title: string; description: string } | null;
  estimated_hours: number;
  kind: ModuleKind;
}

export interface StreamPhase {
  order_index: number;
  title: string;
  modules: StreamModule[];
}

export interface RoadmapMeta {
  title: string;
  summary: string;
  total_weeks: number;
  weekly_hours: number;
  weekly_goals: WeeklyGoal[];
  final_project: FinalProject | null;
}
```

- [ ] **Step 4: Export `BASE_URL` from `frontend/src/services/api/client.ts`**

Change `const BASE_URL = ...` to `export const BASE_URL = ...` (only the one
line changes; everything else in the file stays the same).

- [ ] **Step 5: Write `frontend/src/services/api/sse.ts`**

```typescript
import { BASE_URL } from "@/services/api/client";

export interface SseEvent<T = unknown> {
  event: string;
  data: T;
}

function parseSseBlock(block: string): SseEvent | null {
  let event = "message";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event: ")) event = line.slice(7);
    else if (line.startsWith("data: ")) data = line.slice(6);
  }
  if (!data) return null;
  try {
    return { event, data: JSON.parse(data) };
  } catch {
    return null;
  }
}

/**
 * fetch + ReadableStream SSE reader. Not EventSource, which can't POST.
 * Scans the accumulated buffer for `\n\n` block boundaries rather than
 * assuming a boundary lands inside a single read() chunk — chunk
 * boundaries are a transport detail with no relation to SSE framing,
 * exactly like the backend's own raw-text chunking.
 */
export async function* sseFetch(path: string, init?: RequestInit): AsyncGenerator<SseEvent> {
  const response = await fetch(`${BASE_URL}${path}`, init);
  if (!response.ok || !response.body) {
    throw new Error(`Stream request failed: ${response.status} ${response.statusText}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const event = parseSseBlock(block);
      if (event) yield event;
      boundary = buffer.indexOf("\n\n");
    }
  }
}
```

- [ ] **Step 6: Write `frontend/src/lib/progress.ts`**

```typescript
interface ModuleLike {
  completed_at: string | null;
}

interface PhaseLike {
  order_index: number;
  title: string;
  modules: ModuleLike[];
}

export function isModuleComplete(module: ModuleLike): boolean {
  return module.completed_at !== null;
}

export function phaseCompletion(modules: ModuleLike[]): number {
  if (modules.length === 0) return 0;
  return modules.filter(isModuleComplete).length / modules.length;
}

export function roadmapCompletion(phases: PhaseLike[]): number {
  const allModules = phases.flatMap((p) => p.modules);
  if (allModules.length === 0) return 0;
  return allModules.filter(isModuleComplete).length / allModules.length;
}

export function isPhaseUnlocked(phaseIndex: number, phases: PhaseLike[]): boolean {
  if (phaseIndex === 0) return true;
  return phaseCompletion(phases[phaseIndex - 1].modules) >= 0.8;
}

export function currentPhaseIndex(phases: PhaseLike[]): number {
  for (let i = 0; i < phases.length; i++) {
    if (phaseCompletion(phases[i].modules) < 1) return i;
  }
  return phases.length > 0 ? phases.length - 1 : 0;
}

export interface ProgressSummary {
  completion_pct: number;
  completed_modules: number;
  total_modules: number;
  current_phase_index: number;
  current_phase_title: string | null;
  phases: { order_index: number; completion_pct: number; unlocked: boolean }[];
}

export function buildProgress(phases: PhaseLike[]): ProgressSummary {
  const totalModules = phases.reduce((sum, p) => sum + p.modules.length, 0);
  const completedModules = phases.reduce(
    (sum, p) => sum + p.modules.filter(isModuleComplete).length,
    0,
  );
  const current = currentPhaseIndex(phases);

  return {
    completion_pct: Math.round(roadmapCompletion(phases) * 1000) / 10,
    completed_modules: completedModules,
    total_modules: totalModules,
    current_phase_index: current,
    current_phase_title: phases.length > 0 ? phases[current].title : null,
    phases: phases.map((phase, i) => ({
      order_index: phase.order_index,
      completion_pct: Math.round(phaseCompletion(phase.modules) * 1000) / 10,
      unlocked: isPhaseUnlocked(i, phases),
    })),
  };
}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/lib/__tests__/progress.test.ts src/services/api/__tests__/sse.test.ts`
Expected: PASS — `10 passed` (progress) and `3 passed` (sse)

- [ ] **Step 8: Write the remaining API/hook files (no new tests — thin wiring over what Steps 5-6 already tested)**

`frontend/src/services/api/roadmap.ts`:

```typescript
import { api } from "@/services/api/client";
import { sseFetch } from "@/services/api/sse";
import type { Progress, Roadmap, RoadmapModule } from "@/types";

export function streamRoadmap(trackId: number) {
  return sseFetch(`/api/tracks/${trackId}/roadmap/stream`, { method: "POST" });
}

export const getRoadmap = (trackId: number) => api<Roadmap>(`/api/tracks/${trackId}/roadmap`);

export const toggleModule = (moduleId: number, completed: boolean) =>
  api<{ module: RoadmapModule; progress: Progress }>(`/api/modules/${moduleId}`, {
    method: "PATCH",
    body: JSON.stringify({ completed }),
  });

export const getProgress = (trackId: number) => api<Progress>(`/api/tracks/${trackId}/progress`);
```

`frontend/src/services/api/dashboard.ts`:

```typescript
import { api } from "@/services/api/client";
import type { Dashboard } from "@/types";

export const getDashboard = () => api<Dashboard>("/api/dashboard");
```

`frontend/src/hooks/useRoadmapStream.ts`:

```typescript
import { useCallback, useRef, useState } from "react";

import { streamRoadmap } from "@/services/api/roadmap";
import type { RoadmapMeta, StreamPhase } from "@/types";

type StreamState =
  | { status: "idle" }
  | { status: "streaming"; meta: RoadmapMeta | null; phases: StreamPhase[] }
  | { status: "done"; roadmapId: number }
  | { status: "error"; code: string; message: string };

export function useRoadmapStream() {
  const [state, setState] = useState<StreamState>({ status: "idle" });
  const runningRef = useRef(false);

  const start = useCallback(async (trackId: number) => {
    if (runningRef.current) return;
    runningRef.current = true;
    setState({ status: "streaming", meta: null, phases: [] });

    try {
      for await (const { event, data } of streamRoadmap(trackId)) {
        if (event === "meta") {
          setState((prev) =>
            prev.status === "streaming" ? { ...prev, meta: data as RoadmapMeta } : prev,
          );
        } else if (event === "phase") {
          setState((prev) =>
            prev.status === "streaming"
              ? { ...prev, phases: [...prev.phases, data as StreamPhase] }
              : prev,
          );
        } else if (event === "done") {
          setState({ status: "done", roadmapId: (data as { roadmap_id: number }).roadmap_id });
        } else if (event === "error") {
          const err = data as { code: string; message: string };
          setState({ status: "error", code: err.code, message: err.message });
        }
      }
    } catch (error) {
      setState({
        status: "error",
        code: "network_error",
        message: error instanceof Error ? error.message : "Connection lost.",
      });
    } finally {
      runningRef.current = false;
    }
  }, []);

  return { state, start };
}
```

`frontend/src/hooks/useRoadmap.ts`:

```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getProgress, getRoadmap, toggleModule } from "@/services/api/roadmap";
import { dashboardKey } from "@/hooks/useDashboard";

export const roadmapKey = (trackId: number) => ["roadmap", trackId] as const;
export const progressKey = (trackId: number) => ["progress", trackId] as const;

export function useRoadmap(trackId: number | null) {
  return useQuery({
    queryKey: roadmapKey(trackId ?? -1),
    queryFn: () => getRoadmap(trackId as number),
    enabled: trackId !== null,
  });
}

export function useProgress(trackId: number | null) {
  return useQuery({
    queryKey: progressKey(trackId ?? -1),
    queryFn: () => getProgress(trackId as number),
    enabled: trackId !== null,
  });
}

export function useToggleModule(trackId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ moduleId, completed }: { moduleId: number; completed: boolean }) =>
      toggleModule(moduleId, completed),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: roadmapKey(trackId) });
      queryClient.invalidateQueries({ queryKey: progressKey(trackId) });
      queryClient.invalidateQueries({ queryKey: dashboardKey });
    },
  });
}
```

`frontend/src/hooks/useDashboard.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";

import { getDashboard } from "@/services/api/dashboard";

export const dashboardKey = ["dashboard"] as const;

export function useDashboard() {
  return useQuery({ queryKey: dashboardKey, queryFn: getDashboard });
}
```

- [ ] **Step 9: Typecheck and full frontend test run**

Run: `cd frontend && npx tsc -b --noEmit && npm test`
Expected: typecheck clean; all existing + new tests pass.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/services/api/client.ts frontend/src/services/api/sse.ts frontend/src/services/api/roadmap.ts frontend/src/services/api/dashboard.ts frontend/src/hooks/useRoadmapStream.ts frontend/src/hooks/useRoadmap.ts frontend/src/hooks/useDashboard.ts frontend/src/lib/progress.ts frontend/src/services/api/__tests__/sse.test.ts frontend/src/lib/__tests__/progress.test.ts
git commit -m "feat(frontend): add SSE client, roadmap/dashboard API, hooks, and progress mirror"
```

---

## Task 10: Roadmap viewer components and page

**Files:**
- Create: `frontend/src/components/roadmap/ProgressRing.tsx`, `ModuleRow.tsx`, `PhaseCard.tsx`, `GeneratingRoadmap.tsx`
- Modify: `frontend/src/pages/RoadmapPage.tsx` (new — replaces the `App.tsx` placeholder)
- Modify: `frontend/src/App.tsx` (`/roadmap` renders the real page)

Presentational — per this plan's testing approach, verified by typecheck +
build here, then by a real browser check in Task 11 once there's an actual
track/roadmap to look at (a placeholder track makes for a hollow visual
check right now). No new Vitest coverage in this task.

`RoadmapPage` decides for itself whether to show the live-generating view or
the persisted timeline: it calls `useRoadmap(trackId)`, and if that comes
back `roadmap_not_found` it auto-starts `useRoadmapStream`. This makes the
page correct however the learner arrives at `/roadmap` — straight from
onboarding, from a page refresh mid-generation, or from clicking the sidebar
link on a track that already has one — rather than requiring onboarding to
somehow time a separate "start generation" call against a navigation.

- [ ] **Step 1: Write `frontend/src/components/roadmap/ProgressRing.tsx`**

```tsx
interface ProgressRingProps {
  percent: number;
  size?: number;
  strokeWidth?: number;
  label?: string;
}

export function ProgressRing({ percent, size = 80, strokeWidth = 8, label }: ProgressRingProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.min(100, Math.max(0, percent));
  const offset = circumference - (clamped / 100) * circumference;

  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          className="fill-none stroke-line"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="fill-none stroke-accent transition-[stroke-dashoffset] duration-500"
        />
      </svg>
      <div className="absolute flex flex-col items-center justify-center">
        <span className="text-lg font-semibold text-text-primary">{Math.round(clamped)}%</span>
        {label && <span className="text-[10px] text-text-muted">{label}</span>}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write `frontend/src/components/roadmap/ModuleRow.tsx`**

```tsx
import { Check, Circle, Flag, RotateCcw, Sparkles } from "lucide-react";

import { cn } from "@/lib/cn";
import type { RoadmapModule } from "@/types";

const KIND_ICON: Record<RoadmapModule["kind"], typeof Circle> = {
  module: Circle,
  checkpoint: RotateCcw,
  milestone: Flag,
  project: Sparkles,
};

const KIND_LABEL: Record<RoadmapModule["kind"], string> = {
  module: "Module",
  checkpoint: "Checkpoint",
  milestone: "Milestone",
  project: "Project",
};

interface ModuleRowProps {
  module: RoadmapModule;
  onToggle: (completed: boolean) => void;
  pending?: boolean;
}

export function ModuleRow({ module, onToggle, pending }: ModuleRowProps) {
  const completed = module.completed_at !== null;
  const Icon = KIND_ICON[module.kind];

  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-lg border border-line bg-surface p-3 transition-colors",
        completed && "bg-accent-soft/40",
      )}
    >
      <button
        type="button"
        disabled={pending}
        onClick={() => onToggle(!completed)}
        aria-label={completed ? "Mark incomplete" : "Mark complete"}
        className={cn(
          "mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border transition-colors",
          completed
            ? "border-accent bg-accent text-on-accent"
            : "border-line text-transparent hover:border-accent",
          pending && "opacity-50",
        )}
      >
        <Check className="size-3.5" strokeWidth={3} />
      </button>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "text-sm font-medium",
              completed ? "text-text-secondary line-through" : "text-text-primary",
            )}
          >
            {module.title}
          </span>
          {module.kind !== "module" && (
            <span className="flex items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent">
              <Icon className="size-3" />
              {KIND_LABEL[module.kind]}
            </span>
          )}
        </div>
        {module.description && (
          <p className="mt-0.5 text-xs text-text-secondary">{module.description}</p>
        )}
        <p className="mt-1 text-[11px] text-text-muted">{module.estimated_hours}h estimated</p>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Write `frontend/src/components/roadmap/PhaseCard.tsx`**

```tsx
import { ChevronDown, Lock } from "lucide-react";
import { useState } from "react";

import { ModuleRow } from "@/components/roadmap/ModuleRow";
import { cn } from "@/lib/cn";
import type { RoadmapPhase } from "@/types";

interface PhaseCardProps {
  phase: RoadmapPhase;
  completionPct: number;
  unlocked: boolean;
  isCurrent: boolean;
  onToggleModule: (moduleId: number, completed: boolean) => void;
  togglingModuleId?: number | null;
}

export function PhaseCard({
  phase,
  completionPct,
  unlocked,
  isCurrent,
  onToggleModule,
  togglingModuleId,
}: PhaseCardProps) {
  const [expanded, setExpanded] = useState(isCurrent);

  return (
    <div
      className={cn(
        "rounded-xl border bg-surface transition-colors",
        isCurrent ? "border-accent" : "border-line",
        !unlocked && "opacity-60",
      )}
    >
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="flex w-full items-center gap-3 p-4 text-left"
      >
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-accent-soft text-sm font-semibold text-accent">
          {phase.order_index + 1}
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="truncate text-sm font-semibold text-text-primary">{phase.title}</h3>
            {!unlocked && <Lock className="size-3.5 shrink-0 text-text-muted" />}
          </div>
          <p className="mt-0.5 truncate text-xs text-text-secondary">{phase.goal}</p>
        </div>

        <div className="flex shrink-0 items-center gap-3">
          <div className="hidden w-24 sm:block">
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-line">
              <div
                className="h-full rounded-full bg-accent transition-all duration-base"
                style={{ width: `${completionPct}%` }}
              />
            </div>
          </div>
          <span className="w-10 text-right text-xs font-medium text-text-secondary">
            {Math.round(completionPct)}%
          </span>
          <ChevronDown
            className={cn(
              "size-4 text-text-muted transition-transform",
              expanded && "rotate-180",
            )}
          />
        </div>
      </button>

      {expanded && (
        <div className="space-y-2 border-t border-line p-4 pt-3">
          {!unlocked && (
            <p className="mb-2 text-xs text-text-muted">
              Complete 80% of the previous phase to unlock this one.
            </p>
          )}
          {phase.modules.map((module) => (
            <ModuleRow
              key={module.id}
              module={module}
              onToggle={(completed) => onToggleModule(module.id, completed)}
              pending={togglingModuleId === module.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Write `frontend/src/components/roadmap/GeneratingRoadmap.tsx`**

```tsx
import { motion } from "framer-motion";
import { Loader2, Sparkles } from "lucide-react";

import { Card } from "@/components/ui/card";
import type { RoadmapMeta, StreamPhase } from "@/types";

interface GeneratingRoadmapProps {
  meta: RoadmapMeta | null;
  phases: StreamPhase[];
}

export function GeneratingRoadmap({ meta, phases }: GeneratingRoadmapProps) {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 rounded-xl border border-accent/30 bg-accent-soft px-4 py-3">
        <Loader2 className="size-4 shrink-0 animate-spin text-accent" />
        <p className="text-sm text-accent">
          {meta ? "Writing your roadmap phase by phase…" : "Thinking through your roadmap…"}
        </p>
      </div>

      {meta && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="space-y-1.5">
            <h2 className="text-lg font-semibold text-text-primary">{meta.title}</h2>
            <p className="text-sm text-text-secondary">{meta.summary}</p>
            <p className="text-xs text-text-muted">
              {meta.total_weeks} weeks · ~{meta.weekly_hours}h/week
            </p>
          </Card>
        </motion.div>
      )}

      <div className="space-y-3">
        {phases.map((phase) => (
          <motion.div
            key={`${phase.order_index}-${phase.title}`}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <Card className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="grid size-6 shrink-0 place-items-center rounded-full bg-accent-soft text-xs font-semibold text-accent">
                  {phase.order_index + 1}
                </span>
                <h3 className="text-sm font-semibold text-text-primary">{phase.title}</h3>
              </div>
              <p className="pl-8 text-xs text-text-muted">
                {phase.modules.length} module{phase.modules.length === 1 ? "" : "s"}
              </p>
            </Card>
          </motion.div>
        ))}
      </div>

      {phases.length === 0 && meta && (
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <Sparkles className="size-3.5" />
          Building phase 1…
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Write `frontend/src/pages/RoadmapPage.tsx`**

```tsx
import { useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw } from "lucide-react";
import { useEffect } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";
import { GeneratingRoadmap } from "@/components/roadmap/GeneratingRoadmap";
import { PhaseCard } from "@/components/roadmap/PhaseCard";
import { ProgressRing } from "@/components/roadmap/ProgressRing";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useActiveTrack } from "@/hooks/useProfile";
import { roadmapKey, useRoadmap, useToggleModule } from "@/hooks/useRoadmap";
import { useRoadmapStream } from "@/hooks/useRoadmapStream";
import { ApiError } from "@/services/api/client";

export default function RoadmapPage() {
  const { data: track } = useActiveTrack();
  const trackId = track?.id ?? null;
  const roadmapQuery = useRoadmap(trackId);
  const stream = useRoadmapStream();
  const queryClient = useQueryClient();
  const toggleModule = useToggleModule(trackId ?? -1);

  const roadmapMissing =
    roadmapQuery.error instanceof ApiError && roadmapQuery.error.code === "roadmap_not_found";

  useEffect(() => {
    if (trackId !== null && roadmapMissing && stream.state.status === "idle") {
      stream.start(trackId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trackId, roadmapMissing]);

  useEffect(() => {
    if (stream.state.status === "done" && trackId !== null) {
      queryClient.invalidateQueries({ queryKey: roadmapKey(trackId) });
    }
  }, [stream.state.status, trackId, queryClient]);

  if (!track) {
    return (
      <AppShell>
        <TopBar title="Roadmap" subtitle="Pick a track from the dashboard first." />
      </AppShell>
    );
  }

  if (stream.state.status === "streaming" || stream.state.status === "done") {
    return (
      <AppShell>
        <TopBar title={`${track.topic} roadmap`} subtitle="Generating your personalized plan…" />
        <GeneratingRoadmap
          meta={stream.state.status === "streaming" ? stream.state.meta : null}
          phases={stream.state.status === "streaming" ? stream.state.phases : []}
        />
      </AppShell>
    );
  }

  if (stream.state.status === "error") {
    return (
      <AppShell>
        <TopBar title={`${track.topic} roadmap`} />
        <Card className="space-y-3">
          <p className="text-sm text-text-primary">{stream.state.message}</p>
          <Button size="sm" onClick={() => stream.start(track.id)}>
            <RefreshCw className="size-4" /> Try again
          </Button>
        </Card>
      </AppShell>
    );
  }

  if (roadmapQuery.isPending || !roadmapQuery.data) {
    return (
      <AppShell>
        <div className="grid place-items-center py-24">
          <Loader2 className="size-6 animate-spin text-text-muted" />
        </div>
      </AppShell>
    );
  }

  const roadmap = roadmapQuery.data;

  return (
    <AppShell>
      <TopBar title={roadmap.title} subtitle={roadmap.summary} />

      <div className="mb-6 flex items-center gap-6 rounded-xl border border-line bg-surface p-5">
        <ProgressRing percent={roadmap.progress.completion_pct} />
        <div>
          <p className="text-sm font-medium text-text-primary">
            {roadmap.progress.completed_modules} of {roadmap.progress.total_modules} modules
            complete
          </p>
          <p className="mt-1 text-xs text-text-secondary">
            {roadmap.total_weeks} weeks · ~{roadmap.weekly_hours}h/week
          </p>
          {roadmap.progress.current_phase_title && (
            <p className="mt-1 text-xs text-accent">
              Currently on: {roadmap.progress.current_phase_title}
            </p>
          )}
        </div>
      </div>

      <div className="space-y-3">
        {roadmap.phases.map((phase, index) => {
          const phaseProgress = roadmap.progress.phases[index];
          return (
            <PhaseCard
              key={phase.id}
              phase={phase}
              completionPct={phaseProgress?.completion_pct ?? 0}
              unlocked={phaseProgress?.unlocked ?? true}
              isCurrent={index === roadmap.progress.current_phase_index}
              onToggleModule={(moduleId, completed) =>
                toggleModule.mutate({ moduleId, completed })
              }
              togglingModuleId={
                toggleModule.isPending ? (toggleModule.variables?.moduleId ?? null) : null
              }
            />
          );
        })}
      </div>

      {roadmap.final_project && (
        <Card className="mt-6 space-y-2 border-accent/30">
          <h3 className="text-sm font-semibold text-accent">
            Capstone: {roadmap.final_project.title}
          </h3>
          <p className="text-sm text-text-secondary">{roadmap.final_project.description}</p>
        </Card>
      )}
    </AppShell>
  );
}
```

- [ ] **Step 6: Wire `frontend/src/App.tsx`**

Replace the `/roadmap` placeholder route:

```tsx
<Route path="/roadmap" element={<RoadmapPage />} />
```

Add `import RoadmapPage from "@/pages/RoadmapPage";` next to the other page
imports, and remove `roadmap` from any remaining `Placeholder` usages (the
`interview` route keeps using `Placeholder` — that's Plan 4).

- [ ] **Step 7: Typecheck and build**

Run: `cd frontend && npx tsc -b --noEmit && npm run build`
Expected: both clean, no errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/roadmap frontend/src/pages/RoadmapPage.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add roadmap timeline viewer with live-streaming generation view"
```

---

## Task 11: Dashboard page, onboarding wiring, and full E2E verification

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx` (real data instead of the placeholder)
- Modify: `frontend/src/pages/OnboardingPage.tsx` (Beginner lands on `/roadmap`, not `/`)
- Modify: `frontend/src/components/assessment/ResultSummary.tsx` (+ `onContinue` CTA)
- Modify: `frontend/src/pages/AssessmentPage.tsx` (wire `onContinue` to navigate to `/roadmap`)
- Modify: `frontend/src/pages/RoadmapPage.tsx` (small refinement — see Step 4)

This closes the loop the whole plan has been building toward: both onboarding
paths (Beginner direct, Intermediate/Advanced via assessment) now land on a
real, generating-or-generated roadmap, and the dashboard shows what actually
exists instead of a "coming later" placeholder.

- [ ] **Step 1: Rewrite `frontend/src/pages/DashboardPage.tsx`**

```tsx
import { Loader2, Plus } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";
import { ProgressRing } from "@/components/roadmap/ProgressRing";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { useDashboard } from "@/hooks/useDashboard";

export default function DashboardPage() {
  const { data: dashboard, isPending } = useDashboard();
  const navigate = useNavigate();

  if (isPending || !dashboard) {
    return (
      <AppShell>
        <div className="grid place-items-center py-24">
          <Loader2 className="size-6 animate-spin text-text-muted" />
        </div>
      </AppShell>
    );
  }

  const { profile, active_track: track, next_module: nextModule } = dashboard;

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
          {dashboard.roadmap_summary ? (
            <>
              <CardDescription className="mt-1">{dashboard.roadmap_summary}</CardDescription>
              {dashboard.current_phase && (
                <p className="mt-2 text-xs font-medium text-accent">
                  Currently on: {dashboard.current_phase}
                </p>
              )}
            </>
          ) : (
            <CardDescription className="mt-1">
              {track ? "Not generated yet." : "Start a track to get one."}
            </CardDescription>
          )}
          {track && (
            <Button size="sm" className="mt-4" onClick={() => navigate("/roadmap")}>
              {dashboard.roadmap_summary ? "View roadmap" : "Generate roadmap"}
            </Button>
          )}
        </Card>
      </div>

      {dashboard.roadmap_summary && (
        <div className="mt-4 grid gap-4 sm:grid-cols-[auto_1fr]">
          <Card className="flex items-center justify-center">
            <ProgressRing percent={dashboard.completion_pct} label="complete" />
          </Card>

          <Card className="flex flex-col justify-center gap-1">
            <p className="text-sm text-text-primary">
              {dashboard.completed_modules} of{" "}
              {dashboard.completed_modules + dashboard.remaining_modules} modules done
            </p>
            {nextModule ? (
              <>
                <p className="text-xs text-text-secondary">Next up: {nextModule.title}</p>
                <Button
                  size="sm"
                  className="mt-2 self-start"
                  onClick={() => navigate("/roadmap")}
                >
                  Continue learning
                </Button>
              </>
            ) : (
              <p className="text-xs text-success">Roadmap complete — nice work.</p>
            )}
          </Card>
        </div>
      )}

      <Card className="mt-4">
        <CardTitle>Recent interviews</CardTitle>
        <CardDescription className="mt-1">
          {dashboard.recent_interviews.length === 0
            ? "No interviews yet."
            : `${dashboard.recent_interviews.length} completed.`}
        </CardDescription>
      </Card>
    </AppShell>
  );
}
```

- [ ] **Step 2: Wire Beginner onboarding to `/roadmap`**

In `frontend/src/pages/OnboardingPage.tsx`, in `handleLevel`, change:

```tsx
if (level === "beginner") {
  navigate("/", { replace: true });
  return;
}
```

to:

```tsx
if (level === "beginner") {
  navigate("/roadmap", { replace: true });
  return;
}
```

- [ ] **Step 3: Add a continue CTA to the assessment result, wire it to `/roadmap`**

In `frontend/src/components/assessment/ResultSummary.tsx`, add the import
`import { ArrowRight } from "lucide-react";` and
`import { Button } from "@/components/ui/button";`, change the function
signature to accept an optional callback, and render a CTA right after the
score card:

```tsx
export function ResultSummary({
  assessment,
  onContinue,
}: {
  assessment: Assessment;
  onContinue?: () => void;
}) {
  return (
    <div className="space-y-6">
      <Card className="space-y-4">
        {/* ...unchanged... */}
      </Card>

      {onContinue && (
        <Button onClick={onContinue} className="w-full sm:w-auto">
          Continue to your roadmap <ArrowRight className="size-4" />
        </Button>
      )}

      {/* ...strengths/weaknesses and question breakdown, unchanged... */}
```

In `frontend/src/pages/AssessmentPage.tsx`, import `useNavigate` alongside
the existing `useParams` import, add `const navigate = useNavigate();`, and
pass the callback:

```tsx
<ResultSummary assessment={assessment} onContinue={() => navigate("/roadmap")} />
```

- [ ] **Step 4: Small refinement to `frontend/src/pages/RoadmapPage.tsx`**

`useActiveTrack()` can be genuinely loading (right after onboarding
`invalidateQueries`s the tracks query) rather than genuinely empty. Without
distinguishing the two, the page would flash "Pick a track from the
dashboard first" for a moment on every arrival from onboarding. Destructure
`isPending` too and check it first:

```tsx
const { data: track, isPending: trackPending } = useActiveTrack();
```

Add a new early return right after the existing hooks, before the `!track`
check:

```tsx
if (trackPending) {
  return (
    <AppShell>
      <div className="grid place-items-center py-24">
        <Loader2 className="size-6 animate-spin text-text-muted" />
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 5: Typecheck, build, test**

Run: `cd frontend && npx tsc -b --noEmit && npm run build && npm test`
Expected: all clean.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/DashboardPage.tsx frontend/src/pages/OnboardingPage.tsx frontend/src/components/assessment/ResultSummary.tsx frontend/src/pages/AssessmentPage.tsx frontend/src/pages/RoadmapPage.tsx
git commit -m "feat(frontend): wire onboarding and assessment completion into roadmap generation"
```

- [ ] **Step 7: Full live E2E browser verification**

Start both servers and walk through, in a real browser, exactly like Plan
2's Task 10:

1. Beginner path: onboard with a fresh profile/track at Beginner level →
   confirm landing on `/roadmap` and the generating view appears.
2. Intermediate/Advanced path: onboard at Intermediate → complete the
   assessment → submit → click "Continue to your roadmap" → confirm landing
   on `/roadmap` with the generating view.
3. Dashboard: confirm it reflects real profile/track state at each stage.
4. Once a roadmap exists (from either path, once Gemini quota allows —
   see the note below), toggle a module's checkbox on `/roadmap` and confirm
   the phase/overall progress bars and the dashboard's progress ring update.

**Known blocker at verification time:** the Gemini free-tier quota
(`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, limit 20) has been
exhausted since Task 5's live smoke test. Steps 1-3 above are fully
verifiable right now — onboarding navigation, track creation, the SSE
connection opening, and (critically) the frontend's error-handling path,
since a quota-exhausted generation call surfaces as a real `AIUnavailable` →
an `event: error` SSE frame → the "Try again" card in `RoadmapPage`, which
this step can and should confirm renders correctly. Step 4 (an actual
generated roadmap to scroll, expand, and check off) stays blocked until the
daily quota window resets. Whoever picks this up next with quota available
should re-run step 4 specifically and update this note.

---
