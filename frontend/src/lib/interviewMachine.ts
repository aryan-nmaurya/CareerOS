import type { MachinePhase, TerminationReason } from "@/types";

export interface MachineState {
  phase: MachinePhase;
  questionIndex: number;
  terminationReason: TerminationReason | null;
}

export type MachineEvent =
  | { type: "PREFLIGHT_READY" }
  | { type: "BEGIN" }
  | { type: "TTS_DONE" }
  | { type: "ANSWER_ADVANCE"; isLastQuestion: boolean }
  | { type: "REPORT_READY" }
  | { type: "TERMINATE"; reason: TerminationReason };

export function initialMachineState(): MachineState {
  return { phase: "preflight", questionIndex: 0, terminationReason: null };
}

export function transition(state: MachineState, event: MachineEvent): MachineState {
  if (event.type === "TERMINATE" && state.phase !== "terminated" && state.phase !== "report") {
    return { ...state, phase: "terminated", terminationReason: event.reason };
  }
  if (state.phase === "preflight" && event.type === "PREFLIGHT_READY") {
    return { ...state, phase: "briefing" };
  }
  if (state.phase === "briefing" && event.type === "BEGIN") {
    return { ...state, phase: "speaking", questionIndex: 0 };
  }
  if (state.phase === "speaking" && event.type === "TTS_DONE") {
    return { ...state, phase: "answering" };
  }
  if (state.phase === "answering" && event.type === "ANSWER_ADVANCE") {
    if (event.isLastQuestion) {
      return { ...state, phase: "evaluating" };
    }
    return { ...state, phase: "speaking", questionIndex: state.questionIndex + 1 };
  }
  if (state.phase === "evaluating" && event.type === "REPORT_READY") {
    return { ...state, phase: "report" };
  }
  return state;
}
