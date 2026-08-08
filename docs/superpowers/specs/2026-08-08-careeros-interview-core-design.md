# CareerOS — Interview Core + Speech (Plan 4) Design

**Scope note:** this is a focused design for Plan 4 of the CareerOS series. It
extends and makes concrete the interview-related sections of the master spec
(`docs/superpowers/specs/2026-08-07-careeros-design.md`, sections 5, 7, 8, 10,
14) rather than replacing them. Where this doc is silent, the master spec's
decisions (tech stack, DB conventions, testing philosophy, AI client
patterns) apply unchanged.

## 1. Scope

Matches the master spec's build-order stage 6, "Interview core," exactly:
setup, AI question generation, the speech-driven Q&A loop, transcript
capture. Explicitly **out of scope**, per the master spec's own stage 7/8
split:

- Proctoring (camera, MediaPipe, audio monitoring, warnings) — Plan 5.
- AI evaluation (scoring, feedback, the report) — Plan 5.
- `proctoring_events` table, `/api/interviews/{id}/events`, the
  proctoring-driven `/terminate` endpoint — Plan 5.

**One addition beyond the master spec, decided during this plan's
brainstorming:** a minimal manual-abandon action. The master spec's only path
to `terminated` is proctoring-driven (3-strike warnings, `multiple_faces`
fatal), which doesn't exist yet in Plan 4. Without some way to stop early, an
abandoned interview would sit `active` forever with no path to a normal
state. A learner can end an interview early at any point after it starts;
this sets `status = "terminated"`, `termination_reason = "user_quit"`,
`ended_at` = now, and returns to the dashboard. No warning system, no
severity classification — just basic UX hygiene.

Every score-bearing column the master spec's `interviews`/`interview_questions`
tables define (`overall_score`, `technical_score`, `communication_score`,
`confidence_score`, `strengths`, `weaknesses`, `recommendations`, `summary`,
and per-question `technical_score`/`communication_score`/`confidence_score`/
`missing_concepts`/`better_answer`/`feedback`) stays `NULL` after Plan 4.
Plan 5 populates them; the tables and models don't change shape then, only
which columns are ever written to.

## 2. Backend

### Models — `models/interview.py`

`Interview`: `id`, `track_id` FK (`CASCADE`), `level`, `question_count`
(5|8|10), `status` (`setup|active|completed|terminated`), `started_at`,
`ended_at` nullable, `termination_reason` nullable, `warning_count` int
default 0 (column exists per the master schema; stays 0 until Plan 5), plus
the nullable score/strengths/weaknesses/recommendations/summary columns
(all `NULL` in Plan 4).

`InterviewQuestion`: `id`, `interview_id` FK (`CASCADE`), `order_index`,
`question`, `expected_points` JSON, `transcript` text nullable,
`answer_duration_s` int nullable, plus the nullable per-question score
columns (`NULL` in Plan 4).

`ProctoringEvent` is *not* created in Plan 4 — it's added to this same file
in Plan 5, matching how `models/roadmap.py` grew across Plan 3's tasks.

### Prompt — `ai/prompts/interview.py`

