# CareerOS Plan 5 — Proctoring + Evaluation + Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the interview experience — webcam/audio proctoring with server-authoritative warning escalation, AI evaluation of completed interviews with a real report, a history page spanning assessments and interviews — then a polish pass across the whole app. This is the final plan in the CareerOS series; by the end the app matches the original spec end to end.

**Architecture:** Three sequential phases, each leaving the app runnable. Proctoring adds a `preflight` FSM state and a unified `terminated` state (replacing Plan 4's action-only quit), with two browser-API hooks (`useProctoring` for MediaPipe video, `useAudioMonitor` for Web Audio) dispatching into one `useWarnings` reducer that POSTs to a server-authoritative `/events` endpoint — the backend decides severity and termination, never the client. Evaluation extends Plan 4's `complete_interview` (built then as a pure status flip) into a real AI-scoring call, adds `evaluating`/`report` FSM states, and exposes the `list_interviews` function Plan 4 deliberately left unrouted. Polish is scoped concretely once Phases 1-2 reveal what's actually missing.

**Tech Stack:** `@mediapipe/tasks-vision` (new dependency, video pipeline), Web Audio `AnalyserNode` (audio pipeline), FastAPI/SQLAlchemy/Gemini (backend, all established); React 19, TanStack Query, Framer Motion (frontend, all established).

**Spec:** `docs/superpowers/specs/2026-08-08-careeros-proctoring-evaluation-design.md` (Plan 5 design, extends `docs/superpowers/specs/2026-08-07-careeros-design.md` sections 6, 7, 8, 9, 10, 11, 12, 14)

**Series context:** Plan 5 of 5 — the last one.
1. Foundation (done)
2. AI client + assessment (done)
3. Roadmap SSE generation + viewer + progress + dashboard data (done)
4. Interview core + speech (done)
5. **Proctoring + evaluation + reports + polish** ← you are here

**Verified before writing this plan**, against the real browser tool this project's E2E verification uses (not assumed from documentation):
- `navigator.mediaDevices.getUserMedia({ video: true })` rejects cleanly with `NotAllowedError: Permission denied` at 11ms in this sandboxed browser (no real camera available, confirmed explicitly by the tool itself) — the same class of clean, standard error `SpeechRecognition` produced in Plan 4, not a hang or a crash. `useProctoring`'s preflight check is designed below to treat this rejection as "camera unavailable" and fail the preflight step gracefully, the same defensive pattern already proven for `useSpeechRecognition`.
- Real face-tracking accuracy — like real speech transcription in Plan 4 — cannot be verified in this environment at all (no camera feed exists to detect anything in) and is documented as that same honest gap rather than guessed at. Task 11's live E2E verification confirms everything that *can* be confirmed without a camera: the preflight error path, the FSM plumbing, the warning reducer against synthetic events, the server-authoritative `/events` endpoint against real HTTP calls.

---

## File Structure

**Backend** (`backend/`)

| File | Responsibility |
|---|---|
| `models/interview.py` | modified: `+ProctoringEvent` |
| `services/interview_service.py` | modified: `+record_event`, `+EventResult`; `complete_interview` gains a real AI call and an `ai_client` parameter |
| `ai/prompts/evaluation.py` | `build_evaluation_prompt` — single call, whole interview, pure |
| `schemas/interview.py` | modified: `+ProctoringEventIn`, `+ProctoringEventOut`; `InterviewOut`/`InterviewQuestionOut` gain the score fields that have been `NULL` since Plan 4 |
| `routers/interview.py` | modified: `+POST .../events`, `+GET /api/interviews`; `/submit` gains the `ai_client` dependency |
| `tests/test_interview_models.py` | modified: `+ProctoringEvent` round-trip, cascade delete |
| `tests/test_interview_service.py` | modified: `+record_event` (warning accumulation, 3-strike termination, fatal immediate termination, rejected-after-termination), `+complete_interview` evaluation |
| `tests/test_interview_api.py` | modified: `+/events`, `+GET /api/interviews` |
| `tests/test_evaluation_prompts.py` | pure prompt builder tests |

**Frontend** (`frontend/src/`)

| File | Responsibility |
|---|---|
| `types/index.ts` | modified: `MachinePhase` gains `preflight`/`terminated`/`evaluating`/`report`; `Interview`/`InterviewQuestion` gain score fields; `+ProctoringEventType`, `+RecentAssessment` |
| `lib/interviewMachine.ts` | modified: new states and transitions for preflight, unified termination, evaluating, report |
| `lib/__tests__/interviewMachine.test.ts` | modified: new transition cases |
| `lib/proctorRules.ts` | pure: `matrixToEuler`, threshold/sustain checks — no MediaPipe import |
| `lib/__tests__/proctorRules.test.ts` | matrixToEuler against known matrices, yaw/pitch thresholds, sustain windows |
| `hooks/useWarnings.ts` | the warning reducer both proctoring hooks dispatch into |
| `hooks/__tests__/useWarnings.test.ts` | escalation 1→2→3, cooldown suppression, fatal bypass, backend reconciliation |
| `hooks/useProctoring.ts` | MediaPipe FaceLandmarker video loop |
| `hooks/useAudioMonitor.ts` | Web Audio AnalyserNode loop |
| `hooks/useInterviewMachine.ts` | modified: orchestrates preflight, the two proctoring hooks, evaluating |
| `hooks/useInterview.ts` | modified: `+useRecordEvent`, `+useInterviews` (history list) |
| `services/api/interview.ts` | modified: `+recordEvent`, `+listInterviews` |
| `services/api/assessment.ts` | modified: `+listAssessments` (backend route existed since Plan 2, never had a frontend caller) |
| `components/interview/PreflightCheck.tsx` | camera/mic permission + single-face + noise-floor calibration UI |
| `components/interview/CameraPip.tsx` | small live video feed with landmark overlay |
| `components/interview/WarningOverlay.tsx` | the escalating warning UI, Framer Motion shake |
| `components/interview/QuestionStage.tsx` | modified: renders `preflight`/`terminated`, hosts the camera PiP during active phases |
| `pages/InterviewActivePage.tsx` | modified: wires the proctoring hooks in |
| `pages/InterviewReportPage.tsx` | `/interview/:id/report` — scores, per-question breakdown, strengths/weaknesses/recommendations |
| `pages/HistoryPage.tsx` | `/history` — past assessments and interviews |
| `App.tsx` | modified: `+/interview/:id/report`, `+/history` |
| `components/layout/Sidebar.tsx` | modified: `+History` nav link |
| `public/models/face_landmarker.task`, `public/wasm/*` | vendored MediaPipe assets — downloaded only with explicit permission at that task, filename/source/size stated then |
| `package.json` | modified: `+@mediapipe/tasks-vision` |
| `README.md` | modified: finished-app description |

---

## Task 1: ProctoringEvent model

**Files:**
- Modify: `backend/models/interview.py`
- Test: `backend/tests/test_interview_models.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_interview_models.py`:

```python
from models.interview import ProctoringEvent


def _interview(db_session):
    track = _track(db_session)
    interview = Interview(
        track_id=track.id, level="intermediate", question_count=5, status="active"
    )
    db_session.add(interview)
    db_session.commit()
    return interview


def test_proctoring_event_round_trip(db_session):
    interview = _interview(db_session)

    event = ProctoringEvent(
        interview_id=interview.id,
        type="looking_away",
        severity="warning",
        detail="yaw 30deg for 2.6s",
        warning_index=1,
    )
    db_session.add(event)
    db_session.commit()

    assert interview.events == [event]
    assert event.interview is interview
    assert event.question_id is None
    assert event.created_at is not None


def test_deleting_interview_cascades_to_proctoring_events(db_session):
    interview = _interview(db_session)
    event = ProctoringEvent(
        interview_id=interview.id, type="no_face", severity="warning", detail=""
    )
    db_session.add(event)
    db_session.commit()
    event_id = event.id

    db_session.delete(interview)
    db_session.commit()

    assert db_session.get(ProctoringEvent, event_id) is None


def test_fatal_event_has_no_warning_index(db_session):
    interview = _interview(db_session)

    event = ProctoringEvent(
        interview_id=interview.id,
        type="multiple_faces",
        severity="fatal",
        detail="2 faces detected",
    )
    db_session.add(event)
    db_session.commit()

    assert event.severity == "fatal"
    assert event.warning_index is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_interview_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'ProctoringEvent' from 'models.interview'`

- [ ] **Step 3: Add `ProctoringEvent` to `backend/models/interview.py`**

Add `events` to the existing `Interview` class, right after its `questions`
relationship:

```python
    events: Mapped[list["ProctoringEvent"]] = relationship(
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="ProctoringEvent.created_at",
    )
```

Append a new class at the end of the file:

```python
class ProctoringEvent(Base):
    """One flagged moment during proctoring. warning_index is
    Interview.warning_count's value *after* incrementing, written onto this
    specific row — a fatal event never increments the count, so it always
    has warning_index=NULL."""

    __tablename__ = "proctoring_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"))
    question_id: Mapped[int | None] = mapped_column(
        ForeignKey("interview_questions.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(8), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    warning_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    interview: Mapped["Interview"] = relationship(back_populates="events")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_interview_models.py -v`
Expected: PASS — `6 passed` (3 from Plan 4 + 3 new)

- [ ] **Step 5: Commit**

```bash
git add backend/models/interview.py backend/tests/test_interview_models.py
git commit -m "feat(backend): add ProctoringEvent model"
```

---

## Task 2: record_event service and the /events endpoint

**Files:**
- Modify: `backend/services/interview_service.py`
- Modify: `backend/schemas/interview.py`
- Modify: `backend/routers/interview.py`
- Test: `backend/tests/test_interview_service.py`, `backend/tests/test_interview_api.py`

Server-authoritative: severity classification and the termination decision
both happen here, never on the client. `multiple_faces` is fatal and
terminates on its own first occurrence; the other four types accumulate
`warning_count`, and 3 terminates. Events are rejected once an interview is
no longer `active` — matches the master spec's own test list for this file
exactly (warning accumulation, 3-strike termination, fatal immediate
termination, events rejected after termination).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_interview_service.py`:

```python
def test_record_event_warning_increments_count_and_sets_warning_index(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(5))
    interview = interview_service.start_interview(db_session, fake_ai, track.id, "intermediate", 5)

    result = interview_service.record_event(db_session, interview.id, "looking_away", "yaw 30")

    assert result.warning_count == 1
    assert result.should_terminate is False
    db_session.refresh(interview)
    assert interview.warning_count == 1
    assert interview.events[0].warning_index == 1


def test_record_event_three_warnings_terminates(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(5))
    interview = interview_service.start_interview(db_session, fake_ai, track.id, "intermediate", 5)

    interview_service.record_event(db_session, interview.id, "looking_away", "1")
    interview_service.record_event(db_session, interview.id, "no_face", "2")
    result = interview_service.record_event(db_session, interview.id, "looking_away", "3")

    assert result.warning_count == 3
    assert result.should_terminate is True
    db_session.refresh(interview)
    assert interview.status == "terminated"
    assert interview.termination_reason == "proctoring"


def test_record_event_multiple_faces_terminates_immediately(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(5))
    interview = interview_service.start_interview(db_session, fake_ai, track.id, "intermediate", 5)

    result = interview_service.record_event(db_session, interview.id, "multiple_faces", "2 faces")

    assert result.should_terminate is True
    db_session.refresh(interview)
    assert interview.status == "terminated"
    assert interview.warning_count == 0
    assert interview.events[0].severity == "fatal"
    assert interview.events[0].warning_index is None


def test_record_event_after_termination_raises(db_session, fake_ai):
    track = _track(db_session)
    fake_ai.queue_response(_generation_response(5))
    interview = interview_service.start_interview(db_session, fake_ai, track.id, "intermediate", 5)
    interview_service.record_event(db_session, interview.id, "multiple_faces", "terminated now")

    with pytest.raises(interview_service.InterviewNotActiveError):
        interview_service.record_event(db_session, interview.id, "looking_away", "too late")
```

Append to `backend/tests/test_interview_api.py`:

```python
def test_record_event_warning_returns_count(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload(5))
    interview_id = client.post(
        f"/api/tracks/{track_id}/interviews",
        json={"level": "intermediate", "question_count": 5},
    ).json()["id"]

    response = client.post(
        f"/api/interviews/{interview_id}/events", json={"type": "looking_away", "detail": "yaw 30"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["warning_count"] == 1
    assert body["should_terminate"] is False


def test_record_event_multiple_faces_terminates(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload(5))
    interview_id = client.post(
        f"/api/tracks/{track_id}/interviews",
        json={"level": "intermediate", "question_count": 5},
    ).json()["id"]

    response = client.post(
        f"/api/interviews/{interview_id}/events", json={"type": "multiple_faces", "detail": "2 faces"}
    )

    assert response.status_code == 200
    assert response.json()["should_terminate"] is True
    interview = client.get(f"/api/interviews/{interview_id}").json()
    assert interview["status"] == "terminated"
    assert interview["termination_reason"] == "proctoring"


def test_record_event_unknown_interview_returns_404(client):
    response = client.post("/api/interviews/999/events", json={"type": "no_face", "detail": ""})

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "interview_not_found"


def test_record_event_rejects_invalid_type(client, fake_ai):
    track_id = _onboard_and_track(client)
    fake_ai.queue_response(_generation_payload(5))
    interview_id = client.post(
        f"/api/tracks/{track_id}/interviews",
        json={"level": "intermediate", "question_count": 5},
    ).json()["id"]

    response = client.post(
        f"/api/interviews/{interview_id}/events", json={"type": "bogus_type", "detail": ""}
    )

    assert response.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_interview_service.py tests/test_interview_api.py -v`
Expected: FAIL — `AttributeError: module 'services.interview_service' has no attribute 'record_event'`
for the service tests; the API tests fail on 404s (route doesn't exist yet)

- [ ] **Step 3: Add `record_event` to `backend/services/interview_service.py`**

Add to the imports:

```python
from dataclasses import dataclass

from models.interview import Interview, InterviewQuestion, ProctoringEvent
```

(this replaces the existing `from models.interview import Interview,
InterviewQuestion` line — just adding `ProctoringEvent` to it)

Add near the top, after the exception classes:

```python
_FATAL_EVENT_TYPES = frozenset({"multiple_faces"})
_TERMINATION_WARNING_THRESHOLD = 3


@dataclass(frozen=True)
class EventResult:
    warning_count: int
    should_terminate: bool
```

Append at the end of the file:

```python
def record_event(db: Session, interview_id: int, event_type: str, detail: str) -> EventResult:
    interview = get_interview(db, interview_id)
    if interview.status != "active":
        raise InterviewNotActiveError

    severity = "fatal" if event_type in _FATAL_EVENT_TYPES else "warning"
    warning_index = None

    if severity == "warning":
        interview.warning_count += 1
        warning_index = interview.warning_count

    should_terminate = severity == "fatal" or interview.warning_count >= _TERMINATION_WARNING_THRESHOLD

    db.add(
        ProctoringEvent(
            interview_id=interview.id,
            type=event_type,
            severity=severity,
            detail=detail,
            warning_index=warning_index,
        )
    )

    if should_terminate:
        interview.status = "terminated"
        interview.termination_reason = "proctoring"
        interview.ended_at = datetime.now(UTC).replace(tzinfo=None)

    db.commit()
    return EventResult(warning_count=interview.warning_count, should_terminate=should_terminate)
```

- [ ] **Step 4: Add request/response schemas to `backend/schemas/interview.py`**

Append:

```python
ProctoringEventType = Literal[
    "looking_away", "no_face", "multiple_faces", "excessive_noise", "background_voice"
]


class ProctoringEventIn(BaseModel):
    type: ProctoringEventType
    detail: str = ""


class ProctoringEventOut(BaseModel):
    warning_count: int
    should_terminate: bool
```

- [ ] **Step 5: Add the endpoint to `backend/routers/interview.py`**

Add to the imports:

```python
from schemas.interview import (
    AnswerSave,
    InterviewOut,
    ProctoringEventIn,
    ProctoringEventOut,
    StartInterview,
)
```

(replaces the existing `from schemas.interview import AnswerSave,
InterviewOut, StartInterview` line)

Append at the end of the file:

```python
@router.post("/api/interviews/{interview_id}/events", response_model=ProctoringEventOut)
def record_event(interview_id: int, payload: ProctoringEventIn, db: Session = Depends(get_db)):
    try:
        result = interview_service.record_event(db, interview_id, payload.type, payload.detail)
        return ProctoringEventOut(
            warning_count=result.warning_count, should_terminate=result.should_terminate
        )
    except InterviewNotFoundError:
        raise _INTERVIEW_MISSING
    except InterviewNotActiveError:
        raise _NOT_ACTIVE
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_interview_service.py tests/test_interview_api.py -v`
Expected: PASS — `17 passed` (13 from Plan 4 + 4 new) for service,
`15 passed` (11 from Plan 4 + 4 new) for api

- [ ] **Step 7: Run the full backend suite**

Run: `cd backend && .venv/bin/pytest -v`
Expected: PASS — `160 passed` (149 before this plan + 3 model + 4 service + 4 api)

- [ ] **Step 8: Commit**

```bash
git add backend/services/interview_service.py backend/schemas/interview.py backend/routers/interview.py backend/tests/test_interview_service.py backend/tests/test_interview_api.py
git commit -m "feat(backend): add server-authoritative proctoring event handling"
```

---

## Task 3: Pure proctoring math — `lib/proctorRules.ts`

**Files:**
- Create: `frontend/src/lib/proctorRules.ts`
- Test: `frontend/src/lib/__tests__/proctorRules.test.ts`

No MediaPipe import, no camera, no timers — pure math and a pure
sustain/cooldown tracker the real hook drives with real timestamps. This is
exactly the kind of logic that deserves extra test rigor precisely because
it's the one piece of the proctoring pipeline this environment's lack of
camera access can't otherwise touch at all.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/lib/__tests__/proctorRules.test.ts`:

```typescript
import { describe, expect, it } from "vitest";

import {
  initialSustainState,
  isLookingAway,
  matrixToEuler,
  trackSustain,
} from "@/lib/proctorRules";

describe("matrixToEuler", () => {
  it("reads zero angles from an identity matrix (facing forward)", () => {
    const identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
    const angles = matrixToEuler(identity);
    expect(angles.pitch).toBeCloseTo(0, 1);
    expect(angles.yaw).toBeCloseTo(0, 1);
    expect(angles.roll).toBeCloseTo(0, 1);
  });

  it("extracts yaw from a known Y-axis rotation matrix", () => {
    const rad = (30 * Math.PI) / 180;
    const cos = Math.cos(rad);
    const sin = Math.sin(rad);
    const matrix = [cos, 0, -sin, 0, 0, 1, 0, 0, sin, 0, cos, 0, 0, 0, 0, 1];
    const angles = matrixToEuler(matrix);
    expect(angles.yaw).toBeCloseTo(30, 0);
    expect(angles.pitch).toBeCloseTo(0, 0);
  });

  it("extracts pitch from a known X-axis rotation matrix", () => {
    const rad = (-25 * Math.PI) / 180;
    const cos = Math.cos(rad);
    const sin = Math.sin(rad);
    const matrix = [1, 0, 0, 0, 0, cos, sin, 0, 0, -sin, cos, 0, 0, 0, 0, 1];
    const angles = matrixToEuler(matrix);
    expect(angles.pitch).toBeCloseTo(-25, 0);
    expect(angles.yaw).toBeCloseTo(0, 0);
  });
});

describe("isLookingAway", () => {
  it("is true when yaw exceeds 25 degrees in either direction", () => {
    expect(isLookingAway({ pitch: 0, yaw: 26, roll: 0 })).toBe(true);
    expect(isLookingAway({ pitch: 0, yaw: -26, roll: 0 })).toBe(true);
  });

  it("is true when pitch drops below -20 degrees", () => {
    expect(isLookingAway({ pitch: -21, yaw: 0, roll: 0 })).toBe(true);
  });

  it("is false within both thresholds", () => {
    expect(isLookingAway({ pitch: -10, yaw: 15, roll: 5 })).toBe(false);
  });
});

describe("trackSustain", () => {
  const SUSTAIN_MS = 2500;
  const COOLDOWN_MS = 10000;

  it("does not fire before the sustain duration elapses", () => {
    let state = initialSustainState();
    ({ state } = trackSustain(state, true, 0, SUSTAIN_MS, COOLDOWN_MS));
    const result = trackSustain(state, true, 2000, SUSTAIN_MS, COOLDOWN_MS);
    expect(result.fired).toBe(false);
  });

  it("fires once the sustain duration elapses", () => {
    let state = initialSustainState();
    ({ state } = trackSustain(state, true, 0, SUSTAIN_MS, COOLDOWN_MS));
    const result = trackSustain(state, true, 2600, SUSTAIN_MS, COOLDOWN_MS);
    expect(result.fired).toBe(true);
  });

  it("resets tracking when the condition stops being met", () => {
    let state = initialSustainState();
    ({ state } = trackSustain(state, true, 0, SUSTAIN_MS, COOLDOWN_MS));
    ({ state } = trackSustain(state, false, 1000, SUSTAIN_MS, COOLDOWN_MS));
    const result = trackSustain(state, true, 1200, SUSTAIN_MS, COOLDOWN_MS);
    // only 0ms of sustained time since the reset at 1200, not 1200ms total
    expect(result.fired).toBe(false);
  });

  it("suppresses an immediate re-fire during the cooldown window", () => {
    let state = initialSustainState();
    ({ state } = trackSustain(state, true, 0, SUSTAIN_MS, COOLDOWN_MS));
    let fired: boolean;
    ({ state, fired } = trackSustain(state, true, 2600, SUSTAIN_MS, COOLDOWN_MS));
    expect(fired).toBe(true); // first firing, cooldown now active until 12600

    ({ state } = trackSustain(state, true, 5000, SUSTAIN_MS, COOLDOWN_MS));
    const result = trackSustain(state, true, 8000, SUSTAIN_MS, COOLDOWN_MS);
    expect(result.fired).toBe(false); // still within the 10s cooldown
  });

  it("requires a fresh full sustain period once the cooldown expires", () => {
    let state = initialSustainState();
    ({ state } = trackSustain(state, true, 0, SUSTAIN_MS, COOLDOWN_MS));
    let fired: boolean;
    ({ state, fired } = trackSustain(state, true, 2600, SUSTAIN_MS, COOLDOWN_MS));
    expect(fired).toBe(true); // cooldown active until 12600

    ({ state } = trackSustain(state, true, 13000, SUSTAIN_MS, COOLDOWN_MS)); // cooldown just expired
    const tooSoon = trackSustain(state, true, 14000, SUSTAIN_MS, COOLDOWN_MS); // only 1000ms sustained
    expect(tooSoon.fired).toBe(false);

    const longEnough = trackSustain(tooSoon.state, true, 15600, SUSTAIN_MS, COOLDOWN_MS); // 2600ms sustained
    expect(longEnough.fired).toBe(true);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/lib/__tests__/proctorRules.test.ts`
Expected: FAIL — `Cannot find module '@/lib/proctorRules'`

- [ ] **Step 3: Write `frontend/src/lib/proctorRules.ts`**

```typescript
export interface EulerAngles {
  pitch: number;
  yaw: number;
  roll: number;
}

const RAD_TO_DEG = 180 / Math.PI;

export function matrixToEuler(d: ArrayLike<number>): EulerAngles {
  const pitch = Math.atan2(d[6], d[10]) * RAD_TO_DEG;
  const yaw = Math.atan2(-d[2], Math.hypot(d[6], d[10])) * RAD_TO_DEG;
  const roll = Math.atan2(d[1], d[0]) * RAD_TO_DEG;
  return { pitch, yaw, roll };
}

export function isLookingAway(angles: EulerAngles): boolean {
  return Math.abs(angles.yaw) > 25 || angles.pitch < -20;
}

export interface SustainState {
  conditionStartedAt: number | null;
  cooldownUntil: number | null;
}

export function initialSustainState(): SustainState {
  return { conditionStartedAt: null, cooldownUntil: null };
}

export interface SustainResult {
  state: SustainState;
  fired: boolean;
}

/**
 * Pure sustain/cooldown tracker. The caller feeds real timestamps (ms) on
 * every tick; this never reads a clock itself. During the cooldown window,
 * tracking is fully frozen — once it expires, the condition must be met
 * continuously for the full sustainMs again before firing, rather than
 * silently carrying over elapsed time from before the cooldown started.
 */
export function trackSustain(
  state: SustainState,
  conditionMet: boolean,
  now: number,
  sustainMs: number,
  cooldownMs: number,
): SustainResult {
  if (state.cooldownUntil !== null) {
    if (now < state.cooldownUntil) {
      return { state, fired: false };
    }
    state = { conditionStartedAt: null, cooldownUntil: null };
  }

  if (!conditionMet) {
    return { state: { conditionStartedAt: null, cooldownUntil: null }, fired: false };
  }

  if (state.conditionStartedAt === null) {
    return { state: { conditionStartedAt: now, cooldownUntil: null }, fired: false };
  }

  const elapsed = now - state.conditionStartedAt;
  if (elapsed >= sustainMs) {
    return { state: { conditionStartedAt: null, cooldownUntil: now + cooldownMs }, fired: true };
  }

  return { state, fired: false };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/lib/__tests__/proctorRules.test.ts`
Expected: PASS — `11 passed` (3 matrixToEuler + 3 isLookingAway + 5 trackSustain)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/proctorRules.ts frontend/src/lib/__tests__/proctorRules.test.ts
git commit -m "feat(frontend): add pure proctoring math — angle extraction, sustain/cooldown tracking"
```

---

## Task 4: Warning escalation — `hooks/useWarnings.ts`

**Files:**
- Modify: `frontend/src/services/api/interview.ts` (`+recordEvent`)
- Modify: `frontend/src/hooks/useInterview.ts` (`+useRecordEvent`)
- Create: `frontend/src/hooks/useWarnings.ts`
- Test: `frontend/src/hooks/__tests__/useWarnings.test.ts`

Per-signal sustain/cooldown tracking (Task 3) lives inside each proctoring
hook, one independent `SustainState` per signal type. `useWarnings` is what
those hooks call *once a signal has actually fired* — it owns the
escalation state and is where the server's response becomes the source of
truth. The exported `warningsReducer` is pure and directly testable, same
split as `interviewMachine.ts`'s `transition` — no hook-rendering machinery
needed for the interesting logic.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/hooks/__tests__/useWarnings.test.ts`:

```typescript
import { describe, expect, it } from "vitest";

import { initialWarningsState, warningsReducer } from "@/hooks/useWarnings";

describe("warningsReducer", () => {
  it("sets count to 1 and does not terminate on the first warning", () => {
    const state = warningsReducer(initialWarningsState(), {
      type: "SERVER_RESULT",
      eventType: "looking_away",
      warningCount: 1,
      shouldTerminate: false,
    });
    expect(state.warningCount).toBe(1);
    expect(state.terminated).toBe(false);
  });

  it("escalates 1 -> 2 -> 3 and terminates on the third", () => {
    let state = initialWarningsState();
    state = warningsReducer(state, {
      type: "SERVER_RESULT",
      eventType: "looking_away",
      warningCount: 1,
      shouldTerminate: false,
    });
    state = warningsReducer(state, {
      type: "SERVER_RESULT",
      eventType: "no_face",
      warningCount: 2,
      shouldTerminate: false,
    });
    state = warningsReducer(state, {
      type: "SERVER_RESULT",
      eventType: "looking_away",
      warningCount: 3,
      shouldTerminate: true,
    });
    expect(state.warningCount).toBe(3);
    expect(state.terminated).toBe(true);
    expect(state.terminationReason).toBe("proctoring");
  });

  it("terminates immediately on a fatal event regardless of warning count", () => {
    const state = warningsReducer(initialWarningsState(), {
      type: "SERVER_RESULT",
      eventType: "multiple_faces",
      warningCount: 0,
      shouldTerminate: true,
    });
    expect(state.terminated).toBe(true);
    expect(state.warningCount).toBe(0);
  });

  it("reconciles to whatever the server says, not a locally-incremented count", () => {
    // A dropped/retried request could make the server's own count jump by
    // more than 1 between reconciliations — the reducer must trust the
    // value it's given, never derive its own by incrementing.
    const state = warningsReducer(initialWarningsState(), {
      type: "SERVER_RESULT",
      eventType: "no_face",
      warningCount: 2,
      shouldTerminate: false,
    });
    expect(state.warningCount).toBe(2);
  });

  it("ignores further events once terminated", () => {
    let state = warningsReducer(initialWarningsState(), {
      type: "SERVER_RESULT",
      eventType: "multiple_faces",
      warningCount: 0,
      shouldTerminate: true,
    });
    const terminatedState = state;
    state = warningsReducer(state, {
      type: "SERVER_RESULT",
      eventType: "looking_away",
      warningCount: 1,
      shouldTerminate: false,
    });
    expect(state).toEqual(terminatedState);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useWarnings.test.ts`
Expected: FAIL — `Cannot find module '@/hooks/useWarnings'`

- [ ] **Step 3: Add `recordEvent` to `frontend/src/services/api/interview.ts`**

Append:

```typescript
export const recordEvent = (interviewId: number, type: string, detail: string) =>
  api<{ warning_count: number; should_terminate: boolean }>(
    `/api/interviews/${interviewId}/events`,
    { method: "POST", body: JSON.stringify({ type, detail }) },
  );
```

- [ ] **Step 4: Add `useRecordEvent` to `frontend/src/hooks/useInterview.ts`**

Add `recordEvent` to the existing import from `@/services/api/interview`
(currently `getInterview, quitInterview, saveInterviewAnswer,
startInterview, submitInterview` — add `recordEvent` to that list), then
append:

```typescript
export function useRecordEvent(interviewId: number) {
  return useMutation({
    mutationFn: ({ type, detail }: { type: string; detail: string }) =>
      recordEvent(interviewId, type, detail),
  });
}
```

- [ ] **Step 5: Write `frontend/src/hooks/useWarnings.ts`**

```typescript
import { useCallback, useReducer } from "react";

import { useRecordEvent } from "@/hooks/useInterview";

export interface WarningsState {
  warningCount: number;
  terminated: boolean;
  terminationReason: "proctoring" | null;
  recentEventType: string | null;
}

export function initialWarningsState(): WarningsState {
  return { warningCount: 0, terminated: false, terminationReason: null, recentEventType: null };
}

export type WarningsAction = {
  type: "SERVER_RESULT";
  eventType: string;
  warningCount: number;
  shouldTerminate: boolean;
};

export function warningsReducer(state: WarningsState, action: WarningsAction): WarningsState {
  if (state.terminated) return state;

  return {
    warningCount: action.warningCount,
    terminated: action.shouldTerminate,
    terminationReason: action.shouldTerminate ? "proctoring" : null,
    recentEventType: action.eventType,
  };
}

export function useWarnings(interviewId: number) {
  const [state, dispatch] = useReducer(warningsReducer, initialWarningsState());
  const recordEvent = useRecordEvent(interviewId);

  const reportEvent = useCallback(
    (eventType: string, detail: string) => {
      recordEvent.mutate(
        { type: eventType, detail },
        {
          onSuccess: (result) => {
            dispatch({
              type: "SERVER_RESULT",
              eventType,
              warningCount: result.warning_count,
              shouldTerminate: result.should_terminate,
            });
          },
        },
      );
    },
    [recordEvent],
  );

  return { ...state, reportEvent };
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useWarnings.test.ts`
Expected: PASS — `5 passed`

- [ ] **Step 7: Typecheck**

Run: `cd frontend && npx tsc -b --noEmit`
Expected: clean

- [ ] **Step 8: Commit**

```bash
git add frontend/src/services/api/interview.ts frontend/src/hooks/useInterview.ts frontend/src/hooks/useWarnings.ts frontend/src/hooks/__tests__/useWarnings.test.ts
git commit -m "feat(frontend): add warning escalation reducer and hook"
```

---

## Task 5: FSM changes — preflight, unified termination

**Files:**
- Modify: `frontend/src/lib/interviewMachine.ts`
- Modify: `frontend/src/lib/__tests__/interviewMachine.test.ts`
- Modify: `frontend/src/hooks/useInterviewMachine.ts`
- Modify: `frontend/src/components/interview/QuestionStage.tsx`
- Modify: `frontend/src/types/index.ts`

Two real changes to the machine Plan 4 built, not just additions: a new
`preflight` phase before `briefing` (the initial state moves from
`briefing` to `preflight`), and `terminated` becomes a real, rendered
`MachinePhase` — replacing Plan 4's "quit is an action that navigates
away," since proctoring termination needs an actual screen and having two
different mechanisms reach the same end state would be a real
inconsistency. `MachineState` gains `terminationReason`. This touches
**every** existing test in `interviewMachine.test.ts` (the state shape
changed), so the whole file is replaced, not appended to.

`QuestionStage` gets minimal placeholder rendering for `preflight` and
`terminated` here — just enough that the app doesn't break. Task 8 replaces
both with the real `PreflightCheck` and `WarningOverlay` components.

- [ ] **Step 1: Write the failing tests**

Replace `frontend/src/lib/__tests__/interviewMachine.test.ts` entirely:

```typescript
import { describe, expect, it } from "vitest";

import { initialMachineState, transition } from "@/lib/interviewMachine";

describe("transition", () => {
  it("starts in preflight", () => {
    expect(initialMachineState()).toEqual({
      phase: "preflight",
      questionIndex: 0,
      terminationReason: null,
    });
  });

  it("PREFLIGHT_READY moves from preflight to briefing", () => {
    const state = transition(initialMachineState(), { type: "PREFLIGHT_READY" });
    expect(state.phase).toBe("briefing");
  });

  it("PREFLIGHT_READY is ignored outside preflight", () => {
    const briefing = { phase: "briefing" as const, questionIndex: 0, terminationReason: null };
    expect(transition(briefing, { type: "PREFLIGHT_READY" })).toEqual(briefing);
  });

  it("BEGIN from briefing moves to speaking at question 0", () => {
    const briefing = { phase: "briefing" as const, questionIndex: 0, terminationReason: null };
    const state = transition(briefing, { type: "BEGIN" });
    expect(state).toEqual({ phase: "speaking", questionIndex: 0, terminationReason: null });
  });

  it("BEGIN is ignored outside briefing", () => {
    const speaking = { phase: "speaking" as const, questionIndex: 0, terminationReason: null };
    expect(transition(speaking, { type: "BEGIN" })).toEqual(speaking);
  });

  it("TTS_DONE from speaking moves to answering, same question", () => {
    const speaking = { phase: "speaking" as const, questionIndex: 2, terminationReason: null };
    const state = transition(speaking, { type: "TTS_DONE" });
    expect(state).toEqual({ phase: "answering", questionIndex: 2, terminationReason: null });
  });

  it("TTS_DONE is ignored outside speaking", () => {
    const briefing = { phase: "briefing" as const, questionIndex: 0, terminationReason: null };
    expect(transition(briefing, { type: "TTS_DONE" })).toEqual(briefing);
  });

  it("ANSWER_ADVANCE when not the last question moves to speaking, next question", () => {
    const answering = { phase: "answering" as const, questionIndex: 0, terminationReason: null };
    const state = transition(answering, { type: "ANSWER_ADVANCE", isLastQuestion: false });
    expect(state).toEqual({ phase: "speaking", questionIndex: 1, terminationReason: null });
  });

  it("ANSWER_ADVANCE on the last question moves to review", () => {
    const answering = { phase: "answering" as const, questionIndex: 4, terminationReason: null };
    const state = transition(answering, { type: "ANSWER_ADVANCE", isLastQuestion: true });
    expect(state).toEqual({ phase: "review", questionIndex: 4, terminationReason: null });
  });

  it("ANSWER_ADVANCE is ignored outside answering", () => {
    const speaking = { phase: "speaking" as const, questionIndex: 0, terminationReason: null };
    expect(
      transition(speaking, { type: "ANSWER_ADVANCE", isLastQuestion: false }),
    ).toEqual(speaking);
  });

  it("review is an absorbing state for question-flow events", () => {
    const review = { phase: "review" as const, questionIndex: 4, terminationReason: null };
    expect(transition(review, { type: "BEGIN" })).toEqual(review);
    expect(transition(review, { type: "TTS_DONE" })).toEqual(review);
    expect(
      transition(review, { type: "ANSWER_ADVANCE", isLastQuestion: true }),
    ).toEqual(review);
  });

  it("TERMINATE moves to terminated with the given reason, from any active phase", () => {
    const phases = ["preflight", "briefing", "speaking", "answering"] as const;
    for (const phase of phases) {
      const state = { phase, questionIndex: 1, terminationReason: null };
      const result = transition(state, { type: "TERMINATE", reason: "user_quit" });
      expect(result.phase).toBe("terminated");
      expect(result.terminationReason).toBe("user_quit");
    }
  });

  it("TERMINATE with a proctoring reason is distinguishable from a manual quit", () => {
    const answering = { phase: "answering" as const, questionIndex: 0, terminationReason: null };
    const result = transition(answering, { type: "TERMINATE", reason: "proctoring" });
    expect(result.terminationReason).toBe("proctoring");
  });

  it("TERMINATE does not fire from review — the interview is already wrapping up", () => {
    const review = { phase: "review" as const, questionIndex: 4, terminationReason: null };
    expect(transition(review, { type: "TERMINATE", reason: "user_quit" })).toEqual(review);
  });

  it("terminated is absorbing", () => {
    const terminated = {
      phase: "terminated" as const,
      questionIndex: 0,
      terminationReason: "user_quit" as const,
    };
    expect(transition(terminated, { type: "BEGIN" })).toEqual(terminated);
    expect(
      transition(terminated, { type: "TERMINATE", reason: "proctoring" }),
    ).toEqual(terminated);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/lib/__tests__/interviewMachine.test.ts`
Expected: FAIL — old `transition`/`initialMachineState` don't know about
`preflight`/`terminated`/`TERMINATE`, most assertions fail on shape mismatch

- [ ] **Step 3: Update `MachinePhase` in `frontend/src/types/index.ts`**

Find `export type MachinePhase = "briefing" | "speaking" | "answering" |
"review";` and replace with:

```typescript
export type MachinePhase =
  | "preflight"
  | "briefing"
  | "speaking"
  | "answering"
  | "review"
  | "terminated";

export type TerminationReason = "user_quit" | "proctoring";
```

- [ ] **Step 4: Replace `frontend/src/lib/interviewMachine.ts` entirely**

```typescript
import type { MachinePhase, TerminationReason } from "@/types";

export interface MachineState {
  phase: MachinePhase;
  questionIndex: number;
  terminationReason: TerminationReason | null;
}

export type MachineEvent =
  | { type: "PREFLIGHT_READY" }
  | { type: "BEGIN" }
  | { type: "TTS_DONE" }
  | { type: "ANSWER_ADVANCE"; isLastQuestion: boolean }
  | { type: "TERMINATE"; reason: TerminationReason };

export function initialMachineState(): MachineState {
  return { phase: "preflight", questionIndex: 0, terminationReason: null };
}

export function transition(state: MachineState, event: MachineEvent): MachineState {
  if (event.type === "TERMINATE" && state.phase !== "terminated" && state.phase !== "review") {
    return { ...state, phase: "terminated", terminationReason: event.reason };
  }
  if (state.phase === "preflight" && event.type === "PREFLIGHT_READY") {
    return { ...state, phase: "briefing" };
  }
  if (state.phase === "briefing" && event.type === "BEGIN") {
    return { ...state, phase: "speaking", questionIndex: 0 };
  }
  if (state.phase === "speaking" && event.type === "TTS_DONE") {
    return { ...state, phase: "answering" };
  }
  if (state.phase === "answering" && event.type === "ANSWER_ADVANCE") {
    if (event.isLastQuestion) {
      return { ...state, phase: "review" };
    }
    return { ...state, phase: "speaking", questionIndex: state.questionIndex + 1 };
  }
  return state;
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/lib/__tests__/interviewMachine.test.ts`
Expected: PASS — `15 passed`

- [ ] **Step 6: Update `frontend/src/hooks/useInterviewMachine.ts`**

Replace the whole file:

```typescript
import { useCallback, useEffect, useReducer, useRef } from "react";

import { useQuitInterview, useSaveInterviewAnswer, useSubmitInterview } from "@/hooks/useInterview";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";
import { useSpeechSynthesis } from "@/hooks/useSpeechSynthesis";
import { useWarnings } from "@/hooks/useWarnings";
import { initialMachineState, transition } from "@/lib/interviewMachine";
import type { Interview } from "@/types";

export function useInterviewMachine(interview: Interview) {
  const [state, dispatch] = useReducer(transition, initialMachineState());
  const tts = useSpeechSynthesis();
  const stt = useSpeechRecognition();
  const saveAnswer = useSaveInterviewAnswer(interview.id);
  const submit = useSubmitInterview(interview.id);
  const quit = useQuitInterview(interview.id);
  const warnings = useWarnings(interview.id);
  const answerStartRef = useRef<number | null>(null);

  const currentQuestion = interview.questions[state.questionIndex] ?? null;
  const isLastQuestion = state.questionIndex === interview.questions.length - 1;

  const preflightReady = useCallback(() => dispatch({ type: "PREFLIGHT_READY" }), []);
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

  useEffect(() => {
    if (warnings.terminated) dispatch({ type: "TERMINATE", reason: "proctoring" });
  }, [warnings.terminated]);

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
    dispatch({ type: "TERMINATE", reason: "user_quit" });
    quit.mutate();
  }, [tts, stt, quit]);

  return {
    phase: state.phase,
    terminationReason: state.terminationReason,
    currentQuestion,
    questionNumber: state.questionIndex + 1,
    totalQuestions: interview.questions.length,
    preflightReady,
    begin,
    advance,
    quitNow,
    ttsSupported: tts.supported,
    sttSupported: stt.supported,
    liveTranscript: stt.transcript,
    listening: stt.listening,
    reportProctoringEvent: warnings.reportEvent,
    warningCount: warnings.warningCount,
  };
}
```

`quitNow` now dispatches `TERMINATE` locally *before* the API call resolves
— termination should feel immediate (the screen changes right away), not
wait on a round trip. The API call still fires, in the background, to
persist it. This is a deliberate change from Plan 4, where `quitNow` waited
for `onSuccess` before navigating — that made sense when quitting meant
*leaving the page*; it doesn't once quitting means *showing a screen on
this same page*.

- [ ] **Step 7: Add minimal `preflight`/`terminated` rendering to `frontend/src/components/interview/QuestionStage.tsx`**

Add two new props to `QuestionStageProps`: `onPreflightReady: () => void;`
and `terminationReason: TerminationReason | null;` (import
`TerminationReason` from `@/types` alongside the existing `Interview,
MachinePhase` import). Add two new branches right after the existing
`if (phase === "briefing")` block:

```tsx
  if (phase === "preflight") {
    return (
      <Card className="space-y-4">
        <CardTitle>Getting ready…</CardTitle>
        <CardDescription>Checking camera and microphone access.</CardDescription>
        <Button onClick={onPreflightReady}>Continue</Button>
      </Card>
    );
  }

  if (phase === "terminated") {
    return (
      <Card className="space-y-4">
        <CardTitle>
          {terminationReason === "proctoring" ? "Interview terminated" : "Interview ended"}
        </CardTitle>
        <CardDescription>
          {terminationReason === "proctoring"
            ? "This interview was ended due to repeated proctoring warnings."
            : "You ended this interview early."}
        </CardDescription>
      </Card>
    );
  }
```

This is a stand-in — Task 8 replaces the `preflight` branch with a real
`PreflightCheck` component (camera/mic checks, not just a button) and adds
a proper warning-escalation overlay for the run-up to `terminated`.

- [ ] **Step 8: Wire the new props in `frontend/src/pages/InterviewActivePage.tsx`**

Add `onPreflightReady={machine.preflightReady}` and
`terminationReason={machine.terminationReason}` to the existing
`<QuestionStage>` call in `ActiveInterview`.

- [ ] **Step 9: Typecheck, build, test**

Run: `cd frontend && npx tsc -b --noEmit && npm run build && npm test`
Expected: all clean, `46 passed` — 23 before this plan, +11 from Task 3
(`proctorRules.test.ts`), +5 from Task 4 (`useWarnings.test.ts`), and this
task's `interviewMachine.test.ts` *replacing* Plan 4's 8 tests with 15 new
ones (net +7): 23+11+5+7 = 46.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/lib/interviewMachine.ts frontend/src/lib/__tests__/interviewMachine.test.ts frontend/src/hooks/useInterviewMachine.ts frontend/src/components/interview/QuestionStage.tsx frontend/src/pages/InterviewActivePage.tsx
git commit -m "feat(frontend): add preflight state, unify termination into the FSM"
```

---

## Task 6: Video proctoring — `hooks/useProctoring.ts`

**Files:**
- Modify: `frontend/package.json` (`+@mediapipe/tasks-vision`)
- Modify: `frontend/src/types/index.ts` (`+ProctoringEventType`)
- Create: `frontend/public/wasm/*` (vendored, copied from the installed package)
- Create: `frontend/public/models/face_landmarker.task` (vendored, downloaded)
- Create: `frontend/src/hooks/useProctoring.ts`

**Verified before this task, against the real published package** (not
assumed from prose docs, which is what the previous verification pass
actually flagged as unconfirmed): `@mediapipe/tasks-vision`'s real `.d.ts`
(fetched from unpkg for the latest published version, `1.0.1`) pins
`FaceLandmarkerResult.facialTransformationMatrixes` to `Matrix[]`, where
`Matrix = { rows: number; columns: number; data: number[] }` — `data` is
the flattened, row-major array `matrixToEuler` (Task 3) already indexes as
`d[0]..d[15]`. Field names are camelCase throughout the real type
definitions (`faceLandmarks`, `facialTransformationMatrixes`,
`outputFacialTransformationMatrixes`) — the snake_case seen in an earlier
prose-docs fetch was that page's own paraphrase, not the actual API, and is
disregarded. `FilesetResolver.forVisionTasks(basePath): Promise<WasmFileset>`,
`FaceLandmarker.createFromOptions(fileset, options): Promise<FaceLandmarker>`,
and `detectForVideo(videoFrame: ImageSource, timestamp: number):
FaceLandmarkerResult` are all confirmed exact signatures from the same
fetch. `BaseOptions.delegate?: "CPU" | "GPU"` is confirmed exact.

This hook has no dedicated unit test, matching the established pattern for
`useSpeechRecognition.ts`/`useSpeechSynthesis.ts` (Plan 4) — it's a thin
browser-API wrapper with no test file of its own; the logic worth testing
in isolation already lives in `lib/proctorRules.ts` (Task 3, 11 tests) and
stays that way here. What confirms this hook is wired correctly is
type-checking against the real installed package types, a clean build, and
Task 11's live E2E pass — the same honest split Plan 4 used for speech.

- [ ] **Step 1: Add the dependency**

Add to `frontend/package.json`'s `"dependencies"` block (alphabetically
first, before `"@tanstack/react-query"`):

```json
    "@mediapipe/tasks-vision": "^1.0.1",
```

Run:

```bash
cd frontend && npm install
```

Expected: `node_modules/@mediapipe/tasks-vision` populated,
`package-lock.json` updated.

- [ ] **Step 2: Add `ProctoringEventType` to `frontend/src/types/index.ts`**

Find `export type TerminationReason = "user_quit" | "proctoring";` (added
in Task 5) and add directly after it:

```typescript
export type ProctoringEventType =
  | "looking_away"
  | "no_face"
  | "multiple_faces"
  | "excessive_noise"
  | "background_voice";
```

Matches the backend's `ProctoringEventType` literal exactly
(`backend/services/interview_service.py`, Task 2).

- [ ] **Step 3: Vendor the WASM fileset**

The npm package ships six files (a SIMD build, a no-SIMD fallback, and a
threaded-module build, each as a `.js` loader + `.wasm` binary) under its
own `wasm/` directory. Which pair `FilesetResolver` picks at runtime
depends on browser feature detection, so all six are vendored rather than
guessing which are dead weight — this is a one-time local copy of files
`npm install` already fetched, not a network request:

```bash
cd frontend && mkdir -p public/wasm && cp node_modules/@mediapipe/tasks-vision/wasm/* public/wasm/
```

Expected: `ls public/wasm` shows 6 files (`vision_wasm_internal.js`,
`vision_wasm_internal.wasm`, `vision_wasm_module_internal.js`,
`vision_wasm_module_internal.wasm`, `vision_wasm_nosimd_internal.js`,
`vision_wasm_nosimd_internal.wasm`), roughly 35MB total — this is the
"no runtime CDN dependency" requirement from the master spec (line 437-438)
made concrete.

- [ ] **Step 4: Vendor the face landmark model**

**This step downloads a file from an external source — pause here and ask
the user for permission before running it.** File: `face_landmarker.task`,
3,758,596 bytes (~3.6MB), from
`https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task`
— Google's official MediaPipe model hosting, the same URL MediaPipe's own
web samples point at (confirmed live: `HEAD` on this URL returns
`content-length: 3758596`, `content-type: application/octet-stream`).

Once approved:

```bash
cd frontend && mkdir -p public/models && curl -o public/models/face_landmarker.task "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
```

Expected: `ls -la public/models/face_landmarker.task` shows 3758596 bytes.

- [ ] **Step 5: Write `frontend/src/hooks/useProctoring.ts`**

```typescript
import { useCallback, useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { FaceLandmarker, FilesetResolver } from "@mediapipe/tasks-vision";

import {
  initialSustainState,
  isLookingAway,
  matrixToEuler,
  trackSustain,
  type SustainState,
} from "@/lib/proctorRules";
import type { ProctoringEventType } from "@/types";

const MODEL_ASSET_PATH = "/models/face_landmarker.task";
const WASM_BASE_PATH = "/wasm";
const DETECT_INTERVAL_MS = 100; // 10fps, per the design's throttle
const LOOKING_AWAY_SUSTAIN_MS = 2500;
const LOOKING_AWAY_COOLDOWN_MS = 10000;
const NO_FACE_SUSTAIN_MS = 4000;
const NO_FACE_COOLDOWN_MS = 10000;
const MULTIPLE_FACES_SUSTAIN_MS = 1500;

export type CameraStatus = "pending" | "ready" | "unavailable";

export interface UseProctoringResult {
  videoRef: RefObject<HTMLVideoElement | null>;
  cameraStatus: CameraStatus;
  faceCount: number;
}

/**
 * `cameraActive` drives the camera+model lifecycle (on from `preflight`
 * through `answering`, off for `review`/`terminated`). `warningsArmed` is
 * separate and stays false during `preflight` itself — the calibration
 * step deliberately never reports a warning for the setup time it takes to
 * sit down and be detected.
 */
export function useProctoring(
  cameraActive: boolean,
  warningsArmed: boolean,
  onWarning: (eventType: ProctoringEventType, detail: string) => void,
): UseProctoringResult {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [cameraStatus, setCameraStatus] = useState<CameraStatus>("pending");
  const [faceCount, setFaceCount] = useState(0);

  const landmarkerRef = useRef<FaceLandmarker | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef<number | null>(null);
  const lastDetectAtRef = useRef(0);
  const warningsArmedRef = useRef(warningsArmed);
  const onWarningRef = useRef(onWarning);
  const lookingAwaySustainRef = useRef<SustainState>(initialSustainState());
  const noFaceSustainRef = useRef<SustainState>(initialSustainState());
  const multipleFacesSustainRef = useRef<SustainState>(initialSustainState());

  warningsArmedRef.current = warningsArmed;
  onWarningRef.current = onWarning;

  const detectTick = useCallback(() => {
    const video = videoRef.current;
    const landmarker = landmarkerRef.current;
    if (!video || !landmarker || video.readyState < 2) {
      rafRef.current = requestAnimationFrame(detectTick);
      return;
    }

    const now = performance.now();
    if (now - lastDetectAtRef.current >= DETECT_INTERVAL_MS) {
      lastDetectAtRef.current = now;
      const result = landmarker.detectForVideo(video, now);
      const count = result.faceLandmarks.length;
      setFaceCount(count);

      if (warningsArmedRef.current) {
        // Only evaluated with exactly one face — with zero it's meaningless,
        // and with two or more, `multiple_faces` already takes over as the
        // fatal signal, so whose angle would even apply is ambiguous.
        const matrix = result.facialTransformationMatrixes[0];
        const lookingAway =
          count === 1 && matrix ? isLookingAway(matrixToEuler(matrix.data)) : false;

        const lookingAwayResult = trackSustain(
          lookingAwaySustainRef.current,
          lookingAway,
          now,
          LOOKING_AWAY_SUSTAIN_MS,
          LOOKING_AWAY_COOLDOWN_MS,
        );
        lookingAwaySustainRef.current = lookingAwayResult.state;
        if (lookingAwayResult.fired) {
          onWarningRef.current("looking_away", "sustained face angle beyond threshold");
        }

        const noFaceResult = trackSustain(
          noFaceSustainRef.current,
          count === 0,
          now,
          NO_FACE_SUSTAIN_MS,
          NO_FACE_COOLDOWN_MS,
        );
        noFaceSustainRef.current = noFaceResult.state;
        if (noFaceResult.fired) {
          onWarningRef.current("no_face", "no face detected in frame");
        }

        // Fatal — no cooldown needed. The backend terminates the interview
        // on this event's first occurrence, which tears this whole effect
        // down via `cameraActive` turning false, so there's never a second
        // tick left to suppress.
        const multipleFacesResult = trackSustain(
          multipleFacesSustainRef.current,
          count >= 2,
          now,
          MULTIPLE_FACES_SUSTAIN_MS,
          0,
        );
        multipleFacesSustainRef.current = multipleFacesResult.state;
        if (multipleFacesResult.fired) {
          onWarningRef.current("multiple_faces", `${count} faces detected in frame`);
        }
      }
    }

    rafRef.current = requestAnimationFrame(detectTick);
  }, []);

  useEffect(() => {
    if (!cameraActive) return;

    let cancelled = false;

    async function setup() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          try {
            await videoRef.current.play();
          } catch {
            // Autoplay can be blocked pending a user gesture; srcObject is
            // already set and playback resumes once the preflight screen
            // registers a click, so this alone isn't a hard failure.
          }
        }

        const fileset = await FilesetResolver.forVisionTasks(WASM_BASE_PATH);
        if (cancelled) return;

        const baseOptions = { modelAssetPath: MODEL_ASSET_PATH, delegate: "GPU" as const };
        const options = {
          baseOptions,
          runningMode: "VIDEO" as const,
          numFaces: 2,
          outputFacialTransformationMatrixes: true,
        };
        let landmarker: FaceLandmarker;
        try {
          landmarker = await FaceLandmarker.createFromOptions(fileset, options);
        } catch {
          landmarker = await FaceLandmarker.createFromOptions(fileset, {
            ...options,
            baseOptions: { ...baseOptions, delegate: "CPU" as const },
          });
        }
        if (cancelled) {
          landmarker.close();
          return;
        }

        landmarkerRef.current = landmarker;
        setCameraStatus("ready");
        rafRef.current = requestAnimationFrame(detectTick);
      } catch {
        // getUserMedia rejection (NotAllowedError, no device — live-verified
        // in this plan's header as a clean rejection here, not a hang) or
        // FaceLandmarker init failure both land here the same way.
        if (!cancelled) setCameraStatus("unavailable");
      }
    }

    void setup();

    return () => {
      cancelled = true;
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
      landmarkerRef.current?.close();
      landmarkerRef.current = null;
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      lookingAwaySustainRef.current = initialSustainState();
      noFaceSustainRef.current = initialSustainState();
      multipleFacesSustainRef.current = initialSustainState();
      setCameraStatus("pending");
      setFaceCount(0);
    };
  }, [cameraActive, detectTick]);

  return { videoRef, cameraStatus, faceCount };
}
```

- [ ] **Step 6: Typecheck and build**

Run: `cd frontend && npx tsc -b --noEmit && npm run build`
Expected: both clean. This is the real check for this task — it
type-checks the hook's MediaPipe calls against the actual installed
`@mediapipe/tasks-vision` types, not against assumptions.

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/types/index.ts frontend/src/hooks/useProctoring.ts frontend/public/wasm frontend/public/models
git commit -m "feat(frontend): add MediaPipe video proctoring hook"
```

