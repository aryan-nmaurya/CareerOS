# CareerOS Plan 4 — Interview Core + Speech Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the core mock-interview loop — AI-generated, roadmap-aware questions; a real speech-driven question/answer cycle (TTS asks, STT transcribes); transcript capture; a minimal manual-abandon path. By the end, a learner can start an interview from any track, hear each question spoken, answer out loud (or by typing, if speech isn't available), and reach a completed interview with a full transcript — no scoring yet, no proctoring yet.

**Architecture:** Backend mirrors the assessment/roadmap pattern exactly: a pure prompt builder in `ai/prompts/interview.py`, a service layer that owns all business logic and exception types, explicit reveal/output builders, a thin router. Frontend centers on `useInterviewMachine` — a hand-rolled, pure `transition()` function wrapped in `useReducer`, driving `briefing → speaking → answering → review`, orchestrating two thin browser-API wrapper hooks (`useSpeechSynthesis`, `useSpeechRecognition`) with one hard invariant: recognition never runs while synthesis is speaking.

**Tech Stack:** FastAPI, SQLAlchemy, Gemini via the existing `AIClient` (backend); React 19, TanStack Query, the Web Speech API (`speechSynthesis` + `SpeechRecognition`/`webkitSpeechRecognition`) (frontend).

**Spec:** `docs/superpowers/specs/2026-08-08-careeros-interview-core-design.md` (Plan 4 design, extends `docs/superpowers/specs/2026-08-07-careeros-design.md` sections 5, 7, 8, 10, 14)

**Series context:** Plan 4 of 5.
1. Foundation (done)
2. AI client + assessment (done)
3. Roadmap SSE generation + viewer + progress + dashboard data (done)
4. **Interview core + speech** ← you are here
5. Proctoring + evaluation + reports + polish

**Verified before writing this plan**, against the real browser tool this project's E2E verification uses (not assumed from documentation):
- `speechSynthesis.speak()` on a real `SpeechSynthesisUtterance` fired `onstart` at 27ms and `onend` at 1875ms for a short test phrase — the full round trip the state machine's `speaking → answering` transition depends on works, including the callback.
- `new (SpeechRecognition || webkitSpeechRecognition)().start()` returns without throwing synchronously — but that alone is **not** confirmation recognition is working. In this sandboxed browser (which cannot grant microphone access — confirmed explicitly by the tool itself), `start()` led to `onerror` firing with `error: "not-allowed"` at 12ms, followed by `onend` at 13ms. `"not-allowed"` is the same standard error code a real user declining microphone permission produces, not a sandbox-specific quirk, so `useSpeechRecognition` is designed below to treat `onerror` — not a clean `start()` return — as the signal to fall back.
- Actual speech-to-text transcription of real audio remains unverifiable in this environment (no real microphone available to the automated browser) and is called out explicitly in Task 11 rather than assumed to work.

---

## File Structure

**Backend** (`backend/`)

| File | Responsibility |
|---|---|
| `models/interview.py` | `Interview`, `InterviewQuestion` |
| `ai/prompts/interview.py` | `build_interview_prompt` — pure, roadmap-aware |
| `services/interview_service.py` | `start_interview`, `get_interview`, `list_interviews`, `record_answer`, `complete_interview`, `quit_interview` |
| `services/dashboard_service.py` | modified: `recent_interviews` populated from `list_interviews` |
| `schemas/interview.py` | `InterviewOut`, `InterviewQuestionOut`, `AnswerSave`, `StartInterview` |
| `schemas/dashboard.py` | modified: `RecentInterviewOut`, `DashboardOut.recent_interviews` typed |
| `routers/interview.py` | create, get, answer, submit, quit |
| `main.py` | modified: model import + router wiring |
| `tests/test_interview_models.py` | round-trip, cascade delete from track |
| `tests/test_interview_prompts.py` | roadmap-aware content, schema shape |
| `tests/test_interview_service.py` | generation, roadmap-awareness, answer capture, complete, quit |
| `tests/test_interview_api.py` | router-level: create, get, answer, submit, quit, 404s |
| `tests/test_dashboard_api.py` | modified: `recent_interviews` now populated |
| `tests/conftest.py` | modified: defensive `models.interview` import for `create_all` |

**Frontend** (`frontend/src/`)

| File | Responsibility |
|---|---|
| `types/index.ts` | modified (twice: Task 6, Task 10): `Interview`, `InterviewQuestion`, `RecentInterview`, `MachinePhase` types |
| `services/api/interview.ts` | typed interview calls |
| `services/api/dashboard.ts` | unchanged (shape already generic) |
| `hooks/useInterview.ts` | `useStartInterview`, `useInterview`, `useSaveInterviewAnswer`, `useSubmitInterview`, `useQuitInterview` |
| `lib/interviewMachine.ts` | pure `transition(state, event) -> state`, tested directly |
| `lib/__tests__/interviewMachine.test.ts` | the 8 transition-table cases |
| `hooks/useInterviewMachine.ts` | thin `useReducer` wrapper around `transition`, orchestrates speech hooks |
| `hooks/useSpeechSynthesis.ts` | `speak`, `cancel`, `supported` |
| `hooks/useSpeechRecognition.ts` | `start`, `stop`, `transcript`, `listening`, `supported` |
| `types/speech.d.ts` | minimal ambient `SpeechRecognition` types — not in TS's default DOM lib |
| `components/interview/SetupForm.tsx` | level + question count picker, defaults from track |
| `components/interview/QuestionStage.tsx` | renders briefing/speaking/answering/review content for the current question |
| `components/interview/TranscriptPanel.tsx` | live STT transcript or fallback textarea |
| `pages/InterviewSetupPage.tsx` | collects level/count, calls `start_interview`, navigates to active page |
| `pages/InterviewActivePage.tsx` | mounts `useInterviewMachine`, renders `QuestionStage` |
| `App.tsx` | modified: `/interview` → setup, `/interview/:id` → active |
| `components/layout/Sidebar.tsx` | unchanged — `/interview` link already exists, now resolves to a real page |

---

## Task 1: Interview models

**Files:**
- Create: `backend/models/interview.py`
- Test: `backend/tests/test_interview_models.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_interview_models.py`:

```python
from models.interview import Interview, InterviewQuestion
from models.user import LearningTrack
from schemas.profile import ProfileCreate, TrackCreate
from services import profile_service


def _track(db_session):
    profile_service.create_profile(db_session, ProfileCreate(name="Aryan"))
    return profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level="intermediate")
    )


def test_interview_question_round_trip(db_session):
    track = _track(db_session)

    interview = Interview(
        track_id=track.id, level="intermediate", question_count=8, status="active"
    )
    db_session.add(interview)
    db_session.commit()

    question = InterviewQuestion(
        interview_id=interview.id,
        order_index=0,
        question="Explain the GIL.",
        expected_points=["single lock", "affects CPU-bound threads"],
    )
    db_session.add(question)
    db_session.commit()

    assert interview.questions == [question]
    assert question.interview is interview
    assert question.transcript is None
    assert question.answer_duration_s is None
    assert interview.track.id == track.id
    assert interview.warning_count == 0
    assert interview.overall_score is None


def test_deleting_track_cascades_to_interviews_and_questions(db_session):
    track = _track(db_session)
    interview = Interview(track_id=track.id, level="intermediate", question_count=5, status="active")
    db_session.add(interview)
    db_session.commit()
    question = InterviewQuestion(
        interview_id=interview.id, order_index=0, question="Q", expected_points=["p"]
    )
    db_session.add(question)
    db_session.commit()
    interview_id, question_id = interview.id, question.id

    db_session.delete(db_session.get(LearningTrack, track.id))
    db_session.commit()

    assert db_session.get(Interview, interview_id) is None
    assert db_session.get(InterviewQuestion, question_id) is None


def test_status_and_termination_fields(db_session):
    track = _track(db_session)
    interview = Interview(
        track_id=track.id,
        level="intermediate",
        question_count=5,
        status="terminated",
        termination_reason="user_quit",
    )
    db_session.add(interview)
    db_session.commit()

    assert interview.status == "terminated"
    assert interview.termination_reason == "user_quit"
    assert interview.ended_at is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_interview_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'models.interview'`

- [ ] **Step 3: Write `backend/models/interview.py`**

```python
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from models.user import LearningTrack


class Interview(Base):
    """One mock interview attempt for a track. Score/strengths/weaknesses/
    recommendations/summary all stay NULL until Plan 5's evaluation step —
    Plan 4 only generates questions and captures transcripts."""

    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("learning_tracks.id", ondelete="CASCADE"))
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    termination_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    technical_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    communication_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    strengths: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    weaknesses: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    recommendations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    track: Mapped["LearningTrack"] = relationship()
    questions: Mapped[list["InterviewQuestion"]] = relationship(
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="InterviewQuestion.order_index",
    )


class InterviewQuestion(Base):
    """transcript/answer_duration_s are Plan 4's capture fields, written by
    record_answer. The four score-ish columns after them stay NULL until
    Plan 5's evaluation call."""

    __tablename__ = "interview_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"))
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_points: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    technical_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    communication_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    missing_concepts: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    better_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    interview: Mapped["Interview"] = relationship(back_populates="questions")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_interview_models.py -v`
Expected: PASS — `3 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/models/interview.py backend/tests/test_interview_models.py
git commit -m "feat(backend): add Interview and InterviewQuestion models"
```

---

## Task 2: Interview generation prompt

