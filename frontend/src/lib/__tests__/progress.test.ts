import { describe, expect, it } from "vitest";

import {
  buildProgress,
  currentPhaseIndex,
  isModuleComplete,
  isPhaseUnlocked,
  phaseCompletion,
  roadmapCompletion,
} from "@/lib/progress";

function mod(completed: boolean) {
  return { completed_at: completed ? "2026-01-01T00:00:00" : null };
}

function phase(orderIndex: number, modules: { completed_at: string | null }[]) {
  return { order_index: orderIndex, title: `Phase ${orderIndex}`, modules };
}

describe("isModuleComplete", () => {
  it("checks completed_at", () => {
    expect(isModuleComplete(mod(true))).toBe(true);
    expect(isModuleComplete(mod(false))).toBe(false);
  });
});

describe("phaseCompletion", () => {
  it("is the completed fraction", () => {
    expect(phaseCompletion([mod(true), mod(true), mod(false)])).toBeCloseTo(2 / 3);
  });

  it("is zero for an empty phase, not a crash", () => {
    expect(phaseCompletion([])).toBe(0);
  });
});

describe("roadmapCompletion", () => {
  it("spans all phases", () => {
    const phases = [phase(0, [mod(true), mod(true)]), phase(1, [mod(true), mod(false)])];
    expect(roadmapCompletion(phases)).toBeCloseTo(3 / 4);
  });
});

describe("isPhaseUnlocked", () => {
  it("the first phase is always unlocked", () => {
    expect(isPhaseUnlocked(0, [phase(0, [mod(false)])])).toBe(true);
  });

  it("unlocks at exactly 80% previous completion", () => {
    const previous = phase(0, [mod(true), mod(true), mod(true), mod(true), mod(false)]);
    expect(isPhaseUnlocked(1, [previous, phase(1, [mod(false)])])).toBe(true);
  });

  it("stays locked just under 80% previous completion", () => {
    const previous = phase(0, [mod(true), mod(true), mod(true), mod(false)]);
    expect(isPhaseUnlocked(1, [previous, phase(1, [mod(false)])])).toBe(false);
  });
});

describe("currentPhaseIndex", () => {
  it("is the first incomplete phase", () => {
    const phases = [phase(0, [mod(true)]), phase(1, [mod(false)]), phase(2, [mod(false)])];
    expect(currentPhaseIndex(phases)).toBe(1);
  });

  it("is the last phase when everything is complete", () => {
    expect(currentPhaseIndex([phase(0, [mod(true)]), phase(1, [mod(true)])])).toBe(1);
  });
});

describe("buildProgress", () => {
  it("summarizes everything in one shape", () => {
    const phases = [phase(0, [mod(true), mod(true)]), phase(1, [mod(false)])];
    const progress = buildProgress(phases);

    expect(progress.completed_modules).toBe(2);
    expect(progress.total_modules).toBe(3);
    expect(progress.completion_pct).toBeCloseTo(66.7, 1);
    expect(progress.current_phase_index).toBe(1);
    expect(progress.phases[0].unlocked).toBe(true);
    expect(progress.phases[1].unlocked).toBe(true);
    expect(progress.phases[1].completion_pct).toBe(0);
  });
});
