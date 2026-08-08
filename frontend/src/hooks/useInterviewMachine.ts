import { useCallback, useEffect, useReducer, useRef } from "react";

import { useAudioMonitor } from "@/hooks/useAudioMonitor";
import { useQuitInterview, useSaveInterviewAnswer, useSubmitInterview } from "@/hooks/useInterview";
import { useProctoring } from "@/hooks/useProctoring";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";
import { useSpeechSynthesis } from "@/hooks/useSpeechSynthesis";
import { useWarnings } from "@/hooks/useWarnings";
import { initialMachineState, transition } from "@/lib/interviewMachine";
import type { Interview } from "@/types";

export function useInterviewMachine(interview: Interview) {
  const [state, dispatch] = useReducer(transition, initialMachineState());
  const tts = useSpeechSynthesis();
  const stt = useSpeechRecognition();
  const saveAnswer = useSaveInterviewAnswer(interview.id);
  const submit = useSubmitInterview(interview.id);
  const quit = useQuitInterview(interview.id);
  const warnings = useWarnings(interview.id);
  const answerStart = useRef<number | null>(null);
  const currentQuestion = interview.questions[state.questionIndex] ?? null;
  const isLastQuestion = state.questionIndex === interview.questions.length - 1;
  const captureActive = !["report", "terminated"].includes(state.phase);
  const warningsArmed = captureActive && state.phase !== "preflight";
  const proctoring = useProctoring(captureActive, warningsArmed, warnings.reportEvent);
  const audio = useAudioMonitor(captureActive, warningsArmed, state.phase === "answering", stt.supported, stt.transcript, warnings.reportEvent);
  const preflightPassed = proctoring.cameraStatus === "ready" && proctoring.faceCount === 1 && audio.micStatus === "ready";

  const preflightReady = useCallback(() => dispatch({ type: "PREFLIGHT_READY" }), []);
  const begin = useCallback(() => dispatch({ type: "BEGIN" }), []);

  useEffect(() => {
    if (state.phase !== "speaking" || !currentQuestion) return;
    if (!tts.supported) return void dispatch({ type: "TTS_DONE" });
    tts.speak(currentQuestion.question, () => dispatch({ type: "TTS_DONE" }));
    return () => tts.cancel();
  }, [state.phase, state.questionIndex, currentQuestion, tts]);

  useEffect(() => {
    if (state.phase !== "answering") return;
    answerStart.current = Date.now();
    if (!stt.supported) return;
    stt.start();
    return () => stt.stop();
  }, [state.phase, state.questionIndex, stt]);

  useEffect(() => {
    if (state.phase !== "evaluating") return;
    submit.mutate(undefined, { onSuccess: () => dispatch({ type: "REPORT_READY" }) });
  }, [state.phase, submit]);

  useEffect(() => {
    if (warnings.terminated) dispatch({ type: "TERMINATE", reason: "proctoring" });
  }, [warnings.terminated]);

  const advance = useCallback((manualTranscript?: string) => {
    if (!currentQuestion) return;
    stt.stop();
    const durationS = answerStart.current ? Math.round((Date.now() - answerStart.current) / 1000) : 0;
    const transcript = stt.supported ? stt.transcript : manualTranscript ?? "";
    saveAnswer.mutate({ questionId: currentQuestion.id, transcript, durationS });
    dispatch({ type: "ANSWER_ADVANCE", isLastQuestion });
  }, [currentQuestion, isLastQuestion, saveAnswer, stt]);

  const quitNow = useCallback(() => {
    tts.cancel();
    stt.stop();
    dispatch({ type: "TERMINATE", reason: "user_quit" });
    quit.mutate();
  }, [quit, stt, tts]);

  return {
    phase: state.phase,
    terminationReason: state.terminationReason,
    currentQuestion,
    questionNumber: state.questionIndex + 1,
    totalQuestions: interview.questions.length,
    preflightReady,
    preflightPassed,
    begin,
    advance,
    quitNow,
    ttsSupported: tts.supported,
    sttSupported: stt.supported,
    liveTranscript: stt.transcript,
    listening: stt.listening,
    warningCount: warnings.warningCount,
    recentEventType: warnings.recentEventType,
    videoRef: proctoring.videoRef,
    cameraStatus: proctoring.cameraStatus,
    faceCount: proctoring.faceCount,
    micStatus: audio.micStatus,
    evaluationError: submit.error,
  };
}
