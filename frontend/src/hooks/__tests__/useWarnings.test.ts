import { describe, expect, it } from "vitest";

import { initialWarningsState, warningsReducer } from "@/hooks/useWarnings";

describe("warningsReducer", () => {
  it("trusts server warning counts and termination", () => {
    let state = warningsReducer(initialWarningsState(), { type: "SERVER_RESULT", eventType: "looking_away", warningCount: 1, shouldTerminate: false });
    state = warningsReducer(state, { type: "SERVER_RESULT", eventType: "no_face", warningCount: 2, shouldTerminate: false });
    state = warningsReducer(state, { type: "SERVER_RESULT", eventType: "looking_away", warningCount: 3, shouldTerminate: true });
    expect(state.warningCount).toBe(3);
    expect(state.terminated).toBe(true);
  });
  it("terminates a fatal event without incrementing warning count", () => {
    const state = warningsReducer(initialWarningsState(), { type: "SERVER_RESULT", eventType: "multiple_faces", warningCount: 0, shouldTerminate: true });
    expect(state).toMatchObject({ warningCount: 0, terminated: true });
  });
  it("ignores events after termination", () => {
    const state = warningsReducer(initialWarningsState(), { type: "SERVER_RESULT", eventType: "multiple_faces", warningCount: 0, shouldTerminate: true });
    expect(warningsReducer(state, { type: "SERVER_RESULT", eventType: "no_face", warningCount: 1, shouldTerminate: false })).toEqual(state);
  });
});
