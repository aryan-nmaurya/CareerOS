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