**Files:**
- Create: `backend/ai/prompts/interview.py`
- Test: `backend/tests/test_interview_prompts.py`

Pure function, no client, no DB — matches `prompts/assessment.py` and
`prompts/roadmap.py`. Unlike assessment's mcq/descriptive split, every
interview question has the identical shape (`question` + `expected_points`),
so there's nothing genuinely optional in the schema — no `nullable` fields,
no ambiguity about the exhaustive-required question from Plan 3.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_interview_prompts.py`:

```python
from ai.prompts.interview import build_interview_prompt


def test_beginner_prompt_asks_foundational_questions():
    prompt = build_interview_prompt("Python", "beginner", 5)

    assert "foundational" in prompt.user_content.lower()


def test_advanced_prompt_probes_deep_understanding():
    prompt = build_interview_prompt("Python", "advanced", 5)

    assert "advanced" in prompt.user_content.lower()
    assert (
        "trade-offs" in prompt.user_content.lower()
        or "edge cases" in prompt.user_content.lower()
    )


def test_roadmap_context_is_included_when_present():
    prompt = build_interview_prompt(
        "Python", "intermediate", 8, roadmap_context=["Decorators", "Generators"]
    )

    assert "Decorators" in prompt.user_content
    assert "Generators" in prompt.user_content


def test_no_roadmap_context_omits_the_context_line():
    prompt = build_interview_prompt("Python", "intermediate", 8, roadmap_context=None)

    assert "studying" not in prompt.user_content.lower()


def test_schema_bounds_question_count_exactly():
    prompt = build_interview_prompt("Python", "intermediate", 6)

    questions_schema = prompt.response_schema["properties"]["questions"]
    assert questions_schema["min_items"] == 6
    assert questions_schema["max_items"] == 6
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_interview_prompts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai.prompts.interview'`

- [ ] **Step 3: Write `backend/ai/prompts/interview.py`**

```python
from __future__ import annotations

from ai.client import Prompt

_QUESTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "question": {"type": "STRING"},
        "expected_points": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "min_items": 2,
            "max_items": 5,
        },
    },
    "required": ["question", "expected_points"],
}

_SYSTEM = (
    "You are a technical interviewer for CareerOS conducting a mock interview. "
    "Generate interview questions as strict JSON matching the schema. Each "
    "question needs 2-5 expected_points describing what a strong spoken answer "
    "would cover. Questions should be answerable out loud in 1-3 minutes each "
    "— avoid anything requiring a whiteboard or written code."
)


def build_interview_prompt(
    topic: str, level: str, count: int, roadmap_context: list[str] | None = None
) -> Prompt:
    if level == "beginner":
        difficulty = (
            "This is a beginner-level interview — ask foundational questions "
            "about core concepts and terminology, the kind a hiring manager "
            "would use to confirm basic familiarity."
        )
    elif level == "advanced":
        difficulty = (
            "This is an advanced interview — probe deep understanding, "
            "trade-offs, edge cases, and real-world experience a senior "
            "practitioner would have."
        )
    else:
        difficulty = (
            "This is an intermediate interview — practical, hands-on "
            "questions a working professional with some experience should "
            "be able to answer confidently."
        )

    context_line = ""
    if roadmap_context:
        context_line = (
            "\nThe candidate has been studying these topics recently — weight "
            f"some questions toward them: {', '.join(roadmap_context)}."
        )

    user_content = (
        f"Topic: {topic}\n"
        f"Level: {level}\n"
        f"{difficulty}{context_line}\n\n"
        f"Generate exactly {count} questions, each spoken-answer-friendly and "
        "distinct from the others."
    )

    schema = {
        "type": "OBJECT",
        "properties": {
            "questions": {
                "type": "ARRAY",
                "min_items": count,
                "max_items": count,
                "items": _QUESTION_SCHEMA,
            },
        },
        "required": ["questions"],
    }

    return Prompt(
        system_instruction=_SYSTEM,
        user_content=user_content,
        response_schema=schema,
        temperature=0.6,
        max_output_tokens=4096,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_interview_prompts.py -v`
Expected: PASS — `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/ai/prompts/interview.py backend/tests/test_interview_prompts.py
git commit -m "feat(backend): add interview generation prompt with roadmap-aware context"
```

---

## Task 3: Interview service — generation, read, answer capture

**Files:**
- Create: `backend/services/interview_service.py`
- Test: `backend/tests/test_interview_service.py`

