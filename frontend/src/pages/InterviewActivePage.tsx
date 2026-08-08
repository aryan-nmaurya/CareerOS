import { Loader2 } from "lucide-react";
import { useParams } from "react-router-dom";

import { QuestionStage } from "@/components/interview/QuestionStage";
import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";
import { useInterview } from "@/hooks/useInterview";
import { useInterviewMachine } from "@/hooks/useInterviewMachine";
import type { Interview } from "@/types";

function ActiveInterview({ interview }: { interview: Interview }) {
  const machine = useInterviewMachine(interview);

  return (
    <AppShell>
      <TopBar title={`${interview.level} interview`} />
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
      />
    </AppShell>
  );
}

export default function InterviewActivePage() {
  const { id } = useParams<{ id: string }>();
  const interviewId = Number(id);
  const { data: interview, isPending } = useInterview(interviewId);

  if (isPending || !interview) {
    return (
      <AppShell>
        <div className="grid place-items-center py-24">
          <Loader2 className="size-6 animate-spin text-text-muted" />
        </div>
      </AppShell>
    );
  }

  return <ActiveInterview interview={interview} />;
}