---

## Task 7: Audio proctoring — `hooks/useAudioMonitor.ts`

**Files:**
- Create: `frontend/src/hooks/useAudioMonitor.ts`

No new dependency — Web Audio (`AudioContext`, `AnalyserNode`) is a
standard, fully-typed part of TypeScript's default DOM lib, unlike the
speech APIs (Plan 4 needed `types/speech.d.ts` for those; nothing
equivalent is needed here). No dedicated unit test, same reasoning as
`useProctoring.ts` in Task 6.

**Verified live before this task**, against the real browser tool: 
`getUserMedia({ audio: true })` rejects the same clean way as the
already-confirmed video case — `NotAllowedError: "Permission denied"` at
92ms in this sandboxed browser (no real microphone available), not a hang.
Separately confirmed `AudioContext`/`AnalyserNode` are available
unprefixed, with `createAnalyser()` defaulting to `fftSize: 2048` /
`frequencyBinCount: 1024`, and both `getFloatTimeDomainData` and
`getByteFrequencyData` present — the two calls this hook's RMS and
speech-band calculations depend on. `sampleRate` was `44100` in this
environment but the code below reads it from the live `AudioContext`
rather than assuming a fixed value, since it varies by device.

**Interpreting the design doc's two signals precisely** (both stated as
energy heuristics, not diarization, since real speaker separation isn't
achievable in-browser at this project's scope):
- `excessive_noise` ("RMS > floor + 18dB while not the active speaker"):
  the candidate is "the active speaker" only during `answering`, so this
  check is gated to phases where they're expected to be silently listening
  — `briefing`/`speaking` — via an `isAnswering` flag inverted at the call
  site.