`start_interview` resolves a roadmap-context list (completed modules plus
the current phase's modules, deduped, title-only) when the track has a
roadmap, folds it into the prompt, and persists the interview with
`status="active"` directly — never `"setup"` (see this plan's design doc for
why). `record_answer` has no validation beyond "question belongs to this
interview" — it's a pure capture step, no status transitions.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_interview_service.py`:

```python
from datetime import datetime

import pytest

from ai.errors import AIInvalidResponse
from schemas.profile import ProfileCreate, TrackCreate
from services import interview_service, profile_service, roadmap_service
from services.interview_service import InterviewNotFoundError, QuestionNotFoundError
from services.profile_service import TrackNotFoundError


def _track(db_session, level="intermediate"):
    profile_service.create_profile(db_session, ProfileCreate(name="Aryan"))
    return profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level=level)
    )


def _generation_response(count=5):
    return {
        "questions": [
            {"question": f"Q{i}?", "expected_points": [f"point-{i}-a", f"point-{i}-b"]}
            for i in range(count)
        ]
    }


_ROADMAP_CHUNKS = [
    '{"title": "Python Roadmap", "summary": "S", "total_weeks": 4, "weekly_hours": 5, ',
    '"weekly_goals": [], "final_project": {"title": "F", "description": "D", "skills_demonstrated": []}, ',
    '"phases": [',
    '{"title": "Foundations", "description": "", "goal": "G", "estimated_hours": 1, "modules": [',
    '{"title": "Variables", "description": "", "lessons": [], "exercises": [], ',
    '"project": null, "estimated_hours": 1, "kind": "module"},',
    '{"title": "Loops", "description": "", "lessons": [], "exercises": [], ',
    '"project": null, "estimated_hours": 1, "kind": "module"}',
    ']}',
    ']}',
]


def test_start_interview_persists_generated_questions(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(5))

    interview = interview_service.start_interview(db_session, fake_ai, track.id, "intermediate", 5)

    assert interview.status == "active"
    assert interview.track_id == track.id
    assert len(interview.questions) == 5
    assert interview.questions[0].order_index == 0
    assert interview.questions[0].expected_points == ["point-0-a", "point-0-b"]


def test_start_interview_unknown_track_raises(db_session, fake_ai):
    with pytest.raises(TrackNotFoundError):
        interview_service.start_interview(db_session, fake_ai, 999, "intermediate", 5)

    assert fake_ai.calls == []


def test_start_interview_rejects_wrong_question_count(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(3))

    with pytest.raises(AIInvalidResponse):
        interview_service.start_interview(db_session, fake_ai, track.id, "intermediate", 5)


def test_start_interview_is_roadmap_aware_when_roadmap_exists(db_session, fake_ai):
    track = _track(db_session, level="beginner")
    fake_ai.queue_stream(_ROADMAP_CHUNKS)
    list(roadmap_service.stream_roadmap(db_session, fake_ai, track.id))
    roadmap = roadmap_service.get_roadmap_by_track(db_session, track.id)
    roadmap.phases[0].modules[0].completed_at = datetime(2026, 1, 1)
    db_session.commit()

    fake_ai.queue_response(_generation_response(5))
    interview_service.start_interview(db_session, fake_ai, track.id, "beginner", 5)

    prompt_text = fake_ai.calls[-1].user_content
    assert "Variables" in prompt_text
    assert "Loops" in prompt_text


def test_start_interview_without_roadmap_omits_context(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(5))

    interview_service.start_interview(db_session, fake_ai, track.id, "intermediate", 5)

    assert "studying" not in fake_ai.calls[-1].user_content.lower()


def test_get_interview_unknown_raises(db_session):
    with pytest.raises(InterviewNotFoundError):
        interview_service.get_interview(db_session, 999)


def test_record_answer_stores_transcript_and_duration(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(5))
    interview = interview_service.start_interview(db_session, fake_ai, track.id, "intermediate", 5)
    question = interview.questions[0]

    interview_service.record_answer(
        db_session, interview.id, question.id, "My spoken answer.", 42
    )

    db_session.refresh(question)
    assert question.transcript == "My spoken answer."
    assert question.answer_duration_s == 42


def test_record_answer_unknown_question_raises(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(5))
    interview = interview_service.start_interview(db_session, fake_ai, track.id, "intermediate", 5)

    with pytest.raises(QuestionNotFoundError):
        interview_service.record_answer(db_session, interview.id, 999999, "answer", 10)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_interview_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.interview_service'`

- [ ] **Step 3: Write `backend/services/interview_service.py`**

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from ai.client import AIClient
from ai.errors import AIInvalidResponse
from ai.prompts.interview import build_interview_prompt
from models.interview import Interview, InterviewQuestion
from services import profile_service, roadmap_service
from services.progress_service import current_phase_index
from services.roadmap_service import RoadmapNotFoundError


class InterviewNotFoundError(Exception):
    pass


class QuestionNotFoundError(Exception):
    pass


def _roadmap_context(roadmap) -> list[str] | None:
    titles: list[str] = []
    for phase in roadmap.phases:
        for module in phase.modules:
            if module.completed_at is not None:
                titles.append(module.title)
    if roadmap.phases:
        current = current_phase_index(roadmap.phases)
        titles.extend(m.title for m in roadmap.phases[current].modules)

    seen: set[str] = set()
    deduped: list[str] = []
    for title in titles:
        if title not in seen:
            seen.add(title)
            deduped.append(title)
    return deduped or None


def start_interview(
    db: Session, ai_client: AIClient, track_id: int, level: str, question_count: int
) -> Interview:
    track = profile_service.get_track(db, track_id)

    roadmap_context = None
    try:
        roadmap = roadmap_service.get_roadmap_by_track(db, track.id)
        roadmap_context = _roadmap_context(roadmap)
    except RoadmapNotFoundError:
        pass

    prompt = build_interview_prompt(track.topic, level, question_count, roadmap_context)
    result = ai_client.generate_json(prompt)
    questions_data = result.get("questions", [])
    if len(questions_data) != question_count:
        raise AIInvalidResponse(
            f"Expected {question_count} questions, got {len(questions_data)}"
        )

    interview = Interview(
        track_id=track.id, level=level, question_count=question_count, status="active"
    )
    db.add(interview)
    db.flush()

    for index, q in enumerate(questions_data):
        db.add(
            InterviewQuestion(
                interview_id=interview.id,
                order_index=index,
                question=q["question"],
                expected_points=q.get("expected_points", []),
            )
        )

    db.commit()
    db.refresh(interview)
    return interview


def get_interview(db: Session, interview_id: int) -> Interview:
    interview = db.get(Interview, interview_id)
    if interview is None:
        raise InterviewNotFoundError
    return interview


def record_answer(
    db: Session, interview_id: int, question_id: int, transcript: str, duration_s: int
) -> None:
    interview = get_interview(db, interview_id)
    question = next((q for q in interview.questions if q.id == question_id), None)
    if question is None:
        raise QuestionNotFoundError

    question.transcript = transcript
    question.answer_duration_s = duration_s
    db.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_interview_service.py -v`
Expected: PASS — `8 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/services/interview_service.py backend/tests/test_interview_service.py
git commit -m "feat(backend): add interview service — roadmap-aware generation, read, answer capture"
```

---

## Task 4: complete/quit + list_interviews + dashboard integration

**Files:**
- Modify: `backend/services/interview_service.py`
- Modify: `backend/services/dashboard_service.py`, `backend/schemas/dashboard.py`
- Modify: `backend/tests/test_interview_service.py`, `backend/tests/test_dashboard_api.py`

`recent_interviews` has been hardcoded to `[]` since Plan 3. It's scoped to
the *active track* — the dashboard is fundamentally "here's your current
track's status," and every other field on it already follows that scoping.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_interview_service.py`:

```python
def test_complete_interview_marks_completed_without_requiring_transcripts(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(5))
    interview = interview_service.start_interview(db_session, fake_ai, track.id, "intermediate", 5)

    completed = interview_service.complete_interview(db_session, interview.id)

    assert completed.status == "completed"
    assert completed.ended_at is not None


def test_complete_interview_on_non_active_raises(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(5))
    interview = interview_service.start_interview(db_session, fake_ai, track.id, "intermediate", 5)
    interview_service.complete_interview(db_session, interview.id)

    with pytest.raises(interview_service.InterviewNotActiveError):
        interview_service.complete_interview(db_session, interview.id)


def test_quit_interview_marks_terminated_with_reason(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(5))
    interview = interview_service.start_interview(db_session, fake_ai, track.id, "intermediate", 5)

    quit = interview_service.quit_interview(db_session, interview.id)

    assert quit.status == "terminated"
    assert quit.termination_reason == "user_quit"
    assert quit.ended_at is not None


def test_quit_interview_on_non_active_raises(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(5))
    interview = interview_service.start_interview(db_session, fake_ai, track.id, "intermediate", 5)
    interview_service.quit_interview(db_session, interview.id)

    with pytest.raises(interview_service.InterviewNotActiveError):
        interview_service.quit_interview(db_session, interview.id)


def test_list_interviews_orders_most_recent_first_and_respects_limit(db_session, fake_ai):
    track = _track(db_session)
    for _ in range(4):
        fake_ai.queue_response(_generation_response(5))
        interview_service.start_interview(db_session, fake_ai, track.id, "intermediate", 5)

    listed = interview_service.list_interviews(db_session, track.id, limit=2)

    assert len(listed) == 2
    assert listed[0].id > listed[1].id
```

Append to `backend/tests/test_dashboard_api.py`:

```python
def test_dashboard_reflects_recent_interviews(client, fake_ai):
    client.post("/api/profile", json={"name": "Aryan"})
    track_id = client.post(
        "/api/tracks", json={"topic": "Python", "experience_level": "intermediate"}
    ).json()["id"]
    fake_ai.queue_response(
        {
            "questions": [
                {"question": f"Q{i}?", "expected_points": ["a", "b"]} for i in range(5)
            ]
        }
    )
    client.post(
        f"/api/tracks/{track_id}/interviews",
        json={"level": "intermediate", "question_count": 5},
    )

    body = client.get("/api/dashboard").json()

    assert len(body["recent_interviews"]) == 1
    assert body["recent_interviews"][0]["level"] == "intermediate"
    assert body["recent_interviews"][0]["status"] == "active"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_interview_service.py tests/test_dashboard_api.py -v`
Expected: FAIL — `AttributeError: module 'services.interview_service' has no attribute 'complete_interview'`
(the last test also fails until Task 5 wires the router — expected, comes back green once that lands too)

- [ ] **Step 3: Extend `backend/services/interview_service.py`**

Add to the imports at the top:

```python
from datetime import UTC, datetime

from sqlalchemy import select
```

Add after the existing exception classes:

```python
class InterviewNotActiveError(Exception):
    pass
```

Append at the end of the file:

```python
def list_interviews(db: Session, track_id: int, limit: int = 3) -> list[Interview]:
    return list(
        db.scalars(
            select(Interview)
            .where(Interview.track_id == track_id)
            .order_by(Interview.started_at.desc(), Interview.id.desc())
            .limit(limit)
        )
    )


def complete_interview(db: Session, interview_id: int) -> Interview:
    interview = get_interview(db, interview_id)
    if interview.status != "active":
        raise InterviewNotActiveError
    interview.status = "completed"
    interview.ended_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    db.refresh(interview)
    return interview


def quit_interview(db: Session, interview_id: int) -> Interview:
    interview = get_interview(db, interview_id)
    if interview.status != "active":
        raise InterviewNotActiveError
    interview.status = "terminated"
    interview.termination_reason = "user_quit"
    interview.ended_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    db.refresh(interview)
    return interview
```

- [ ] **Step 4: Add `RecentInterviewOut` to `backend/schemas/dashboard.py`**

Replace the whole file:

```python
from datetime import datetime

from pydantic import BaseModel

from schemas.profile import ProfileOut, TrackOut


class NextModuleOut(BaseModel):
    id: int
    title: str
    kind: str
    phase_title: str


class RecentInterviewOut(BaseModel):
    id: int
    level: str
    status: str
    started_at: datetime


class DashboardOut(BaseModel):
    profile: ProfileOut | None
    active_track: TrackOut | None
    roadmap_summary: str | None
    current_phase: str | None
    completed_modules: int
    remaining_modules: int
    completion_pct: float
    next_module: NextModuleOut | None
    recent_interviews: list[RecentInterviewOut] = []
```

- [ ] **Step 5: Wire `backend/services/dashboard_service.py`**

Replace the whole file:

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from schemas.dashboard import DashboardOut, NextModuleOut, RecentInterviewOut
from schemas.profile import ProfileOut, TrackOut
from services import interview_service, profile_service, roadmap_service
from services.progress_service import build_progress, current_phase_index
from services.roadmap_service import RoadmapNotFoundError

_EMPTY_ROADMAP_FIELDS = dict(
    roadmap_summary=None,
    current_phase=None,
    completed_modules=0,
    remaining_modules=0,
    completion_pct=0.0,
    next_module=None,
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


def _recent_interviews_out(db: Session, track_id: int) -> list[RecentInterviewOut]:
    interviews = interview_service.list_interviews(db, track_id, limit=3)
    return [
        RecentInterviewOut(id=i.id, level=i.level, status=i.status, started_at=i.started_at)
        for i in interviews
    ]


def get_dashboard(db: Session) -> DashboardOut:
    user = profile_service.get_profile(db)
    if user is None:
        return DashboardOut(
            profile=None, active_track=None, recent_interviews=[], **_EMPTY_ROADMAP_FIELDS
        )

    profile_out = ProfileOut.model_validate(user)
    active_track = profile_service.get_active_track(db)
    if active_track is None:
        return DashboardOut(
            profile=profile_out,
            active_track=None,
            recent_interviews=[],
            **_EMPTY_ROADMAP_FIELDS,
        )

    track_out = TrackOut.model_validate(active_track)
    recent_interviews = _recent_interviews_out(db, active_track.id)

    try:
        roadmap = roadmap_service.get_roadmap_by_track(db, active_track.id)
    except RoadmapNotFoundError:
        return DashboardOut(
            profile=profile_out,
            active_track=track_out,
            recent_interviews=recent_interviews,
            **_EMPTY_ROADMAP_FIELDS,
        )

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
        recent_interviews=recent_interviews,
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_interview_service.py -v`
Expected: PASS — `13 passed` (8 from Task 3 + 5 new)

`test_dashboard_reflects_recent_interviews` still fails at this point — it
needs the router from Task 5 to `POST .../interviews`. That's expected; it's
listed here because it belongs conceptually with this task's change, not
because it passes yet.

- [ ] **Step 7: Commit**

```bash
git add backend/services/interview_service.py backend/services/dashboard_service.py backend/schemas/dashboard.py backend/tests/test_interview_service.py backend/tests/test_dashboard_api.py
git commit -m "feat(backend): add interview complete/quit, wire recent_interviews into dashboard"
```

---

## Task 5: Interview schemas, router, output builders, main.py wiring

**Files:**
- Create: `backend/schemas/interview.py`
- Modify: `backend/services/interview_service.py` (output builders)
- Create: `backend/routers/interview.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_interview_api.py`

`question_count` is constrained to exactly `5 | 8 | 10` via a `Literal`, not
a range — matches the master spec's schema comment precisely, and FastAPI
rejects anything else with a 422 for free.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_interview_api.py`:

```python
def _onboard_and_track(client, level="intermediate"):
    client.post("/api/profile", json={"name": "Aryan"})
    track = client.post(
        "/api/tracks", json={"topic": "Python", "experience_level": level}
    )
    return track.json()["id"]


def _generation_payload(count=5):
    return {
        "questions": [
            {"question": f"Q{i}?", "expected_points": [f"a{i}", f"b{i}"]}
            for i in range(count)
        ]
    }


def test_start_interview_returns_201_with_questions(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload(5))

    response = client.post(
        f"/api/tracks/{track_id}/interviews",
        json={"level": "intermediate", "question_count": 5},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "active"
    assert len(body["questions"]) == 5
    assert body["questions"][0]["transcript"] is None


def test_start_interview_unknown_track_returns_404(client):
    response = client.post(
        "/api/tracks/999/interviews", json={"level": "intermediate", "question_count": 5}
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "track_not_found"


def test_start_interview_rejects_invalid_question_count(client):
    track_id = _onboard_and_track(client)

    response = client.post(
        f"/api/tracks/{track_id}/interviews",
        json={"level": "intermediate", "question_count": 7},
    )

    assert response.status_code == 422


def test_get_interview_returns_full_shape(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload(5))
    interview_id = client.post(
        f"/api/tracks/{track_id}/interviews",
        json={"level": "intermediate", "question_count": 5},
    ).json()["id"]

    response = client.get(f"/api/interviews/{interview_id}")

    assert response.status_code == 200
    assert response.json()["track_id"] == track_id


def test_get_interview_unknown_returns_404(client):
    response = client.get("/api/interviews/999")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "interview_not_found"


def test_save_answer_stores_transcript(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload(5))
    interview = client.post(
        f"/api/tracks/{track_id}/interviews",
        json={"level": "intermediate", "question_count": 5},
    ).json()
    question_id = interview["questions"][0]["id"]

    response = client.post(
        f"/api/interviews/{interview['id']}/questions/{question_id}/answer",
        json={"transcript": "Spoken answer here.", "duration_s": 30},
    )

    assert response.status_code == 204
    refreshed = client.get(f"/api/interviews/{interview['id']}").json()
    assert refreshed["questions"][0]["transcript"] == "Spoken answer here."
    assert refreshed["questions"][0]["answer_duration_s"] == 30


def test_save_answer_unknown_interview_returns_404(client):
    response = client.post(
        "/api/interviews/999/questions/1/answer",
        json={"transcript": "x", "duration_s": 1},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "interview_not_found"


def test_submit_interview_marks_completed(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload(5))
    interview_id = client.post(
        f"/api/tracks/{track_id}/interviews",
        json={"level": "intermediate", "question_count": 5},
    ).json()["id"]

    response = client.post(f"/api/interviews/{interview_id}/submit")

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_submit_interview_already_completed_returns_409(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload(5))
    interview_id = client.post(
        f"/api/tracks/{track_id}/interviews",
        json={"level": "intermediate", "question_count": 5},
    ).json()["id"]
    client.post(f"/api/interviews/{interview_id}/submit")

    response = client.post(f"/api/interviews/{interview_id}/submit")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "interview_not_active"


def test_quit_interview_marks_terminated(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload(5))
    interview_id = client.post(
        f"/api/tracks/{track_id}/interviews",
        json={"level": "intermediate", "question_count": 5},
    ).json()["id"]

    response = client.post(f"/api/interviews/{interview_id}/quit")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "terminated"
    assert body["termination_reason"] == "user_quit"


def test_quit_interview_already_terminated_returns_409(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload(5))
    interview_id = client.post(
        f"/api/tracks/{track_id}/interviews",
        json={"level": "intermediate", "question_count": 5},
    ).json()["id"]
    client.post(f"/api/interviews/{interview_id}/quit")

    response = client.post(f"/api/interviews/{interview_id}/quit")

    assert response.status_code == 409
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_interview_api.py -v`
Expected: FAIL — not an import error this time, since this test file has no
top-level imports of anything new (only the `client`/`fake_ai` fixtures).
Every request hits a route FastAPI doesn't know about yet, so every test
fails on a status-code assertion instead, e.g.
`assert 404 == 201` on `test_start_interview_returns_201_with_questions`.
That's the correct failure to see here — a real 404 from an unregistered
route, not a crash.

- [ ] **Step 3: Write `backend/schemas/interview.py`**

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

InterviewLevel = Literal["beginner", "intermediate", "advanced"]
InterviewStatus = Literal["setup", "active", "completed", "terminated"]


class InterviewQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_index: int
    question: str
    expected_points: list[str]
    transcript: str | None
    answer_duration_s: int | None


class InterviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    track_id: int
    level: InterviewLevel
    question_count: int
    status: InterviewStatus
    started_at: datetime
    ended_at: datetime | None
    termination_reason: str | None
    questions: list[InterviewQuestionOut]


class StartInterview(BaseModel):
    level: InterviewLevel
    question_count: Literal[5, 8, 10]


class AnswerSave(BaseModel):
    transcript: str
    duration_s: int = Field(ge=0)
```

- [ ] **Step 4: Add output builders to `backend/services/interview_service.py`**

Add to the imports:

```python
from schemas.interview import InterviewOut, InterviewQuestionOut
```

Append at the end of the file:

```python
def _question_out(question: InterviewQuestion) -> InterviewQuestionOut:
    return InterviewQuestionOut(
        id=question.id,
        order_index=question.order_index,
        question=question.question,
        expected_points=question.expected_points,
        transcript=question.transcript,
        answer_duration_s=question.answer_duration_s,
    )


def to_interview_out(interview: Interview) -> InterviewOut:
    return InterviewOut(
        id=interview.id,
        track_id=interview.track_id,
        level=interview.level,
        question_count=interview.question_count,
        status=interview.status,
        started_at=interview.started_at,
        ended_at=interview.ended_at,
        termination_reason=interview.termination_reason,
        questions=[_question_out(q) for q in interview.questions],
    )
```

- [ ] **Step 5: Write `backend/routers/interview.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ai.client import AIClient, get_ai_client
from db.session import get_db
from schemas.interview import AnswerSave, InterviewOut, StartInterview
from services import interview_service
from services.interview_service import (
    InterviewNotActiveError,
    InterviewNotFoundError,
    QuestionNotFoundError,
)
from services.profile_service import TrackNotFoundError

router = APIRouter(tags=["interview"])

_TRACK_MISSING = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "track_not_found", "message": "That learning track does not exist."},
)
_INTERVIEW_MISSING = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "interview_not_found", "message": "That interview does not exist."},
)
_QUESTION_MISSING = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "question_not_found", "message": "That question does not exist."},
)
_NOT_ACTIVE = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail={"code": "interview_not_active", "message": "This interview is no longer active."},
)


