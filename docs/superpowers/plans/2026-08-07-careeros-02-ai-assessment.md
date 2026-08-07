# CareerOS Plan 2 — AI Client + Assessment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the centralized Gemini client (with retries and a fake test double), then the full assessment vertical slice — question generation, autosave, AI-graded scoring — so an Intermediate or Advanced learner takes a real adaptive skill assessment after onboarding and gets a scored result.

**Architecture:** `ai/client.py` defines a provider-agnostic `AIClient` Protocol plus `Prompt`, with `FakeAIClient` for tests and `GeminiClient` (in `ai/gemini_client.py`) as the real implementation. A generic, provider-agnostic `call_with_retries` helper in `ai/retry.py` handles exponential-backoff retry with an injectable sleep function, so it's fully unit-tested without real delays or network. Assessment prompt builders are pure functions returning `Prompt` objects, tested without any client at all. The assessment service is the only thing that calls `ai_client.generate_json`; everything else (scoring, banding, grouping) is pure and tested directly.

**Tech Stack:** `google-genai` 2.x, FastAPI, SQLAlchemy, pytest (backend); React 19, TanStack Query (frontend).

**Spec:** `docs/superpowers/specs/2026-08-07-careeros-design.md` (sections 6 assessment score/banding/grouping, 7 assessment API, 8 AI layer, 11 `/assessment/:id`)

**Series context:** Plan 2 of 5.
1. Foundation (done)
2. **AI client + assessment** ← you are here
3. Roadmap SSE generation + viewer + progress + dashboard data
4. Interview core + speech
5. Proctoring + evaluation + reports + polish

**Verified before writing this plan:** every Gemini SDK call pattern below (`genai.Client` construction, `generate_content` with a plain-dict `response_schema` using uppercase type names like `"OBJECT"`/`"STRING"`, the `errors.APIError`/`ClientError`/`ServerError` hierarchy with a `.code` int, `response.text`) was exercised against the real API with a live key before being written into this plan. The model is `gemini-3.5-flash` — `gemini-2.5-flash` (used in Plan 1's default) returns 404 "no longer available to new users" and was already corrected in `backend/config.py` and `backend/.env.example`.

**Deliberately out of scope for this plan:** the spec's `/history` page (viewing
past assessments and interviews together). The backend `GET /api/assessments`
endpoint that page will need is built here, tested, and already returns full
history — there's just no frontend route for it yet. A history page with only
assessments and no interviews to show alongside them would be a half-populated
screen; it lands once Plan 4 gives it something worth listing next to.

---

## File Structure

**Backend** (`backend/`)

| File | Responsibility |
|---|---|
| `ai/errors.py` | `AIUnavailable`, `AIInvalidResponse` |
| `ai/retry.py` | `call_with_retries` — pure, provider-agnostic, injectable sleep |
| `ai/client.py` | `Prompt` dataclass, `AIClient` Protocol, `FakeAIClient`, `get_ai_client` dependency |
| `ai/gemini_client.py` | `GeminiClient` — real implementation, retry classification, JSON parsing |
| `ai/prompts/__init__.py` | empty |
| `ai/prompts/assessment.py` | `build_generation_prompt`, `build_grading_prompt` — pure |
| `models/assessment.py` | `Assessment`, `AssessmentQuestion` |
| `schemas/assessment.py` | `AssessmentQuestionOut`, `AssessmentOut`, `AnswerSave` |
| `services/assessment_service.py` | generation, autosave, submit/scoring/grading, `score_mcq_question`, `band_level`, `group_by_topic` |
| `routers/assessment.py` | `/api/tracks/{id}/assessment`, `/api/assessments*` |
| `main.py` | + global exception handlers for `AIUnavailable`/`AIInvalidResponse` |
| `services/profile_service.py` | + `get_track` (deferred from Plan 1, now has a real caller) |
| `tests/conftest.py` | + `fake_ai` fixture, `get_ai_client` override |
| `tests/test_retry.py` | retry/backoff logic, no network |
| `tests/test_ai_client.py` | `FakeAIClient` behaves correctly as a test double |
| `tests/test_assessment_models.py` | round trip + cascade delete for the two new tables |
| `tests/test_assessment_prompts.py` | prompt builders are correct pure functions |
| `tests/test_assessment_service.py` | scoring, banding, grouping, generation/submit orchestration |
| `tests/test_assessment_api.py` | router-level happy paths + structured error codes |

**Frontend** (`frontend/src/`)

| File | Responsibility |
|---|---|
| `types/index.ts` | + `Assessment`, `AssessmentQuestion`, related literal types |
| `services/api/assessment.ts` | typed assessment calls |
| `hooks/useAssessment.ts` | query/mutation hooks |
| `components/ui/textarea.tsx` | shadcn-pattern textarea primitive |
| `components/assessment/QuestionCard.tsx` | topic badge + question text shell |
| `components/assessment/McqOptions.tsx` | radio-style option list |
| `components/assessment/DescriptiveAnswer.tsx` | textarea |
| `components/assessment/ResultSummary.tsx` | score, level, strengths/weaknesses, per-question breakdown |
| `pages/AssessmentPage.tsx` | one-question-at-a-time flow + result view |
| `pages/OnboardingPage.tsx` | modified: Intermediate/Advanced routes into the assessment instead of the dashboard |
| `components/onboarding/LevelStep.tsx` | modified: dynamic pending label, inline error message |
| `App.tsx` | + `/assessment/:id` route |

---

## Task 1: AI client core — Prompt, protocol, errors, retry, fake

**Files:**
- Create: `backend/ai/__init__.py`, `backend/ai/errors.py`, `backend/ai/retry.py`, `backend/ai/client.py`
- Test: `backend/tests/test_retry.py`, `backend/tests/test_ai_client.py`

- [ ] **Step 1: Write the failing retry tests**

```bash
mkdir -p backend/ai/prompts
```

Create `backend/ai/__init__.py` (empty) and `backend/ai/prompts/__init__.py` (empty).

Create `backend/tests/test_retry.py`:

```python
import pytest

from ai.errors import AIUnavailable
from ai.retry import call_with_retries


class _Retryable(Exception):
    pass


def _is_retryable(exc: Exception) -> bool:
    return isinstance(exc, _Retryable)


def test_succeeds_without_retry_when_first_call_works():
    calls = []

    def fn():
        calls.append(1)
        return "ok"

    sleeps = []
    result = call_with_retries(fn, is_retryable=_is_retryable, sleep=sleeps.append)

    assert result == "ok"
    assert len(calls) == 1
    assert sleeps == []


def test_retries_then_succeeds():
    attempts = {"n": 0}

    def fn():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise _Retryable("transient")
        return "ok"

    sleeps = []
    result = call_with_retries(
        fn, is_retryable=_is_retryable, max_attempts=3, base_delay=1.0, sleep=sleeps.append
    )

    assert result == "ok"
    assert attempts["n"] == 3
    assert len(sleeps) == 2


def test_backoff_delays_double_each_time():
    attempts = {"n": 0}

    def fn():
        attempts["n"] += 1
        raise _Retryable("still down")

    sleeps = []
    with pytest.raises(AIUnavailable):
        call_with_retries(
            fn, is_retryable=_is_retryable, max_attempts=3, base_delay=1.0, sleep=sleeps.append
        )

    assert len(sleeps) == 2
    # jitter adds 0-0.5s, so check the base progression rather than exact values
    assert 1.0 <= sleeps[0] < 1.5
    assert 2.0 <= sleeps[1] < 2.5


def test_raises_ai_unavailable_after_exhausting_attempts():
    def fn():
        raise _Retryable("still down")

    with pytest.raises(AIUnavailable):
        call_with_retries(fn, is_retryable=_is_retryable, max_attempts=3, sleep=lambda s: None)


def test_non_retryable_error_propagates_immediately_without_sleeping():
    calls = []
    sleeps = []

    def fn():
        calls.append(1)
        raise ValueError("not retryable")

    with pytest.raises(ValueError):
        call_with_retries(fn, is_retryable=_is_retryable, max_attempts=3, sleep=sleeps.append)

    assert len(calls) == 1
    assert sleeps == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_retry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai'`

- [ ] **Step 3: Write `backend/ai/errors.py`**

```python
class AIUnavailable(Exception):
    """The AI provider could not be reached after retries were exhausted,
    or returned a non-retryable error."""


class AIInvalidResponse(Exception):
    """The AI provider returned a response that failed schema or shape
    validation."""
```

- [ ] **Step 4: Write `backend/ai/retry.py`**

```python
from __future__ import annotations

import random
import time
from typing import Callable, TypeVar

from ai.errors import AIUnavailable

T = TypeVar("T")


def call_with_retries(
    fn: Callable[[], T],
    *,
    is_retryable: Callable[[Exception], bool],
    max_attempts: int = 3,
    base_delay: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Calls fn, retrying exceptions that `is_retryable` accepts, with
    exponential backoff (base_delay * 2**attempt) plus jitter. Raises
    AIUnavailable once max_attempts is exhausted. Non-retryable exceptions
    propagate immediately, unwrapped — this function is provider-agnostic;
    callers decide what counts as transient.
    """
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as exc:
            if not is_retryable(exc):
                raise
            last_error = exc
            if attempt < max_attempts - 1:
                delay = base_delay * (2**attempt) + random.uniform(0, 0.5)
                sleep(delay)
    raise AIUnavailable(str(last_error)) from last_error
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_retry.py -v`
Expected: PASS — `5 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/ai/__init__.py backend/ai/prompts/__init__.py backend/ai/errors.py backend/ai/retry.py backend/tests/test_retry.py
git commit -m "feat(backend): add provider-agnostic retry helper with backoff"
```

- [ ] **Step 7: Write the failing client tests**

Create `backend/tests/test_ai_client.py`:

