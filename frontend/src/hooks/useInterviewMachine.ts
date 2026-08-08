import { useCallback, useEffect, useReducer, useRef } from "react";
import { useNavigate } from "react-router-dom";

import { useQuitInterview, useSaveInterviewAnswer, useSubmitInterview } from "@/hooks/useInterview";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";
import { useSpeechSynthesis } from "@/hooks/useSpeechSynthesis";
import { initialMachineState, transition } from "@/lib/interviewMachine";
import type { Interview } from "@/types";

export function useInterviewMachine(interview: Interview) {
  const [state, dispatch] = useReducer(transition, initialMachineState());
  const tts = useSpeechSynthesis();
  const stt = useSpeechRecognition();
  const saveAnswer = useSaveInterviewAnswer(interview.id);
  const submit = useSubmitInterview(interview.id);
  const quit = useQuitInterview(interview.id);
  const navigate = useNavigate();
  const answerStartRef = useRef<number | null>(null);

  const currentQuestion = interview.questions[state.questionIndex] ?? null;
  const isLastQuestion = state.questionIndex === interview.questions.length - 1;

  const begin = useCallback(() => dispatch({ type: "BEGIN" }), []);

  useEffect(() => {
    if (state.phase !== "speaking" || !currentQuestion) return;
    if (!tts.supported) {
      dispatch({ type: "TTS_DONE" });
      return;
    }
    tts.speak(currentQuestion.question, () => dispatch({ type: "TTS_DONE" }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.phase, state.questionIndex]);

  useEffect(() => {
    if (state.phase !== "answering") return;
    answerStartRef.current = Date.now();
    if (!stt.supported) return;
    stt.start();
    return () => stt.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.phase, state.questionIndex]);

  useEffect(() => {
    if (state.phase === "review") submit.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.phase]);

  const advance = useCallback(
    (manualTranscript?: string) => {
      if (!currentQuestion) return;
      stt.stop();
      const durationS = answerStartRef.current
        ? Math.round((Date.now() - answerStartRef.current) / 1000)
        : 0;
      const transcript = stt.supported ? stt.transcript : (manualTranscript ?? "");
      saveAnswer.mutate({ questionId: currentQuestion.id, transcript, durationS });
      dispatch({ type: "ANSWER_ADVANCE", isLastQuestion });
    },
    [currentQuestion, isLastQuestion, saveAnswer, stt],
  );

  const quitNow = useCallback(() => {
    tts.cancel();
    stt.stop();
    quit.mutate(undefined, { onSuccess: () => navigate("/") });
  }, [tts, stt, quit, navigate]);

  return {
    phase: state.phase,
    currentQuestion,
    questionNumber: state.questionIndex + 1,
    totalQuestions: interview.questions.length,
    begin,
    advance,
    quitNow,
    ttsSupported: tts.supported,
    sttSupported: stt.supported,
    liveTranscript: stt.transcript,
    listening: stt.listening,
  };
}
