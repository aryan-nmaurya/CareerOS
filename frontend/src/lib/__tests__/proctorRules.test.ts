import { describe, expect, it } from "vitest";

import { initialSustainState, isLookingAway, matrixToEuler, trackSustain } from "@/lib/proctorRules";

describe("proctor rules", () => {
  it("extracts identity angles", () => {
    expect(matrixToEuler([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])).toEqual({ pitch: 0, yaw: 0, roll: 0 });
  });
  it("flags yaw and pitch outside thresholds", () => {
    expect(isLookingAway({ pitch: 0, yaw: 26, roll: 0 })).toBe(true);
    expect(isLookingAway({ pitch: -21, yaw: 0, roll: 0 })).toBe(true);
    expect(isLookingAway({ pitch: -10, yaw: 20, roll: 0 })).toBe(false);
  });
  it("requires a sustained condition and then applies cooldown", () => {
    let state = initialSustainState();
    ({ state } = trackSustain(state, true, 0, 2500, 10000));
    expect(trackSustain(state, true, 2000, 2500, 10000).fired).toBe(false);
    const fired = trackSustain(state, true, 2600, 2500, 10000);
    expect(fired.fired).toBe(true);
    expect(trackSustain(fired.state, true, 5000, 2500, 10000).fired).toBe(false);
  });
});