@router.post(
    "/api/tracks/{track_id}/interviews",
    response_model=InterviewOut,
    status_code=status.HTTP_201_CREATED,
)
def start_interview(
    track_id: int,
    payload: StartInterview,
    db: Session = Depends(get_db),
    ai_client: AIClient = Depends(get_ai_client),
):
    try:
        interview = interview_service.start_interview(
            db, ai_client, track_id, payload.level, payload.question_count
        )
        return interview_service.to_interview_out(interview)
    except TrackNotFoundError:
        raise _TRACK_MISSING


@router.get("/api/interviews/{interview_id}", response_model=InterviewOut)
def read_interview(interview_id: int, db: Session = Depends(get_db)):
    try:
        interview = interview_service.get_interview(db, interview_id)
        return interview_service.to_interview_out(interview)
    except InterviewNotFoundError:
        raise _INTERVIEW_MISSING


@router.post(
    "/api/interviews/{interview_id}/questions/{question_id}/answer",
    status_code=status.HTTP_204_NO_CONTENT,
)
def save_answer(
    interview_id: int,
    question_id: int,
    payload: AnswerSave,
    db: Session = Depends(get_db),
):
    try:
        interview_service.record_answer(
            db, interview_id, question_id, payload.transcript, payload.duration_s
        )
    except InterviewNotFoundError:
        raise _INTERVIEW_MISSING
    except QuestionNotFoundError:
        raise _QUESTION_MISSING


