import { ArrowRight, LogOut } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import type { ReactNode, RefObject } from "react";

import { CameraPip } from "@/components/interview/CameraPip";
import { PreflightCheck } from "@/components/interview/PreflightCheck";
import { TranscriptPanel } from "@/components/interview/TranscriptPanel";
import { WarningOverlay } from "@/components/interview/WarningOverlay";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import type { MicStatus } from "@/hooks/useAudioMonitor";
import type { CameraStatus } from "@/hooks/useProctoring";
import type { Interview, MachinePhase, TerminationReason } from "@/types";

interface Props {
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
  onPreflightReady: () => void;
  terminationReason: TerminationReason | null;
  videoRef: RefObject<HTMLVideoElement | null>;
  cameraStatus: CameraStatus;
  faceCount: number;
  micStatus: MicStatus;
  preflightPassed: boolean;
  warningCount: number;
  recentEventType: string | null;
}

export function QuestionStage({
  interview, phase, currentQuestion, questionNumber, totalQuestions, ttsSupported, sttSupported,
  listening, liveTranscript, onBegin, onAdvance, onQuit, onPreflightReady, terminationReason,
  videoRef, cameraStatus, faceCount, micStatus, preflightPassed, warningCount, recentEventType,
}: Props) {
  const [manualAnswer, setManualAnswer] = useState("");
  let content: ReactNode;
  if (phase === "preflight") content = <PreflightCheck videoRef={videoRef} cameraStatus={cameraStatus} faceCount={faceCount} micStatus={micStatus} ready={preflightPassed} onContinue={onPreflightReady} />;
  else if (phase === "terminated") content = <Card className="space-y-4"><CardTitle>{terminationReason === "proctoring" ? "Interview terminated" : "Interview ended"}</CardTitle><CardDescription>{terminationReason === "proctoring" ? (recentEventType === "multiple_faces" ? "Multiple faces were detected, so the interview ended immediately." : `The interview ended after ${warningCount} proctoring warning${warningCount === 1 ? "" : "s"}.`) : "You ended this interview early."}</CardDescription></Card>;
  else if (phase === "evaluating") content = <Card className="space-y-3"><CardTitle>Evaluating your interview…</CardTitle><CardDescription>Gemini is reviewing all answers together and preparing feedback.</CardDescription></Card>;
  else if (phase === "report") content = <Card className="space-y-3"><CardTitle>Interview evaluated</CardTitle><CardDescription>Your report is ready.</CardDescription></Card>;
  else if (phase === "briefing") content = <Card className="space-y-4"><CardTitle>Ready when you are</CardTitle><CardDescription>{totalQuestions} questions, {interview.level} level. {ttsSupported ? "Each question will be read aloud." : "Questions will be shown as text."}</CardDescription><Button onClick={onBegin}>Start <ArrowRight className="size-4" /></Button></Card>;
  else content = <div className="space-y-4"><CameraPip videoRef={videoRef} cameraStatus={cameraStatus} faceCount={faceCount} /><WarningOverlay warningCount={warningCount} recentEventType={recentEventType} /><div className="flex items-center justify-between"><p className="text-xs font-medium text-text-muted">Question {questionNumber} of {totalQuestions}</p><Button variant="ghost" size="sm" onClick={onQuit}><LogOut className="size-4" /> End interview</Button></div><Card><CardTitle>{currentQuestion?.question}</CardTitle></Card>{phase === "answering" && <><TranscriptPanel sttSupported={sttSupported} listening={listening} liveTranscript={liveTranscript} manualValue={manualAnswer} onManualChange={setManualAnswer} /><Button onClick={() => onAdvance(manualAnswer)}>{questionNumber === totalQuestions ? "Finish" : "Next question"} <ArrowRight className="size-4" /></Button></>}</div>;
  return <AnimatePresence mode="wait" initial={false}><motion.div key={phase} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.18 }}>{content}</motion.div></AnimatePresence>;
}
