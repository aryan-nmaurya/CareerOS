import type { RefObject } from "react";

import type { CameraStatus } from "@/hooks/useProctoring";
import { cn } from "@/lib/cn";

export function CameraPip({ videoRef, cameraStatus, faceCount }: { videoRef: RefObject<HTMLVideoElement | null>; cameraStatus: CameraStatus; faceCount: number }) {
  if (cameraStatus !== "ready") return null;
  const ring = faceCount === 1 ? "ring-success" : faceCount === 0 ? "ring-warning" : "ring-danger";
  return <div className={cn("fixed bottom-20 right-4 z-40 h-28 w-40 overflow-hidden rounded-lg bg-surface-hover shadow-lg ring-2 md:bottom-6 md:right-6", ring)}>
    <video ref={videoRef} autoPlay muted playsInline className="h-full w-full -scale-x-100 object-cover" />
  </div>;
}