```python
import pytest

from ai.client import FakeAIClient, Prompt


def _prompt(text: str = "hello") -> Prompt:
    return Prompt(
        system_instruction="system",
        user_content=text,
        response_schema={"type": "OBJECT", "properties": {}},
    )


def test_fake_client_returns_queued_responses_in_order():
    client = FakeAIClient()
    client.queue_response({"a": 1})
    client.queue_response({"a": 2})

    first = client.generate_json(_prompt())
    second = client.generate_json(_prompt())

    assert first == {"a": 1}
    assert second == {"a": 2}


def test_fake_client_records_calls():
    client = FakeAIClient()
    client.queue_response({"a": 1})

    client.generate_json(_prompt("specific text"))

    assert len(client.calls) == 1
    assert client.calls[0].user_content == "specific text"


def test_fake_client_raises_when_queue_is_empty():
    client = FakeAIClient()

    with pytest.raises(AssertionError):
        client.generate_json(_prompt())
```

- [ ] **Step 8: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_ai_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai.client'`

- [ ] **Step 9: Write `backend/ai/client.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Prompt:
    system_instruction: str
    user_content: str
    response_schema: dict[str, Any]
    temperature: float = 0.4
    max_output_tokens: int = 4096


class AIClient(Protocol):
    def generate_json(self, prompt: Prompt) -> dict[str, Any]: ...


class FakeAIClient:
    """Test double. Queue responses with queue_response(); each call to
    generate_json pops one, in order. Raises AssertionError if the queue
    runs dry, so an under-specified test fails loudly instead of hanging.
    """

    def __init__(self) -> None:
        self._queue: list[dict[str, Any]] = []
        self.calls: list[Prompt] = []

    def queue_response(self, response: dict[str, Any]) -> None:
        self._queue.append(response)

    def generate_json(self, prompt: Prompt) -> dict[str, Any]:
        self.calls.append(prompt)
        if not self._queue:
            raise AssertionError("FakeAIClient: no queued response left")
        return self._queue.pop(0)


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

- [ ] **Step 10: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_ai_client.py -v`
Expected: PASS — `3 passed`

- [ ] **Step 11: Commit**

```bash
git add backend/ai/client.py backend/tests/test_ai_client.py
git commit -m "feat(backend): add AIClient protocol, Prompt, and FakeAIClient test double"
```

---

## Task 2: GeminiClient + global AI error handlers

**Files:**
- Create: `backend/ai/gemini_client.py`
- Modify: `backend/main.py`

This task's core logic (retry classification) piggybacks on Task 1's already-tested
`call_with_retries`, so there is no new pure logic to unit test here — the network
call itself is the one thing in this plan that legitimately can't be tested without
hitting a real API. It's verified with a live smoke call in Step 4 instead.

- [ ] **Step 1: Write `backend/ai/gemini_client.py`**

```python
from __future__ import annotations

import json
import logging

from google import genai
from google.genai import errors, types

from ai.client import Prompt
from ai.errors import AIInvalidResponse, AIUnavailable
from ai.retry import call_with_retries
from config import settings

log = logging.getLogger(__name__)

_RETRYABLE_CODES = frozenset({429, 500, 502, 503, 504})


def _is_retryable(exc: Exception) -> bool:
    return isinstance(exc, errors.APIError) and exc.code in _RETRYABLE_CODES


class GeminiClient:
    """AIClient implementation backed by Google Gemini. One instance per
    process — the underlying SDK client is safe to reuse across calls."""

    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def generate_json(self, prompt: Prompt) -> dict:
        def call() -> str:
            response = self._client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt.user_content,
                config=types.GenerateContentConfig(
                    system_instruction=prompt.system_instruction,
                    response_mime_type="application/json",
                    response_schema=prompt.response_schema,
                    temperature=prompt.temperature,
                    max_output_tokens=prompt.max_output_tokens,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            if not response.text:
                raise AIInvalidResponse("Gemini returned an empty response")
            return response.text

        try:
            text = call_with_retries(call, is_retryable=_is_retryable)
        except errors.APIError as exc:
            # Non-retryable APIError (e.g. 400 bad request, 404 unknown
            # model) reaches here unwrapped from call_with_retries, since
            # that helper only wraps the retry-exhaustion case.
            log.warning("Gemini API error (non-retryable): %s", exc)
            raise AIUnavailable(str(exc)) from exc

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise AIInvalidResponse(f"Gemini returned invalid JSON: {exc}") from exc
```

- [ ] **Step 2: Add global exception handlers to `backend/main.py`**

Modify the imports and `create_app` function:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ai.errors import AIInvalidResponse, AIUnavailable
from config import settings
from db.base import Base
from db.session import engine
from models import assessment as _assessment_models  # noqa: F401
from models import user as _user_models  # noqa: F401
from routers import assessment, health, profile, tracks


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

    @app.exception_handler(AIUnavailable)
    def handle_ai_unavailable(request, exc: AIUnavailable):
        return JSONResponse(
            status_code=503,
            content={"detail": {"code": "ai_unavailable", "message": str(exc)}},
        )

    @app.exception_handler(AIInvalidResponse)
    def handle_ai_invalid_response(request, exc: AIInvalidResponse):
        return JSONResponse(
            status_code=502,
            content={"detail": {"code": "ai_invalid_response", "message": str(exc)}},
        )

    app.include_router(health.router)
    app.include_router(profile.router)
    app.include_router(tracks.router)
    app.include_router(assessment.router)
    return app


app = create_app()
```

This references `models.assessment` and `routers.assessment`, which don't exist
yet — that's expected, they're built in Tasks 3 and 7. This step will not import
cleanly until then, so **do not run the server or the test suite yet**; just save
the file and continue to Task 3.

- [ ] **Step 3: Commit**

```bash
git add backend/ai/gemini_client.py backend/main.py
git commit -m "feat(backend): add GeminiClient and global AI error handlers"
```

Note: this commit leaves `main.py` importing modules that don't exist yet
(`models.assessment`, `routers.assessment`). That's an intentional, temporary
broken state inside this plan — Task 3 and Task 7 complete it. If you need a
runnable checkpoint before then, skip this commit and fold Task 2 into Task 7's
commit instead.

- [ ] **Step 4: Live smoke test (after Task 7 makes the app importable again)**

Once Tasks 3–7 are done and `.venv/bin/pytest` passes, come back and run this
manual check with a real `GEMINI_API_KEY` in `backend/.env`:

```bash
cd backend && .venv/bin/python -c "
from ai.client import get_ai_client
from ai.prompts.assessment import build_generation_prompt

client = get_ai_client()
prompt = build_generation_prompt('Python', 'intermediate')
result = client.generate_json(prompt)
print(len(result['questions']), 'questions generated')
print(result['questions'][0])
"
```

Expected: prints a question count between 8 and 12, and a real generated question
dict. This proves the whole chain — config, client construction, schema,
retry wrapper, JSON parsing — works against the live API before it's wired into
the HTTP layer.

---

## Task 3: Track lookup + Assessment models

**Files:**
- Modify: `backend/services/profile_service.py`, `backend/tests/test_profile_service.py`
- Create: `backend/models/assessment.py`
- Test: `backend/tests/test_assessment_models.py`

Plan 1 deliberately left out a single-track lookup (`get_track`) because nothing
called it yet. `POST /api/tracks/{id}/assessment` is that caller — this task adds
it back the same way everything else in this codebase gets added: a failing test
first.

- [ ] **Step 1: Write the failing `get_track` tests**

Append to `backend/tests/test_profile_service.py`:

```python
def test_get_track_returns_the_track(db_session):
    _onboard(db_session)
    created = profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level="beginner")
    )

    fetched = profile_service.get_track(db_session, created.id)

    assert fetched.id == created.id


def test_get_track_unknown_raises(db_session):
    _onboard(db_session)

    with pytest.raises(TrackNotFoundError):
        profile_service.get_track(db_session, 4242)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_profile_service.py -v`
Expected: FAIL — `AttributeError: module 'services.profile_service' has no attribute 'get_track'`

- [ ] **Step 3: Add `get_track` to `backend/services/profile_service.py`**

Append to the end of the file:

```python
def get_track(db: Session, track_id: int) -> LearningTrack:
    track = db.get(LearningTrack, track_id)
    if track is None:
        raise TrackNotFoundError
    return track
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_profile_service.py -v`
Expected: PASS — `16 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/services/profile_service.py backend/tests/test_profile_service.py
git commit -m "feat(backend): add single-track lookup, now that assessment needs it"
```

- [ ] **Step 6: Write the failing model tests**

Create `backend/tests/test_assessment_models.py`:

```python
from models.assessment import Assessment, AssessmentQuestion
from models.user import LearningTrack, User
from services import profile_service
from schemas.profile import ProfileCreate, TrackCreate


def _track(db_session):
    profile_service.create_profile(db_session, ProfileCreate(name="Aryan"))
    return profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level="intermediate")
    )


def test_assessment_and_question_round_trip(db_session):
    track = _track(db_session)

    assessment = Assessment(track_id=track.id, level="intermediate", status="in_progress")
    db_session.add(assessment)
    db_session.commit()

    mcq = AssessmentQuestion(
        assessment_id=assessment.id,
        order_index=0,
        type="mcq",
        topic_tag="loops",
        question="What does `range(3)` produce?",
        options=["0,1,2", "1,2,3", "0,1,2,3", "1,2"],
        correct_option=0,
    )
    descriptive = AssessmentQuestion(
        assessment_id=assessment.id,
        order_index=1,
        type="descriptive",
        topic_tag="oop",
        question="Explain inheritance.",
        expected_points=["base class", "override", "super()"],
    )
    db_session.add_all([mcq, descriptive])
    db_session.commit()

    assert len(assessment.questions) == 2
    # order_by="AssessmentQuestion.order_index" keeps them in question order
    assert [q.order_index for q in assessment.questions] == [0, 1]
    assert assessment.track.topic == "Python"


