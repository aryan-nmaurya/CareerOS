import { api } from "@/services/api/client";
import { sseFetch } from "@/services/api/sse";
import type { Progress, Roadmap, RoadmapModule } from "@/types";

export function streamRoadmap(trackId: number) {
  return sseFetch(`/api/tracks/${trackId}/roadmap/stream`, { method: "POST" });
}

export const getRoadmap = (trackId: number) => api<Roadmap>(`/api/tracks/${trackId}/roadmap`);

export const toggleModule = (moduleId: number, completed: boolean) =>
  api<{ module: RoadmapModule; progress: Progress }>(`/api/modules/${moduleId}`, {
    method: "PATCH",
    body: JSON.stringify({ completed }),
  });

export const getProgress = (trackId: number) => api<Progress>(`/api/tracks/${trackId}/progress`);
