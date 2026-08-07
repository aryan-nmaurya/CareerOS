import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { dashboardKey } from "@/hooks/useDashboard";
import { getProgress, getRoadmap, toggleModule } from "@/services/api/roadmap";

export const roadmapKey = (trackId: number) => ["roadmap", trackId] as const;
export const progressKey = (trackId: number) => ["progress", trackId] as const;

export function useRoadmap(trackId: number | null) {
  return useQuery({
    queryKey: roadmapKey(trackId ?? -1),
    queryFn: () => getRoadmap(trackId as number),
    enabled: trackId !== null,
  });
}

export function useProgress(trackId: number | null) {
  return useQuery({
    queryKey: progressKey(trackId ?? -1),
    queryFn: () => getProgress(trackId as number),
    enabled: trackId !== null,
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
