import { useNavigate } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";
import { ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { SetupForm } from "@/components/interview/SetupForm";
import { useStartInterview } from "@/hooks/useInterview";
import { useActiveTrack } from "@/hooks/useProfile";
import type { InterviewLevel } from "@/types";

export default function InterviewSetupPage() {
  const { data: track, isPending, error, refetch } = useActiveTrack();
  const startInterview = useStartInterview();
  const navigate = useNavigate();

  if (isPending) {
    return (
      <AppShell>
        <LoadingState label="Loading interview setup…" />
      </AppShell>
    );
  }

  if (error) return <AppShell><ErrorState message={error instanceof Error ? error.message : "Could not load the active track."} onRetry={() => void refetch()} /></AppShell>;

  if (!track) {
    return (
      <AppShell>
        <TopBar title="Mock interview" subtitle="Pick a track from the dashboard first." />
      </AppShell>
    );
  }

  const handleStart = (level: InterviewLevel, questionCount: number) => {
    startInterview.mutate(
      { trackId: track.id, level, questionCount },
      { onSuccess: (interview) => navigate(`/interview/${interview.id}`) },
    );
  };

  return (
    <AppShell>
      <TopBar
        title="Mock interview"
        subtitle={`${track.topic} — questions are generated for you, answer out loud.`}
      />
      <SetupForm
        defaultLevel={track.experience_level}
        pending={startInterview.isPending}
        onStart={handleStart}
      />
      {startInterview.error && (
        <p className="mt-4 text-sm text-danger">
          {startInterview.error instanceof Error
            ? startInterview.error.message
            : "Something went wrong generating your questions."}
        </p>
      )}
    </AppShell>
  );
}
