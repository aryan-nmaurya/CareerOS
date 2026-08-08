# CareerOS Demo Sign-Up Gate + Sign-Out Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a one-click demo sign-up gate shown before anything else in the app, and a sign-out action in Settings that wipes all data and returns to that gate.

**Architecture:** A `localStorage` flag (no backend session) gates the whole app in `App.tsx`, checked before the existing profile/onboarding check. Sign-out deletes the single `User` row backend-side, which cascades through every table via foreign keys already configured with `ondelete="CASCADE"` — no per-table cleanup code needed.

**Tech Stack:** FastAPI/SQLAlchemy (backend, existing), React 19 + TanStack Query + React Router (frontend, existing). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-08-careeros-demo-auth-gate-design.md`

---

## File Structure

**Backend** (`backend/`)

| File | Responsibility |
|---|---|
| `services/profile_service.py` | modified: `+delete_profile` |
| `routers/profile.py` | modified: `+DELETE /api/profile` |
| `tests/test_profile_service.py` | modified: `+delete_profile` cascade tests |
| `tests/test_api_smoke.py` | modified: `+DELETE /api/profile` tests |

**Frontend** (`frontend/src/`)

| File | Responsibility |
|---|---|
| `lib/demoAuth.ts` | pure: fixed demo credentials, `isSignedIn`/`signIn`/`signOut` over one `localStorage` key |
| `lib/__tests__/demoAuth.test.ts` | the above, directly tested |
| `pages/SignUpPage.tsx` | the one-click gate screen |
| `App.tsx` | modified: `+` signed-in gate, checked before the existing profile gate |
| `services/api/profile.ts` | modified: `+deleteProfile` |
| `hooks/useProfile.ts` | modified: `+useDeleteProfile` |
| `pages/SettingsPage.tsx` | modified: `+` Sign out card |

---

## Task 1: Backend — `DELETE /api/profile`

**Files:**
- Modify: `backend/services/profile_service.py`
- Modify: `backend/routers/profile.py`
- Test: `backend/tests/test_profile_service.py`
- Test: `backend/tests/test_api_smoke.py`

- [ ] **Step 1: Write the failing service tests**

Append to `backend/tests/test_profile_service.py`:

```python
from models.assessment import Assessment, AssessmentQuestion
from models.interview import Interview, InterviewQuestion, ProctoringEvent


def test_delete_profile_cascades_to_every_table(db_session):
    user = _onboard(db_session)
    track = profile_service.create_track(
        db_session, TrackCreate(topic="Python", experience_level="beginner")
    )

    assessment = Assessment(track_id=track.id, level="intermediate", status="in_progress")
    db_session.add(assessment)
    db_session.commit()
    db_session.add(
        AssessmentQuestion(
            assessment_id=assessment.id,
            order_index=0,
            type="mcq",
            topic_tag="loops",
            question="What does `range(3)` produce?",
            options=["0,1,2", "1,2,3", "0,1,2,3", "1,2"],
            correct_option=0,
        )
    )

    interview = Interview(
        track_id=track.id, level="intermediate", question_count=5, status="active"
    )
    db_session.add(interview)
    db_session.commit()
    db_session.add(
        InterviewQuestion(
            interview_id=interview.id,
            order_index=0,
            question="Explain the GIL.",
            expected_points=["single lock"],
        )
    )
    db_session.add(
        ProctoringEvent(
            interview_id=interview.id,
            type="looking_away",
            severity="warning",
            detail="yaw 30deg",
            warning_index=1,
        )
    )
    db_session.commit()

    profile_service.delete_profile(db_session)

    assert db_session.get(User, user.id) is None
    assert db_session.get(LearningTrack, track.id) is None
    assert db_session.get(Assessment, assessment.id) is None
    assert db_session.query(AssessmentQuestion).count() == 0
    assert db_session.get(Interview, interview.id) is None
    assert db_session.query(InterviewQuestion).count() == 0
    assert db_session.query(ProctoringEvent).count() == 0


def test_delete_profile_when_none_exists_is_a_noop(db_session):
    profile_service.delete_profile(db_session)  # must not raise

    assert profile_service.get_profile(db_session) is None
```

`_onboard` is the helper already defined in this file (creates a profile
and returns the `User`); `TrackCreate` is already imported here too, used
by the existing track-lifecycle tests further down the file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_profile_service.py -k delete_profile -v`
Expected: FAIL — `AttributeError: module 'services.profile_service' has no attribute 'delete_profile'`

- [ ] **Step 3: Add `delete_profile` to `backend/services/profile_service.py`**

Append at the end of the file:

