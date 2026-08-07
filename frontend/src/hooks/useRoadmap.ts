import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { dashboardKey } from "@/hooks/useDashboard";
import { getProgress, getRoadmap, toggleModule } from "@/services/api/roadmap";

export const roadmapKey = (trackId: number) => ["roadmap", trackId] as const;
export const progressKey = (trackId: number) => ["progress", trackId] as const;

// retry: false on both reads below — a 404 here means "not generated yet",
// a real, expected state RoadmapPage checks for (roadmapMissing) to decide
// whether to start streaming. Retrying doesn't turn a 404 into a 200, and
// the default retry:1 was observed to leave the query's fetchStatus stuck
// at "paused" indefinitely in this dev environment instead of settling into
// "error", which meant roadmapMissing never became true and generation
// never auto-started.
export function useRoadmap(trackId: number | null) {
  return useQuery({
    queryKey: roadmapKey(trackId ?? -1),
    queryFn: () => getRoadmap(trackId as number),
    enabled: trackId !== null,
    retry: false,
  });
}

export function useProgress(trackId: number | null) {
  return useQuery({
    queryKey: progressKey(trackId ?? -1),
    queryFn: () => getProgress(trackId as number),
    enabled: trackId !== null,
    retry: false,
  });
}

export function useToggleModule(trackId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ moduleId, completed }: { moduleId: number; completed: boolean }) =>
      toggleModule(moduleId, completed),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: roadmapKey(trackId) });
      queryClient.invalidateQueries({ queryKey: progressKey(trackId) });
      queryClient.invalidateQueries({ queryKey: dashboardKey });
    },
  });
}
