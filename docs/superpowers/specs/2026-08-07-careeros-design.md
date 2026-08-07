# CareerOS — Design Spec

**Date:** 2026-08-07
**Status:** Approved
**Scope:** University mini project. Single user, local-only, no auth.

---

## 1. Purpose

CareerOS is an AI Career Mentor. A learner picks a technical topic, declares an
experience level, optionally sits an adaptive assessment, receives a personalized
multi-phase learning roadmap, tracks progress through it, and takes AI-generated
proctored mock interviews that produce scored reports.

The project demonstrates three things: practical LLM integration with structured
output, a real-time browser ML pipeline (proctoring), and a polished product
surface. It deliberately excludes auth, multi-tenancy, deployment, and billing.

---

## 2. Decisions

| Decision | Choice | Reason |
|---|---|---|
| LLM | Google Gemini (`gemini-2.5-flash`) via `google-genai` | Native `response_schema` structured output makes roadmap/assessment JSON reliable without prompt gymnastics. Generous free tier. |
| Proctoring | In-browser MediaPipe Tasks Vision (WASM) | Real-time at 10fps, no video leaves the machine, no bandwidth. Also: MediaPipe's Python wheels do not support the installed Python 3.14. |
| Long AI waits | SSE streaming, phase-by-phase | Roadmap generation is 15–45s. Streaming turns a dead spinner into the best moment in the demo. |
| Testing | Focused (~28 tests) | Cover the logic where silent bugs hide: stream parsing, scoring, progress math, warning escalation. No network in tests. |
| Migrations | None — `create_all()` on startup | YAGNI for a single-user local DB. |

**On OpenCV:** the original brief named MediaPipe *and* OpenCV. Because detection
runs in the browser, OpenCV is not used — its role there (frame decode, color
conversion, drawing) is handled by `<video>`, `<canvas>`, and MediaPipe's own
WASM pipeline. Adding a Python OpenCV path would mean shipping webcam frames over
HTTP for no gain in capability. This is a deliberate substitution, noted so the
divergence from the brief is visible rather than silent.

---

## 3. System architecture

```
┌──────────────────────────────┐          ┌─────────────────────┐
│ Browser (React 19 + TS)      │          │ FastAPI             │
│                              │  REST    │                     │
│  TanStack Query ─────────────┼─────────▶│  routers/           │
│  sseFetch() ─────────────────┼── SSE ──▶│  services/          │──▶ Gemini 2.5 Flash
│                              │          │  ai/ (client+prompts)│
│  MediaPipe FaceLandmarker    │  events  │  models/ (SQLAlchemy)│
│  Web Audio AnalyserNode  ────┼─────────▶│         │           │
│  Web Speech TTS / STT        │  (JSON,  │         ▼           │
│                              │  no A/V) │    careeros.db      │
└──────────────────────────────┘          └─────────────────────┘
```

**Boundary rule:** the browser owns everything real-time and continuous (video
frames, audio buffers, speech). The backend owns everything durable and
authoritative (state, AI calls, scoring, warning counts). Camera and microphone
data never cross the network — only derived events do, and a proctoring event is
roughly 80 bytes.

---

## 4. Repository layout

