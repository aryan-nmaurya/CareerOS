# CareerOS — Proctoring + Evaluation + Polish (Plan 5) Design

**Scope note:** this is a focused design for Plan 5, the final plan in the
CareerOS series. It extends and makes concrete the proctoring/evaluation
sections of the master spec (`docs/superpowers/specs/2026-08-07-careeros-design.md`,
sections 6, 7, 8, 9, 10, 11, 12, 14) rather than replacing them. Where this
doc is silent, the master spec's decisions apply unchanged.

## 1. Scope

One plan, per the master spec's original series (confirmed during this
plan's brainstorming rather than re-split), sequenced internally as three
phases matching the master spec's own build-order stages 7-9. Each phase
leaves the app runnable before the next starts:

1. **Proctoring** — `preflight` FSM state, MediaPipe video pipeline, audio
   monitoring, warning escalation, the `/events` endpoint, the
   `proctoring_events` table.
2. **Evaluation** — the real (AI-calling) `complete_interview`,
   `evaluating`/`report` FSM states, the report page, a unified history page
   covering both interviews and assessments.
3. **Polish** — animations, empty/error/retry states, responsive pass,
   README.

**A known, deliberate divergence from the master spec's page table, carried
over from Plan 4 and not worth correcting now:** the spec lists
`/interview/:id/active`; Plan 4 built `/interview/:id`. Same for
`/dashboard` vs. the actual `/`. Both are cosmetic URL differences with zero
functional impact — renaming now is pure churn against working, tested
routes. Noted here so it doesn't read as an oversight when this doc's own
route references use the real, already-built paths.

## 2. Phase 1 — Proctoring

### FSM changes — `hooks/useInterviewMachine.ts`, `lib/interviewMachine.ts`

Adds `preflight` before `briefing`: verifies camera + microphone permission,
confirms exactly one face is visible, calibrates the audio noise floor
(3-second sample) before the interview can start.

Also **changes** how termination works, not just adds to it. Plan 4's quit
is an action, not a state — clicking "End interview" calls the API and
navigates away immediately, with no rendered "terminated" screen. Proctoring
termination needs a real screen (the escalation UI ending in
"Interview Terminated," per the master spec), and having two different
mechanisms for reaching the same end state — one that navigates away
silently, one that renders — would be a real inconsistency. Phase 1
unifies them: `terminated` becomes a real state in `MachinePhase`
(`briefing | preflight | speaking | answering | review | terminated`),
reachable from `preflight`/`briefing`/`speaking`/`answering` via either a
`QUIT` event (manual, `termination_reason="user_quit"`) or a proctoring
event that crosses the fatal/3-warning threshold
(`termination_reason="proctoring"`). The rendered screen reads
`termination_reason` to decide what to show — a plain "you left" message
for `user_quit`, the fuller warning-history / "Interview Terminated"
treatment for `proctoring`.

### Video — `hooks/useProctoring.ts`, `lib/proctorRules.ts`

`@mediapipe/tasks-vision` `FaceLandmarker`, `VIDEO` running mode,
`numFaces: 2` (need to detect *two* to flag `multiple_faces`, not just miss
past one), `outputFacialTransformationMatrixes: true`, GPU delegate with CPU
fallback. The `.task` model and WASM fileset are vendored into `public/` per
the spec — real files from an external source, downloaded only with
explicit permission at the point Phase 1 actually needs them, filename/
source/size stated at that time. Detection runs in a `requestAnimationFrame`
loop throttled to 10fps.

`lib/proctorRules.ts` is pure — no I/O, no MediaPipe import, just math and
threshold logic against inputs the hook feeds it:

```
pitch = atan2(d[6],  d[10])
yaw   = atan2(-d[2], hypot(d[6], d[10]))
roll  = atan2(d[1],  d[0])
```

| Signal | Condition | Sustain | Action |
|---|---|---|---|
| `looking_away` | `abs(yaw) > 25°` or `pitch < -20°` | 2.5s | +1 warning, 10s cooldown |
| `no_face` | `faceCount == 0` | 4s | +1 warning, 10s cooldown |
| `multiple_faces` | `faceCount >= 2` | 1.5s | fatal — terminate immediately |