- `background_voice` ("speech-band energy present while STT reports no
  user speech"): read literally as "STT's transcript isn't growing despite
  audible speech-band energy," tracked by comparing `transcript.length`
  across ticks rather than inventing an interim-speech signal that doesn't
  exist anywhere in this codebase. This is only meaningful while STT is
  actually the answer-capture mechanism, so it additionally requires
  `sttAvailable` (`stt.supported`) — without it, "STT reports no user
  speech" is vacuously true for the entire manual-typing fallback, which
  would misfire on the candidate's own voice. Gated to `answering`, the
  only phase where transcript growth is expected at all.

- [ ] **Step 1: Write `frontend/src/hooks/useAudioMonitor.ts`**

```typescript
import { useCallback, useEffect, useRef, useState } from "react";

import { initialSustainState, trackSustain, type SustainState } from "@/lib/proctorRules";
import type { ProctoringEventType } from "@/types";

const SAMPLE_INTERVAL_MS = 50; // 20Hz
const CALIBRATION_DURATION_MS = 3000;
const EXCESSIVE_NOISE_DELTA_DB = 18;
const EXCESSIVE_NOISE_SUSTAIN_MS = 3000;
const EXCESSIVE_NOISE_COOLDOWN_MS = 10000;
const BACKGROUND_VOICE_SUSTAIN_MS = 3000;
const BACKGROUND_VOICE_COOLDOWN_MS = 10000;
const SPEECH_BAND_LOW_HZ = 300;
const SPEECH_BAND_HIGH_HZ = 3400;
// Byte-magnitude (0-255, from getByteFrequencyData) bar for "speech-band
// energy present" — an energy heuristic, not real speaker diarization, per
// the master spec's own framing for this signal. getByteFrequencyData reads
// near 0 for silence, so this is a low-but-nonzero bar; it would benefit
// from tuning against a real microphone, which this environment can't
// provide (same honest gap as face-tracking accuracy in Task 6).
const VOICE_BAND_PRESENCE_THRESHOLD = 30;

export type MicStatus = "pending" | "calibrating" | "ready" | "unavailable";

export interface UseAudioMonitorResult {
  micStatus: MicStatus;
  noiseFloorDb: number | null;
}

function rmsToDb(rms: number): number {
  return 20 * Math.log10(Math.max(rms, 1e-8));
}

/**
 * `micActive` mirrors `useProctoring`'s `cameraActive` — on from `preflight`
 * through `answering`, off for `review`/`terminated`. `warningsArmed` stays
 * false during `preflight`'s own calibration window, same reasoning as the
 * video hook. `isAnswering` narrows `excessive_noise` to phases where the
 * candidate is expected to be silent, and gates `background_voice` the
 * other way, since that signal only means anything while STT is meant to be
 * capturing the candidate's own speech. `sttAvailable` is `stt.supported`.
 * `transcript` is `stt.transcript`, used to detect whether STT is actually
 * hearing anything during the current answer.
 */
export function useAudioMonitor(
  micActive: boolean,
  warningsArmed: boolean,
  isAnswering: boolean,
  sttAvailable: boolean,
  transcript: string,
  onWarning: (eventType: ProctoringEventType, detail: string) => void,
): UseAudioMonitorResult {
  const [micStatus, setMicStatus] = useState<MicStatus>("pending");
  const [noiseFloorDb, setNoiseFloorDb] = useState<number | null>(null);

  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef<number | null>(null);
  const lastSampleAtRef = useRef(0);
  const calibrationSamplesRef = useRef<number[]>([]);
  const calibrationStartedAtRef = useRef<number | null>(null);
  const noiseFloorRef = useRef<number | null>(null);

  const warningsArmedRef = useRef(warningsArmed);
  const isAnsweringRef = useRef(isAnswering);
  const sttAvailableRef = useRef(sttAvailable);
  const transcriptRef = useRef(transcript);
  const onWarningRef = useRef(onWarning);
  const lastTranscriptLengthRef = useRef(0);
  const lastTranscriptGrowthAtRef = useRef(0);

  const excessiveNoiseSustainRef = useRef<SustainState>(initialSustainState());
  const backgroundVoiceSustainRef = useRef<SustainState>(initialSustainState());

  warningsArmedRef.current = warningsArmed;
  isAnsweringRef.current = isAnswering;
  sttAvailableRef.current = sttAvailable;
  transcriptRef.current = transcript;
  onWarningRef.current = onWarning;

  // Resets the "has STT heard anything" baseline at the start of every
  // answering window, not just once at mount — `micActive` stays true
  // continuously across all questions, so the main setup effect below only
  // runs once and can't be where this per-question reset lives.
  useEffect(() => {
    if (isAnswering) {
      lastTranscriptGrowthAtRef.current = performance.now();
      lastTranscriptLengthRef.current = transcriptRef.current.length;
    }
  }, [isAnswering]);

  const sampleTick = useCallback(() => {
    const analyser = analyserRef.current;
    const audioContext = audioContextRef.current;
    if (!analyser || !audioContext) {
      rafRef.current = requestAnimationFrame(sampleTick);
      return;
    }

    const now = performance.now();
    if (now - lastSampleAtRef.current >= SAMPLE_INTERVAL_MS) {
      lastSampleAtRef.current = now;

      const timeDomain = new Float32Array(analyser.fftSize);
      analyser.getFloatTimeDomainData(timeDomain);
      let sumSquares = 0;
      for (let i = 0; i < timeDomain.length; i++) sumSquares += timeDomain[i] * timeDomain[i];
      const rms = Math.sqrt(sumSquares / timeDomain.length);
      const db = rmsToDb(rms);

      if (calibrationStartedAtRef.current === null) {
        calibrationStartedAtRef.current = now;
      }

      const noiseFloor = noiseFloorRef.current;
      if (noiseFloor === null) {
        calibrationSamplesRef.current.push(db);
        if (now - calibrationStartedAtRef.current >= CALIBRATION_DURATION_MS) {
          const samples = calibrationSamplesRef.current;
          const floor = samples.reduce((sum, v) => sum + v, 0) / samples.length;
          noiseFloorRef.current = floor;
          setNoiseFloorDb(floor);
          setMicStatus("ready");
        }
        rafRef.current = requestAnimationFrame(sampleTick);
        return;
      }

      if (warningsArmedRef.current) {
        const excessiveNoise =
          !isAnsweringRef.current && db > noiseFloor + EXCESSIVE_NOISE_DELTA_DB;
        const excessiveNoiseResult = trackSustain(
          excessiveNoiseSustainRef.current,
          excessiveNoise,
          now,
          EXCESSIVE_NOISE_SUSTAIN_MS,
          EXCESSIVE_NOISE_COOLDOWN_MS,
        );
        excessiveNoiseSustainRef.current = excessiveNoiseResult.state;
        if (excessiveNoiseResult.fired) {
          onWarningRef.current(
            "excessive_noise",
            `${db.toFixed(1)}dB, floor ${noiseFloor.toFixed(1)}dB`,
          );
        }

        if (sttAvailableRef.current) {
          const freqData = new Uint8Array(analyser.frequencyBinCount);
          analyser.getByteFrequencyData(freqData);
          const binHz = audioContext.sampleRate / analyser.fftSize;
          const startBin = Math.floor(SPEECH_BAND_LOW_HZ / binHz);
          const endBin = Math.min(freqData.length - 1, Math.ceil(SPEECH_BAND_HIGH_HZ / binHz));
          let voiceBandSum = 0;
          for (let i = startBin; i <= endBin; i++) voiceBandSum += freqData[i];
          const voiceBandAvg = voiceBandSum / (endBin - startBin + 1);
          const voiceBandPresent = voiceBandAvg > VOICE_BAND_PRESENCE_THRESHOLD;

          if (transcriptRef.current.length !== lastTranscriptLengthRef.current) {
            lastTranscriptLengthRef.current = transcriptRef.current.length;
            lastTranscriptGrowthAtRef.current = now;
          }
          const sttSilent = now - lastTranscriptGrowthAtRef.current > BACKGROUND_VOICE_SUSTAIN_MS;
          const backgroundVoice = isAnsweringRef.current && voiceBandPresent && sttSilent;

          const backgroundVoiceResult = trackSustain(
            backgroundVoiceSustainRef.current,
            backgroundVoice,
            now,
            BACKGROUND_VOICE_SUSTAIN_MS,
            BACKGROUND_VOICE_COOLDOWN_MS,
          );
          backgroundVoiceSustainRef.current = backgroundVoiceResult.state;
          if (backgroundVoiceResult.fired) {
            onWarningRef.current(
              "background_voice",
              "speech-band energy without matching STT output",
            );
          }
        }
      }
    }

    rafRef.current = requestAnimationFrame(sampleTick);
  }, []);

  useEffect(() => {
    if (!micActive) return;

    let cancelled = false;

    async function setup() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;

        const audioContext = new AudioContext();
        const source = audioContext.createMediaStreamSource(stream);
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 2048;
        source.connect(analyser);

        audioContextRef.current = audioContext;
        analyserRef.current = analyser;
        setMicStatus("calibrating");
        rafRef.current = requestAnimationFrame(sampleTick);
      } catch {
        // getUserMedia rejection — live-verified for this exact call shape
        // as the same clean NotAllowedError class as the video case (Task
        // 6's header), not a hang.
        if (!cancelled) setMicStatus("unavailable");
      }
    }

    void setup();

    return () => {
      cancelled = true;
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
      analyserRef.current?.disconnect();
      analyserRef.current = null;
      audioContextRef.current?.close();
      audioContextRef.current = null;
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      calibrationSamplesRef.current = [];
      calibrationStartedAtRef.current = null;
      noiseFloorRef.current = null;
      excessiveNoiseSustainRef.current = initialSustainState();
      backgroundVoiceSustainRef.current = initialSustainState();
      lastTranscriptLengthRef.current = 0;
      lastTranscriptGrowthAtRef.current = 0;
      setMicStatus("pending");
      setNoiseFloorDb(null);
    };
  }, [micActive, sampleTick]);

  return { micStatus, noiseFloorDb };
}
```

- [ ] **Step 2: Typecheck and build**

Run: `cd frontend && npx tsc -b --noEmit && npm run build`
Expected: both clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useAudioMonitor.ts
git commit -m "feat(frontend): add Web Audio proctoring hook"
```

---

## Task 8: Wire proctoring in — preflight UI, camera PiP, warning overlay

**Files:**
- Create: `frontend/src/components/interview/PreflightCheck.tsx`
- Create: `frontend/src/components/interview/CameraPip.tsx`
- Create: `frontend/src/components/interview/WarningOverlay.tsx`
- Modify: `frontend/src/hooks/useInterviewMachine.ts`
- Modify: `frontend/src/components/interview/QuestionStage.tsx`
- Modify: `frontend/src/pages/InterviewActivePage.tsx`

Four decisions worth stating before the code, since none of them are
spelled out this concretely anywhere earlier in this plan or the design
doc:

**Preflight is a hard gate, not a soft fallback.** Plan 4's speech hooks
degrade gracefully (no STT → type your answer instead) because that's a
convenience fallback with no integrity implications. Camera/mic access for
a *proctored* interview is different — if denying permission let someone
proceed anyway, proctoring would be trivially bypassable by anyone who
just says no, defeating the feature. So `PreflightCheck` disables
"Continue" until `cameraStatus === "ready" && faceCount === 1 && micStatus
=== "ready"`, with no bypass. The consequence, already anticipated in this
plan's header, is that this environment's live E2E (Task 11) can confirm
the preflight screen and its error path but can't click past it — there's
no real camera to satisfy the gate with.

**`CameraPip`'s "landmark overlay" is a status ring, not a rendered mesh.**
Drawing all 478 individual face-mesh points on a canvas would need
exposing raw landmark coordinates out of `useProctoring` and a
coordinate-mapping layer this project's scope doesn't call for anywhere
else. A colored ring around the preview (green = one face centered, amber
= none, red = more than one) delivers the same "you're being watched, here's
your status" feedback with data the hook already returns (`faceCount`) —
scoped down deliberately, not an oversight.

**The terminated screen uses `recentEventType` + `warningCount`, not a full
event history.** The design doc's "fuller warning-history... treatment for
`proctoring`" could mean fetching every persisted `ProctoringEvent` row —
but that needs a new `GET .../events` list endpoint nowhere else in this
plan, to build a screen that's shown exactly once, right before the page
is left. `useWarnings` (Task 4) already tracks `recentEventType` alongside
`warningCount`; threading both through is enough to distinguish "3
accumulated warnings" from an immediate `multiple_faces` termination
(`warningCount` stays 0 for a fatal event — Task 2's backend never
increments it for those) without new backend surface.

**`reportProctoringEvent` comes out of `useInterviewMachine`'s return
value.** Task 5 exposed `warnings.reportEvent` directly, anticipating that
something outside the hook would call it. Now that `useProctoring` and
`useAudioMonitor` both call it internally via their `onWarning` callback,
nothing external does anymore — leaving it exported would be dead surface.

- [ ] **Step 1: Write `frontend/src/components/interview/PreflightCheck.tsx`**

```tsx
import { Loader2, Mic, Video } from "lucide-react";
import type { RefObject } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import type { MicStatus } from "@/hooks/useAudioMonitor";
import type { CameraStatus } from "@/hooks/useProctoring";
import { cn } from "@/lib/cn";

interface PreflightCheckProps {
  videoRef: RefObject<HTMLVideoElement | null>;
  cameraStatus: CameraStatus;
  faceCount: number;
  micStatus: MicStatus;
  ready: boolean;
  onContinue: () => void;
}

function faceMessage(cameraStatus: CameraStatus, faceCount: number): string {
  if (cameraStatus === "pending") return "Requesting camera access…";
  if (cameraStatus === "unavailable") return "Camera unavailable";
  if (faceCount === 0) return "No face detected — center yourself in frame";
  if (faceCount >= 2) return "Multiple faces detected — only the candidate should be visible";
  return "Face detected";
}

function micMessage(micStatus: MicStatus): string {
  if (micStatus === "pending") return "Requesting microphone access…";
  if (micStatus === "unavailable") return "Microphone unavailable";
  if (micStatus === "calibrating") return "Calibrating background noise level…";
  return "Microphone ready";
}

export function PreflightCheck({
  videoRef,
  cameraStatus,
  faceCount,
  micStatus,
  ready,
  onContinue,
}: PreflightCheckProps) {
  const cameraOk = cameraStatus === "ready" && faceCount === 1;
  const cameraFailed = cameraStatus === "unavailable";
  const micFailed = micStatus === "unavailable";

  return (
    <Card className="space-y-4">
      <CardTitle>Getting ready…</CardTitle>
      <CardDescription>
        This is a proctored interview — camera and microphone access are required.
      </CardDescription>

      <div className="overflow-hidden rounded-lg bg-surface-hover">
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          className="aspect-video w-full -scale-x-100 object-cover"
        />
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex items-center gap-2">
          <Video className={cn("size-4", cameraOk ? "text-success" : "text-text-muted")} />
          <span className={cameraFailed ? "text-danger" : "text-text-secondary"}>
            {faceMessage(cameraStatus, faceCount)}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Mic className={cn("size-4", micStatus === "ready" ? "text-success" : "text-text-muted")} />
          <span className={micFailed ? "text-danger" : "text-text-secondary"}>
            {micMessage(micStatus)}
          </span>
          {micStatus === "calibrating" && (
            <Loader2 className="size-3 animate-spin text-text-muted" />
          )}
        </div>
      </div>

      {(cameraFailed || micFailed) && (
        <CardDescription className="text-danger">
          Camera and microphone access are both required to start a proctored interview. Please
          allow access in your browser and reload this page.
        </CardDescription>
      )}

      <Button onClick={onContinue} disabled={!ready}>
        Continue
      </Button>
    </Card>
  );
}
```

- [ ] **Step 2: Write `frontend/src/components/interview/CameraPip.tsx`**

```tsx
import type { RefObject } from "react";

import type { CameraStatus } from "@/hooks/useProctoring";
import { cn } from "@/lib/cn";

interface CameraPipProps {
  videoRef: RefObject<HTMLVideoElement | null>;
  cameraStatus: CameraStatus;
  faceCount: number;
}

export function CameraPip({ videoRef, cameraStatus, faceCount }: CameraPipProps) {
  if (cameraStatus !== "ready") return null;

  const ringColor =
    faceCount === 1 ? "ring-success" : faceCount === 0 ? "ring-warning" : "ring-danger";

  return (
    <div
      className={cn(
        "fixed bottom-6 right-6 z-40 h-32 w-44 overflow-hidden rounded-lg bg-surface-hover shadow-lg ring-2",
        ringColor,
      )}
    >
      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        className="h-full w-full -scale-x-100 object-cover"
      />
    </div>
  );
}
```

- [ ] **Step 3: Write `frontend/src/components/interview/WarningOverlay.tsx`**

```tsx
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle } from "lucide-react";
import { useEffect, useState } from "react";