```
CareerOS/
├── README.md
├── .gitignore
├── docs/superpowers/specs/
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── main.py                      # app factory, CORS, router mounting, create_all
│   ├── config.py                    # pydantic-settings
│   ├── db/
│   │   ├── base.py                  # DeclarativeBase
│   │   └── session.py               # engine, SessionLocal, get_db, PRAGMA listeners
│   ├── models/
│   │   ├── user.py                  # User, LearningTrack
│   │   ├── assessment.py            # Assessment, AssessmentQuestion
│   │   ├── roadmap.py               # Roadmap, RoadmapPhase, RoadmapModule
│   │   └── interview.py             # Interview, InterviewQuestion, ProctoringEvent
│   ├── schemas/
│   │   ├── common.py profile.py assessment.py roadmap.py interview.py dashboard.py
│   ├── ai/
│   │   ├── client.py                # AIClient protocol + GeminiClient + FakeAIClient
│   │   ├── errors.py                # AIUnavailable, AIInvalidResponse
│   │   ├── stream_parser.py         # PhaseStreamParser (pure, no I/O)
│   │   └── prompts/
│   │       ├── assessment.py roadmap.py interview.py evaluation.py
│   ├── services/
│   │   ├── profile_service.py assessment_service.py roadmap_service.py
│   │   ├── progress_service.py interview_service.py evaluation_service.py
│   │   └── proctoring_service.py
│   ├── routers/
│   │   ├── health.py profile.py tracks.py assessment.py roadmap.py
│   │   ├── interview.py dashboard.py
│   └── tests/
│       ├── conftest.py              # in-memory DB + FakeAIClient dependency override
│       ├── test_stream_parser.py test_assessment_service.py
│       ├── test_roadmap_service.py test_progress_service.py
│       ├── test_interview_service.py test_api_smoke.py
└── frontend/
    ├── package.json vite.config.ts tsconfig*.json components.json index.html
    ├── public/
    │   ├── models/face_landmarker.task      # vendored, no CDN at runtime
    │   └── mediapipe-wasm/                  # vendored WASM fileset
    └── src/
        ├── main.tsx App.tsx index.css
        ├── components/
        │   ├── ui/                  # shadcn primitives
        │   ├── layout/              # AppShell, Sidebar, TopBar, ThemeToggle
        │   ├── onboarding/          # NameStep, TopicStep, LevelStep
        │   ├── assessment/          # QuestionCard, McqOptions, DescriptiveAnswer, ResultSummary
        │   ├── roadmap/             # RoadmapTimeline, PhaseCard, ModuleAccordion,
        │   │                        # ModuleRow, ProgressRing, LockBadge
        │   ├── interview/           # SetupForm, PreflightCheck, QuestionStage, CameraPip,
        │   │                        # TranscriptPanel, TimerRing, ProctorHud, WarningOverlay
        │   └── report/              # ScoreBreakdown, PerQuestionCard, RecommendationList
        ├── pages/                   # Onboarding, Dashboard, Assessment, Roadmap,
        │                            # InterviewSetup, InterviewActive, InterviewReport,
        │                            # History, Settings
        ├── hooks/
        │   ├── useTheme.ts useProfile.ts useRoadmap.ts useProgress.ts
        │   ├── useSpeechSynthesis.ts useSpeechRecognition.ts
        │   ├── useProctoring.ts useAudioMonitor.ts useWarnings.ts
        │   └── useInterviewMachine.ts
        ├── lib/
        │   ├── cn.ts constants.ts format.ts
        │   ├── proctorRules.ts      # pure: matrixToEuler, sustain windows
        │   └── progress.ts          # pure: mirrors backend unlock rule
        ├── services/api/            # typed clients + sse.ts
        └── types/
```

**Sizing rule:** any file past ~250 lines is a signal to split. Services hold
logic; routers stay thin (validate → call service → return schema).

---

## 5. Database schema

SQLite via SQLAlchemy 2.0 (`DeclarativeBase`, `Mapped`, `mapped_column`).
`create_all()` runs at startup. Two PRAGMAs are set through a `connect` event
listener — **`foreign_keys=ON` matters because SQLite ignores FK constraints by
default** — plus `journal_mode=WAL`.

### users
| col | type | notes |
|---|---|---|
| id | int PK | always 1 in practice |
| name | str | editable in Settings |
| theme | str | `light` \| `dark` \| `system`, default `system` |
| created_at, updated_at | datetime | |

### learning_tracks
| col | type | notes |
|---|---|---|
| id | int PK | |
| user_id | FK users | |
| topic | str | preset or custom, free text |
| experience_level | str | `beginner` \| `intermediate` \| `advanced` |
| is_active | bool | exactly one active track; activating one deactivates others |
| created_at | datetime | |

Multiple tracks let the learner study Python now and React later. The dashboard
renders the active track.

### assessments
`id`, `track_id` FK, `level` (the declared level), `status`
(`in_progress`\|`completed`), `started_at`, `completed_at`, `score` (0–100 float),
`estimated_level` (`foundational`\|`intermediate`\|`advanced`), `strengths` JSON
(list of topic tags), `weaknesses` JSON, `summary` (text).