Every rule is sustain-debounced against real elapsed time (not frame count,
since frame rate isn't guaranteed) — a single bad frame from a blink or a
glance at the keyboard must not fire a warning.

### Audio — `hooks/useAudioMonitor.ts`

Web Audio `AnalyserNode` on the mic stream, RMS sampled at 20Hz, noise floor
calibrated during `preflight`.

| Signal | Condition | Sustain | Action |
|---|---|---|---|
| `excessive_noise` | RMS > floor + 18dB while not the active speaker | 3s | +1 warning |
| `background_voice` | speech-band energy present while STT reports no user speech | 3s | +1 warning |

Documented honestly, per the master spec, as energy heuristics against a
calibrated floor — not real speaker diarization, which isn't achievable
in-browser at this project's scope.

### Escalation — `hooks/useWarnings.ts`

One reducer both `useProctoring` and `useAudioMonitor` dispatch into, so
counts can't drift between video and audio signals. Each event POSTs to
`POST /api/interviews/{id}/events {type, detail}` →
`{warning_count, should_terminate}`. **The backend is authoritative**:
severity classification (`warning` vs `fatal`) and the termination decision
both happen server-side, and the frontend reconciles its local count against
the response rather than deciding for itself — a tampered client can't
downgrade a `fatal` event to a mere warning. Three accumulated warnings
terminates; any single `fatal` event terminates on its first occurrence,
independent of the warning count.

UI: `Warning 1 of 3` → `Warning 2 of 3` → `Final Warning` (the 3rd,
terminating warning's own label — not a 4th separate step) →
`Interview Terminated`, a Framer Motion overlay with a shake transition.

### Backend — `models/interview.py` (+`ProctoringEvent`), `services/interview_service.py`, `routers/interview.py`

`ProctoringEvent`: `id`, `interview_id` FK, `question_id` FK nullable,
`created_at`, `type` (the 5 signal names above), `severity`
(`warning`|`fatal`), `detail` text, `warning_index` int nullable — added to
`models/interview.py` alongside `Interview`/`InterviewQuestion`, matching
how `models/roadmap.py` grew across Plan 3's tasks and how this file's own
docstring already anticipated Plan 5 adding `ProctoringEvent` here.

`record_event(db, interview_id, event_type, detail) -> EventResult`:
classifies severity from `event_type` (fatal for `multiple_faces`, warning
for the other four), persists the `ProctoringEvent`, increments
`Interview.warning_count` for `warning`-severity events, and sets
`status="terminated"` + `termination_reason="proctoring"` when either a
`fatal` event lands or `warning_count` reaches 3. Returns
`(warning_count, should_terminate)` for the router to serialize.

`warning_index` is `Interview.warning_count`'s value *after* incrementing,
written onto that specific event row (a `warning`-severity event that
brought the count from 1 to 2 stores `warning_index=2`) — it's what lets a
future audit or report say "this was warning 2 of 3" per event rather than
only knowing the interview's final tally. `fatal` events never increment
`warning_count`, so they always store `warning_index=NULL`.

`POST /api/interviews/{interview_id}/events` — new endpoint, the one the
master spec's API table already lists and Plan 4 deliberately left out.

## 3. Phase 2 — Evaluation

### Prompt — `ai/prompts/evaluation.py`

`build_evaluation_prompt(topic, level, items) -> Prompt` where `items` is
`list[(question, expected_points, transcript, answer_duration_s)]`. One call
for the whole interview, matching the master spec's explicit reasoning: cheaper
than per-question calls, and it lets the model judge consistency across
answers rather than scoring each in isolation. For each item the prompt
includes the transcript, `answer_duration_s`, and a word count computed from
the transcript (`len(transcript.split())`) — confidence scoring is grounded
in real pacing/filler signals the model reasons over, not invented. Response
schema pins the questions array to `len(items)`, every property
required (no nullable ambiguity — same reasoning as Plan 4's interview
prompt, nothing here is genuinely optional). Empty-transcript items are
still sent through the same batch; the prompt instructs the model to score
those 0 with "not answered" feedback rather than the code special-casing
them, matching the master spec's description of this behavior as the
model's job.

Returns per-question `technical_score`/`communication_score`/
`confidence_score` (0-10 each), `missing_concepts`, `better_answer`,
`feedback`, plus interview-level `overall_score`/`technical_score`/
`communication_score`/`confidence_score` (0-100 each), `strengths`,
`weaknesses`, `recommendations`, `summary`.

**Terminated interviews are never evaluated.** `complete_interview` — and
therefore the AI call — only fires from the `review` state's entry effect,
which is only reachable by answering the last question, not by
termination. A `terminated` interview (either reason) simply stays
unscored; the history/report views show it as terminated, not as a
completed-with-a-score result. Evaluating a proctoring-flagged or
voluntarily-abandoned interview wouldn't produce a meaningful score anyway,
so this isn't a gap to fill later — it's the intended behavior.

### Service — `services/interview_service.py`

`complete_interview` (built in Plan 4 as a pure status flip, no scoring)
gains the AI call: builds the evaluation prompt from the interview's
questions, calls `ai_client.generate_json`, writes every returned score
field onto the `Interview` and its `InterviewQuestion` rows, *then* sets
`status="completed"`. Same function Plan 4 built, extended rather than
replaced — exactly what Plan 4's own note anticipated. Needs `ai_client:
AIClient` added to its signature (currently `complete_interview(db,
interview_id)`; becomes `complete_interview(db, ai_client, interview_id)`),
which means `routers/interview.py`'s `/submit` endpoint gains the
`ai_client` dependency it didn't need before.

### History — `services/interview_service.py`, `routers/interview.py`

The `list_interviews` function Plan 4 built (used internally by
`dashboard_service`, deliberately not exposed as a route) finally gets its
route: `GET /api/interviews`, the one entry the master spec's interview API
table has that Plan 4's design doc explicitly deferred to "whenever there's
something worth paginating through." There's something now.

### Frontend — report and history pages

`evaluating` and `report` FSM states (Plan 4 deliberately excluded both).
`pages/InterviewReportPage.tsx` at `/interview/:id/report`: overall scores,
per-question breakdown with missing concepts and better answers, strengths/
weaknesses/recommendations. `pages/HistoryPage.tsx` at `/history`: past
assessments (`GET /api/assessments`, already built in Plan 2, just not
wired to any frontend list view yet) and interviews (`GET /api/interviews`,
new above), each linking to its report/result view.

## 4. Phase 3 — Polish

Animations (the warning-escalation shake overlay from Phase 1, phase
transitions already using Framer Motion elsewhere getting the same
treatment here), empty states and error/retry states on any page still
missing them, a responsive pass, README updates reflecting the finished
app. Scoped at plan-writing time once Phases 1-2 are built and it's clear
what's actually missing — listing specific gaps now would be guessing.

## 5. Testing

Backend: `test_evaluation_prompts.py` (pure, mirrors
`test_interview_prompts.py`'s shape), `test_interview_service.py` additions
for the now-AI-calling `complete_interview` and for `record_event`
(warning accumulation, 3-strike termination, `multiple_faces` immediate
termination, events rejected once terminated — the master spec's own test
list for this file). `test_interview_api.py` additions for `/events` and
`GET /api/interviews`.

Frontend: `lib/proctorRules.test.ts` (matrixToEuler against known matrices,
yaw threshold, pitch threshold, sustain windows) and `hooks/useWarnings.test.ts`
(escalation 1→2→3, cooldown suppression, fatal bypass, backend
reconciliation) — both named explicitly in the master spec's own testing
section, both pure/reducer logic with no camera or microphone needed.

**Live verification, before the plan locks in:** this session's browser
tool cannot grant camera access, confirmed the same way microphone access
was confirmed blocked during Plan 4 — `getUserMedia` for video should fail
the same class of way STT's `start()` did (a real permission-denial error,
not a silent hang), and that needs confirming live before the plan assumes
it. Real face-tracking accuracy, like real speech transcription in Plan 4,
needs an actual device and is documented as that same honest gap rather
than guessed at.
