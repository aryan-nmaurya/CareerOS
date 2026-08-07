interface ModuleLike {
  completed_at: string | null;
}

interface PhaseLike {
  order_index: number;
  title: string;
  modules: ModuleLike[];
}

export function isModuleComplete(module: ModuleLike): boolean {
  return module.completed_at !== null;
}

export function phaseCompletion(modules: ModuleLike[]): number {
  if (modules.length === 0) return 0;
  return modules.filter(isModuleComplete).length / modules.length;
}

export function roadmapCompletion(phases: PhaseLike[]): number {
  const allModules = phases.flatMap((p) => p.modules);
  if (allModules.length === 0) return 0;
  return allModules.filter(isModuleComplete).length / allModules.length;
}

export function isPhaseUnlocked(phaseIndex: number, phases: PhaseLike[]): boolean {
  if (phaseIndex === 0) return true;
  return phaseCompletion(phases[phaseIndex - 1].modules) >= 0.8;
}

export function currentPhaseIndex(phases: PhaseLike[]): number {
  for (let i = 0; i < phases.length; i++) {
    if (phaseCompletion(phases[i].modules) < 1) return i;
  }
  return phases.length > 0 ? phases.length - 1 : 0;
}

export interface ProgressSummary {
  completion_pct: number;
  completed_modules: number;
  total_modules: number;
  current_phase_index: number;
  current_phase_title: string | null;
  phases: { order_index: number; completion_pct: number; unlocked: boolean }[];
}

export function buildProgress(phases: PhaseLike[]): ProgressSummary {
  const totalModules = phases.reduce((sum, p) => sum + p.modules.length, 0);
  const completedModules = phases.reduce(
    (sum, p) => sum + p.modules.filter(isModuleComplete).length,
    0,
  );
  const current = currentPhaseIndex(phases);

  return {
    completion_pct: Math.round(roadmapCompletion(phases) * 1000) / 10,
    completed_modules: completedModules,
    total_modules: totalModules,
    current_phase_index: current,
    current_phase_title: phases.length > 0 ? phases[current].title : null,
    phases: phases.map((phase, i) => ({
      order_index: phase.order_index,
      completion_pct: Math.round(phaseCompletion(phase.modules) * 1000) / 10,
      unlocked: isPhaseUnlocked(i, phases),
    })),
  };
}