def test_deleting_track_cascades_to_assessment(db_session):
    track = _track(db_session)
    assessment = Assessment(track_id=track.id, level="intermediate", status="in_progress")
    db_session.add(assessment)
    db_session.commit()
    assessment_id = assessment.id

    db_session.delete(db_session.get(LearningTrack, track.id))
    db_session.commit()

    assert db_session.get(Assessment, assessment_id) is None


def test_deleting_assessment_cascades_to_questions(db_session):
    track = _track(db_session)
    assessment = Assessment(track_id=track.id, level="intermediate", status="in_progress")
    db_session.add(assessment)
    db_session.commit()

    question = AssessmentQuestion(
        assessment_id=assessment.id,
        order_index=0,
        type="mcq",
        topic_tag="loops",
        question="...",
        options=["a", "b", "c", "d"],
        correct_option=1,
    )
    db_session.add(question)
    db_session.commit()
    question_id = question.id

    db_session.delete(assessment)
    db_session.commit()

    assert db_session.get(AssessmentQuestion, question_id) is None
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_assessment_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'models.assessment'`

- [ ] **Step 8: Write `backend/models/assessment.py`**

```python
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from models.user import LearningTrack


class Assessment(Base):
    """One skill assessment attempt for a track. Beginner tracks never get
    one — that path skips straight to roadmap generation."""

    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("learning_tracks.id", ondelete="CASCADE"))
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="in_progress")
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    strengths: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    weaknesses: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    track: Mapped["LearningTrack"] = relationship()
    questions: Mapped[list["AssessmentQuestion"]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
        order_by="AssessmentQuestion.order_index",
    )