### assessment_questions
`id`, `assessment_id` FK, `order_index`, `type` (`mcq`\|`descriptive`),
`topic_tag` (e.g. `oop`, `loops`), `question`, `options` JSON (4 items, mcq only),
`correct_option` int (mcq only, **never serialized to the client before submit**),
`expected_points` JSON (descriptive only — the rubric), `user_answer` text,
`score` float 0–10, `ai_feedback` text.

### roadmaps
`id`, `track_id` FK, `title`, `summary`, `total_weeks` int, `weekly_hours` int,
`weekly_goals` JSON, `final_project` JSON, `assessment_id` FK nullable (null for
Beginner), `created_at`.

`weekly_goals` is a list of `{week, goal, phase_order}` — the model plans the
whole span week by week, which is what makes "12 weeks" a schedule rather than a
number. `final_project` is `{title, description, skills_demonstrated}` and is
deliberately roadmap-level: it is the capstone spanning every phase, distinct
from the per-phase mini projects stored on modules. `weekly_hours` is proposed by
the model as a study pace, not collected during onboarding.

### roadmap_phases
`id`, `roadmap_id` FK, `order_index`, `title`, `description`, `goal`,
`estimated_hours` int.

### roadmap_modules
`id`, `phase_id` FK, `order_index`, `title`, `description`, `lessons` JSON
(list of strings), `exercises` JSON (covers both hands-on exercises and practice
tasks), `project` JSON nullable (`{title, description}` — a mini project),
`estimated_hours` int, `kind`
(`module`\|`checkpoint`\|`milestone`\|`project`), `started_at` nullable,
`completed_at` nullable.

`kind` is how revision checkpoints and milestones are represented: they are
modules the learner completes like any other, but the timeline renders them with
distinct treatment (checkpoint = review marker, milestone = phase capstone).

Progress lives on the module row rather than in a side table — it is strictly 1:1
and a join table would be ceremony without benefit.

### interviews
`id`, `track_id` FK, `level` (`beginner`\|`intermediate`\|`advanced`),
`question_count` (5\|8\|10), `status` (`setup`\|`active`\|`completed`\|`terminated`),
`started_at`, `ended_at`, `termination_reason` nullable, `warning_count` int
default 0, `overall_score`, `technical_score`, `communication_score`,
`confidence_score` (all 0–100 float, null until evaluated), `strengths` JSON,
`weaknesses` JSON, `recommendations` JSON, `summary` text.

### interview_questions
`id`, `interview_id` FK, `order_index`, `question`, `expected_points` JSON,
`transcript` text, `answer_duration_s` int, `technical_score`,
`communication_score`, `confidence_score` (0–10 each), `missing_concepts` JSON,
`better_answer` text, `feedback` text.

### proctoring_events
`id`, `interview_id` FK, `question_id` FK nullable, `created_at`, `type`
(`looking_away`\|`no_face`\|`multiple_faces`\|`excessive_noise`\|`background_voice`),
`severity` (`warning`\|`fatal`), `detail` text, `warning_index` int nullable.

---

## 6. Derived logic (pure, shared, tested)

These rules are implemented once on the backend (`progress_service.py`) and
mirrored on the frontend (`lib/progress.ts`) so the UI can update optimistically.
Both sides are unit-tested against the same cases.

**Module complete** — `completed_at IS NOT NULL`.

**Phase completion** — `completed_modules / total_modules` in that phase.

**Roadmap completion** — `completed_modules / total_modules` across all phases.

**Phase unlocked** — `order_index == 0` **OR** previous phase completion `>= 0.8`.
All modules inside an unlocked phase are available; modules do not lock each
other within a phase. This is what makes the roadmap feel like Linear rather than
a rigid course player.

**Current phase** — the first phase below 100% completion; if every phase is
complete, the last phase.

**Assessment score** — MCQ scores 10 (correct) or 0; descriptive is graded 0–10
by the model against `expected_points`. Final `score` = mean of all question
scores × 10.

