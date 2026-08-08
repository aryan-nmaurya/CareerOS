import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { QuestionStage } from "@/components/interview/QuestionStage";
import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";
import { ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { useInterview } from "@/hooks/useInterview";
import { useInterviewMachine } from "@/hooks/useInterviewMachine";
import type { Interview } from "@/types";

function ActiveInterview({ interview }: { interview: Interview }) {
  const machine = useInterviewMachine(interview);
  const navigate = useNavigate();

  useEffect(() => {
    if (machine.phase === "report") navigate(`/interview/${interview.id}/report`, { replace: true });
  }, [interview.id, machine.phase, navigate]);

  return (
    <AppShell>
      <TopBar
        title={`${interview.level.charAt(0).toUpperCase()}${interview.level.slice(1)} Interview`}
      />
      <QuestionStage
        key={machine.currentQuestion?.id ?? "review"}
        interview={interview}
        phase={machine.phase}
        currentQuestion={machine.currentQuestion}
        questionNumber={machine.questionNumber}
        totalQuestions={machine.totalQuestions}
        ttsSupported={machine.ttsSupported}
        sttSupported={machine.sttSupported}
        listening={machine.listening}
        liveTranscript={machine.liveTranscript}
        onBegin={machine.begin}
        onAdvance={machine.advance}
        onQuit={machine.quitNow}
        onPreflightReady={machine.preflightReady}
        terminationReason={machine.terminationReason}
        videoRef={machine.videoRef}
        cameraStatus={machine.cameraStatus}
        faceCount={machine.faceCount}
        micStatus={machine.micStatus}
        preflightPassed={machine.preflightPassed}
        warningCount={machine.warningCount}
        recentEventType={machine.recentEventType}
      />
    </AppShell>
  );
}

export default function InterviewActivePage() {
  const { id } = useParams<{ id: string }>();
  const interviewId = Number(id);
  const { data: interview, isPending, error, refetch } = useInterview(interviewId);

  if (isPending) {
    return (
      <AppShell>
        <LoadingState label="Loading interview…" />
      </AppShell>
    );
  }

  if (error || !interview) {
    return <AppShell><ErrorState message={error instanceof Error ? error.message : "Interview not found."} onRetry={() => void refetch()} /></AppShell>;
  }

  return <ActiveInterview interview={interview} />;
}