const EVENT_LABELS: Record<string, string> = {
  looking_away: "Looking away from the camera",
  no_face: "No face detected",
  multiple_faces: "Multiple faces detected",
  excessive_noise: "Excessive background noise",
  background_voice: "Unidentified background voice",
};

interface WarningOverlayProps {
  warningCount: number;
  recentEventType: string | null;
}

export function WarningOverlay({ warningCount, recentEventType }: WarningOverlayProps) {
  const [banner, setBanner] = useState(false);

  useEffect(() => {
    if (warningCount === 0) return;
    setBanner(true);
    const timeout = setTimeout(() => setBanner(false), 4000);
    return () => clearTimeout(timeout);
  }, [warningCount]);

  if (warningCount === 0) return null;

  const label = warningCount >= 3 ? "Final warning" : `Warning ${warningCount} of 3`;
  const detail = recentEventType ? (EVENT_LABELS[recentEventType] ?? recentEventType) : null;

  return (
    <AnimatePresence>
      {banner ? (
        <motion.div
          key="banner"
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0, x: [0, -6, 6, -4, 4, 0] }}
          exit={{ opacity: 0, y: -12 }}
          transition={{ duration: 0.4 }}
          className="fixed left-1/2 top-6 z-50 flex -translate-x-1/2 items-center gap-2 rounded-lg border border-warning bg-surface px-4 py-3 shadow-lg"
        >
          <AlertTriangle className="size-5 text-warning" />
          <div>
            <p className="text-sm font-semibold text-text-primary">{label}</p>
            {detail && <p className="text-xs text-text-secondary">{detail}</p>}
          </div>
        </motion.div>
      ) : (
        <motion.div
          key="badge"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed left-6 top-6 z-50 flex items-center gap-1.5 rounded-full border border-warning bg-surface px-3 py-1 text-xs font-medium text-warning shadow"
        >
          <AlertTriangle className="size-3.5" />
          {warningCount} of 3
        </motion.div>
      )}
    </AnimatePresence>
  );
}
```

- [ ] **Step 4: Replace `frontend/src/hooks/useInterviewMachine.ts`**

```typescript
import { useCallback, useEffect, useReducer, useRef } from "react";

