import type { Ref } from "react";

import type { CameraStatus } from "@/hooks/useProctoring";
import { cn } from "@/lib/cn";

export function CameraPip({ videoRef, cameraStatus, faceCount, preflight = false }: { videoRef: Ref<HTMLVideoElement>; cameraStatus: CameraStatus; faceCount: number; preflight?: boolean }) {
  if (cameraStatus !== "ready") return null;
  const ring = faceCount === 1 ? "ring-success" : faceCount === 0 ? "ring-warning" : "ring-danger";
  return <div className={cn(
    preflight
      ? "mx-auto mb-4 aspect-video w-full max-w-xl overflow-hidden rounded-lg bg-surface-hover shadow-lg ring-2"
      : "fixed bottom-20 right-4 z-40 h-28 w-40 overflow-hidden rounded-lg bg-surface-hover shadow-lg ring-2 md:bottom-6 md:right-6",
    ring,
  )}>
    <video ref={videoRef} autoPlay muted playsInline className="h-full w-full -scale-x-100 object-cover" />
  </div>;
}