@router.post("/api/interviews/{interview_id}/submit", response_model=InterviewOut)
def submit_interview(interview_id: int, db: Session = Depends(get_db)):
    try:
        interview = interview_service.complete_interview(db, interview_id)
        return interview_service.to_interview_out(interview)
    except InterviewNotFoundError:
        raise _INTERVIEW_MISSING
    except InterviewNotActiveError:
        raise _NOT_ACTIVE


@router.post("/api/interviews/{interview_id}/quit", response_model=InterviewOut)
def quit_interview(interview_id: int, db: Session = Depends(get_db)):
    try:
        interview = interview_service.quit_interview(db, interview_id)
        return interview_service.to_interview_out(interview)
    except InterviewNotFoundError:
        raise _INTERVIEW_MISSING
    except InterviewNotActiveError:
        raise _NOT_ACTIVE
```

- [ ] **Step 6: Wire `backend/main.py`**

Add `from models import interview as _interview_models  # noqa: F401` next
to the other model imports, add `interview` to the `from routers import ...`
line, and add `app.include_router(interview.router)` next to the other
`include_router` calls.

- [ ] **Step 7: Add the same defensive model import to `backend/tests/conftest.py`**

Add next to the existing model imports:

```python
from models import interview as _interview_models  # noqa: E402,F401
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_interview_api.py tests/test_dashboard_api.py -v`
Expected: PASS — `11 passed` (interview_api) and `5 passed` (dashboard_api,
including the one that was failing since Task 4)

- [ ] **Step 9: Run the full backend suite**

Run: `cd backend && .venv/bin/pytest -v`
Expected: PASS — `149 passed` (116 before this plan + 33 new: 3 in
`test_interview_models.py`, 5 in `test_interview_prompts.py`, 13 in
`test_interview_service.py` — 8 from Task 3, 5 from Task 4 — 1 added to
`test_dashboard_api.py` in Task 4, and 11 in `test_interview_api.py`)

- [ ] **Step 10: Commit**

```bash
git add backend/schemas/interview.py backend/services/interview_service.py backend/routers/interview.py backend/main.py backend/tests/conftest.py backend/tests/test_interview_api.py
git commit -m "feat(backend): add interview schemas, router, and output builders"
```

---

## Task 6: Frontend types, API client, data hooks

**Files:**
- Modify: `frontend/src/types/index.ts`
- Create: `frontend/src/services/api/interview.ts`
- Create: `frontend/src/hooks/useInterview.ts`

Thin wiring over the backend just built — no new tests here, matching Plan
3 Task 9's precedent (the pure/hard-to-get-right logic gets its own tests in
Task 7; this is straightforward typed pass-through, same shape as
`services/api/roadmap.ts`/`hooks/useRoadmap.ts`). This also finally types
`Dashboard.recent_interviews`, which has been `unknown[]` since Plan 3
because the real shape didn't exist yet.

- [ ] **Step 1: Add interview types to `frontend/src/types/index.ts`**

Append:

```typescript
export type InterviewLevel = "beginner" | "intermediate" | "advanced";
export type InterviewStatus = "setup" | "active" | "completed" | "terminated";

export interface InterviewQuestion {
  id: number;
  order_index: number;
  question: string;
  expected_points: string[];
  transcript: string | null;
  answer_duration_s: number | null;
}

export interface Interview {
  id: number;
  track_id: number;
  level: InterviewLevel;
  question_count: number;
  status: InterviewStatus;
  started_at: string;
  ended_at: string | null;
  termination_reason: string | null;
  questions: InterviewQuestion[];
}

export interface RecentInterview {
  id: number;
  level: InterviewLevel;
  status: InterviewStatus;
  started_at: string;
}
```

Then find the existing `Dashboard` interface and change
`recent_interviews: unknown[];` to `recent_interviews: RecentInterview[];`.

- [ ] **Step 2: Write `frontend/src/services/api/interview.ts`**

```typescript
import { api } from "@/services/api/client";
import type { Interview, InterviewLevel } from "@/types";

export const startInterview = (trackId: number, level: InterviewLevel, questionCount: number) =>
  api<Interview>(`/api/tracks/${trackId}/interviews`, {
    method: "POST",
    body: JSON.stringify({ level, question_count: questionCount }),
  });

export const getInterview = (interviewId: number) =>
  api<Interview>(`/api/interviews/${interviewId}`);

export const saveInterviewAnswer = (
  interviewId: number,
  questionId: number,
  transcript: string,
  durationS: number,
) =>
  api<null>(`/api/interviews/${interviewId}/questions/${questionId}/answer`, {
    method: "POST",
    body: JSON.stringify({ transcript, duration_s: durationS }),
  });

export const submitInterview = (interviewId: number) =>
  api<Interview>(`/api/interviews/${interviewId}/submit`, { method: "POST" });

export const quitInterview = (interviewId: number) =>
  api<Interview>(`/api/interviews/${interviewId}/quit`, { method: "POST" });
```

- [ ] **Step 3: Write `frontend/src/hooks/useInterview.ts`**

```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { dashboardKey } from "@/hooks/useDashboard";
import {
  getInterview,
  quitInterview,
  saveInterviewAnswer,
  startInterview,
  submitInterview,
} from "@/services/api/interview";
import type { InterviewLevel } from "@/types";

export const interviewKey = (id: number) => ["interview", id] as const;

export function useInterview(interviewId: number) {
  return useQuery({
    queryKey: interviewKey(interviewId),
    queryFn: () => getInterview(interviewId),
  });
}

export function useStartInterview() {
  return useMutation({
    mutationFn: ({
      trackId,
      level,
      questionCount,
    }: {
      trackId: number;
      level: InterviewLevel;
      questionCount: number;
    }) => startInterview(trackId, level, questionCount),
  });
}

export function useSaveInterviewAnswer(interviewId: number) {
  return useMutation({
    mutationFn: ({
      questionId,
      transcript,
      durationS,
    }: {
      questionId: number;
      transcript: string;
      durationS: number;
    }) => saveInterviewAnswer(interviewId, questionId, transcript, durationS),
  });
}

export function useSubmitInterview(interviewId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => submitInterview(interviewId),
    onSuccess: (data) => {
      queryClient.setQueryData(interviewKey(interviewId), data);
      queryClient.invalidateQueries({ queryKey: dashboardKey });
    },
  });
}

export function useQuitInterview(interviewId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => quitInterview(interviewId),
    onSuccess: (data) => {
      queryClient.setQueryData(interviewKey(interviewId), data);
      queryClient.invalidateQueries({ queryKey: dashboardKey });
    },
  });
}
```

- [ ] **Step 4: Typecheck**

Run: `cd frontend && npx tsc -b --noEmit`
Expected: clean (no errors)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/services/api/interview.ts frontend/src/hooks/useInterview.ts
git commit -m "feat(frontend): add interview types, API client, and data hooks"
```

---

## Task 7: Interview state machine — pure transition + orchestration hook

**Files:**
- Create: `frontend/src/lib/interviewMachine.ts`
- Test: `frontend/src/lib/__tests__/interviewMachine.test.ts`
- Create: `frontend/src/hooks/useInterviewMachine.ts`

`transition()` is pure — no React, no browser APIs, no I/O — and gets direct
unit tests, same pattern as `lib/progress.ts`. `useInterviewMachine` wraps it
in `useReducer` and orchestrates the two speech hooks (built next, in Task
8) plus the interview mutations from Task 6; it is **not** unit-tested,
matching this plan's stated testing approach — it depends on
`SpeechSynthesis`/`SpeechRecognition`, which don't exist in jsdom at all, so
it's verified by the live browser checks in Task 11 instead.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/lib/__tests__/interviewMachine.test.ts`:

```typescript
import { describe, expect, it } from "vitest";

import { initialMachineState, transition } from "@/lib/interviewMachine";

describe("transition", () => {
  it("BEGIN from briefing moves to speaking at question 0", () => {
    const state = transition(initialMachineState(), { type: "BEGIN" });
    expect(state).toEqual({ phase: "speaking", questionIndex: 0 });
  });

  it("BEGIN is ignored outside briefing", () => {
    const speaking = { phase: "speaking" as const, questionIndex: 0 };
    expect(transition(speaking, { type: "BEGIN" })).toEqual(speaking);
  });

  it("TTS_DONE from speaking moves to answering, same question", () => {
    const speaking = { phase: "speaking" as const, questionIndex: 2 };
    const state = transition(speaking, { type: "TTS_DONE" });
    expect(state).toEqual({ phase: "answering", questionIndex: 2 });
  });

  it("TTS_DONE is ignored outside speaking", () => {
    const briefing = initialMachineState();
    expect(transition(briefing, { type: "TTS_DONE" })).toEqual(briefing);
  });

  it("ANSWER_ADVANCE when not the last question moves to speaking, next question", () => {
    const answering = { phase: "answering" as const, questionIndex: 0 };
    const state = transition(answering, { type: "ANSWER_ADVANCE", isLastQuestion: false });
    expect(state).toEqual({ phase: "speaking", questionIndex: 1 });
  });

  it("ANSWER_ADVANCE on the last question moves to review", () => {
    const answering = { phase: "answering" as const, questionIndex: 4 };
    const state = transition(answering, { type: "ANSWER_ADVANCE", isLastQuestion: true });
    expect(state).toEqual({ phase: "review", questionIndex: 4 });
  });

  it("ANSWER_ADVANCE is ignored outside answering", () => {
    const speaking = { phase: "speaking" as const, questionIndex: 0 };
    expect(
      transition(speaking, { type: "ANSWER_ADVANCE", isLastQuestion: false }),
    ).toEqual(speaking);
  });

  it("review is an absorbing state — all events are ignored", () => {
    const review = { phase: "review" as const, questionIndex: 4 };
    expect(transition(review, { type: "BEGIN" })).toEqual(review);
    expect(transition(review, { type: "TTS_DONE" })).toEqual(review);
    expect(
      transition(review, { type: "ANSWER_ADVANCE", isLastQuestion: true }),
    ).toEqual(review);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/lib/__tests__/interviewMachine.test.ts`
