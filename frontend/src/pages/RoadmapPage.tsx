import { useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw } from "lucide-react";
import { useEffect } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { TopBar } from "@/components/layout/TopBar";
import { GeneratingRoadmap } from "@/components/roadmap/GeneratingRoadmap";
import { PhaseCard } from "@/components/roadmap/PhaseCard";
import { ProgressRing } from "@/components/roadmap/ProgressRing";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useActiveTrack } from "@/hooks/useProfile";
import { roadmapKey, useRoadmap, useToggleModule } from "@/hooks/useRoadmap";
import { useRoadmapStream } from "@/hooks/useRoadmapStream";
import { ApiError } from "@/services/api/client";

export default function RoadmapPage() {
  const { data: track, isPending: trackPending } = useActiveTrack();
  const trackId = track?.id ?? null;
  const roadmapQuery = useRoadmap(trackId);
  const stream = useRoadmapStream();
  const queryClient = useQueryClient();
  const toggleModule = useToggleModule(trackId ?? -1);

  const roadmapMissing =
    roadmapQuery.error instanceof ApiError && roadmapQuery.error.code === "roadmap_not_found";

  useEffect(() => {
    if (trackId !== null && roadmapMissing && stream.state.status === "idle") {
      stream.start(trackId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trackId, roadmapMissing]);

  useEffect(() => {
    if (stream.state.status === "done" && trackId !== null) {
      queryClient.invalidateQueries({ queryKey: roadmapKey(trackId) });
    }
  }, [stream.state.status, trackId, queryClient]);

  if (trackPending) {
    return (
      <AppShell>
        <div className="grid place-items-center py-24">
          <Loader2 className="size-6 animate-spin text-text-muted" />
        </div>
      </AppShell>
    );
  }

  if (!track) {
    return (
      <AppShell>
        <TopBar title="Roadmap" subtitle="Pick a track from the dashboard first." />
      </AppShell>
    );
  }

  if (stream.state.status === "streaming" || stream.state.status === "done") {
    return (
      <AppShell>
        <TopBar title={`${track.topic} roadmap`} subtitle="Generating your personalized plan…" />
        <GeneratingRoadmap
          meta={stream.state.status === "streaming" ? stream.state.meta : null}
          phases={stream.state.status === "streaming" ? stream.state.phases : []}
        />
      </AppShell>
    );
  }

  if (stream.state.status === "error") {
    return (
      <AppShell>
        <TopBar title={`${track.topic} roadmap`} />
        <Card className="space-y-3">
          <p className="text-sm text-text-primary">{stream.state.message}</p>
          <Button size="sm" onClick={() => stream.start(track.id)}>
            <RefreshCw className="size-4" /> Try again
          </Button>
        </Card>
      </AppShell>
    );
  }

  if (roadmapQuery.isPending || !roadmapQuery.data) {
    return (
      <AppShell>
        <div className="grid place-items-center py-24">
          <Loader2 className="size-6 animate-spin text-text-muted" />
        </div>
      </AppShell>
    );
  }

  const roadmap = roadmapQuery.data;

  return (
    <AppShell>
      <TopBar title={roadmap.title} subtitle={roadmap.summary} />

      <div className="mb-6 flex items-center gap-6 rounded-xl border border-line bg-surface p-5">
        <ProgressRing percent={roadmap.progress.completion_pct} />
        <div>
          <p className="text-sm font-medium text-text-primary">
            {roadmap.progress.completed_modules} of {roadmap.progress.total_modules} modules
            complete
          </p>
          <p className="mt-1 text-xs text-text-secondary">
            {roadmap.total_weeks} weeks · ~{roadmap.weekly_hours}h/week
          </p>
          {roadmap.progress.current_phase_title && (
            <p className="mt-1 text-xs text-accent">
              Currently on: {roadmap.progress.current_phase_title}
            </p>
          )}
        </div>
      </div>

      <div className="space-y-3">
        {roadmap.phases.map((phase, index) => {
          const phaseProgress = roadmap.progress.phases[index];
          return (
            <PhaseCard
              key={phase.id}
              phase={phase}
              completionPct={phaseProgress?.completion_pct ?? 0}
              unlocked={phaseProgress?.unlocked ?? true}
              isCurrent={index === roadmap.progress.current_phase_index}
              onToggleModule={(moduleId, completed) =>
                toggleModule.mutate({ moduleId, completed })
              }
              togglingModuleId={
                toggleModule.isPending ? (toggleModule.variables?.moduleId ?? null) : null
              }
            />
          );
        })}
      </div>

      {roadmap.final_project && (
        <Card className="mt-6 space-y-2 border-accent/30">
          <h3 className="text-sm font-semibold text-accent">
            Capstone: {roadmap.final_project.title}
          </h3>
          <p className="text-sm text-text-secondary">{roadmap.final_project.description}</p>
        </Card>
      )}
    </AppShell>
  );
}
