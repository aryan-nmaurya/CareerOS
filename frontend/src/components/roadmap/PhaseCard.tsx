import { ChevronDown, Lock } from "lucide-react";
import { useState } from "react";

import { ModuleRow } from "@/components/roadmap/ModuleRow";
import { cn } from "@/lib/cn";
import type { RoadmapPhase } from "@/types";

interface PhaseCardProps {
  phase: RoadmapPhase;
  completionPct: number;
  unlocked: boolean;
  isCurrent: boolean;
  onToggleModule: (moduleId: number, completed: boolean) => void;
  togglingModuleId?: number | null;
}

export function PhaseCard({
  phase,
  completionPct,
  unlocked,
  isCurrent,
  onToggleModule,
  togglingModuleId,
}: PhaseCardProps) {
  const [expanded, setExpanded] = useState(isCurrent);

  return (
    <div
      className={cn(
        "rounded-xl border bg-surface transition-colors",
        isCurrent ? "border-accent" : "border-line",
        !unlocked && "opacity-60",
      )}
    >
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="flex w-full items-center gap-3 p-4 text-left"
      >
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-accent-soft text-sm font-semibold text-accent">
          {phase.order_index + 1}
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="truncate text-sm font-semibold text-text-primary">{phase.title}</h3>
            {!unlocked && <Lock className="size-3.5 shrink-0 text-text-muted" />}
          </div>
          <p className="mt-0.5 truncate text-xs text-text-secondary">{phase.goal}</p>
        </div>

        <div className="flex shrink-0 items-center gap-3">
          <div className="hidden w-24 sm:block">
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-line">
              <div
                className="h-full rounded-full bg-accent transition-all duration-base"
                style={{ width: `${completionPct}%` }}
              />
            </div>
          </div>
          <span className="w-10 text-right text-xs font-medium text-text-secondary">
            {Math.round(completionPct)}%
          </span>
          <ChevronDown
            className={cn(
              "size-4 text-text-muted transition-transform",
              expanded && "rotate-180",
            )}
          />
        </div>
      </button>

      {expanded && (
        <div className="space-y-2 border-t border-line p-4 pt-3">
          {!unlocked && (
            <p className="mb-2 text-xs text-text-muted">
              Complete 80% of the previous phase to unlock this one.
            </p>
          )}
          {phase.modules.map((module) => (
            <ModuleRow
              key={module.id}
              module={module}
              onToggle={(completed) => onToggleModule(module.id, completed)}
              pending={togglingModuleId === module.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}
