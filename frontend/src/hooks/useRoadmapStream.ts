import { useCallback, useRef, useState } from "react";

import { streamRoadmap } from "@/services/api/roadmap";
import type { RoadmapMeta, StreamPhase } from "@/types";

type StreamState =
  | { status: "idle" }
  | { status: "streaming"; meta: RoadmapMeta | null; phases: StreamPhase[] }
  | { status: "done"; roadmapId: number }
  | { status: "error"; code: string; message: string };

export function useRoadmapStream() {
  const [state, setState] = useState<StreamState>({ status: "idle" });
  const runningRef = useRef(false);

  const start = useCallback(async (trackId: number) => {
    if (runningRef.current) return;
    runningRef.current = true;
    setState({ status: "streaming", meta: null, phases: [] });

    try {
      for await (const { event, data } of streamRoadmap(trackId)) {
        if (event === "meta") {
          setState((prev) =>
            prev.status === "streaming" ? { ...prev, meta: data as RoadmapMeta } : prev,
          );
        } else if (event === "phase") {
          setState((prev) =>
            prev.status === "streaming"
              ? { ...prev, phases: [...prev.phases, data as StreamPhase] }
              : prev,
          );
        } else if (event === "done") {
          setState({ status: "done", roadmapId: (data as { roadmap_id: number }).roadmap_id });
        } else if (event === "error") {
          const err = data as { code: string; message: string };
          setState({ status: "error", code: err.code, message: err.message });
        }
      }
    } catch (error) {
      setState({
        status: "error",
        code: "network_error",
        message: error instanceof Error ? error.message : "Connection lost.",
      });
    } finally {
      runningRef.current = false;
    }
  }, []);

  return { state, start };
}
