import { useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { EXPERIENCE_LEVELS } from "@/lib/constants";
import type { InterviewLevel } from "@/types";

const QUESTION_COUNTS = [5, 8, 10] as const;

interface SetupFormProps {
  defaultLevel: InterviewLevel;
  pending: boolean;
  onStart: (level: InterviewLevel, questionCount: number) => void;
}

export function SetupForm({ defaultLevel, pending, onStart }: SetupFormProps) {
  const [level, setLevel] = useState<InterviewLevel>(defaultLevel);
  const [questionCount, setQuestionCount] = useState<number>(8);

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <p className="text-sm font-medium text-text-primary">Level</p>
        <div className="flex flex-wrap gap-2">
          {EXPERIENCE_LEVELS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setLevel(option.value)}
              className={cn(
                "rounded-full border px-4 py-2 text-sm font-medium transition-colors",
                level === option.value
                  ? "border-accent bg-accent-soft text-accent"
                  : "border-line text-text-secondary hover:border-accent/50",
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-sm font-medium text-text-primary">Number of questions</p>
        <div className="flex gap-2">
          {QUESTION_COUNTS.map((count) => (
            <button
              key={count}
              type="button"
              onClick={() => setQuestionCount(count)}
              className={cn(
                "rounded-full border px-4 py-2 text-sm font-medium transition-colors",
                questionCount === count
                  ? "border-accent bg-accent-soft text-accent"
                  : "border-line text-text-secondary hover:border-accent/50",
              )}
            >
              {count}
            </button>
          ))}
        </div>
      </div>

      <Button disabled={pending} onClick={() => onStart(level, questionCount)}>
        {pending ? "Generating questions…" : "Start interview"}
      </Button>
    </div>
  );
}