import { useQuitInterview, useSaveInterviewAnswer, useSubmitInterview } from "@/hooks/useInterview";
import { useAudioMonitor } from "@/hooks/useAudioMonitor";
import { useProctoring } from "@/hooks/useProctoring";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";
import { useSpeechSynthesis } from "@/hooks/useSpeechSynthesis";
import { useWarnings } from "@/hooks/useWarnings";
import { initialMachineState, transition } from "@/lib/interviewMachine";
import type { Interview } from "@/types";

export function useInterviewMachine(interview: Interview) {
  const [state, dispatch] = useReducer(transition, initialMachineState());
  const tts = useSpeechSynthesis();
  const stt = useSpeechRecognition();
  const saveAnswer = useSaveInterviewAnswer(interview.id);
  const submit = useSubmitInterview(interview.id);
  const quit = useQuitInterview(interview.id);
  const warnings = useWarnings(interview.id);
  const answerStartRef = useRef<number | null>(null);

  const currentQuestion = interview.questions[state.questionIndex] ?? null;
  const isLastQuestion = state.questionIndex === interview.questions.length - 1;

  // Camera/mic run continuously from preflight through the last answer;
  // warnings are armed only once preflight's own calibration is done, so
  // sitting down and getting centered never counts against the candidate.
  const cameraActive = state.phase !== "review" && state.phase !== "terminated";
  const warningsArmed = cameraActive && state.phase !== "preflight";
  const isAnswering = state.phase === "answering";

  const proctoring = useProctoring(cameraActive, warningsArmed, warnings.reportEvent);
  const audio = useAudioMonitor(
    cameraActive,
    warningsArmed,
    isAnswering,
    stt.supported,
    stt.transcript,
    warnings.reportEvent,
  );

  const preflightPassed =
    proctoring.cameraStatus === "ready" &&
    proctoring.faceCount === 1 &&
    audio.micStatus === "ready";

  const preflightReady = useCallback(() => dispatch({ type: "PREFLIGHT_READY" }), []);
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

  useEffect(() => {
    if (warnings.terminated) dispatch({ type: "TERMINATE", reason: "proctoring" });
  }, [warnings.terminated]);

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
    dispatch({ type: "TERMINATE", reason: "user_quit" });
    quit.mutate();
  }, [tts, stt, quit]);

  return {
    phase: state.phase,
    terminationReason: state.terminationReason,
    currentQuestion,
    questionNumber: state.questionIndex + 1,
    totalQuestions: interview.questions.length,
    preflightReady,
    preflightPassed,
    begin,
    advance,
    quitNow,
    ttsSupported: tts.supported,
    sttSupported: stt.supported,
    liveTranscript: stt.transcript,
    listening: stt.listening,
    warningCount: warnings.warningCount,
    recentEventType: warnings.recentEventType,
    videoRef: proctoring.videoRef,
    cameraStatus: proctoring.cameraStatus,
    faceCount: proctoring.faceCount,
    micStatus: audio.micStatus,
  };
}
```

- [ ] **Step 5: Replace `frontend/src/components/interview/QuestionStage.tsx`**

```tsx
import { ArrowRight, LogOut } from "lucide-react";
import { useState } from "react";
import type { RefObject } from "react";