class AssessmentQuestion(Base):
    """One question. `options`/`correct_option` are mcq-only; `expected_points`
    is descriptive-only. `score` and `ai_feedback` stay null until submit —
    the Pydantic response schema mirrors this 1:1, so "withheld until
    submit" falls out of the data model for free, no extra serialization
    logic needed."""

    __tablename__ = "assessment_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"))
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    topic_tag: Mapped[str] = mapped_column(String(60), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    correct_option: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_points: Mapped[list | None] = mapped_column(JSON, nullable=True)
    user_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    assessment: Mapped["Assessment"] = relationship(back_populates="questions")
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_assessment_models.py -v`
Expected: PASS — `3 passed`

- [ ] **Step 10: Commit**

```bash
git add backend/models/assessment.py backend/tests/test_assessment_models.py
git commit -m "feat(backend): add Assessment and AssessmentQuestion models"
```

---

## Task 4: Assessment prompts

**Files:**
- Create: `backend/ai/prompts/assessment.py`
- Test: `backend/tests/test_assessment_prompts.py`

Pure functions returning `Prompt` objects — no client, no network, no DB. Tests
check the schema shape and that key facts (topic, level, question count bounds)
actually appear in what gets sent.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_assessment_prompts.py`:

```python
from ai.prompts.assessment import build_generation_prompt, build_grading_prompt


def test_generation_prompt_includes_topic_and_level():
    prompt = build_generation_prompt("Python", "intermediate")

    assert "Python" in prompt.user_content
    assert "intermediate" in prompt.user_content


def test_generation_prompt_advanced_mentions_skipping_fundamentals():
    prompt = build_generation_prompt("Python", "advanced")

    assert "advanced" in prompt.user_content.lower()
    assert "fundamentals" in prompt.user_content.lower()


def test_generation_prompt_schema_bounds_question_count():
    prompt = build_generation_prompt("Python", "intermediate")

    questions_schema = prompt.response_schema["properties"]["questions"]
    assert questions_schema["min_items"] == 8
    assert questions_schema["max_items"] == 12
    assert questions_schema["type"] == "ARRAY"


def test_generation_prompt_schema_item_shape():
    prompt = build_generation_prompt("Python", "intermediate")

    item = prompt.response_schema["properties"]["questions"]["items"]
    assert set(item["required"]) == {"type", "topic_tag", "question"}
    assert item["properties"]["options"]["nullable"] is True
    assert item["properties"]["correct_option"]["nullable"] is True
    assert item["properties"]["expected_points"]["nullable"] is True


def test_grading_prompt_includes_each_question_and_answer():
    items = [
        ("Explain inheritance.", ["base class", "override"], "A subclass extends a base class."),
        ("Explain decorators.", ["wraps a function", "@syntax"], "They wrap functions."),
    ]

    prompt = build_grading_prompt("Python", items)

    for question, _points, answer in items:
        assert question in prompt.user_content
        assert answer in prompt.user_content


def test_grading_prompt_schema_pins_exact_grading_count():
    items = [
        ("Q1", ["p1"], "A1"),
        ("Q2", ["p2"], "A2"),
        ("Q3", ["p3"], "A3"),
    ]

    prompt = build_grading_prompt("Python", items)

    gradings_schema = prompt.response_schema["properties"]["gradings"]
    assert gradings_schema["min_items"] == 3
    assert gradings_schema["max_items"] == 3


def test_grading_prompt_requires_summary():
    prompt = build_grading_prompt("Python", [("Q1", ["p1"], "A1")])

    assert "summary" in prompt.response_schema["required"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_assessment_prompts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai.prompts.assessment'`

- [ ] **Step 3: Write `backend/ai/prompts/assessment.py`**

```python
from __future__ import annotations

from ai.client import Prompt

_QUESTION_ITEM_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "type": {"type": "STRING", "enum": ["mcq", "descriptive"]},
        "topic_tag": {"type": "STRING"},
        "question": {"type": "STRING"},
        "options": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "min_items": 4,
            "max_items": 4,
            "nullable": True,
        },
        "correct_option": {"type": "INTEGER", "nullable": True},
        "expected_points": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "min_items": 2,
            "max_items": 4,
            "nullable": True,
        },
    },
    "required": ["type", "topic_tag", "question"],
}

_GENERATION_SYSTEM = (
    "You are a technical skill assessor for CareerOS. Generate a skill "
    "assessment as strict JSON matching the provided schema. Mix mcq and "
    "descriptive questions covering distinct subtopics of the given topic. "
    "MCQ questions must have exactly 4 options and a zero-indexed "
    "correct_option, and must NOT include expected_points. Descriptive "
    "questions must have 2-4 expected_points describing what a strong "
    "answer would cover, and must NOT include options or correct_option."
)


def build_generation_prompt(topic: str, level: str) -> Prompt:
    """level is the track's declared experience_level — always
    'intermediate' or 'advanced' here, since beginner tracks never reach
    this function (assessment_service rejects them before calling it)."""
    if level == "advanced":
        difficulty = (
            "This is an advanced revision assessment — skip fundamentals "
            "entirely, probe edge cases, internals, and real-world "
            "tradeoffs a working professional would face."
        )
    else:
        difficulty = (
            "This is a standard intermediate assessment — cover the core "
            "working areas of the topic at a practical, hands-on depth "
            "(for a language: syntax, control flow, functions, data "
            "structures, OOP, error handling, common libraries)."
        )

    user_content = (
        f"Topic: {topic}\n"
        f"Declared experience level: {level}\n"
        f"{difficulty}\n"
        "Generate between 8 and 12 questions total, tagged with concise "
        "lowercase topic_tag values (e.g. 'loops', 'oop', 'file_handling')."
    )

    schema = {
        "type": "OBJECT",
        "properties": {
            "questions": {
                "type": "ARRAY",
                "min_items": 8,
                "max_items": 12,
                "items": _QUESTION_ITEM_SCHEMA,
            },
        },
        "required": ["questions"],
    }

    return Prompt(
        system_instruction=_GENERATION_SYSTEM,
        user_content=user_content,
        response_schema=schema,
        temperature=0.6,
        max_output_tokens=4096,
    )


_GRADING_SYSTEM = (
    "You are grading a technical skill assessment for CareerOS. Score each "
    "descriptive answer from 0 to 10 against its expected points: 10 covers "
    "all points with correct depth, 5 is partially correct or shallow, 0 is "
    "wrong or missing. Give one specific sentence of feedback per answer. "
    "Then write a 2-3 sentence overall summary of the candidate's "
    "demonstrated skill across these answers."
)


def build_grading_prompt(
    topic: str, items: list[tuple[str, list[str], str]]
) -> Prompt:
    """items: (question, expected_points, user_answer) tuples. Gradings in
    the response must come back in this same order — the caller zips them
    back positionally rather than relying on the model echoing an id."""
    blocks = []
    for index, (question, expected_points, answer) in enumerate(items):
        blocks.append(
            f"Question {index + 1}: {question}\n"
            f"Expected points: {', '.join(expected_points)}\n"
            f"Candidate's answer: {answer}"
        )

    user_content = (
        f"Topic: {topic}\n\n"
        + "\n\n".join(blocks)
        + f"\n\nReturn exactly {len(items)} gradings, in the same order as "
        "the questions above."
    )

    schema = {
        "type": "OBJECT",
        "properties": {
            "gradings": {
                "type": "ARRAY",
                "min_items": len(items),
                "max_items": len(items),
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "score": {"type": "NUMBER"},
                        "feedback": {"type": "STRING"},
                    },
                    "required": ["score", "feedback"],
                },
            },
            "summary": {"type": "STRING"},
        },
        "required": ["gradings", "summary"],
    }

    return Prompt(
        system_instruction=_GRADING_SYSTEM,
        user_content=user_content,
        response_schema=schema,
        temperature=0.3,
        max_output_tokens=2048,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_assessment_prompts.py -v`
Expected: PASS — `7 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/ai/prompts/assessment.py backend/tests/test_assessment_prompts.py
git commit -m "feat(backend): add assessment generation and grading prompt builders"
```

---

## Task 5: Assessment service — generation, read, autosave

**Files:**
- Create: `backend/schemas/assessment.py`, `backend/services/assessment_service.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_assessment_service.py`

- [ ] **Step 1: Add the `fake_ai` fixture and wire it into `client`**

Read `backend/tests/conftest.py` first, then replace it in full — this adds a
`fake_ai` fixture and overrides `get_ai_client` alongside the existing `get_db`
override:

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

from ai.client import FakeAIClient, get_ai_client  # noqa: E402
from db.base import Base  # noqa: E402
from db.session import get_db  # noqa: E402
from main import app  # noqa: E402
from models import assessment as _assessment_models  # noqa: E402,F401
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
```

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_assessment_service.py`:

```python
import pytest

from ai.client import Prompt
from ai.errors import AIInvalidResponse
from schemas.profile import ProfileCreate, TrackCreate
from services import assessment_service, profile_service
from services.assessment_service import (
    AssessmentNotApplicableError,
    AssessmentNotFoundError,
    QuestionNotFoundError,
)
from schemas.assessment import AnswerSave


def _track(db_session, level="intermediate"):
    profile_service.create_profile(db_session, ProfileCreate(name="Aryan"))
    return profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level=level)
    )


def _generation_response(count=8):
    questions = []
    for i in range(count):
        if i % 2 == 0:
            questions.append(
                {
                    "type": "mcq",
                    "topic_tag": f"tag{i}",
                    "question": f"Q{i}?",
                    "options": ["a", "b", "c", "d"],
                    "correct_option": 1,
                }
            )
        else:
            questions.append(
                {
                    "type": "descriptive",
                    "topic_tag": f"tag{i}",
                    "question": f"Q{i}?",
                    "expected_points": ["point a", "point b"],
                }
            )
    return {"questions": questions}


def test_start_assessment_persists_generated_questions(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(8))

    assessment = assessment_service.start_assessment(db_session, fake_ai, track.id)

    assert assessment.status == "in_progress"
    assert len(assessment.questions) == 8
    assert assessment.questions[0].order_index == 0
    assert fake_ai.calls[0].user_content.find("Python") != -1


def test_start_assessment_rejects_beginner_track(db_session, fake_ai):
    track = _track(db_session, level="beginner")

    with pytest.raises(AssessmentNotApplicableError):
        assessment_service.start_assessment(db_session, fake_ai, track.id)

    assert fake_ai.calls == []


def test_start_assessment_rejects_out_of_range_question_count(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(3))

    with pytest.raises(AIInvalidResponse):
        assessment_service.start_assessment(db_session, fake_ai, track.id)


def test_get_assessment_unknown_raises(db_session):
    with pytest.raises(AssessmentNotFoundError):
        assessment_service.get_assessment(db_session, 4242)


def test_list_assessments_orders_most_recent_first(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(8))
    first = assessment_service.start_assessment(db_session, fake_ai, track.id)
    fake_ai.queue_response(_generation_response(8))
    second = assessment_service.start_assessment(db_session, fake_ai, track.id)

    listed = assessment_service.list_assessments(db_session)

    assert [a.id for a in listed] == [second.id, first.id]


def test_save_answer_stores_the_answer(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(8))
    assessment = assessment_service.start_assessment(db_session, fake_ai, track.id)
    question = assessment.questions[0]

    assessment_service.save_answer(
        db_session, assessment.id, AnswerSave(question_id=question.id, answer="1")
    )

    db_session.refresh(question)
    assert question.user_answer == "1"


def test_save_answer_unknown_question_raises(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(8))
    assessment = assessment_service.start_assessment(db_session, fake_ai, track.id)

    with pytest.raises(QuestionNotFoundError):
        assessment_service.save_answer(
            db_session, assessment.id, AnswerSave(question_id=999999, answer="x")
        )
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_assessment_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.assessment_service'`

- [ ] **Step 4: Write `backend/schemas/assessment.py`**

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

QuestionType = Literal["mcq", "descriptive"]
AssessmentStatus = Literal["in_progress", "completed"]
EstimatedLevel = Literal["foundational", "intermediate", "advanced"]


class AssessmentQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_index: int
    type: QuestionType
    topic_tag: str
    question: str
    options: list[str] | None = None
    correct_option: int | None = None
    expected_points: list[str] | None = None
    user_answer: str | None = None
    score: float | None = None
    ai_feedback: str | None = None


class AssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    track_id: int
    level: str
    status: AssessmentStatus
    started_at: datetime
    completed_at: datetime | None
    score: float | None
    estimated_level: EstimatedLevel | None
    strengths: list[str]
    weaknesses: list[str]
    summary: str | None
    questions: list[AssessmentQuestionOut]


class AnswerSave(BaseModel):
    question_id: int
    answer: str
```

- [ ] **Step 5: Write `backend/services/assessment_service.py`**

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.client import AIClient
from ai.errors import AIInvalidResponse
from ai.prompts.assessment import build_generation_prompt
from models.assessment import Assessment, AssessmentQuestion
from schemas.assessment import AnswerSave
from services import profile_service


class AssessmentNotApplicableError(Exception):
    """Beginner tracks skip assessment entirely."""


class AssessmentNotFoundError(Exception):
    pass


class QuestionNotFoundError(Exception):
    pass


class AssessmentAlreadySubmittedError(Exception):
    pass


def start_assessment(db: Session, ai_client: AIClient, track_id: int) -> Assessment:
    track = profile_service.get_track(db, track_id)
    if track.experience_level == "beginner":
        raise AssessmentNotApplicableError

    prompt = build_generation_prompt(track.topic, track.experience_level)
    result = ai_client.generate_json(prompt)
    questions_data = result.get("questions", [])
    if not (8 <= len(questions_data) <= 12):
        raise AIInvalidResponse(f"Expected 8-12 questions, got {len(questions_data)}")

    assessment = Assessment(
        track_id=track.id, level=track.experience_level, status="in_progress"
    )
    db.add(assessment)
    db.flush()  # assigns assessment.id so the child rows below can reference it

    for index, q in enumerate(questions_data):
        db.add(
            AssessmentQuestion(
                assessment_id=assessment.id,
                order_index=index,
                type=q["type"],
                topic_tag=q["topic_tag"],
                question=q["question"],
                options=q.get("options"),
                correct_option=q.get("correct_option"),
                expected_points=q.get("expected_points"),
            )
        )

    db.commit()
    db.refresh(assessment)
    return assessment


def get_assessment(db: Session, assessment_id: int) -> Assessment:
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise AssessmentNotFoundError
    return assessment


def list_assessments(db: Session) -> list[Assessment]:
    return list(db.scalars(select(Assessment).order_by(Assessment.started_at.desc())))


def save_answer(db: Session, assessment_id: int, payload: AnswerSave) -> None:
    assessment = get_assessment(db, assessment_id)
    if assessment.status == "completed":
        raise AssessmentAlreadySubmittedError

    question = next(
        (q for q in assessment.questions if q.id == payload.question_id), None
    )
    if question is None:
        raise QuestionNotFoundError

    question.user_answer = payload.answer
    db.commit()
```

`submit_assessment` and its scoring helpers land in Task 6 — this file grows
rather than getting replaced.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_assessment_service.py -v`
Expected: PASS — `7 passed`

Run the full suite too, since `conftest.py` changed:

Run: `cd backend && .venv/bin/pytest -v`
Expected: PASS — `49 passed` (22 from Plan 1 + 5 retry + 3 ai_client + 2 get_track
+ 3 assessment_models + 7 assessment_prompts + 7 assessment_service)

- [ ] **Step 7: Commit**

```bash
git add backend/schemas/assessment.py backend/services/assessment_service.py backend/tests/conftest.py backend/tests/test_assessment_service.py
git commit -m "feat(backend): add assessment generation, read, and autosave"
```

---

## Task 6: Assessment service — submit, scoring, banding, grouping

**Files:**
- Modify: `backend/services/assessment_service.py`, `backend/tests/test_assessment_service.py`

`score_mcq_question`, `band_level`, and `group_by_topic` are the pure, directly
testable derived-logic functions from spec section 6 — no DB, no AI client, just
data in and data out. `submit_assessment` orchestrates them plus one batched AI
call for descriptive grading.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_assessment_service.py`:

```python
from models.assessment import AssessmentQuestion
from services.assessment_service import (
    AssessmentAlreadySubmittedError,
    band_level,
    group_by_topic,
    score_mcq_question,
)


# ── score_mcq_question — pure ────────────────────────────────────────────


def _mcq(user_answer=None, correct_option=1, options=("a", "b", "c", "d")):
    return AssessmentQuestion(
        type="mcq",
        topic_tag="x",
        question="q",
        options=list(options),
        correct_option=correct_option,
        user_answer=user_answer,
    )


def test_score_mcq_correct_answer():
    question = _mcq(user_answer="1", correct_option=1)

    score_mcq_question(question)

    assert question.score == 10.0
    assert question.ai_feedback == "Correct."


def test_score_mcq_incorrect_answer_names_the_right_option():
    question = _mcq(user_answer="0", correct_option=1, options=("a", "b", "c", "d"))

    score_mcq_question(question)

    assert question.score == 0.0
    assert "b" in question.ai_feedback


def test_score_mcq_unanswered():
    question = _mcq(user_answer=None)

    score_mcq_question(question)

    assert question.score == 0.0
    assert question.ai_feedback == "Not answered."


def test_score_mcq_malformed_answer_scores_zero_without_crashing():
    question = _mcq(user_answer="not-a-number")

    score_mcq_question(question)

    assert question.score == 0.0


# ── band_level — pure ─────────────────────────────────────────────────────


def test_band_level_boundaries():
    assert band_level(39) == "foundational"
    assert band_level(40) == "intermediate"
    assert band_level(69) == "intermediate"
    assert band_level(70) == "advanced"


# ── group_by_topic — pure ────────────────────────────────────────────────


def test_group_by_topic_strengths_and_weaknesses():
    def q(tag, score):
        question = _mcq()
        question.topic_tag = tag
        question.score = score
        return question

    questions = [
        q("loops", 8),
        q("loops", 9),  # mean 8.5 -> strength
        q("oop", 3),
        q("oop", 2),  # mean 2.5 -> weakness
        q("files", 5),  # mean 5 -> neither
    ]

    strengths, weaknesses = group_by_topic(questions)

    assert strengths == ["loops"]
    assert weaknesses == ["oop"]


# ── submit_assessment — orchestration ────────────────────────────────────


def _start_with_mix(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(
        {
            "questions": [
                {
                    "type": "mcq",
                    "topic_tag": "loops",
                    "question": "Q0",
                    "options": ["a", "b", "c", "d"],
                    "correct_option": 1,
                },
                {
                    "type": "descriptive",
                    "topic_tag": "oop",
                    "question": "Explain inheritance.",
                    "expected_points": ["base class", "override"],
                },
                *[
                    {
                        "type": "mcq",
                        "topic_tag": f"tag{i}",
                        "question": f"Q{i}",
                        "options": ["a", "b", "c", "d"],
                        "correct_option": 0,
                    }
                    for i in range(6)
                ],
            ]
        }
    )
    return assessment_service.start_assessment(db_session, fake_ai, track.id)


def test_submit_scores_mcq_and_grades_descriptive_via_one_ai_call(db_session, fake_ai):
    assessment = _start_with_mix(db_session, fake_ai)
    mcq_question = assessment.questions[0]
    descriptive_question = assessment.questions[1]

    assessment_service.save_answer(
        db_session, assessment.id, AnswerSave(question_id=mcq_question.id, answer="1")
    )
    assessment_service.save_answer(
        db_session,
        assessment.id,
        AnswerSave(
            question_id=descriptive_question.id,
            answer="A subclass extends a base class and can override methods.",
        ),
    )
    for question in assessment.questions[2:]:
        assessment_service.save_answer(
            db_session, assessment.id, AnswerSave(question_id=question.id, answer="0")
        )

    fake_ai.queue_response(
        {
            "gradings": [{"score": 9.0, "feedback": "Strong answer covering both points."}],
            "summary": "Solid grasp of OOP fundamentals.",
        }
    )

    result = assessment_service.submit_assessment(db_session, fake_ai, assessment.id)

    assert result.status == "completed"
    assert result.completed_at is not None
    assert result.summary == "Solid grasp of OOP fundamentals."
    # 8 questions, 7 correct mcq (score 10) + 1 descriptive (score 9) = mean 9.875 * 10
    assert result.score == pytest.approx(98.75, abs=0.1)
    assert result.estimated_level == "advanced"
    # Grading call only covered the one descriptive question, not all 8.
    grading_call = fake_ai.calls[-1]
    assert grading_call.user_content.count("Question ") == 1


def test_submit_skips_ai_call_when_no_descriptive_answers_given(db_session, fake_ai):
    assessment = _start_with_mix(db_session, fake_ai)
    # Answer nothing at all.

    calls_before = len(fake_ai.calls)
    result = assessment_service.submit_assessment(db_session, fake_ai, assessment.id)

    assert len(fake_ai.calls) == calls_before  # no grading call was made
    assert result.status == "completed"
    assert result.score == 0.0
    assert result.summary == "Assessment completed."


def test_submit_twice_raises(db_session, fake_ai):
    assessment = _start_with_mix(db_session, fake_ai)
    fake_ai.queue_response({"gradings": [], "summary": "done"})
    # No descriptive answers given, so no grading call is actually made —
    # queue is harmless leftover, submit still succeeds on the mcq-only path.
    assessment_service.submit_assessment(db_session, fake_ai, assessment.id)

    with pytest.raises(AssessmentAlreadySubmittedError):
        assessment_service.submit_assessment(db_session, fake_ai, assessment.id)


def test_save_answer_after_submit_raises(db_session, fake_ai):
    assessment = _start_with_mix(db_session, fake_ai)
    assessment_service.submit_assessment(db_session, fake_ai, assessment.id)

    with pytest.raises(AssessmentAlreadySubmittedError):
        assessment_service.save_answer(
            db_session,
            assessment.id,
            AnswerSave(question_id=assessment.questions[0].id, answer="1"),
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_assessment_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'band_level' from 'services.assessment_service'`

- [ ] **Step 3: Append the scoring, banding, grouping, and submit logic**

Add these imports to the top of `backend/services/assessment_service.py`,
replacing the existing import block:

```python
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.client import AIClient
from ai.errors import AIInvalidResponse
from ai.prompts.assessment import build_generation_prompt, build_grading_prompt
from models.assessment import Assessment, AssessmentQuestion
from schemas.assessment import AnswerSave
from services import profile_service
```

Then append to the end of the file:

```python
def score_mcq_question(question: AssessmentQuestion) -> None:
    """Mutates question.score and question.ai_feedback in place."""
    if question.user_answer is None:
        question.score = 0.0
        question.ai_feedback = "Not answered."
        return

    try:
        selected = int(question.user_answer)
    except ValueError:
        selected = None

    if selected == question.correct_option:
        question.score = 10.0
        question.ai_feedback = "Correct."
    else:
        correct_text = question.options[question.correct_option]
        question.score = 0.0
        question.ai_feedback = f"Incorrect. The correct answer was: {correct_text}"


def band_level(score: float) -> str:
    if score < 40:
        return "foundational"
    if score < 70:
        return "intermediate"
    return "advanced"


def group_by_topic(questions: list[AssessmentQuestion]) -> tuple[list[str], list[str]]:
    """Groups scored questions by topic_tag; mean >= 7 is a strength,
    mean <= 4 is a weakness, otherwise the tag is neither."""
    by_tag: dict[str, list[float]] = defaultdict(list)
    for question in questions:
        by_tag[question.topic_tag].append(question.score)

    strengths: list[str] = []
    weaknesses: list[str] = []
    for tag, scores in by_tag.items():
        mean = sum(scores) / len(scores)
        if mean >= 7:
            strengths.append(tag)
        elif mean <= 4:
            weaknesses.append(tag)
    return strengths, weaknesses


def submit_assessment(db: Session, ai_client: AIClient, assessment_id: int) -> Assessment:
    assessment = get_assessment(db, assessment_id)
    if assessment.status == "completed":
        raise AssessmentAlreadySubmittedError

    descriptive_to_grade: list[AssessmentQuestion] = []

    for question in assessment.questions:
        if question.type == "mcq":
            score_mcq_question(question)
        elif question.user_answer and question.user_answer.strip():
            descriptive_to_grade.append(question)
        else:
            question.score = 0.0
            question.ai_feedback = "Not answered."

    summary = "Assessment completed."
    if descriptive_to_grade:
        prompt = build_grading_prompt(
            assessment.track.topic,
            [
                (q.question, q.expected_points, q.user_answer)
                for q in descriptive_to_grade
            ],
        )
        result = ai_client.generate_json(prompt)
        gradings = result.get("gradings", [])
        if len(gradings) != len(descriptive_to_grade):
            raise AIInvalidResponse(
                f"Expected {len(descriptive_to_grade)} gradings, got {len(gradings)}"
            )
        for question, grading in zip(descriptive_to_grade, gradings):
            question.score = float(grading["score"])
            question.ai_feedback = grading["feedback"]
        summary = result.get("summary", summary)

    all_scores = [q.score for q in assessment.questions]
    final_score = (sum(all_scores) / len(all_scores)) * 10 if all_scores else 0.0

    assessment.score = round(final_score, 1)
    assessment.estimated_level = band_level(final_score)
    assessment.strengths, assessment.weaknesses = group_by_topic(assessment.questions)
    assessment.summary = summary
    assessment.status = "completed"
    assessment.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(assessment)
    return assessment
```

Also add the guard to the top of `save_answer` (it already checks
`assessment.status == "completed"` from Task 5 — no change needed there, but
double check it's still in place since `test_save_answer_after_submit_raises`
depends on it).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_assessment_service.py -v`
Expected: PASS — `17 passed`

Run the full suite:

Run: `cd backend && .venv/bin/pytest -v`
Expected: PASS — `59 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/services/assessment_service.py backend/tests/test_assessment_service.py
git commit -m "feat(backend): add assessment submit with mcq scoring, AI grading, banding, grouping"
```

---

## Task 7: Assessment router

**Files:**
- Create: `backend/routers/assessment.py`
- Test: `backend/tests/test_assessment_api.py`

This is the task that makes `main.py` (edited back in Task 2) importable again —
it creates `routers/assessment.py`, which Task 2's import line already expects.

- [ ] **Step 1: Write the failing API tests**

Create `backend/tests/test_assessment_api.py`:

```python
def _onboard_and_track(client, level="intermediate"):
    client.post("/api/profile", json={"name": "Aryan"})
    track = client.post(
        "/api/tracks", json={"topic": "Python", "experience_level": level}
    )
    return track.json()["id"]


def _generation_payload(count=8):
    questions = []
    for i in range(count):
        if i == 0:
            questions.append(
                {
                    "type": "mcq",
                    "topic_tag": "loops",
                    "question": "Q0?",
                    "options": ["a", "b", "c", "d"],
                    "correct_option": 1,
                }
            )
        else:
            questions.append(
                {
                    "type": "mcq",
                    "topic_tag": f"tag{i}",
                    "question": f"Q{i}?",
                    "options": ["a", "b", "c", "d"],
                    "correct_option": 0,
                }
            )
    return {"questions": questions}


def test_start_assessment_returns_201_with_questions(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload())

    response = client.post(f"/api/tracks/{track_id}/assessment")

    assert response.status_code == 201
    body = response.json()
    assert len(body["questions"]) == 8
    # correct_option is populated in the DB immediately at generation time,
    # but to_assessment_out withholds it from the response until the
    # assessment is completed — this is the reveal-gating from Task 7 Step 3.
    assert body["questions"][0]["correct_option"] is None
    assert body["questions"][0]["score"] is None


def test_start_assessment_on_beginner_track_returns_400(client):
    track_id = _onboard_and_track(client, level="beginner")

    response = client.post(f"/api/tracks/{track_id}/assessment")

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "assessment_not_applicable"


def test_start_assessment_unknown_track_returns_404(client):
    client.post("/api/profile", json={"name": "Aryan"})

    response = client.post("/api/tracks/999/assessment")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "track_not_found"


def test_get_assessment_unknown_returns_404(client):
    response = client.get("/api/assessments/999")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "assessment_not_found"


def test_full_lifecycle_answer_and_submit(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload())
    started = client.post(f"/api/tracks/{track_id}/assessment").json()
    assessment_id = started["id"]

    for question in started["questions"]:
        answer = "1" if question["topic_tag"] == "loops" else "0"
        saved = client.patch(
            f"/api/assessments/{assessment_id}/answers",
            json={"question_id": question["id"], "answer": answer},
        )
        assert saved.status_code == 204

    submitted = client.post(f"/api/assessments/{assessment_id}/submit")

    assert submitted.status_code == 200
    body = submitted.json()
    assert body["status"] == "completed"
    assert body["score"] == 100.0
    # After submit, correct_option is revealed — the DB column is now set.
    assert body["questions"][0]["correct_option"] == 1
    assert body["questions"][0]["score"] == 10.0


def test_submit_unknown_assessment_returns_404(client):
    response = client.post("/api/assessments/999/submit")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "assessment_not_found"


def test_submit_twice_returns_409(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload())
    started = client.post(f"/api/tracks/{track_id}/assessment").json()
    client.post(f"/api/assessments/{started['id']}/submit")

    response = client.post(f"/api/assessments/{started['id']}/submit")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "assessment_already_submitted"


def test_list_assessments_returns_history(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload())
    client.post(f"/api/tracks/{track_id}/assessment")

    response = client.get("/api/assessments")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_answer_unknown_question_returns_404(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload())
    started = client.post(f"/api/tracks/{track_id}/assessment").json()

    response = client.patch(
        f"/api/assessments/{started['id']}/answers",
        json={"question_id": 999999, "answer": "x"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "question_not_found"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_assessment_api.py -v`
Expected: FAIL — collection error, `ModuleNotFoundError: No module named 'routers.assessment'`
(this is also why `main.py` has been unimportable since Task 2 — that's expected)

- [ ] **Step 3: Add reveal-gated serialization to `assessment_service.py`**

`correct_option` and `expected_points` are written to the DB immediately at
generation time (in `start_assessment`, straight from the AI response) — they
are not naturally null before submit the way `score`/`ai_feedback` are. Spec
section 7 says these fields are "withheld from every response until after
submit," which is a rule about what gets **serialized**, not what gets
**stored**. A plain `from_attributes=True` mapping would leak the answer key
in the very first response. `test_start_assessment_returns_201_with_questions`
above already asserts the correct (hidden) behavior — this step is what makes
it true.

Add this import to the top of `backend/services/assessment_service.py`,
replacing the existing `from schemas.assessment import AnswerSave` line:

```python
from schemas.assessment import AnswerSave, AssessmentOut, AssessmentQuestionOut
```

Append these two functions to the end of the file:

```python
def _question_out(question: AssessmentQuestion, reveal: bool) -> AssessmentQuestionOut:
    return AssessmentQuestionOut(
        id=question.id,
        order_index=question.order_index,
        type=question.type,
        topic_tag=question.topic_tag,
        question=question.question,
        options=question.options,
        correct_option=question.correct_option if reveal else None,
        expected_points=question.expected_points if reveal else None,
        user_answer=question.user_answer,
        score=question.score,
        ai_feedback=question.ai_feedback,
    )


def to_assessment_out(assessment: Assessment) -> AssessmentOut:
    """The only place that decides what a client is allowed to see. Options
    (the 4 mcq choices) are always visible — a question is unanswerable
    without them. The answer key (correct_option, expected_points) is only
    revealed once the assessment is completed."""
    reveal = assessment.status == "completed"
    return AssessmentOut(
        id=assessment.id,
        track_id=assessment.track_id,
        level=assessment.level,
        status=assessment.status,
        started_at=assessment.started_at,
        completed_at=assessment.completed_at,
        score=assessment.score,
        estimated_level=assessment.estimated_level,
        strengths=assessment.strengths,
        weaknesses=assessment.weaknesses,
        summary=assessment.summary,
        questions=[_question_out(q, reveal) for q in assessment.questions],
    )
```

- [ ] **Step 4: Write `backend/routers/assessment.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ai.client import AIClient, get_ai_client
from db.session import get_db
from schemas.assessment import AnswerSave, AssessmentOut
from services import assessment_service
from services.assessment_service import (
    AssessmentAlreadySubmittedError,
    AssessmentNotApplicableError,
    AssessmentNotFoundError,
    QuestionNotFoundError,
)
from services.profile_service import TrackNotFoundError

router = APIRouter(tags=["assessment"])

_TRACK_MISSING = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "track_not_found", "message": "That learning track does not exist."},
)
_ASSESSMENT_MISSING = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "assessment_not_found", "message": "That assessment does not exist."},
)
_QUESTION_MISSING = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "question_not_found", "message": "That question does not exist."},
)
_ALREADY_SUBMITTED = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail={
        "code": "assessment_already_submitted",
        "message": "This assessment has already been submitted.",
    },
)
_NOT_APPLICABLE = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail={
        "code": "assessment_not_applicable",
        "message": "Beginner tracks skip assessment and go straight to the roadmap.",
    },
)