**Estimated level banding** — `score < 40` → `foundational`; `40 ≤ score < 70` →
`intermediate`; `score ≥ 70` → `advanced`. The bands are relative to the declared
level, because an Advanced assessment asks harder questions than an Intermediate
one. The declared level is passed to the roadmap prompt alongside the estimate.

**Strengths / weaknesses** — group question scores by `topic_tag`, take the mean:
mean `≥ 7` → strength, mean `≤ 4` → weakness, otherwise neutral. Deterministic
and testable; the model only writes the prose `summary`.

**Warning escalation** — `multiple_faces` is `fatal` and terminates immediately.
Every other event type is a `warning`. Three warnings of any mix terminate the
interview. The backend is the authority on the count; the frontend mirrors it for
instant feedback and reconciles from the response.

---

## 7. API

All routes under `/api`. Errors return
`{"detail": {"code": "...", "message": "..."}}`.

### Profile & tracks
```
GET    /api/profile                      → User | 204 if not onboarded
POST   /api/profile                      {name}                → User
PATCH  /api/profile                      {name?, theme?}       → User

GET    /api/tracks                       → Track[]
POST   /api/tracks                       {topic, experience_level} → Track
POST   /api/tracks/{id}/activate         → Track
```

### Assessment
```
POST   /api/tracks/{id}/assessment       → Assessment + questions (answers stripped)
GET    /api/assessments/{id}             → Assessment + questions
PATCH  /api/assessments/{id}/answers     {question_id, answer}  → 204   (autosave)
POST   /api/assessments/{id}/submit      → graded Assessment (score, level,
                                            strengths, weaknesses, per-question feedback)
GET    /api/assessments                  → Assessment[] (history)
```
Generation asks for 8–12 questions mixing MCQ and descriptive, tagged by subtopic
and adapted to the track topic. `correct_option` and `expected_points` are
withheld from every response until after submit.

`POST /api/tracks/{id}/assessment` returns **400 `assessment_not_applicable`** for
a Beginner track. Beginners skip assessment entirely and go straight to roadmap
generation, which is conditioned on zero prior knowledge.

### Roadmap
```
POST   /api/tracks/{id}/roadmap/stream   → text/event-stream
GET    /api/tracks/{id}/roadmap          → Roadmap + phases + modules + progress
PATCH  /api/modules/{id}                 {completed: bool} → {module, progress}
GET    /api/tracks/{id}/progress         → progress summary
```

### Interview
```
POST   /api/tracks/{id}/interviews       {level, question_count} → Interview + questions
GET    /api/interviews/{id}              → Interview + questions
POST   /api/interviews/{id}/questions/{qid}/answer  {transcript, duration_s} → 204
POST   /api/interviews/{id}/events       {type, detail}
                                         → {warning_count, should_terminate}
POST   /api/interviews/{id}/terminate    {reason} → Interview
POST   /api/interviews/{id}/submit       → evaluated Interview (the report)
GET    /api/interviews                   → Interview[] (history)
```
Question generation is roadmap-aware: the prompt receives the track topic, the
requested level and count, and the titles of completed plus current-phase modules
when a roadmap exists. No fixed question bank exists anywhere in the codebase.

### Dashboard
```
GET    /api/dashboard  → {profile, active_track, roadmap_summary, current_phase,
                          completed_modules, remaining_modules, completion_pct,
                          next_module, recent_interviews}
```

---

## 8. AI layer

### Client

`ai/client.py` defines an `AIClient` Protocol with two methods, implemented by
`GeminiClient` and by `FakeAIClient` (tests):

```python
def generate_json(prompt: Prompt) -> dict
def generate_json_stream(prompt: Prompt) -> Iterator[str]   # raw text chunks
```

`Prompt` is a frozen dataclass — `system_instruction`, `user_content`,
`response_schema`, `temperature`, `max_output_tokens`. Every module in
`ai/prompts/` exposes pure builder functions returning a `Prompt`, which makes
prompt construction testable without any client at all.

`GeminiClient` calls `client.models.generate_content(...)` with
`response_mime_type="application/json"` and `response_schema`, and
`generate_content_stream(...)` for the streaming path. Simple extraction calls
set `thinking_config=ThinkingConfig(thinking_budget=0)` for latency; roadmap
generation and interview evaluation leave thinking enabled.