```python
def delete_profile(db: Session) -> None:
    """Deletes the single user row, if one exists. Every other table cascades
    from it (ondelete="CASCADE" on every FK down the chain), so nothing else
    needs deleting explicitly. A no-op when there's no profile yet — sign-out
    must always succeed, including before onboarding ever finished."""
    user = get_profile(db)
    if user is None:
        return
    db.delete(user)
    db.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_profile_service.py -k delete_profile -v`
Expected: PASS — `2 passed`

- [ ] **Step 5: Write the failing API tests**

Append to `backend/tests/test_api_smoke.py`:

```python
def test_delete_profile_removes_it(client):
    client.post("/api/profile", json={"name": "Aryan"})

    response = client.delete("/api/profile")

    assert response.status_code == 204
    assert client.get("/api/profile").status_code == 204


def test_delete_profile_when_none_exists_still_returns_204(client):
    response = client.delete("/api/profile")

    assert response.status_code == 204
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_api_smoke.py -k delete_profile -v`
Expected: FAIL — `405 Method Not Allowed` (no DELETE route yet)

- [ ] **Step 7: Add the route to `backend/routers/profile.py`**

Append at the end of the file:

```python
@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(db: Session = Depends(get_db)):
    profile_service.delete_profile(db)
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_profile_service.py tests/test_api_smoke.py -v`
Expected: PASS, all green

- [ ] **Step 9: Commit**

```bash
git add backend/services/profile_service.py backend/routers/profile.py backend/tests/test_profile_service.py backend/tests/test_api_smoke.py
git commit -m "feat(backend): add DELETE /api/profile, cascades to every table"
```

---

## Task 2: `lib/demoAuth.ts`

**Files:**
- Create: `frontend/src/lib/demoAuth.ts`
- Test: `frontend/src/lib/__tests__/demoAuth.test.ts`

Pure — no React, no network. `App.tsx`, `SignUpPage.tsx`, and
`SettingsPage.tsx` will all import from here rather than each touching
`localStorage` directly.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/lib/__tests__/demoAuth.test.ts`:

```typescript
import { beforeEach, describe, expect, it } from "vitest";

import { isSignedIn, signIn, signOut } from "@/lib/demoAuth";