Expected: FAIL — `Cannot find module '@/lib/interviewMachine'`

- [ ] **Step 3: Write `frontend/src/lib/interviewMachine.ts`**

```typescript
export type MachinePhase = "briefing" | "speaking" | "answering" | "review";

export interface MachineState {
  phase: MachinePhase;
  questionIndex: number;
}

export type MachineEvent =
  | { type: "BEGIN" }
  | { type: "TTS_DONE" }
  | { type: "ANSWER_ADVANCE"; isLastQuestion: boolean };

export function initialMachineState(): MachineState {
  return { phase: "briefing", questionIndex: 0 };
}

export function transition(state: MachineState, event: MachineEvent): MachineState {
  if (state.phase === "briefing" && event.type === "BEGIN") {
    return { phase: "speaking", questionIndex: 0 };
  }
  if (state.phase === "speaking" && event.type === "TTS_DONE") {
    return { ...state, phase: "answering" };
  }
  if (state.phase === "answering" && event.type === "ANSWER_ADVANCE") {
    if (event.isLastQuestion) {
      return { ...state, phase: "review" };
    }
    return { phase: "speaking", questionIndex: state.questionIndex + 1 };
  }
  return state;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/lib/__tests__/interviewMachine.test.ts`
Expected: PASS — `8 passed`

- [ ] **Step 5: Write `frontend/src/hooks/useInterviewMachine.ts`**

```typescript
import { useCallback, useEffect, useReducer, useRef } from "react";
import { useNavigate } from "react-router-dom";

import { useQuitInterview, useSaveInterviewAnswer, useSubmitInterview } from "@/hooks/useInterview";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";
import { useSpeechSynthesis } from "@/hooks/useSpeechSynthesis";
import { initialMachineState, transition } from "@/lib/interviewMachine";
import type { Interview } from "@/types";

export function useInterviewMachine(interview: Interview) {
  const [state, dispatch] = useReducer(transition, initialMachineState());
  const tts = useSpeechSynthesis();
  const stt = useSpeechRecognition();
  const saveAnswer = useSaveInterviewAnswer(interview.id);
  const submit = useSubmitInterview(interview.id);
  const quit = useQuitInterview(interview.id);
  const navigate = useNavigate();
  const answerStartRef = useRef<number | null>(null);

  const currentQuestion = interview.questions[state.questionIndex] ?? null;
  const isLastQuestion = state.questionIndex === interview.questions.length - 1;

  const begin = useCallback(() => dispatch({ type: "BEGIN" }), []);

  useEffect(() => {
    if (state.phase !== "speaking" || !currentQuestion) return;
    if (!tts.supported) {
      dispatch({ type: "TTS_DONE" });
      return;
    }
    tts.speak(currentQuestion.question, () => dispatch({ type: "TTS_DONE" }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.phase, state.questionIndex]);

  useEffect(() => {
    if (state.phase !== "answering") return;
    answerStartRef.current = Date.now();
    if (!stt.supported) return;
    stt.start();
    return () => stt.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.phase, state.questionIndex]);

  useEffect(() => {
    if (state.phase === "review") submit.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.phase]);

  const advance = useCallback(
    (manualTranscript?: string) => {
      if (!currentQuestion) return;
      stt.stop();
      const durationS = answerStartRef.current
        ? Math.round((Date.now() - answerStartRef.current) / 1000)
        : 0;
      const transcript = stt.supported ? stt.transcript : (manualTranscript ?? "");
      saveAnswer.mutate({ questionId: currentQuestion.id, transcript, durationS });
      dispatch({ type: "ANSWER_ADVANCE", isLastQuestion });
    },
    [currentQuestion, isLastQuestion, saveAnswer, stt],
  );

  const quitNow = useCallback(() => {
    tts.cancel();
    stt.stop();
    quit.mutate(undefined, { onSuccess: () => navigate("/") });
  }, [tts, stt, quit, navigate]);

  return {
    phase: state.phase,
    currentQuestion,
    questionNumber: state.questionIndex + 1,
    totalQuestions: interview.questions.length,
    begin,
    advance,
    quitNow,
    ttsSupported: tts.supported,
    sttSupported: stt.supported,
    liveTranscript: stt.transcript,
    listening: stt.listening,
  };
}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/interviewMachine.ts frontend/src/lib/__tests__/interviewMachine.test.ts frontend/src/hooks/useInterviewMachine.ts
git commit -m "feat(frontend): add pure interview state machine and orchestration hook"
```

Note: this won't typecheck cleanly until Task 8 adds `useSpeechRecognition`
and `useSpeechSynthesis` — that's expected and fine to commit anyway, same
as Plan 3's Task 4/5 split where a step was known-incomplete until the next
task landed. If your workflow requires green typecheck before every commit,
do Task 8 first and commit both together instead.

---

## Task 8: Speech hooks

**Files:**
- Create: `frontend/src/types/speech.d.ts`
- Create: `frontend/src/hooks/useSpeechSynthesis.ts`
- Create: `frontend/src/hooks/useSpeechRecognition.ts`

**A real finding, verified live before writing this task:** `SpeechRecognition`
is not part of TypeScript's default DOM lib — checked directly with
`npx tsc --noEmit --lib es2020,dom` against a two-line probe file using
`SpeechSynthesisUtterance` (compiled clean) and `new SpeechRecognition()`
(failed with `Cannot find name 'SpeechRecognition'`). `SpeechSynthesis`/
`SpeechSynthesisUtterance` are standard and need no extra typing;
`SpeechRecognition` does. `types/speech.d.ts` below declares only the
members actually used, not the full spec surface.

No new tests in this task — matches this plan's stated approach (these are
un-mockable-in-jsdom browser API wrappers; the earlier live checks confirm
the runtime behavior they're built around, Task 11 confirms them wired
correctly in the real app).

- [ ] **Step 1: Write `frontend/src/types/speech.d.ts`**

```typescript
interface SpeechRecognitionResult {
  0: { transcript: string };
  length: number;
}

interface SpeechRecognitionResultList {
  length: number;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  start(): void;
  stop(): void;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
}

interface Window {
  SpeechRecognition?: new () => SpeechRecognition;
  webkitSpeechRecognition?: new () => SpeechRecognition;
}
```

- [ ] **Step 2: Write `frontend/src/hooks/useSpeechSynthesis.ts`**

```typescript
import { useCallback, useRef } from "react";

export function useSpeechSynthesis() {
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  const speak = useCallback(
    (text: string, onEnd: () => void) => {
      if (!supported) {
        onEnd();
        return;
      }
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.95;
      const voice = window.speechSynthesis.getVoices().find((v) => v.lang.startsWith("en"));
      if (voice) utterance.voice = voice;
      utterance.onend = onEnd;
      utterance.onerror = onEnd;
      utteranceRef.current = utterance;
      window.speechSynthesis.speak(utterance);
    },
    [supported],
  );

  const cancel = useCallback(() => {
    if (supported) window.speechSynthesis.cancel();
  }, [supported]);

  return { speak, cancel, supported };
}
```

`onerror` falls through to the same `onEnd` callback as a normal finish —
if speech fails mid-utterance there's no good recovery, and the interview
must still be able to move forward rather than hang waiting for a callback
that will never come.

- [ ] **Step 3: Write `frontend/src/hooks/useSpeechRecognition.ts`**

```typescript
import { useCallback, useRef, useState } from "react";

function getSpeechRecognitionCtor(): (new () => SpeechRecognition) | null {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

export function useSpeechRecognition() {
  const [transcript, setTranscript] = useState("");
  const [listening, setListening] = useState(false);
  const [supported, setSupported] = useState(getSpeechRecognitionCtor() !== null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  const start = useCallback(() => {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) {
      setSupported(false);
      return;
    }
    setTranscript("");
    const recognition = new Ctor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.onresult = (event) => {
      let combined = "";
      for (let i = 0; i < event.results.length; i++) {
        combined += event.results[i][0].transcript;
      }
      setTranscript(combined);
    };
    // A real user declining microphone permission surfaces here as
    // error: "not-allowed" — live-verified in this plan's header. Any
    // error means recognition cannot be trusted for the rest of this
    // session, not just this question, so it downgrades `supported`
    // rather than only stopping this one attempt.
    recognition.onerror = () => {
      setSupported(false);
      setListening(false);
    };
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  }, []);

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
    setListening(false);
  }, []);

  return { start, stop, transcript, listening, supported };
}
```

- [ ] **Step 4: Typecheck, build, test**

