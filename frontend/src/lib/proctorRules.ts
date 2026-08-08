export interface EulerAngles {
  pitch: number;
  yaw: number;
  roll: number;
}

const RAD_TO_DEG = 180 / Math.PI;

export function matrixToEuler(d: ArrayLike<number>): EulerAngles {
  const pitch = Math.atan2(d[6], d[10]) * RAD_TO_DEG;
  const yaw = (Math.atan2(-d[2], Math.hypot(d[6], d[10])) * RAD_TO_DEG) || 0;
  const roll = Math.atan2(d[1], d[0]) * RAD_TO_DEG;
  return { pitch, yaw, roll };
}

export function isLookingAway(angles: EulerAngles): boolean {
  return Math.abs(angles.yaw) > 25 || angles.pitch < -20;
}

export interface SustainState {
  conditionStartedAt: number | null;
  cooldownUntil: number | null;
}

export function initialSustainState(): SustainState {
  return { conditionStartedAt: null, cooldownUntil: null };
}

export interface SustainResult {
  state: SustainState;
  fired: boolean;
}

export function trackSustain(
  state: SustainState,
  conditionMet: boolean,
  now: number,
  sustainMs: number,
  cooldownMs: number,
): SustainResult {
  if (state.cooldownUntil !== null) {
    if (now < state.cooldownUntil) return { state, fired: false };
    state = initialSustainState();
  }
  if (!conditionMet) return { state: initialSustainState(), fired: false };
  if (state.conditionStartedAt === null) {
    return { state: { conditionStartedAt: now, cooldownUntil: null }, fired: false };
  }
  if (now - state.conditionStartedAt >= sustainMs) {
    return {
      state: { conditionStartedAt: null, cooldownUntil: now + cooldownMs },
      fired: true,
    };
  }
  return { state, fired: false };
}
