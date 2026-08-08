import { ArrowRight, LogOut } from "lucide-react";
import { useState } from "react";

import { TranscriptPanel } from "@/components/interview/TranscriptPanel";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import type { Interview, MachinePhase } from "@/types";

interface QuestionStageProps {
  interview: Interview;
  phase: MachinePhase;
  currentQuestion: Interview["questions"][number] | null;
  questionNumber: number;
  totalQuestions: number;
  ttsSupported: boolean;
  sttSupported: boolean;
  listening: boolean;
  liveTranscript: string;
  onBegin: () => void;
  onAdvance: (manualTranscript?: string) => void;
  onQuit: () => void;
}

export function QuestionStage({
  interview,
  phase,
  currentQuestion,
  questionNumber,
  totalQuestions,
  ttsSupported,
  sttSupported,
  listening,
  liveTranscript,
  onBegin,
  onAdvance,
  onQuit,
}: QuestionStageProps) {
  const [manualAnswer, setManualAnswer] = useState("");

  if (phase === "briefing") {
    return (
      <Card className="space-y-4">
        <CardTitle>Ready when you are</CardTitle>
        <CardDescription>
          {totalQuestions} questions, {interview.level} level.{" "}
          {ttsSupported
            ? "Each question will be read aloud."
            : "Your browser can't read questions aloud — they'll be shown as text instead."}
        </CardDescription>
        <Button onClick={onBegin}>
          Start <ArrowRight className="size-4" />
        </Button>
      </Card>
    );
  }

  if (phase === "review") {
    return (
      <Card className="space-y-4">
        <CardTitle>Interview complete</CardTitle>
        <CardDescription>
          You answered all {totalQuestions} questions. Scoring and feedback arrive in a later
          build.
        </CardDescription>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-text-muted">
          Question {questionNumber} of {totalQuestions}
        </p>
        <Button variant="ghost" size="sm" onClick={onQuit}>
          <LogOut className="size-4" /> End interview
        </Button>
      </div>

      <Card>
        <CardTitle>{currentQuestion?.question}</CardTitle>
      </Card>

      {phase === "answering" && (
        <>
          <TranscriptPanel
            sttSupported={sttSupported}
            listening={listening}
            liveTranscript={liveTranscript}
            manualValue={manualAnswer}
            onManualChange={setManualAnswer}
          />
          <Button onClick={() => onAdvance(manualAnswer)}>
            {questionNumber === totalQuestions ? "Finish" : "Next question"}{" "}
            <ArrowRight className="size-4" />
          </Button>
        </>
      )}
    </div>
  );
}