Run: `cd frontend && npx tsc -b --noEmit && npm run build && npm test`
Expected: all clean, `23 passed` (15 before this plan + the 8
`interviewMachine.test.ts` cases from Task 7) — this is also where Task 7's
`useInterviewMachine` finally typechecks, since both speech hooks now exist.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/speech.d.ts frontend/src/hooks/useSpeechSynthesis.ts frontend/src/hooks/useSpeechRecognition.ts
git commit -m "feat(frontend): add TTS/STT hooks with a minimal SpeechRecognition type declaration"
```

---

## Task 9: Setup form and setup page

**Files:**
- Create: `frontend/src/components/interview/SetupForm.tsx`
- Create: `frontend/src/pages/InterviewSetupPage.tsx`

Presentational — verified by typecheck/build here, by real browser check in
Task 11, no new Vitest coverage, matching this plan's established approach.

Level defaults to the active track's **declared** `experience_level`, not
its assessed level — the backend has no endpoint exposing "latest assessed
level for a track" (assessment_service's `get_latest_completed_assessment`
is only ever used internally by `roadmap_service`), and adding one just for
a nicer default isn't worth the new surface. The declared level is already
available client-side via `useActiveTrack()`, and it's a one-click override
either way — a deliberate simplification from this plan's design doc, not
an oversight.

- [ ] **Step 1: Write `frontend/src/components/interview/SetupForm.tsx`**

```tsx
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { EXPERIENCE_LEVELS } from "@/lib/constants";
import type { InterviewLevel } from "@/types";

const QUESTION_COUNTS = [5, 8, 10] as const;

interface SetupFormProps {
  defaultLevel: InterviewLevel;
  pending: boolean;
  onStart: (level: InterviewLevel, questionCount: number) => void;
}