@router.post(
    "/api/tracks/{track_id}/assessment",
    response_model=AssessmentOut,
    status_code=status.HTTP_201_CREATED,
)
def start_assessment(
    track_id: int,
    db: Session = Depends(get_db),
    ai_client: AIClient = Depends(get_ai_client),
):
    try:
        assessment = assessment_service.start_assessment(db, ai_client, track_id)
        return assessment_service.to_assessment_out(assessment)
    except TrackNotFoundError:
        raise _TRACK_MISSING
    except AssessmentNotApplicableError:
        raise _NOT_APPLICABLE


@router.get("/api/assessments", response_model=list[AssessmentOut])
def list_assessments(db: Session = Depends(get_db)):
    return [
        assessment_service.to_assessment_out(a)
        for a in assessment_service.list_assessments(db)
    ]


@router.get("/api/assessments/{assessment_id}", response_model=AssessmentOut)
def read_assessment(assessment_id: int, db: Session = Depends(get_db)):
    try:
        assessment = assessment_service.get_assessment(db, assessment_id)
        return assessment_service.to_assessment_out(assessment)
    except AssessmentNotFoundError:
        raise _ASSESSMENT_MISSING


@router.patch("/api/assessments/{assessment_id}/answers", status_code=status.HTTP_204_NO_CONTENT)
def save_answer(assessment_id: int, payload: AnswerSave, db: Session = Depends(get_db)):
    try:
        assessment_service.save_answer(db, assessment_id, payload)
    except AssessmentNotFoundError:
        raise _ASSESSMENT_MISSING
    except QuestionNotFoundError:
        raise _QUESTION_MISSING
    except AssessmentAlreadySubmittedError:
        raise _ALREADY_SUBMITTED


