import { Loader2 } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";
import { SetupForm } from "@/components/interview/SetupForm";
import { useStartInterview } from "@/hooks/useInterview";
import { useActiveTrack } from "@/hooks/useProfile";
import type { InterviewLevel } from "@/types";

export default function InterviewSetupPage() {
  const { data: track, isPending } = useActiveTrack();
  const startInterview = useStartInterview();
  const navigate = useNavigate();

  if (isPending) {
    return (
      <AppShell>
        <div className="grid place-items-center py-24">
          <Loader2 className="size-6 animate-spin text-text-muted" />
        </div>
      </AppShell>
    );
  }

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