export function SetupForm({ defaultLevel, pending, onStart }: SetupFormProps) {
  const [level, setLevel] = useState<InterviewLevel>(defaultLevel);
  const [questionCount, setQuestionCount] = useState<number>(8);

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <p className="text-sm font-medium text-text-primary">Level</p>
        <div className="flex flex-wrap gap-2">
          {EXPERIENCE_LEVELS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setLevel(option.value)}
              className={cn(
                "rounded-full border px-4 py-2 text-sm font-medium transition-colors",
                level === option.value
                  ? "border-accent bg-accent-soft text-accent"
                  : "border-line text-text-secondary hover:border-accent/50",
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-sm font-medium text-text-primary">Number of questions</p>
        <div className="flex gap-2">
          {QUESTION_COUNTS.map((count) => (
            <button
              key={count}
              type="button"
              onClick={() => setQuestionCount(count)}
              className={cn(
                "rounded-full border px-4 py-2 text-sm font-medium transition-colors",
                questionCount === count
                  ? "border-accent bg-accent-soft text-accent"
                  : "border-line text-text-secondary hover:border-accent/50",
              )}
            >
              {count}
            </button>
          ))}
        </div>
      </div>

      <Button disabled={pending} onClick={() => onStart(level, questionCount)}>
        {pending ? "Generating questions…" : "Start interview"}
      </Button>
    </div>
  );
}
```

- [ ] **Step 2: Write `frontend/src/pages/InterviewSetupPage.tsx`**

```tsx
import { Loader2 } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";
import { SetupForm } from "@/components/interview/SetupForm";
import { useStartInterview } from "@/hooks/useInterview";
import { useActiveTrack } from "@/hooks/useProfile";
import type { InterviewLevel } from "@/types";

export default function InterviewSetupPage() {
  const { data: track, isPending } = useActiveTrack();
  const startInterview = useStartInterview();
  const navigate = useNavigate();

  if (isPending) {
    return (
      <AppShell>
        <div className="grid place-items-center py-24">
          <Loader2 className="size-6 animate-spin text-text-muted" />
        </div>
      </AppShell>
    );
  }

  if (!track) {
    return (
      <AppShell>
        <TopBar title="Mock interview" subtitle="Pick a track from the dashboard first." />
      </AppShell>
    );
  }

  const handleStart = (level: InterviewLevel, questionCount: number) => {
    startInterview.mutate(
      { trackId: track.id, level, questionCount },
      { onSuccess: (interview) => navigate(`/interview/${interview.id}`) },
    );
  };

  return (
    <AppShell>
      <TopBar
        title="Mock interview"
        subtitle={`${track.topic} — questions are generated for you, answer out loud.`}
      />
      <SetupForm
        defaultLevel={track.experience_level}
        pending={startInterview.isPending}
        onStart={handleStart}
      />
      {startInterview.error && (
        <p className="mt-4 text-sm text-danger">
          {startInterview.error instanceof Error
            ? startInterview.error.message
            : "Something went wrong generating your questions."}
        </p>
      )}
    </AppShell>
  );
}
```

- [ ] **Step 3: Typecheck and build**

Run: `cd frontend && npx tsc -b --noEmit && npm run build`
Expected: both clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/interview/SetupForm.tsx frontend/src/pages/InterviewSetupPage.tsx
git commit -m "feat(frontend): add interview setup form and page"
```

---

## Task 10: Active interview page and App.tsx wiring

**Files:**
- Create: `frontend/src/components/interview/TranscriptPanel.tsx`
- Create: `frontend/src/components/interview/QuestionStage.tsx`
- Create: `frontend/src/pages/InterviewActivePage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write `frontend/src/components/interview/TranscriptPanel.tsx`**

```tsx
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/cn";

interface TranscriptPanelProps {
  sttSupported: boolean;
  listening: boolean;
  liveTranscript: string;
  manualValue: string;
  onManualChange: (value: string) => void;
}

export function TranscriptPanel({
  sttSupported,
  listening,
  liveTranscript,
  manualValue,
  onManualChange,
}: TranscriptPanelProps) {
  if (!sttSupported) {
    return (
      <div className="space-y-2">
        <p className="text-xs text-text-muted">
          Speech recognition unavailable in this browser — type your answer.
        </p>
        <Textarea
          value={manualValue}
          onChange={(e) => onManualChange(e.target.value)}
          rows={6}
          placeholder="Type your answer…"
        />
      </div>
    );
  }

  return (
    <div className="space-y-2 rounded-lg border border-line bg-surface p-4">
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "size-2 rounded-full",
            listening ? "animate-pulse bg-danger" : "bg-text-muted",
          )}
        />
        <p className="text-xs text-text-muted">{listening ? "Listening…" : "Not listening"}</p>
      </div>
      <p className="min-h-24 text-sm text-text-primary">
        {liveTranscript || "Start speaking — your words will appear here."}
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Write `frontend/src/components/interview/QuestionStage.tsx`**

```tsx
import { ArrowRight, LogOut } from "lucide-react";
import { useState } from "react";

import { TranscriptPanel } from "@/components/interview/TranscriptPanel";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import type { Interview, MachinePhase } from "@/types";

interface QuestionStageProps {
  interview: Interview;
  phase: MachinePhase;
  currentQuestion: Interview["questions"][number] | null;
  questionNumber: number;
  totalQuestions: number;
  ttsSupported: boolean;
  sttSupported: boolean;
  listening: boolean;
  liveTranscript: string;
  onBegin: () => void;
  onAdvance: (manualTranscript?: string) => void;
  onQuit: () => void;
}

export function QuestionStage({
  interview,
  phase,
  currentQuestion,
  questionNumber,
  totalQuestions,
  ttsSupported,
  sttSupported,
  listening,
  liveTranscript,
  onBegin,
  onAdvance,
  onQuit,
}: QuestionStageProps) {
  const [manualAnswer, setManualAnswer] = useState("");

  if (phase === "briefing") {
    return (
      <Card className="space-y-4">
        <CardTitle>Ready when you are</CardTitle>
        <CardDescription>
          {totalQuestions} questions, {interview.level} level.{" "}
          {ttsSupported
            ? "Each question will be read aloud."
            : "Your browser can't read questions aloud — they'll be shown as text instead."}
        </CardDescription>
        <Button onClick={onBegin}>
          Start <ArrowRight className="size-4" />
        </Button>
      </Card>
    );
  }

  if (phase === "review") {
    return (
      <Card className="space-y-4">
        <CardTitle>Interview complete</CardTitle>
        <CardDescription>
          You answered all {totalQuestions} questions. Scoring and feedback arrive in a later
          build.
        </CardDescription>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-text-muted">
          Question {questionNumber} of {totalQuestions}
        </p>
        <Button variant="ghost" size="sm" onClick={onQuit}>
          <LogOut className="size-4" /> End interview
        </Button>
      </div>

      <Card>
        <CardTitle>{currentQuestion?.question}</CardTitle>
      </Card>

      {phase === "answering" && (
        <>
          <TranscriptPanel
            sttSupported={sttSupported}
            listening={listening}
            liveTranscript={liveTranscript}
            manualValue={manualAnswer}
            onManualChange={setManualAnswer}
          />
          <Button onClick={() => onAdvance(manualAnswer)}>
            {questionNumber === totalQuestions ? "Finish" : "Next question"}{" "}
            <ArrowRight className="size-4" />
          </Button>
        </>
      )}
    </div>
  );
}
```

Add `MachinePhase` to `frontend/src/types/index.ts` (it's currently only
exported from `lib/interviewMachine.ts`, which components shouldn't import
from directly — types belong in `types/index.ts`, machine logic in `lib/`):

```typescript
export type MachinePhase = "briefing" | "speaking" | "answering" | "review";
```

Then in `frontend/src/lib/interviewMachine.ts`, replace the local
`MachinePhase` definition with an import:

```typescript
import type { MachinePhase } from "@/types";
```

(removing the `export type MachinePhase = ...` line that's now in `types/index.ts` instead).

- [ ] **Step 3: Write `frontend/src/pages/InterviewActivePage.tsx`**

```tsx
import { Loader2 } from "lucide-react";
import { useParams } from "react-router-dom";

import { QuestionStage } from "@/components/interview/QuestionStage";
import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";
import { useInterview } from "@/hooks/useInterview";
import { useInterviewMachine } from "@/hooks/useInterviewMachine";
import type { Interview } from "@/types";

function ActiveInterview({ interview }: { interview: Interview }) {
  const machine = useInterviewMachine(interview);

  return (
    <AppShell>
      <TopBar title={`${interview.level} interview`} />
      <QuestionStage
        interview={interview}
        phase={machine.phase}
        currentQuestion={machine.currentQuestion}
        questionNumber={machine.questionNumber}
        totalQuestions={machine.totalQuestions}
        ttsSupported={machine.ttsSupported}
        sttSupported={machine.sttSupported}
        listening={machine.listening}
        liveTranscript={machine.liveTranscript}
        onBegin={machine.begin}
        onAdvance={machine.advance}
        onQuit={machine.quitNow}
      />
    </AppShell>
  );
}

export default function InterviewActivePage() {
  const { id } = useParams<{ id: string }>();
  const interviewId = Number(id);
  const { data: interview, isPending } = useInterview(interviewId);

  if (isPending || !interview) {
    return (
      <AppShell>
        <div className="grid place-items-center py-24">
          <Loader2 className="size-6 animate-spin text-text-muted" />
        </div>
      </AppShell>
    );
  }

  return <ActiveInterview interview={interview} />;
}
```

The split between `InterviewActivePage` and `ActiveInterview` exists because
`useInterviewMachine` requires a non-null `Interview` — it can't be called
conditionally after an early return in the same component (rules of hooks),
so the outer component handles the loading state and the inner one only
ever mounts once real data exists.

- [ ] **Step 4: Wire `frontend/src/App.tsx`**

Replace the whole file:

```tsx
import { Loader2 } from "lucide-react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { useProfile } from "@/hooks/useProfile";
import AssessmentPage from "@/pages/AssessmentPage";
import DashboardPage from "@/pages/DashboardPage";
import InterviewActivePage from "@/pages/InterviewActivePage";
import InterviewSetupPage from "@/pages/InterviewSetupPage";
import OnboardingPage from "@/pages/OnboardingPage";
import RoadmapPage from "@/pages/RoadmapPage";
import SettingsPage from "@/pages/SettingsPage";

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
      <Route path="/assessment/:id" element={<AssessmentPage />} />
      <Route path="/" element={<DashboardPage />} />
      <Route path="/roadmap" element={<RoadmapPage />} />
      <Route path="/interview" element={<InterviewSetupPage />} />
      <Route path="/interview/:id" element={<InterviewActivePage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
```

The `Placeholder` helper is removed along with its only remaining use (the
old `/interview` route) — and since nothing else in this file used
`AppShell`/`TopBar` directly (both were only ever used inside
`Placeholder`), their imports are dropped too. `noUnusedLocals` would fail
the build otherwise. Both components are still used plenty elsewhere (every
page imports them itself) — just not in `App.tsx` anymore.

- [ ] **Step 5: Typecheck, build, test**

Run: `cd frontend && npx tsc -b --noEmit && npm run build && npm test`
Expected: all clean, still `23 passed` — Tasks 9-10 are presentational, no
new Vitest coverage, matching this plan's established approach.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/interview/TranscriptPanel.tsx frontend/src/components/interview/QuestionStage.tsx frontend/src/pages/InterviewActivePage.tsx frontend/src/App.tsx frontend/src/types/index.ts frontend/src/lib/interviewMachine.ts
git commit -m "feat(frontend): add active interview page, wire /interview routes"
```

---

## Task 11: Full live E2E browser verification

**Files:** none — verification only, matching Plan 3's Task 11 structure.

Start both servers (`uvicorn main:app --reload` on :8000, `npm run dev` on
:5173) in a real browser. Gemini quota was unpredictable throughout Plan 3
— sometimes a real `429`, sometimes a genuine `400`, never fully reliable —
so this task is split into what's verifiable for free versus what needs a
real, successful Gemini call.

- [x] **Step 1: Zero-quota verification — seed an interview directly**

Question generation itself is already proven by `FakeAIClient`-backed tests
in Tasks 3 and 5 (13 + 11 tests). What those tests *cannot* touch is
real-browser behavior: TTS actually speaking, STT's fallback path actually
rendering, the machine actually advancing through real DOM interactions. To
verify all of that without spending any quota, seed an interview straight
into the dev DB, the same technique Plan 3's Task 11 used for the assessment
result screen:

```bash
cd backend && .venv/bin/python -c "
from db.session import SessionLocal
from models.user import User, LearningTrack
from models.interview import Interview, InterviewQuestion

db = SessionLocal()
user = db.query(User).first() or User(name='Aryan')
if user.id is None:
    db.add(user); db.commit(); db.refresh(user)
track = LearningTrack(user_id=user.id, topic='Python', experience_level='intermediate', is_active=True)
for t in db.query(LearningTrack).all():
    t.is_active = False
db.add(track); db.commit(); db.refresh(track)

interview = Interview(track_id=track.id, level='intermediate', question_count=2, status='active')
db.add(interview); db.commit(); db.refresh(interview)
for i, q in enumerate(['Explain what a Python decorator does.', 'What is the GIL?']):
    db.add(InterviewQuestion(interview_id=interview.id, order_index=i, question=q, expected_points=['a', 'b']))
db.commit()
print('interview_id:', interview.id)
"
```

Navigate to `/interview/{id}` from that output and confirm, in order — all
confirmed working, done 2026-08-08:
1. [x] Briefing screen showed "2 questions, intermediate level" and stated
   TTS would read questions aloud.
2. [x] Clicking "Start" spoke the first question and the UI moved to the
   answering view once `onEnd` fired.
3. [x] `useSpeechRecognition` correctly hit its `onerror` path (no real mic
   in this environment) and the transcript panel fell back to the plain
   textarea with the "Speech recognition unavailable" message — did not get
   stuck showing "Listening…".
4. [x] Typing an answer and clicking "Next question" advanced to question 2
   and spoke it.
5. [x] Answering the last question and clicking "Finish" moved to the
   review screen and called `/submit` — confirmed via `GET
   /api/interviews/{id}` that `status: "completed"`, `ended_at` set, and
   critically that **both questions had their own distinct transcript**
   ("ANSWER ONE" / "ANSWER TWO") with real, different
   `answer_duration_s` values (23s, 32s) — proving per-question state
   doesn't bleed across questions.
6. [x] Seeded a second `active` interview, clicked "End interview" partway
   through — navigated to the dashboard, and `GET /api/interviews/{id}`
   confirmed `status: "terminated"`, `termination_reason: "user_quit"`.

**A real bug was found and fixed here, not anticipated by this plan:**
step 5's distinct-transcript check initially failed — question 2's textarea
loaded pre-filled with question 1's answer. `QuestionStage`'s `manualAnswer`
is `useState` local to that component, but `QuestionStage` itself never
unmounts across questions (only its props change as the machine advances),
so the state persisted across questions instead of resetting. Fixed by
keying `<QuestionStage>` on `machine.currentQuestion?.id` in
`InterviewActivePage.tsx` — forces a fresh mount (and fresh `manualAnswer`)
on every new question, the standard React fix for "reset local state when
the thing it belongs to changes." Re-ran the full flow after the fix with
two different answers and confirmed both landed on the correct questions.

- [x] **Step 2: Setup page and dashboard, still zero-quota**

Navigated to `/interview` directly — level selector correctly defaulted to
the active track's declared level ("Intermediate"), question count defaulted
to 8, both changeable.

Loaded `/` (dashboard) — the interviews from Step 1 appeared under "Recent
interviews". **A second real bug was found and fixed here:** the card's
label was hardcoded from Plan 3 as `"${recent_interviews.length}
completed."` regardless of actual status — with one `terminated` and one
`completed` interview both showing as "completed," this was visibly wrong
once real status data existed. Fixed by rendering each interview's actual
`level` and `status` (color-coded: green completed, red terminated, accent
active) instead of a single aggregate count. This was Plan 3 code, not Plan
4 code, but the bug was only ever visible once Plan 4 gave the dashboard
real interviews to show — fixing it now rather than leaving a known-wrong
label in place.

- [x] **Step 3: Real generation — confirmed working, not just best-effort**

From `/interview`, picked Intermediate / 5 questions, clicked "Start
interview." **Quota was available this time** (unlike every attempt during
Plan 3) — this proved the entire chain for real: prompt → Gemini →
persisted questions → briefing screen. Confirmed via `GET
/api/interviews/4` that all 5 questions were genuine, high-quality,
distinct intermediate Python questions (list vs. tuple, the `with`
statement/context managers, decorators, generators, deep vs. shallow copy),
each with 4 substantive `expected_points` — real model output, not
boilerplate. This also incidentally confirms the interview prompt's schema
(fully-required, no nullable fields, per this plan's Task 2 note) is
accepted by Gemini without any `400`.

- [x] **Step 4: Record results and clean up**

Results recorded above — everything in this task's scope is confirmed
working, including the real-generation step this plan expected might stay
blocked. Two real bugs found via this live pass (question-answer bleeding
across questions; a stale hardcoded dashboard label) were fixed inline,
re-verified live, and are included in this task's commit. Dev database reset
(`rm backend/careeros.db`) and both servers stopped after verification.

---