@router.post("/api/assessments/{assessment_id}/submit", response_model=AssessmentOut)
def submit_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    ai_client: AIClient = Depends(get_ai_client),
):
    try:
        assessment = assessment_service.submit_assessment(db, ai_client, assessment_id)
        return assessment_service.to_assessment_out(assessment)
    except AssessmentNotFoundError:
        raise _ASSESSMENT_MISSING
    except AssessmentAlreadySubmittedError:
        raise _ALREADY_SUBMITTED
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_assessment_api.py -v`
Expected: PASS — `9 passed`

Run the full suite — this is the first point since Task 2 where `main.py`
imports cleanly:

Run: `cd backend && .venv/bin/pytest -v`
Expected: PASS — `68 passed`

- [ ] **Step 6: Verify the server boots with all routes**

```bash
cd backend && rm -f careeros.db careeros.db-wal careeros.db-shm
.venv/bin/uvicorn main:app --port 8000 > /tmp/careeros_backend_smoke.log 2>&1 &
UVICORN_PID=$!
sleep 3
curl -s localhost:8000/health
echo
curl -s localhost:8000/openapi.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('\n'.join(sorted(d['paths'].keys())))"
kill $UVICORN_PID 2>/dev/null
wait $UVICORN_PID 2>/dev/null
rm -f careeros.db careeros.db-wal careeros.db-shm
```

Expected: `{"status":"ok"}` plus the full route list including
`/api/tracks/{track_id}/assessment`, `/api/assessments`, and
`/api/assessments/{assessment_id}` / `/answers` / `/submit`.

- [ ] **Step 7: Commit**

```bash
git add backend/routers/assessment.py backend/services/assessment_service.py backend/tests/test_assessment_api.py
git commit -m "feat(backend): add assessment router with reveal-gated serialization"
```

- [ ] **Step 8: Now run the Task 2 live smoke test**

Task 2's Step 4 was deferred until the app was importable — it is now. Run it:

```bash
cd backend && .venv/bin/python -c "
from ai.client import get_ai_client
from ai.prompts.assessment import build_generation_prompt

client = get_ai_client()
prompt = build_generation_prompt('Python', 'intermediate')
result = client.generate_json(prompt)
print(len(result['questions']), 'questions generated')
print(result['questions'][0])
"
```

Expected: a real question count between 8 and 12 and a real question dict,
printed from an actual Gemini call. If this fails with `AIUnavailable`, check
that `backend/.env` has a working `GEMINI_API_KEY`.

---

## Task 8: Frontend — types, API client, hooks

**Files:**
- Modify: `frontend/src/types/index.ts`
- Create: `frontend/src/services/api/assessment.ts`, `frontend/src/hooks/useAssessment.ts`

No new Vitest tests here — this mirrors Plan 1 Task 9, which established that
thin API-client wrappers and TanStack Query hooks are verified by the TypeScript
build plus the manual browser walkthrough in Task 10, not unit-tested in
isolation.

- [ ] **Step 1: Add assessment types to `frontend/src/types/index.ts`**

Append to the end of the file:

```ts
export type QuestionType = "mcq" | "descriptive";
export type AssessmentStatus = "in_progress" | "completed";
export type EstimatedLevel = "foundational" | "intermediate" | "advanced";