Transient failures (429, 503, timeout) retry three times with exponential backoff
(1s, 2s, 4s) plus jitter. Exhausted retries raise `AIUnavailable`, which
`main.py` maps to HTTP 503 with code `ai_unavailable`. A response that fails
schema validation raises `AIInvalidResponse` → 502 `ai_invalid_response`. The
frontend renders a retry card for both.

Tests never touch the network: `conftest.py` overrides the `get_ai_client`
dependency with `FakeAIClient`, which returns canned fixtures.

### Streaming roadmap

The model returns one object:

```json
{"title": "...", "summary": "...", "total_weeks": 12, "weekly_hours": 8,
 "weekly_goals": [{"week": 1, "goal": "...", "phase_order": 0}, ...],
 "final_project": {"title": "...", "description": "...", "skills_demonstrated": [...]},
 "phases": [{"title": "...", "goal": "...", "modules": [...]}, ...]}
```

`phases` is required to be the **last key** in the schema so that every scalar
field is already complete by the time the first phase streams — the `meta` event
can therefore fire with full data before any phase arrives.

`ai/stream_parser.py` holds `PhaseStreamParser` — a pure incremental scanner with
no I/O. It accumulates chunks, tracks brace depth while correctly skipping over
string literals and backslash escapes, and yields each complete phase object the
moment its closing brace arrives. The route wraps it as SSE:

```
event: meta   data: {"title":..., "summary":..., "total_weeks":..., "weekly_hours":...,
                     "weekly_goals":[...], "final_project":{...}}
event: phase  data: {"order_index":0, "title":"Foundations", "modules":[...]}
event: phase  data: {"order_index":1, ...}
event: done   data: {"roadmap_id": 3}
event: error  data: {"code":"ai_unavailable","message":"..."}
```

Phases are persisted as they arrive, inside one transaction committed on `done`.
If the stream dies mid-way, nothing is committed and the client retries.

**Transport note:** `EventSource` cannot issue POST requests, so the frontend uses
`fetch` + `ReadableStream` through a small `services/api/sse.ts` helper. This
avoids inventing a job table purely to satisfy `EventSource`'s GET-only contract.

### Prompt responsibilities

| Module | Produces |
|---|---|
| `prompts/assessment.py` | 8–12 tagged questions for the topic and level; then the grading prompt for descriptive answers (batched, one call) |
| `prompts/roadmap.py` | Phases → modules → lessons/exercises/mini-projects, plus week-by-week goals, revision checkpoints, milestones, and one capstone project. Conditioned on declared level, estimated level, strengths, weaknesses. Beginner variant assumes zero knowledge and starts at fundamentals; Advanced variant skips fundamentals, weights weak tags, and adds interview-focused revision |
| `prompts/interview.py` | N questions at the requested difficulty, roadmap-aware, each with `expected_points` |
| `prompts/evaluation.py` | One call containing every Q/A pair → per-question and overall scores |

Interview evaluation is a **single call for the whole interview**, not one per
question. It is cheaper, and it lets the model judge consistency and confidence
across answers rather than in isolation. The response schema pins the array
length to the question count. Unanswered questions (early termination) arrive
with an empty transcript and are scored 0 with explicit "not answered" feedback.

Confidence scoring is grounded rather than guessed: the prompt receives
`answer_duration_s` and word count per answer alongside the transcript, so the
model reasons over filler ratio and pacing instead of inventing a number.

---

## 9. Proctoring

### Video — `useProctoring`

`@mediapipe/tasks-vision` `FaceLandmarker` in `VIDEO` running mode, `numFaces: 2`,
`outputFacialTransformationMatrixes: true`, GPU delegate with CPU fallback. The
`.task` model and the WASM fileset are **vendored into `public/`** so the app has
no runtime CDN dependency. Detection runs in a `requestAnimationFrame` loop
throttled to 10fps — enough for head-pose tracking, cheap enough to leave the UI
responsive.

`lib/proctorRules.ts` holds the pure math. `matrixToEuler(d: Float32Array)` reads
the column-major 4×4 transformation matrix and returns degrees:

