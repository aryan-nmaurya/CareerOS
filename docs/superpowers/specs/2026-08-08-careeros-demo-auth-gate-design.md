# CareerOS — Demo Sign-Up Gate + Sign-Out Reset Design

## 1. Scope

A cosmetic front door for the app, not real authentication. CareerOS remains
single-user (`models/user.py`'s `User` is explicitly documented as "the
single local user," not an account system) — this feature adds a gate in
front of it and a way to wipe it clean, nothing more:

- **Sign up** — one screen, shown before anything else including onboarding.
  A single fixed demo email/password, both pre-filled, so the whole
  interaction is one click. There is no real account creation and no second
  "Sign in" screen — the same screen is shown again after sign-out, since
  there's nothing that differs between a first visit and a later one.
- **Sign out** — a Settings action that deletes all app data (profile,
  tracks, roadmaps, assessments, interviews) and returns to the sign-up
  screen, so the next person sees a genuinely empty app.

**Explicitly not built:** real accounts, per-user data isolation, password
hashing/storage, backend session/token verification, or any protection
against someone bypassing the gate via devtools. The password is displayed
on the same screen as the field that accepts it, so a server-side check
would add an endpoint and a config value for zero real security benefit.
This is a demo convenience, confirmed with the user during design.

## 2. Flow & gating

`App.tsx` currently gates on one condition: no `profile` loaded → force
`/onboarding`. This adds a check in front of that one, using a plain
`localStorage` flag rather than a backend session:

```
not signed in           → only /signup is reachable
signed in, no profile   → only /onboarding is reachable   (existing, unchanged)
signed in, has profile  → normal app
```

Both checks use the same pattern already in `App.tsx`: redirect to the
required screen unless already on it. The sign-up check runs first, so an
unsigned-in visitor is bounced to `/signup` even if they try to deep-link
into `/onboarding` or anywhere else.

**Sign out** (Settings, behind a confirm dialog): deletes the backend's
single `User` row, clears the TanStack Query cache client-side so no stale
cached data (e.g. a cached dashboard response) flashes before the redirect,
clears the `localStorage` sign-in flag, and navigates to `/signup`.

## 3. Backend — one new endpoint

`DELETE /api/profile`, added to `routers/profile.py` and
`services/profile_service.py` alongside the existing `GET`/`POST`/`PATCH`.
It deletes the `User` row if one exists; if none exists (someone signs out
before ever finishing onboarding), it's a no-op rather than an error — sign
out must always succeed.

No manual per-table cleanup is needed. Every table in the schema already
cascades from `users` via `ondelete="CASCADE"`, confirmed by reading every
model file:

```
users
  └─(CASCADE)─ learning_tracks
                  ├─(CASCADE)─ roadmaps ─(CASCADE)─ roadmap_phases ─(CASCADE)─ roadmap_modules
                  ├─(CASCADE)─ assessments ─(CASCADE)─ assessment_questions
                  └─(CASCADE)─ interviews ─(CASCADE)─ interview_questions, proctoring_events
```

SQLite enforces this because `PRAGMA foreign_keys=ON` is already set
globally (`db/session.py`); Postgres enforces `ondelete="CASCADE"` natively.
Deleting and committing the one `User` row is sufficient.

This is a strictly bigger reset than the existing "Replay onboarding"
button in Settings (which only clears the active track and explicitly
keeps assessments/interviews). That button is untouched by this work — it
remains a lighter, separate reset useful mid-session; sign-out is the full
wipe.

## 4. Frontend

**New: `frontend/src/lib/demoAuth.ts`** — pure, no React. Holds the fixed
credential constants and the `localStorage` read/write, so `App.tsx`,
`SignUpPage.tsx`, and `SettingsPage.tsx` share one source of truth instead
of each duplicating a key string:

- `DEMO_EMAIL = "demo@careeros.app"`, `DEMO_PASSWORD = "CareerOS#2026"`
- `isSignedIn(): boolean` — reads the flag
- `signIn(): void` — writes it
- `signOut(): void` — clears it

**New: `frontend/src/pages/SignUpPage.tsx`** — both the email and password
fields are pre-filled with the real values (password field masked, as a
real password input would be); the actual password is also shown as plain
text underneath the field as a visible reference. One "Sign up" button —
since both fields already hold correct values, clicking it is enough. On
click: `signIn()`, navigate to `/`.

**Modify `App.tsx`** — add the `isSignedIn()` redirect in front of the
existing profile check, per section 2.

**Modify `frontend/src/services/api/profile.ts`** — add
`deleteProfile = () => api<null>("/api/profile", { method: "DELETE" })`,
matching the file's existing thin-wrapper style.

**Modify `frontend/src/hooks/useProfile.ts`** — add `useDeleteProfile()`, a
`useMutation` wrapping `deleteProfile`.

**Modify `frontend/src/pages/SettingsPage.tsx`** — new "Sign out" card.
Click calls the browser's native `window.confirm("This deletes all data
and signs out. Continue?")` — no custom dialog component exists anywhere
in this codebase yet, and building one for this single confirmation would
be exactly the kind of infrastructure this project avoids adding ahead of
need. If confirmed, runs the delete mutation; its `onSuccess` calls
`queryClient.clear()`, then `signOut()`, then `navigate("/signup")`. Its
`error` case renders the same inline pattern already used for
`updateProfile` a few lines above in this file (`<p className="text-sm
text-danger">`), so a failed delete leaves the user on Settings with a
visible message instead of silently doing nothing.

## 5. Testing

**`frontend/src/lib/__tests__/demoAuth.test.ts`** — pure, no DOM
rendering needed beyond a stubbed `localStorage` (already available in the
jsdom test environment this project uses everywhere else): `isSignedIn()`
is `false` before any call, `true` after `signIn()`, `false` again after
`signOut()`.

**Backend** — extend `backend/tests/test_profile_service.py` with a
cascade-delete test: create a user, a track, an assessment (with at least
one question), an interview (with at least one question and one
proctoring event), call the new delete function, and assert every row
across every table is gone. Extend `backend/tests/test_api_smoke.py` with
`DELETE /api/profile` returning 204 both when a profile exists and when it
doesn't (the no-op case).

**Live E2E** — the gating order in `App.tsx` (signup → onboarding →
app) and the full sign-up → use the app → sign-out → back-to-signup loop
are best confirmed by actually driving the app in a browser, matching how
every other page-level flow in this project has been verified. No camera
or microphone involved, so this one has no verification gaps to flag.
