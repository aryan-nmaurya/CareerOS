import type { MachinePhase } from "@/types";

export interface MachineState {
  phase: MachinePhase;
  questionIndex: number;
}

export type MachineEvent =
  | { type: "BEGIN" }
  | { type: "TTS_DONE" }
  | { type: "ANSWER_ADVANCE"; isLastQuestion: boolean };

export function initialMachineState(): MachineState {
  return { phase: "briefing", questionIndex: 0 };
}

export function transition(state: MachineState, event: MachineEvent): MachineState {
  if (state.phase === "briefing" && event.type === "BEGIN") {
    return { phase: "speaking", questionIndex: 0 };
  }
  if (state.phase === "speaking" && event.type === "TTS_DONE") {
    return { ...state, phase: "answering" };
  }
  if (state.phase === "answering" && event.type === "ANSWER_ADVANCE") {
    if (event.isLastQuestion) {
      return { ...state, phase: "review" };
    }
    return { phase: "speaking", questionIndex: state.questionIndex + 1 };
  }
  return state;
}