import { CameraPip } from "@/components/interview/CameraPip";
import { PreflightCheck } from "@/components/interview/PreflightCheck";
import { TranscriptPanel } from "@/components/interview/TranscriptPanel";
import { WarningOverlay } from "@/components/interview/WarningOverlay";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import type { MicStatus } from "@/hooks/useAudioMonitor";
import type { CameraStatus } from "@/hooks/useProctoring";
import type { Interview, MachinePhase, TerminationReason } from "@/types";

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
  onPreflightReady: () => void;
  terminationReason: TerminationReason | null;
  videoRef: RefObject<HTMLVideoElement | null>;
  cameraStatus: CameraStatus;
  faceCount: number;
  micStatus: MicStatus;
  preflightPassed: boolean;
  warningCount: number;
  recentEventType: string | null;
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
  onPreflightReady,
  terminationReason,
  videoRef,
  cameraStatus,
  faceCount,
  micStatus,
  preflightPassed,
  warningCount,
  recentEventType,
}: QuestionStageProps) {
  const [manualAnswer, setManualAnswer] = useState("");

  if (phase === "preflight") {
    return (
      <PreflightCheck
        videoRef={videoRef}
        cameraStatus={cameraStatus}
        faceCount={faceCount}
        micStatus={micStatus}
        ready={preflightPassed}
        onContinue={onPreflightReady}
      />
    );
  }

  if (phase === "terminated") {
    const isProctoring = terminationReason === "proctoring";
    const isFatal = isProctoring && recentEventType === "multiple_faces";
    return (
      <Card className="space-y-4">
        <CardTitle>{isProctoring ? "Interview terminated" : "Interview ended"}</CardTitle>
        <CardDescription>
          {!isProctoring
            ? "You ended this interview early."
            : isFatal
              ? "This interview was terminated: multiple faces were detected in frame."
              : `This interview was terminated after ${warningCount} proctoring warnings.`}
        </CardDescription>
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
      <CameraPip videoRef={videoRef} cameraStatus={cameraStatus} faceCount={faceCount} />
      <WarningOverlay warningCount={warningCount} recentEventType={recentEventType} />

      {phase === "briefing" ? (
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
      ) : (
        <>
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
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Update `frontend/src/pages/InterviewActivePage.tsx`**

Replace the `<QuestionStage>` call inside `ActiveInterview` with:

```tsx
      <QuestionStage
        key={machine.currentQuestion?.id ?? "review"}
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
        onPreflightReady={machine.preflightReady}
        terminationReason={machine.terminationReason}
        videoRef={machine.videoRef}
        cameraStatus={machine.cameraStatus}
        faceCount={machine.faceCount}
        micStatus={machine.micStatus}
        preflightPassed={machine.preflightPassed}
        warningCount={machine.warningCount}
        recentEventType={machine.recentEventType}
      />
```

- [ ] **Step 7: Typecheck, build, run the full test suite**

Run: `cd frontend && npx tsc -b --noEmit && npm run build && npm test`
Expected: all clean, `46 passed` — unchanged from Task 5, since this task
wires existing pieces together and adds no new pure logic to test.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/interview/PreflightCheck.tsx frontend/src/components/interview/CameraPip.tsx frontend/src/components/interview/WarningOverlay.tsx frontend/src/hooks/useInterviewMachine.ts frontend/src/components/interview/QuestionStage.tsx frontend/src/pages/InterviewActivePage.tsx
git commit -m "feat(frontend): wire proctoring into the interview UI"
```

---