`build_interview_prompt(topic: str, level: str, count: int, roadmap_context: list[str] | None) -> Prompt`.
Same `Prompt`/`response_schema` pattern as `prompts/assessment.py` and
`prompts/roadmap.py` — a pure function, no client. Returns `count` questions
(schema-bounded to exactly `count` via `min_items`/`max_items` both set to
`count`), each `{question: str, expected_points: list[str]}`. Every property
in every nested schema object lists itself in that object's own `required`
array (the exhaustive-required pattern confirmed the hard way in Plan 3 —
see that plan's Task 4 note). `roadmap_context` is a flat list of module
titles (completed + current-phase, when a roadmap exists) folded into the
prompt text — this is what "roadmap-aware" means per the master spec; no
schema change, just richer prompt content when the caller has it.

### Service — `services/interview_service.py`

- `start_interview(db, ai_client, track_id, level, question_count) -> Interview`
  — resolves the track, resolves its roadmap if one exists (module titles
  for context), builds the prompt, generates, persists `Interview` +
  `InterviewQuestion` rows, `status="active"`, `started_at=now`. Goes
  straight to `"active"`, not the schema's reserved `"setup"` value — level
  and question count are chosen client-side, before this call, on
  `InterviewSetupPage` (plain local state, no DB row yet, same shape as
  onboarding's level step choosing a level before `createTrack` exists).
  Once this call succeeds the interview simply *is* active; there's no
  meaningful gap between "creating" and "active" for a synchronous
  `generate_json` call. `"setup"` stays a real, unused-in-Plan-4 value in
  the enum, not a dead one — Plan 5 or later can use it if async generation
  ever needs a real pending phase. Beginner tracks are **not** blocked here
  — unlike assessments, interviews make sense at any declared level per the
  master spec ("N questions at the requested difficulty").
- `get_interview(db, interview_id) -> Interview`
- `list_interviews(db, limit: int) -> list[Interview]` — most-recent-first,
  `id` tiebreak (matching `started_at.desc(), id.desc()`). Used internally by
  `dashboard_service` (below) in Plan 4; **not** exposed as its own
  `GET /api/interviews` route yet — the master spec's build order stages the
  history *page* under "8. Evaluation," and a page listing interviews with
  no scores isn't worth a dedicated route and page yet. Plan 5 adds the
  route once there's something worth paginating through.
- `record_answer(db, interview_id, question_id, transcript, duration_s) -> None`
  — writes transcript + duration onto the question row. No status change,
  no validation beyond "question belongs to this interview."
- `complete_interview(db, interview_id) -> Interview` — sets
  `status="completed"`, `ended_at=now`. No scoring, no validation that every
  question has a transcript (an expired timer can legitimately leave one
  empty — that's a valid, if weak, answer, not an error). This is what
  `/submit` calls in Plan 4; Plan 5 is expected to extend this same function
  with the evaluation call rather than replace it.
- `quit_interview(db, interview_id) -> Interview` — sets
  `status="terminated"`, `termination_reason="user_quit"`, `ended_at=now`.
  Idempotent-safe to call on an already-terminated/completed interview? No —
  raises if the interview isn't `active` (can't quit a `completed` one),
  mirroring `AssessmentAlreadySubmittedError`'s shape.

### Dashboard integration — `services/dashboard_service.py`

`recent_interviews` has been hardcoded to `[]` since Plan 3 with a comment
saying Plan 4 would populate it. It does: `get_dashboard` calls
`interview_service.list_interviews(db, limit=3)` for the active track and
maps each to a small `RecentInterviewOut` (topic comes from the track,
`level`, `status`, `started_at` — no score fields, since none exist yet).
`schemas/dashboard.py` gains that type; `DashboardOut.recent_interviews`
changes from `list = []` to `list[RecentInterviewOut]`.

### Router — `routers/interview.py`

The master spec's endpoint list, Plan-4 subset (no `GET /api/interviews` —
see `list_interviews` above), plus the one addition:

```
POST   /api/tracks/{id}/interviews       {level, question_count} → Interview + questions
GET    /api/interviews/{id}              → Interview + questions
POST   /api/interviews/{id}/questions/{qid}/answer  {transcript, duration_s} → 204
POST   /api/interviews/{id}/submit       → Interview (completed, unscored)
POST   /api/interviews/{id}/quit         → Interview (terminated, reason=user_quit)   ← new
```

`expected_points` and the per-question score columns follow the same
reveal-gating precedent as assessments: an explicit `to_interview_out`
builder, not bare `model_validate`. Unlike assessment's MCQ answer key
though, there's nothing to withhold here in Plan 4 — `expected_points` is
visible immediately (it's not a "correct answer" the learner could game,
it's grading criteria for content nobody's scoring yet). Worth a one-line
comment noting the deliberate difference from assessment's pattern, so it
doesn't read as an oversight.

## 3. Frontend

### State machine — `hooks/useInterviewMachine.ts`

Pure transition function, hand-rolled (not a library — this is a short
linear loop with one branch, not enough state-chart complexity to justify
XState as a new dependency), wrapped in a thin `useReducer`. States:
`briefing | speaking | answering | review`. No `idle` state — by the time
`InterviewActivePage` mounts the machine, `start_interview` has already run
(on the separate `InterviewSetupPage`) and a real, loaded interview exists;
the machine only owns the parts of the flow that happen *after* creation.
`preflight` and `evaluating`/`report` are Plan 5 states, not built here.

| From | Event | To | Notes |
|---|---|---|---|
| *(mount)* | — | `briefing` | initial state once the interview + questions have loaded |
| `briefing` | `BEGIN` | `speaking` | user clicks "I'm ready"; first `speak()` call happens here, inside the click handler, so it's gesture-adjacent even though live testing showed `speak()` works without one |
| `speaking` | `TTS_DONE` | `answering` | fires from `speak()`'s `onEnd`, or immediately if TTS unsupported |
| `answering` | `ANSWER_ADVANCE` | `speaking` (next question) or `review` (was last question) | fires on manual "next" or timer expiry; always persists whatever transcript exists via `record_answer` first |
| `briefing`/`speaking`/`answering` | `QUIT` | *(not a rendered state)* | calls `quit_interview`, navigates to dashboard immediately — no "terminated" screen to build in Plan 4 |

`review` renders the raw Q&A transcript (question + what was said, no
scores) and calls `complete_interview` on entry.

### Speech hooks

`useSpeechSynthesis()` — `speak(text, onEnd)`, `cancel()`, `supported`.
`useSpeechRecognition()` — `start()`, `stop()`, `transcript`, `listening`,
`supported`.

**Live-verified in this session**, in the actual browser tool available for
later E2E work (not assumed from documentation):
- `speechSynthesis.speak()` on a real `SpeechSynthesisUtterance` correctly
  fired `onstart` at 27ms and `onend` at 1875ms for a short test phrase —
  full round trip confirmed, including the `onEnd` callback the state
  machine's `speaking → answering` transition depends on.
- `new (SpeechRecognition || webkitSpeechRecognition)().start()` returns
  without throwing synchronously, matching the spec's assumption that it's
  safe to call directly. But a synchronous non-throw is **not** confirmation
  recognition is working: in this sandboxed browser (no real microphone
  available — confirmed explicitly by the tool itself), `start()` led to
  `onerror` firing with `error: "not-allowed"` at 12ms, followed by `onend`
  at 13ms. `"not-allowed"` is the same standard error code a real user
  declining microphone permission would produce, not a sandbox-specific
  quirk — so this is genuine, reusable information: `useSpeechRecognition`
  must treat `onerror` (any code, but especially `not-allowed` and
  `audio-capture`) as the signal to report `supported: false` for the rest
  of the session and let the caller fall back, rather than trusting
  `start()`'s clean return as sufficient.
- **Still unverifiable in this environment, flagged honestly rather than
  guessed at:** actual speech-to-text transcription of real audio. The
  sandboxed browser cannot grant microphone access at all. Building this
  correctly (continuous + interimResults, hard-stopped during TTS,
  `onresult` feeding a live transcript) is Plan 4's job; confirming a real
  human's voice actually transcribes needs a real Chrome tab with mic
  access, done by a person, same boundary the master spec already draws
  around proctoring's webcam requirement.

**Fallback, per the master spec:** when `!ttsSupported`, `speaking` shows the
question text immediately with a manual "I'm ready to answer" advance
instead of waiting for `onEnd`. When `!sttSupported` (including the
runtime-discovered "unsupported" via `onerror`, not just a missing global),
`answering` renders a plain textarea instead of the live transcript panel.

### Pages/components

`pages/InterviewSetupPage.tsx` (level defaults to the active track's
assessed level if an assessment exists, else its declared level;
question_count defaults to 8; both overridable — same default-plus-override
shape as onboarding's level step), `pages/InterviewActivePage.tsx` (renders
whichever of briefing/speaking/answering/review the machine is in),
`components/interview/{SetupForm,QuestionStage,TranscriptPanel}.tsx`.
`InterviewReport.tsx` and any proctoring-related component
(`PreflightCheck`, `CameraPip`) are Plan 5.

## 4. Testing

Backend: `test_interview_service.py` against `FakeAIClient` — generation
persists questions, roadmap-aware prompt content (mirrors assessment's
`fake_ai.calls[0].user_content` assertion pattern), `record_answer` writes
transcript/duration without touching status, `complete_interview` sets
completed regardless of blank transcripts, `quit_interview` sets terminated
with the right reason and rejects a second call. `test_interview_api.py`
mirrors `test_assessment_api.py`'s router-level conventions.

Frontend: `transition()` is pure and gets direct unit tests covering the
table in section 3 — same pattern as `lib/progress.ts`. The speech hooks
are not unit-tested (jsdom has no `SpeechSynthesis`/`SpeechRecognition`
globals at all) — verified instead by the live browser checks above plus a
manual real-browser pass, consistent with the master spec's existing
"presentational, verified by build + manual check" carve-out.
