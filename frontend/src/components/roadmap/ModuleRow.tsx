import { Check, Circle, Flag, RotateCcw, Sparkles } from "lucide-react";

import { cn } from "@/lib/cn";
import type { RoadmapModule } from "@/types";

const KIND_ICON: Record<RoadmapModule["kind"], typeof Circle> = {
  module: Circle,
  checkpoint: RotateCcw,
  milestone: Flag,
  project: Sparkles,
};

const KIND_LABEL: Record<RoadmapModule["kind"], string> = {
  module: "Module",
  checkpoint: "Checkpoint",
  milestone: "Milestone",
  project: "Project",
};

interface ModuleRowProps {
  module: RoadmapModule;
  onToggle: (completed: boolean) => void;
  pending?: boolean;
}

export function ModuleRow({ module, onToggle, pending }: ModuleRowProps) {
  const completed = module.completed_at !== null;
  const Icon = KIND_ICON[module.kind];

  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-lg border border-line bg-surface p-3 transition-colors",
        completed && "bg-accent-soft/40",
      )}
    >
      <button
        type="button"
        disabled={pending}
        onClick={() => onToggle(!completed)}
        aria-label={completed ? "Mark incomplete" : "Mark complete"}
        className={cn(
          "mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border transition-colors",
          completed
            ? "border-accent bg-accent text-on-accent"
            : "border-line text-transparent hover:border-accent",
          pending && "opacity-50",
        )}
      >
        <Check className="size-3.5" strokeWidth={3} />
      </button>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "text-sm font-medium",
              completed ? "text-text-secondary line-through" : "text-text-primary",
            )}
          >
            {module.title}
          </span>
          {module.kind !== "module" && (
            <span className="flex items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent">
              <Icon className="size-3" />
              {KIND_LABEL[module.kind]}
            </span>
          )}
        </div>
        {module.description && (
          <p className="mt-0.5 text-xs text-text-secondary">{module.description}</p>
        )}
        <p className="mt-1 text-[11px] text-text-muted">{module.estimated_hours}h estimated</p>
      </div>
    </div>
  );
}
