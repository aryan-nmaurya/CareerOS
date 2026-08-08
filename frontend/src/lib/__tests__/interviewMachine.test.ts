import { describe, expect, it } from "vitest";

import { initialMachineState, transition } from "@/lib/interviewMachine";

describe("transition", () => {
  it("BEGIN from briefing moves to speaking at question 0", () => {
    const state = transition(initialMachineState(), { type: "BEGIN" });
    expect(state).toEqual({ phase: "speaking", questionIndex: 0 });
  });

  it("BEGIN is ignored outside briefing", () => {
    const speaking = { phase: "speaking" as const, questionIndex: 0 };
    expect(transition(speaking, { type: "BEGIN" })).toEqual(speaking);
  });

  it("TTS_DONE from speaking moves to answering, same question", () => {
    const speaking = { phase: "speaking" as const, questionIndex: 2 };
    const state = transition(speaking, { type: "TTS_DONE" });
    expect(state).toEqual({ phase: "answering", questionIndex: 2 });
  });

  it("TTS_DONE is ignored outside speaking", () => {
    const briefing = initialMachineState();
    expect(transition(briefing, { type: "TTS_DONE" })).toEqual(briefing);
  });

  it("ANSWER_ADVANCE when not the last question moves to speaking, next question", () => {
    const answering = { phase: "answering" as const, questionIndex: 0 };
    const state = transition(answering, { type: "ANSWER_ADVANCE", isLastQuestion: false });
    expect(state).toEqual({ phase: "speaking", questionIndex: 1 });
  });

  it("ANSWER_ADVANCE on the last question moves to review", () => {
    const answering = { phase: "answering" as const, questionIndex: 4 };
    const state = transition(answering, { type: "ANSWER_ADVANCE", isLastQuestion: true });
    expect(state).toEqual({ phase: "review", questionIndex: 4 });
  });

  it("ANSWER_ADVANCE is ignored outside answering", () => {
    const speaking = { phase: "speaking" as const, questionIndex: 0 };
    expect(
      transition(speaking, { type: "ANSWER_ADVANCE", isLastQuestion: false }),
    ).toEqual(speaking);
  });

  it("review is an absorbing state — all events are ignored", () => {
    const review = { phase: "review" as const, questionIndex: 4 };
    expect(transition(review, { type: "BEGIN" })).toEqual(review);
    expect(transition(review, { type: "TTS_DONE" })).toEqual(review);
    expect(
      transition(review, { type: "ANSWER_ADVANCE", isLastQuestion: true }),
    ).toEqual(review);
  });
});