export interface AssessmentQuestion {
  id: number;
  order_index: number;
  type: QuestionType;
  topic_tag: string;
  question: string;
  options: string[] | null;
  correct_option: number | null;
  expected_points: string[] | null;
  user_answer: string | null;
  score: number | null;
  ai_feedback: string | null;
}

export interface Assessment {
  id: number;
  track_id: number;
  level: ExperienceLevel;
  status: AssessmentStatus;
  started_at: string;
  completed_at: string | null;
  score: number | null;
  estimated_level: EstimatedLevel | null;
  strengths: string[];
  weaknesses: string[];
  summary: string | null;
  questions: AssessmentQuestion[];
}
```

- [ ] **Step 2: Write `frontend/src/services/api/assessment.ts`**

```ts
import { api } from "@/services/api/client";
import type { Assessment } from "@/types";

export const startAssessment = (trackId: number) =>
  api<Assessment>(`/api/tracks/${trackId}/assessment`, { method: "POST" });

export const getAssessment = (assessmentId: number) =>
  api<Assessment>(`/api/assessments/${assessmentId}`);

export const saveAnswer = (assessmentId: number, questionId: number, answer: string) =>
  api<null>(`/api/assessments/${assessmentId}/answers`, {
    method: "PATCH",
    body: JSON.stringify({ question_id: questionId, answer }),
  });

export const submitAssessment = (assessmentId: number) =>
  api<Assessment>(`/api/assessments/${assessmentId}/submit`, { method: "POST" });
```

- [ ] **Step 3: Write `frontend/src/hooks/useAssessment.ts`**

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getAssessment,
  saveAnswer,
  startAssessment,
  submitAssessment,
} from "@/services/api/assessment";

export const assessmentKey = (id: number) => ["assessment", id] as const;

export function useAssessment(assessmentId: number) {
  return useQuery({
    queryKey: assessmentKey(assessmentId),
    queryFn: () => getAssessment(assessmentId),
  });
}

export function useStartAssessment() {
  return useMutation({ mutationFn: (trackId: number) => startAssessment(trackId) });
}

export function useSaveAnswer(assessmentId: number) {
  return useMutation({
    mutationFn: ({ questionId, answer }: { questionId: number; answer: string }) =>
      saveAnswer(assessmentId, questionId, answer),
  });
}

export function useSubmitAssessment(assessmentId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => submitAssessment(assessmentId),
    onSuccess: (data) => queryClient.setQueryData(assessmentKey(assessmentId), data),
  });
}
```

- [ ] **Step 4: Verify it compiles**