```
pitch = atan2(d[6],  d[10])
yaw   = atan2(-d[2], hypot(d[6], d[10]))
roll  = atan2(d[1],  d[0])
```

**Every rule is sustain-debounced.** Firing on a single frame would turn a blink
or a glance at the keyboard into a warning.

| Signal | Condition | Sustain | Action |
|---|---|---|---|
| `looking_away` | `abs(yaw) > 25°` or `pitch < -20°` | 2.5s | +1 warning, then 10s cooldown |
| `no_face` | `faceCount == 0` | 4s | +1 warning, then 10s cooldown |
| `multiple_faces` | `faceCount >= 2` | 1.5s | **fatal — terminate immediately** |

### Audio — `useAudioMonitor`

Web Audio `AnalyserNode` on the microphone stream, RMS sampled at 20Hz. During
the 3-second preflight the hook calibrates a noise floor from the ambient room.

| Signal | Condition | Sustain | Action |
|---|---|---|---|
| `excessive_noise` | RMS > floor + 18dB while the user is not the active speaker | 3s | +1 warning |
| `background_voice` | speech-band energy present while STT reports no user speech | 3s | +1 warning |

**Stated honestly:** true multi-speaker diarization is not achievable in-browser
within this project's scope. These two rules are energy heuristics against a
calibrated floor. They behave correctly for the cases that matter (a TV on in the
room, someone talking nearby) and they are documented as heuristics in the README
rather than presented as speaker identification.

### Escalation — `useWarnings`

A single reducer owns warning state; both hooks dispatch into it, which is why
counts cannot drift between video and audio. Each event POSTs to
`/api/interviews/{id}/events`; the backend response is authoritative and
reconciles the local count. Severity classification lives server-side so a
tampered client cannot downgrade a `fatal`.

UI: `Warning 1 of 3` → `Warning 2 of 3` → `Final Warning` → `Interview
Terminated`, rendered as a Framer Motion overlay with a shake transition.

---

## 10. Speech and the interview machine

**TTS** — `speechSynthesis`, preferring an `en-US` voice, rate 0.95. Each question
is spoken on entry to the `speaking` state.

**STT** — `webkitSpeechRecognition`, `continuous` and `interimResults` on, feeding
the live transcript panel. **Recognition is hard-stopped while TTS is playing.**
Without this the microphone transcribes the AI's own question back as the
candidate's answer — the single most important detail in this module.

**Browser support** — Web Speech STT is Chrome/Edge only. When
`SpeechRecognition` is undefined the interview still runs, substituting a
textarea labelled "Speech recognition unavailable in this browser — type your
answer." The README recommends Chrome. This keeps the app demonstrable on any
machine.

**State machine** — `useInterviewMachine`:

```
idle → preflight → briefing → speaking → answering → review
                                  ▲                     │
                                  └─────────────────────┘  (next question)
                                                        │
                                                        ▼
                                                    evaluating → report

terminated  ← reachable from preflight/briefing/speaking/answering (absorbing)
```

`preflight` verifies camera and microphone permission, confirms exactly one face
is visible, and calibrates the audio noise floor before the interview can start.
Each question carries a countdown timer; expiry advances to `review`
automatically with whatever transcript exists.

---

## 11. Frontend design system

Tailwind v4 with `@theme` tokens, the same token-swap approach as the reference
repo but with its own palette — a neutral slate scale plus a single indigo/violet
accent, so CareerOS reads as its own product rather than a reskin. Tokens cover
color, type scale, radii, and durations; flipping `class="dark"` on `<html>`
swaps the whole palette with no rebuild.

- **Themes:** light / dark / system. `useTheme` persists to `localStorage` and
  subscribes to `matchMedia('(prefers-color-scheme: dark)')` for the system mode.
- **Components:** shadcn/ui primitives (button, card, dialog, input, select, tabs,
  textarea, tooltip, progress, badge, accordion).
- **Server state:** TanStack Query everywhere. Module completion toggles
  optimistically using the shared `lib/progress.ts` rule.
