import { Loader2, Mic, Video } from "lucide-react";
import type { RefObject } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import type { MicStatus } from "@/hooks/useAudioMonitor";
import type { CameraStatus } from "@/hooks/useProctoring";
import { cn } from "@/lib/cn";

interface Props {
  videoRef: RefObject<HTMLVideoElement | null>;
  cameraStatus: CameraStatus;
  faceCount: number;
  micStatus: MicStatus;
  ready: boolean;
  onContinue: () => void;
}

export function PreflightCheck({ videoRef, cameraStatus, faceCount, micStatus, ready, onContinue }: Props) {
  const cameraOk = cameraStatus === "ready" && faceCount === 1;
  const micOk = micStatus === "ready";
  return (
    <Card className="mx-auto max-w-xl space-y-4">
      <CardTitle>Interview preflight</CardTitle>
      <CardDescription>
        Allow camera and microphone access. We process the camera locally and use it only to verify
        that the interview has one visible candidate.
      </CardDescription>
      <div className="overflow-hidden rounded-lg bg-surface-hover">
        <video ref={videoRef} autoPlay muted playsInline className="aspect-video w-full -scale-x-100 object-cover" />
      </div>
      <div className="space-y-2 text-sm">
        <div className="flex items-center gap-2">
          <Video className={cn("size-4", cameraOk ? "text-success" : "text-text-muted")} />
          <span>{cameraStatus === "pending" ? "Requesting camera access…" : cameraStatus === "unavailable" ? "Camera unavailable" : faceCount === 1 ? "One face detected" : faceCount === 0 ? "No face detected" : "Multiple faces detected"}</span>
        </div>
        <div className="flex items-center gap-2">
          <Mic className={cn("size-4", micOk ? "text-success" : "text-text-muted")} />
          <span>{micStatus === "pending" ? "Requesting microphone access…" : micStatus === "calibrating" ? "Calibrating noise floor…" : micStatus === "unavailable" ? "Microphone unavailable" : "Microphone ready"}</span>
          {micStatus === "calibrating" && <Loader2 className="size-3 animate-spin" />}
        </div>
      </div>
      <Button onClick={onContinue} disabled={!ready}>Continue to briefing</Button>
    </Card>
  );
}