Run: `cd frontend && npm run build`
Expected: `✓ built in ...` — no TypeScript errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/services/api/assessment.ts frontend/src/hooks/useAssessment.ts
git commit -m "feat(frontend): add assessment types, API client, and data hooks"
```

---

## Task 9: Frontend — assessment UI and page

**Files:**
- Create: `frontend/src/components/ui/textarea.tsx`, `frontend/src/components/assessment/QuestionCard.tsx`, `frontend/src/components/assessment/McqOptions.tsx`, `frontend/src/components/assessment/DescriptiveAnswer.tsx`, `frontend/src/components/assessment/ResultSummary.tsx`, `frontend/src/pages/AssessmentPage.tsx`
- Modify: `frontend/src/App.tsx`

Presentational components — verified by build and by eye in the browser, same as
Plan 1 Task 8, not by Vitest.

- [ ] **Step 1: Write `frontend/src/components/ui/textarea.tsx`**

```bash
mkdir -p frontend/src/components/assessment
```

```tsx
import type { TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export function Textarea({
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "min-h-32 w-full resize-y rounded-lg border border-line bg-surface px-3.5 py-3 text-sm",
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

- [ ] **Step 2: Write `frontend/src/components/assessment/QuestionCard.tsx`**

```tsx
import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import type { AssessmentQuestion } from "@/types";

interface QuestionCardProps {
  question: AssessmentQuestion;
  index: number;
  total: number;
  children: ReactNode;
}

export function QuestionCard({ question, index, total, children }: QuestionCardProps) {
  return (
    <Card className="space-y-5">
      <div className="flex items-center justify-between text-sm text-text-secondary">
        <span>
          Question {index + 1} of {total}
        </span>
        <span className="rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-medium text-accent">
          {question.topic_tag}
        </span>
      </div>
      <p className="text-lg font-medium text-text-primary">{question.question}</p>
      {children}
    </Card>
  );
}
```

- [ ] **Step 3: Write `frontend/src/components/assessment/McqOptions.tsx`**

```tsx
import { cn } from "@/lib/cn";

interface McqOptionsProps {
  options: string[];
  selected: number | null;
  onSelect: (index: number) => void;
}

export function McqOptions({ options, selected, onSelect }: McqOptionsProps) {
  return (
    <div className="grid gap-2">
      {options.map((option, index) => (
        <button
          key={index}
          type="button"
          aria-pressed={selected === index}
          onClick={() => onSelect(index)}
          className={cn(
            "rounded-lg border px-4 py-3 text-left text-sm transition-colors duration-fast",
            selected === index
              ? "border-accent bg-accent-soft text-accent"
              : "border-line bg-surface text-text-primary hover:bg-surface-hover",
          )}
        >
          {option}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Write `frontend/src/components/assessment/DescriptiveAnswer.tsx`**

```tsx
import { Textarea } from "@/components/ui/textarea";

interface DescriptiveAnswerProps {
  value: string;
  onChange: (value: string) => void;
  onBlur: () => void;
}

export function DescriptiveAnswer({ value, onChange, onBlur }: DescriptiveAnswerProps) {
  return (
    <Textarea
      value={value}
      onChange={(event) => onChange(event.target.value)}
      onBlur={onBlur}
      placeholder="Type your answer…"
      aria-label="Your answer"
    />
  );
}
```

- [ ] **Step 5: Write `frontend/src/components/assessment/ResultSummary.tsx`**

```tsx
import { Award, TrendingDown, TrendingUp } from "lucide-react";

import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/cn";
import type { Assessment } from "@/types";

const LEVEL_LABEL: Record<string, string> = {
  foundational: "Foundational",
  intermediate: "Intermediate",
  advanced: "Advanced",
};

export function ResultSummary({ assessment }: { assessment: Assessment }) {
  return (
    <div className="space-y-6">
      <Card className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-text-secondary">Your score</p>
            <p className="text-4xl font-semibold text-text-primary">
              {Math.round(assessment.score ?? 0)}
              <span className="text-lg text-text-secondary">/100</span>
            </p>
          </div>
          {assessment.estimated_level && (
            <span className="flex items-center gap-1.5 rounded-full bg-accent-soft px-3 py-1.5 text-sm font-medium text-accent">
              <Award className="size-4" />
              {LEVEL_LABEL[assessment.estimated_level]}
            </span>
          )}
        </div>
        {assessment.summary && (
          <p className="text-sm text-text-secondary">{assessment.summary}</p>
        )}
      </Card>

      {(assessment.strengths.length > 0 || assessment.weaknesses.length > 0) && (
        <div className="grid gap-4 sm:grid-cols-2">
          {assessment.strengths.length > 0 && (
            <Card>
              <CardTitle className="flex items-center gap-1.5 text-success">
                <TrendingUp className="size-4" /> Strengths
              </CardTitle>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {assessment.strengths.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full bg-success/10 px-2.5 py-0.5 text-xs font-medium text-success"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </Card>
          )}
          {assessment.weaknesses.length > 0 && (
            <Card>
              <CardTitle className="flex items-center gap-1.5 text-danger">
                <TrendingDown className="size-4" /> Needs work
              </CardTitle>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {assessment.weaknesses.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full bg-danger/10 px-2.5 py-0.5 text-xs font-medium text-danger"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-text-secondary">Question breakdown</h3>
        {assessment.questions.map((question, index) => (
          <Card key={question.id} className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-text-primary">
                Question {index + 1}
              </span>
              <span
                className={cn(
                  "text-sm font-semibold",
                  (question.score ?? 0) >= 7
                    ? "text-success"
                    : (question.score ?? 0) >= 4
                      ? "text-warning"
                      : "text-danger",
                )}
              >
                {question.score ?? 0}/10
              </span>
            </div>
            <p className="text-sm text-text-primary">{question.question}</p>
            <CardDescription>
              Your answer:{" "}
              {question.type === "mcq" && question.options && question.user_answer !== null
                ? question.options[Number(question.user_answer)]
                : question.user_answer || "Not answered"}
            </CardDescription>
            {question.type === "mcq" &&
              question.correct_option !== null &&
              question.options && (
                <CardDescription>
                  Correct answer: {question.options[question.correct_option]}
                </CardDescription>
              )}
            {question.ai_feedback && (
              <CardDescription className="text-text-primary">
                {question.ai_feedback}
              </CardDescription>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Write `frontend/src/pages/AssessmentPage.tsx`**

```tsx
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";

import { DescriptiveAnswer } from "@/components/assessment/DescriptiveAnswer";
import { McqOptions } from "@/components/assessment/McqOptions";
import { QuestionCard } from "@/components/assessment/QuestionCard";
import { ResultSummary } from "@/components/assessment/ResultSummary";
import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";
import { Button } from "@/components/ui/button";
import { useAssessment, useSaveAnswer, useSubmitAssessment } from "@/hooks/useAssessment";

export default function AssessmentPage() {
  const { id } = useParams<{ id: string }>();
  const assessmentId = Number(id);

  const { data: assessment, isPending } = useAssessment(assessmentId);
  const saveAnswer = useSaveAnswer(assessmentId);
  const submitAssessment = useSubmitAssessment(assessmentId);

  const [index, setIndex] = useState(0);
  const [drafts, setDrafts] = useState<Record<number, string>>({});

  if (isPending || !assessment) {
    return (
      <AppShell>
        <div className="grid place-items-center py-24">
          <Loader2 className="size-6 animate-spin text-text-muted" />
        </div>
      </AppShell>
    );
  }

  if (assessment.status === "completed") {
    return (
      <AppShell>
        <TopBar title="Assessment results" subtitle={`${assessment.level} level`} />
        <ResultSummary assessment={assessment} />
      </AppShell>
    );
  }

  const question = assessment.questions[index];
  const draft = drafts[question.id] ?? question.user_answer ?? "";
  const isLast = index === assessment.questions.length - 1;

  const setDraft = (value: string) => {
    setDrafts((prev) => ({ ...prev, [question.id]: value }));
  };

  const flush = (value: string) => {
    if (!value) return;
    saveAnswer.mutate({ questionId: question.id, answer: value });
  };

  const goNext = () => {
    flush(draft);
    setIndex((i) => Math.min(i + 1, assessment.questions.length - 1));
  };

  const goPrev = () => {
    flush(draft);
    setIndex((i) => Math.max(i - 1, 0));
  };

  const handleSubmit = async () => {
    flush(draft);
    await submitAssessment.mutateAsync();
    // No navigation needed: submitAssessment's onSuccess writes the
    // completed assessment into this same query's cache, so this component
    // re-renders straight into the status === "completed" branch above.
  };

  return (
    <AppShell>
      <TopBar
        title="Skill assessment"
        subtitle={`${assessment.level} level — answer honestly, this shapes your roadmap.`}
      />

      <div className="mb-6 h-1.5 w-full rounded-full bg-line">
        <div
          className="h-full rounded-full bg-accent transition-all duration-base"
          style={{ width: `${((index + 1) / assessment.questions.length) * 100}%` }}
        />
      </div>

      <QuestionCard question={question} index={index} total={assessment.questions.length}>
        {question.type === "mcq" && question.options ? (
          <McqOptions
            options={question.options}
            selected={draft === "" ? null : Number(draft)}
            onSelect={(optionIndex) => {
              const value = String(optionIndex);
              setDraft(value);
              flush(value);
            }}
          />
        ) : (
          <DescriptiveAnswer value={draft} onChange={setDraft} onBlur={() => flush(draft)} />
        )}
      </QuestionCard>

      <div className="mt-6 flex items-center justify-between">
        <Button variant="secondary" onClick={goPrev} disabled={index === 0}>
          Previous
        </Button>
        {isLast ? (
          <Button onClick={handleSubmit} disabled={submitAssessment.isPending}>
            {submitAssessment.isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" /> Grading…
              </>
            ) : (
              "Submit assessment"
            )}
          </Button>
        ) : (
          <Button onClick={goNext}>Next</Button>
        )}
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 7: Add the route in `frontend/src/App.tsx`**

Add the import:

```tsx
import AssessmentPage from "@/pages/AssessmentPage";
```

Add the route, right after the onboarding route:

```tsx
      <Route path="/onboarding" element={<OnboardingPage />} />
      <Route path="/assessment/:id" element={<AssessmentPage />} />
      <Route path="/" element={<DashboardPage />} />
```

- [ ] **Step 8: Verify it compiles**

Run: `cd frontend && npm run build`
Expected: `✓ built in ...` — no TypeScript errors.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/ui/textarea.tsx frontend/src/components/assessment/ frontend/src/pages/AssessmentPage.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add assessment UI — question flow and result summary"
```

---

## Task 10: Wire onboarding to the assessment + full live verification

**Files:**
- Modify: `frontend/src/components/onboarding/LevelStep.tsx`, `frontend/src/pages/OnboardingPage.tsx`

Beginner still skips straight to the dashboard, unchanged. Intermediate and
Advanced now create the track, generate a real assessment, and land the user
on it — this is the one place a multi-second live AI call sits directly in a
user flow, so the loading state needs to say so, and a failure needs to be
visible and retryable rather than a silent hang.

- [ ] **Step 1: Replace `frontend/src/components/onboarding/LevelStep.tsx`**

```tsx
import { Loader2 } from "lucide-react";

import { EXPERIENCE_LEVELS } from "@/lib/constants";
import { cn } from "@/lib/cn";
import type { ExperienceLevel } from "@/types";

interface LevelStepProps {
  topic: string;
  pending: boolean;
  pendingLabel: string;
  errorMessage?: string;
  onSelect: (level: ExperienceLevel) => void;
}

export function LevelStep({
  topic,
  pending,
  pendingLabel,
  errorMessage,
  onSelect,
}: LevelStepProps) {
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
            <span className="mt-1 block text-sm text-text-secondary">{description}</span>
          </button>
        ))}
      </div>

      {pending && (
        <p className="flex items-center gap-2 text-sm text-text-secondary">
          <Loader2 className="size-4 animate-spin" /> {pendingLabel}
        </p>
      )}

      {errorMessage && !pending && (
        <p className="text-sm text-danger">{errorMessage} — pick a level again to retry.</p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Replace `frontend/src/pages/OnboardingPage.tsx`**

```tsx
import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { LevelStep } from "@/components/onboarding/LevelStep";
import { NameStep } from "@/components/onboarding/NameStep";
import { TopicStep } from "@/components/onboarding/TopicStep";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { useStartAssessment } from "@/hooks/useAssessment";
import { useCreateProfile, useCreateTrack, useProfile } from "@/hooks/useProfile";
import { cn } from "@/lib/cn";
import type { ExperienceLevel } from "@/types";

export default function OnboardingPage() {
  const navigate = useNavigate();
  const { data: profile } = useProfile();
  const createProfile = useCreateProfile();
  const createTrack = useCreateTrack();
  const startAssessment = useStartAssessment();

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
    try {
      const track = await createTrack.mutateAsync({ topic, experienceLevel: level });
      if (level === "beginner") {
        navigate("/", { replace: true });
        return;
      }
      const assessment = await startAssessment.mutateAsync(track.id);
      navigate(`/assessment/${assessment.id}`, { replace: true });
    } catch {
      // Surfaced via createTrack.error / startAssessment.error below —
      // nothing further to do here.
    }
  };

  const pending = createTrack.isPending || startAssessment.isPending;
  const pendingLabel = startAssessment.isPending
    ? "Generating your assessment — this can take up to 30 seconds…"
    : "Setting up your track…";
  const errorMessage = createTrack.error?.message ?? startAssessment.error?.message;

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
                pending={pending}
                pendingLabel={pendingLabel}
                errorMessage={errorMessage}
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

- [ ] **Step 3: Verify it compiles**

Run: `cd frontend && npm run build`
Expected: `✓ built in ...` — no TypeScript errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/onboarding/LevelStep.tsx frontend/src/pages/OnboardingPage.tsx
git commit -m "feat(frontend): route Intermediate and Advanced onboarding into the assessment"
```

- [ ] **Step 5: Full backend and frontend verification**

Run: `cd backend && .venv/bin/pytest -v`
Expected: PASS — `68 passed`

Run: `cd frontend && npm run build && npm test`
Expected: build succeeds, `2 passed`

- [ ] **Step 6: Live end-to-end walkthrough**

This requires a real `GEMINI_API_KEY` in `backend/.env` (see Task 2 Step 4 — if
that live smoke test worked, this will too).

```bash
cd backend && rm -f careeros.db careeros.db-wal careeros.db-shm
.venv/bin/uvicorn main:app --reload
```

```bash
cd frontend && npm run dev
```

Open `http://localhost:5173` and walk through:

1. Onboard with a name, pick "Python" as the topic.
2. Select **Intermediate**. Confirm the loading state changes from "Setting up
   your track…" to "Generating your assessment — this can take up to 30
   seconds…", and after a real wait (roughly 5-30s), you land on
   `/assessment/:id` with 8-12 real, topic-relevant questions — not a fixed
   question bank, genuinely generated for Python at intermediate level.
3. Confirm the progress bar reads "Question 1 of N" and updates as you
   navigate.
4. Answer a few MCQ questions (click an option — it should visually select).
5. Reach a descriptive question, type a real answer, and click Next.
6. Click Previous once — confirm your MCQ selection and descriptive text are
   both still there (proves the draft/autosave round-trip works).
7. Navigate to the last question and click "Submit assessment". Confirm the
   button shows "Grading…" for a few seconds (this is the real batched
   descriptive-grading AI call), then the result view appears.
8. Confirm the result view shows: a score out of 100, an estimated level
   badge, strengths/weaknesses chips (if any topic hit the >=7/<=4
   thresholds), a real AI-written summary sentence, and a per-question
   breakdown where descriptive answers show real, specific AI feedback (not
   generic text).
9. Reload the page at `/assessment/:id` — confirm it still shows the
   completed result (not a blank in-progress view).
10. Go to `/settings` → back to `/` → click "New track" → onboard a second
    track with **Beginner** selected. Confirm this path is unchanged from
    Plan 1: no assessment, straight to the dashboard.

- [ ] **Step 7: Clean up the manual-test database**

```bash
cd backend && rm -f careeros.db careeros.db-wal careeros.db-shm
```

---

## Done when

- `cd backend && .venv/bin/pytest` → 68 passed
- `cd frontend && npm run build && npm test` → build clean, 2 passed
- A real Gemini call generates a topic-and-level-appropriate assessment (not a
  static question bank)
- Autosave survives Previous/Next navigation between questions
- Submit triggers exactly one batched AI call for all descriptive grading, not
  one call per question
- The result view shows a real AI-written summary and per-question feedback
- `correct_option`/`expected_points` are absent from every response until the
  assessment is completed
- Beginner onboarding is unchanged: no assessment, straight to the dashboard

**Next:** Plan 3 — roadmap SSE generation (the streaming phase-by-phase
`PhaseStreamParser`), the timeline viewer, progress tracking, and the full
dashboard aggregate endpoint. The assessment's `estimated_level`,
`strengths`, and `weaknesses` become the roadmap prompt's real input.
