# CareerOS

An AI Career Mentor: personalized learning roadmaps, skill assessments, and
AI-proctored mock interviews with evaluation reports. University mini project.

**Stack:** React 19 + TypeScript + Vite + Tailwind v4 · FastAPI + SQLAlchemy +
SQLite · Google Gemma 4 31B · MediaPipe Tasks Vision (in-browser proctoring) · Web
Speech API · Web Audio API.

## What it does

CareerOS starts with a learner profile and a topic/experience level. Google
Gemma 4 31B generates an assessment for intermediate and advanced learners, grades the
answers, and uses the resulting strengths and weaknesses to create a phased
learning roadmap. Learners can complete modules, monitor progress, and start a
roadmap-aware mock interview.

During an interview, the browser reads questions aloud and transcribes spoken
answers. MediaPipe Face Landmarker checks the local camera feed for one visible
face, looking away, and multiple faces; Web Audio monitors energy-based noise
signals. Proctoring warnings are sent to the backend, which is authoritative
about severity and termination. Once all questions are answered, one Gemma 4 31B
evaluation call scores the full interview and produces the report shown under
History.

The browser-side MediaPipe assets are vendored in `frontend/public/models` and
`frontend/public/wasm`, so camera frames do not need to leave the device.

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
