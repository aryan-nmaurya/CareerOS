import { Loader2 } from "lucide-react";

import { EXPERIENCE_LEVELS } from "@/lib/constants";
import { cn } from "@/lib/cn";
import type { ExperienceLevel } from "@/types";

interface LevelStepProps {
  topic: string;
  pending: boolean;
  pendingLabel: string;
  errorMessage?: string;
  onSelect: (level: ExperienceLevel) => void;
}

export function LevelStep({
  topic,
  pending,
  pendingLabel,
  errorMessage,
  onSelect,
}: LevelStepProps) {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-3xl font-semibold tracking-tight">
          How much {topic} do you already know?
        </h2>
        <p className="text-text-secondary">
          This decides whether we assess you first or go straight to the roadmap.
        </p>
      </div>

      <div className="grid gap-3">
        {EXPERIENCE_LEVELS.map(({ value, label, description }) => (
          <button
            key={value}
            type="button"
            disabled={pending}
            onClick={() => onSelect(value)}
            className={cn(
              "rounded-xl border border-line bg-surface p-5 text-left",
              "transition-colors duration-fast",
              "hover:border-accent hover:bg-accent-soft",
              "disabled:pointer-events-none disabled:opacity-60",
            )}
          >
            <span className="block font-semibold text-text-primary">{label}</span>
            <span className="mt-1 block text-sm text-text-secondary">{description}</span>
          </button>
        ))}
      </div>

      {pending && (
        <p className="flex items-center gap-2 text-sm text-text-secondary">
          <Loader2 className="size-4 animate-spin" /> {pendingLabel}
        </p>
      )}

      {errorMessage && !pending && (
        <p className="text-sm text-danger">{errorMessage} — pick a level again to retry.</p>
      )}
    </div>
  );
}
