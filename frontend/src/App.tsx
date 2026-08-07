import { Loader2 } from "lucide-react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";
import { useProfile } from "@/hooks/useProfile";
import AssessmentPage from "@/pages/AssessmentPage";
import DashboardPage from "@/pages/DashboardPage";
import OnboardingPage from "@/pages/OnboardingPage";
import RoadmapPage from "@/pages/RoadmapPage";
import SettingsPage from "@/pages/SettingsPage";

function Placeholder({ title }: { title: string }) {
  return (
    <AppShell>
      <TopBar title={title} subtitle="Coming in a later plan." />
    </AppShell>
  );
}

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
      <Route path="/interview" element={<Placeholder title="Interviews" />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