- **Motion:** Framer Motion for phase stagger as the roadmap streams in, progress
  ring transitions, page transitions, and the warning overlay.
- **Responsive:** sidebar collapses to a bottom nav below `md`.

### Pages

| Route | Content |
|---|---|
| `/onboarding` | Three steps: name → topic (20 preset chips + free-text custom) → experience level cards |
| `/dashboard` | Greeting, active track, current phase, progress ring, next module, Continue Learning, recent interviews |
| `/assessment/:id` | One question at a time, progress bar, MCQ cards or textarea, autosave per answer, result summary on submit |
| `/roadmap` | Vertical timeline, expandable phase cards, module rows with checkboxes, lock badges, per-phase and overall completion, estimated time |
| `/interview` | Level selector, question count (5/8/10), preflight check |
| `/interview/:id/active` | Full-screen stage: question card, camera PiP with landmark overlay, live transcript, timer ring, proctor HUD, warning overlay |
| `/interview/:id/report` | Overall scores, per-question breakdown with missing concepts and better answers, strengths, weaknesses, recommendations |
| `/history` | Past assessments and interviews, linking to reports |
| `/settings` | Edit name, theme selector, reset-data danger zone |

---

## 12. Testing

Focused coverage of logic where bugs stay silent. No test performs network I/O.

**Backend — pytest**, in-memory SQLite, `FakeAIClient` via dependency override:

| File | Tests | Covers |
|---|---|---|
| `test_stream_parser.py` | 5 | phase emission, nested objects, `}` inside strings, backslash escapes, truncated stream |
| `test_assessment_service.py` | 5 | MCQ auto-scoring, mean scoring, level banding at boundaries (39/40/69/70), strength/weakness grouping |
| `test_roadmap_service.py` | 4 | schema validation, rejects empty phases, ordering persisted, beginner path with null assessment |
| `test_progress_service.py` | 5 | phase completion, roadmap completion, 80% unlock rule, current-phase detection, all-complete edge |
| `test_interview_service.py` | 4 | warning accumulation, 3-strike termination, `multiple_faces` immediate termination, events after termination rejected |
| `test_api_smoke.py` | 3 | onboarding → track → roadmap happy path; interview lifecycle; 503 on `AIUnavailable` |

**Frontend — Vitest:**

| File | Tests | Covers |
|---|---|---|
| `useWarnings.test.ts` | 4 | escalation 1→2→3, cooldown suppression, fatal bypass, backend reconciliation |
| `proctorRules.test.ts` | 4 | `matrixToEuler` against known matrices, yaw threshold, pitch threshold, sustain windows |
| `progress.test.ts` | 2 | frontend unlock rule matches backend fixtures exactly |

---

## 13. Configuration

`backend/.env` (gitignored; `.env.example` committed):

```
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
DATABASE_URL=sqlite:///./careeros.db
CORS_ORIGINS=http://localhost:5173
```

`frontend/.env`:

```
VITE_API_BASE_URL=http://localhost:8000
```

Backend runs on `:8000` (`uvicorn main:app --reload`), frontend on `:5173`
(`npm run dev`). No Docker, no CI, no deployment — explicitly out of scope.

---

## 14. Build order

Each stage leaves the app runnable.

1. **Scaffold** — both projects, Tailwind tokens, theme system, app shell, routing. No AI.
2. **Profile & tracks** — schema, `create_all`, profile/track endpoints, onboarding wizard.
3. **Assessment** — AI client, `FakeAIClient`, generation, autosave, grading, results UI.
4. **Roadmap** — stream parser, SSE route, `sseFetch`, timeline viewer, progress toggles.
5. **Dashboard** — aggregate endpoint, dashboard page.
6. **Interview core** — setup, question generation, TTS/STT hooks, state machine, transcript.
7. **Proctoring** — MediaPipe pipeline, audio monitor, warning reducer, event API, overlays.
8. **Evaluation** — single-call evaluation, report page, history page.
9. **Polish** — animations, empty states, error/retry states, responsive pass, README.

---

## 15. Out of scope

Authentication, user roles, multi-user support, cloud deployment, Docker, CI/CD,
payments, Alembic migrations, and true speaker diarization.
