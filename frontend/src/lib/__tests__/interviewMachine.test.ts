import { describe, expect, it } from "vitest";

import { initialMachineState, transition } from "@/lib/interviewMachine";

describe("interview machine", () => {
  it("starts in preflight and enters briefing when checks pass", () => {
    const initial = initialMachineState();
    expect(initial.phase).toBe("preflight");
    expect(transition(initial, { type: "PREFLIGHT_READY" }).phase).toBe("briefing");
  });
  it("runs the question flow and evaluates on the last answer", () => {
    const briefing = { phase: "briefing" as const, questionIndex: 0, terminationReason: null };
    const speaking = transition(briefing, { type: "BEGIN" });
    const answering = transition(speaking, { type: "TTS_DONE" });
    expect(answering.phase).toBe("answering");
    expect(transition({ ...answering, questionIndex: 4 }, { type: "ANSWER_ADVANCE", isLastQuestion: true }).phase).toBe("evaluating");
  });
  it("moves evaluation to report", () => {
    const state = { phase: "evaluating" as const, questionIndex: 0, terminationReason: null };
    expect(transition(state, { type: "REPORT_READY" }).phase).toBe("report");
  });
  it("terminates active phases and keeps termination absorbing", () => {
    const active = { phase: "answering" as const, questionIndex: 1, terminationReason: null };
    const terminated = transition(active, { type: "TERMINATE", reason: "proctoring" });
    expect(terminated).toEqual({ phase: "terminated", questionIndex: 1, terminationReason: "proctoring" });
    expect(transition(terminated, { type: "BEGIN" })).toEqual(terminated);
  });
});
