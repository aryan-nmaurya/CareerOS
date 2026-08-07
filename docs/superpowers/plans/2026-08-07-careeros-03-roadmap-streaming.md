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