describe("demoAuth", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("is not signed in before signIn is called", () => {
    expect(isSignedIn()).toBe(false);
  });

  it("is signed in after signIn", () => {
    signIn();
    expect(isSignedIn()).toBe(true);
  });

  it("is not signed in after signOut", () => {
    signIn();
    signOut();
    expect(isSignedIn()).toBe(false);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/lib/__tests__/demoAuth.test.ts`
Expected: FAIL — `Cannot find module '@/lib/demoAuth'`

- [ ] **Step 3: Write `frontend/src/lib/demoAuth.ts`**

```typescript
const SIGNED_IN_KEY = "careeros_signed_in";

export const DEMO_EMAIL = "demo@careeros.app";
export const DEMO_PASSWORD = "CareerOS#2026";

export function isSignedIn(): boolean {
  return localStorage.getItem(SIGNED_IN_KEY) === "true";
}

export function signIn(): void {
  localStorage.setItem(SIGNED_IN_KEY, "true");
}

export function signOut(): void {
  localStorage.removeItem(SIGNED_IN_KEY);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/lib/__tests__/demoAuth.test.ts`
Expected: PASS — `3 passed`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/demoAuth.ts frontend/src/lib/__tests__/demoAuth.test.ts
git commit -m "feat(frontend): add demo auth gate helpers"
```

---

## Task 3: `SignUpPage.tsx` + `App.tsx` gating

**Files:**
- Create: `frontend/src/pages/SignUpPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write `frontend/src/pages/SignUpPage.tsx`**

```tsx
import { useNavigate } from "react-router-dom";

import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { DEMO_EMAIL, DEMO_PASSWORD, signIn } from "@/lib/demoAuth";

export default function SignUpPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-dvh bg-bg">
      <div className="mx-auto flex w-full max-w-sm flex-col gap-10 px-5 py-16">
        <div className="flex items-center justify-between">
          <span className="text-lg font-semibold tracking-tight">
            Career<span className="text-accent">OS</span>
          </span>
          <ThemeToggle />
        </div>

        <Card className="space-y-4">
          <CardTitle>Sign up</CardTitle>
          <CardDescription>
            This is a demo build — use the pre-filled demo account below.
          </CardDescription>

          <div className="space-y-3">
            <div>
              <label
                className="mb-1.5 block text-xs font-medium text-text-secondary"
                htmlFor="signup-email"
              >
                Email
              </label>
              <Input id="signup-email" type="email" value={DEMO_EMAIL} readOnly />
            </div>
            <div>
              <label
                className="mb-1.5 block text-xs font-medium text-text-secondary"
                htmlFor="signup-password"
              >
                Password
              </label>
              <Input id="signup-password" type="password" value={DEMO_PASSWORD} readOnly />
              <p className="mt-1.5 text-xs text-text-muted">Demo password: {DEMO_PASSWORD}</p>
            </div>
          </div>

          <Button
            className="w-full"
            onClick={() => {
              signIn();
              navigate("/");
            }}
          >
            Sign up
          </Button>
        </Card>
      </div>
    </div>
  );
}
```

Both fields are `readOnly` — the button signs in unconditionally regardless
of field contents (there's nothing to validate against, per the design),
so leaving them editable would misleadingly suggest otherwise.

- [ ] **Step 2: Replace `frontend/src/App.tsx` entirely**

```tsx
import { Loader2 } from "lucide-react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { useProfile } from "@/hooks/useProfile";
import { isSignedIn } from "@/lib/demoAuth";
import AssessmentPage from "@/pages/AssessmentPage";
import DashboardPage from "@/pages/DashboardPage";
import InterviewActivePage from "@/pages/InterviewActivePage";
import InterviewSetupPage from "@/pages/InterviewSetupPage";
import InterviewReportPage from "@/pages/InterviewReportPage";
import HistoryPage from "@/pages/HistoryPage";
import OnboardingPage from "@/pages/OnboardingPage";
import RoadmapPage from "@/pages/RoadmapPage";
import SettingsPage from "@/pages/SettingsPage";
import SignUpPage from "@/pages/SignUpPage";

export default function App() {
  const { data: profile, isPending } = useProfile();
  const location = useLocation();

  // Not signed in means the demo gate is the only reachable screen. This
  // check runs before useProfile's isPending, deliberately — someone who
  // isn't signed in shouldn't wait on (or care about) a profile fetch at
  // all before seeing the gate.
  if (!isSignedIn()) {
    if (location.pathname !== "/signup") return <Navigate to="/signup" replace />;
    return <SignUpPage />;
  }

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
      <Route path="/interview/:id/report" element={<InterviewReportPage />} />
      <Route path="/history" element={<HistoryPage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
```

`/signup` is deliberately **not** one of the `<Route>` entries below — it's
handled entirely by the early-return above. Once signed in, hitting
`/signup` (e.g. via the back button) falls through to the final catch-all
route and bounces to `/`, the same way any other unrecognized path does —
adding a matching `<Route>` here would instead let a signed-in visitor see
the gate screen again, which isn't the intent.

- [ ] **Step 3: Typecheck and build**

Run: `cd frontend && npx tsc -b --noEmit && npm run build`
Expected: both clean

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/SignUpPage.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add sign-up gate screen and wire it in front of the app"
```

---

## Task 4: Sign-out — delete wiring + Settings card

**Files:**
- Modify: `frontend/src/services/api/profile.ts`
- Modify: `frontend/src/hooks/useProfile.ts`
- Modify: `frontend/src/pages/SettingsPage.tsx`

No new test file — these are thin API/mutation/UI wiring, the same
untested-wrapper category as `useCreateProfile`/`useUpdateProfile` already
in this codebase. Covered by Task 5's live E2E pass instead.

- [ ] **Step 1: Add `deleteProfile` to `frontend/src/services/api/profile.ts`**

Append:

```typescript
export const deleteProfile = () => api<null>("/api/profile", { method: "DELETE" });
```

- [ ] **Step 2: Add `useDeleteProfile` to `frontend/src/hooks/useProfile.ts`**

Add `deleteProfile` to the existing import from `@/services/api/profile`
(currently `createProfile, createTrack, getProfile, listTracks,
updateProfile` — add `deleteProfile` to that list), then append:

```typescript
export function useDeleteProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteProfile,
    onSuccess: () => queryClient.clear(),
  });
}
```

`queryClient.clear()` wipes every cached query, not just profile — the
point is that nothing stale (a cached dashboard response, roadmap, etc.)
can flash on screen after the underlying data is gone. Clearing the
`localStorage` flag and navigating are handled by the caller in Task 4
Step 3, not here — those are routing concerns, not cache concerns, and
every other mutation hook in this file keeps that same separation.

- [ ] **Step 3: Replace `frontend/src/pages/SettingsPage.tsx` entirely**

```tsx
import { LogOut } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useDeleteProfile, useProfile, useUpdateProfile } from "@/hooks/useProfile";
import { signOut } from "@/lib/demoAuth";

export default function SettingsPage() {
  const navigate = useNavigate();
  const { data: profile } = useProfile();
  const updateProfile = useUpdateProfile();
  const deleteProfile = useDeleteProfile();
  const [name, setName] = useState("");

  useEffect(() => {
    if (profile) setName(profile.name);
  }, [profile]);

  const trimmed = name.trim();
  const dirty = Boolean(trimmed) && trimmed !== profile?.name;

  const handleSignOut = () => {
    if (!window.confirm("This deletes all data and signs out. Continue?")) return;
    deleteProfile.mutate(undefined, {
      onSuccess: () => {
        signOut();
        navigate("/signup");
      },
    });
  };

  return (
    <AppShell>
      <TopBar title="Settings" subtitle="Your profile and appearance." />

      <Card className="max-w-md">
        <CardTitle>Your name</CardTitle>
        <CardDescription className="mt-1">
          Used across your dashboard and reports.
        </CardDescription>

        <div className="mt-4 flex gap-2">
          <Input
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={120}
            aria-label="Your name"
          />
          <Button
            disabled={!dirty || updateProfile.isPending}
            onClick={() => updateProfile.mutate({ name: trimmed })}
          >
            Save
          </Button>
        </div>
        {updateProfile.error && <p className="mt-3 text-sm text-danger">{updateProfile.error instanceof Error ? updateProfile.error.message : "Could not save your profile."}</p>}
      </Card>

      <Card className="mt-4 max-w-md">
        <CardTitle>Classroom demo</CardTitle>
        <CardDescription className="mt-1">
          Replay onboarding from the beginning and create a fresh active learning track. Existing
          assessments and interviews stay in History.
        </CardDescription>
        <Button
          className="mt-4"
          variant="secondary"
          onClick={() => navigate("/onboarding?replay=1")}
        >
          Replay onboarding
        </Button>
      </Card>

      <Card className="mt-4 max-w-md">
        <CardTitle>Sign out</CardTitle>
        <CardDescription className="mt-1">
          Deletes your profile, tracks, roadmap, assessments, and interviews, and returns to the
          sign-up screen.
        </CardDescription>
        <Button className="mt-4" variant="secondary" onClick={handleSignOut}>
          <LogOut className="size-4" /> Sign out
        </Button>
        {deleteProfile.error && (
          <p className="mt-3 text-sm text-danger">
            {deleteProfile.error instanceof Error ? deleteProfile.error.message : "Could not sign out."}
          </p>
        )}
      </Card>
    </AppShell>
  );
}
```

- [ ] **Step 4: Typecheck, build, run the full frontend test suite**

Run: `cd frontend && npx tsc -b --noEmit && npm run build && npm test`
Expected: all clean, `28 passed` — 25 currently passing (verified live
before this plan was written) + 3 from this plan's `demoAuth.test.ts`,
no regressions.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/api/profile.ts frontend/src/hooks/useProfile.ts frontend/src/pages/SettingsPage.tsx
git commit -m "feat(frontend): add sign-out — deletes all data, returns to sign-up"
```

---

## Task 5: Full live E2E verification

**Files:** none — verification only.

- [ ] **Step 1: Start both servers**

Backend: `cd backend && .venv/bin/uvicorn main:app --reload`
Frontend: `cd frontend && npm run dev`

- [ ] **Step 2: Clear state and confirm the gate blocks everything**

In the browser, clear `localStorage` for the dev origin (devtools →
Application → Local Storage → clear) and clear `backend/careeros.db` if it
has leftover data from earlier manual testing (`rm backend/careeros.db*`
with the server stopped, or just call `DELETE /api/profile` once the app
is reachable). Then:

- Navigate to `/`. Expect an immediate redirect to `/signup`.
- Navigate directly to `/onboarding`, `/settings`, `/history`. Expect each
  to redirect to `/signup` too — confirm the gate isn't bypassable by
  deep link.
- Confirm the email field shows `demo@careeros.app`, the password field is
  masked, and `Demo password: CareerOS#2026` is visible underneath it.

- [ ] **Step 3: Sign up and confirm the handoff to onboarding**

Click "Sign up". Expect a redirect to `/onboarding` (no profile exists
yet, so the existing onboarding gate takes over correctly). Complete
onboarding far enough to reach the dashboard (name + topic + level is
enough; the assessment/roadmap steps aren't this plan's concern).

- [ ] **Step 4: Confirm signed-in state survives a reload**

Reload the page while on the dashboard. Expect to land back on the
dashboard, not bounced to `/signup` — confirms the `localStorage` flag
persists across reloads, not just client-side navigation.

- [ ] **Step 5: Sign out and confirm the full wipe**

Go to `/settings`, click "Sign out". Expect a native browser confirm
dialog. Confirm it. Expect an immediate redirect to `/signup`.

Then verify the wipe actually happened, not just the redirect: sign in
again (click "Sign up") and confirm you land on `/onboarding` again, not
the dashboard — if any profile data had survived, the app would instead
show the dashboard directly, which would mean the delete silently failed.

- [ ] **Step 6: Record results**

Note any deviations from the above in this task's own text before
marking it complete — this plan's whole point is a demo reset flow, so a
step that doesn't behave as described here is a real bug, not a nitpick.
