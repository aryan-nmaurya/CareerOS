import { motion } from "framer-motion";
import { Loader2, Sparkles } from "lucide-react";

import { Card } from "@/components/ui/card";
import type { RoadmapMeta, StreamPhase } from "@/types";

interface GeneratingRoadmapProps {
  meta: RoadmapMeta | null;
  phases: StreamPhase[];
}

export function GeneratingRoadmap({ meta, phases }: GeneratingRoadmapProps) {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 rounded-xl border border-accent/30 bg-accent-soft px-4 py-3">
        <Loader2 className="size-4 shrink-0 animate-spin text-accent" />
        <p className="text-sm text-accent">
          {meta ? "Writing your roadmap phase by phase…" : "Thinking through your roadmap…"}
        </p>
      </div>

      {meta && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="space-y-1.5">
            <h2 className="text-lg font-semibold text-text-primary">{meta.title}</h2>
            <p className="text-sm text-text-secondary">{meta.summary}</p>
            <p className="text-xs text-text-muted">
              {meta.total_weeks} weeks · ~{meta.weekly_hours}h/week
            </p>
          </Card>
        </motion.div>
      )}

      <div className="space-y-3">
        {phases.map((phase) => (
          <motion.div
            key={`${phase.order_index}-${phase.title}`}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <Card className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="grid size-6 shrink-0 place-items-center rounded-full bg-accent-soft text-xs font-semibold text-accent">
                  {phase.order_index + 1}
                </span>
                <h3 className="text-sm font-semibold text-text-primary">{phase.title}</h3>
              </div>
              <p className="pl-8 text-xs text-text-muted">
                {phase.modules.length} module{phase.modules.length === 1 ? "" : "s"}
              </p>
            </Card>
          </motion.div>
        ))}
      </div>

      {phases.length === 0 && meta && (
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <Sparkles className="size-3.5" />
          Building phase 1…
        </div>
      )}
    </div>
  );
}
