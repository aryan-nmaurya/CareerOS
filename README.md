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
