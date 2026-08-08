import { useEffect, useRef, useState } from "react";

import {
  initialSustainState,
  isLookingAway,
  matrixToEuler,
  trackSustain,
  type SustainState,
} from "@/lib/proctorRules";
import type { ProctoringEventType } from "@/types";

export type CameraStatus = "pending" | "ready" | "unavailable";

interface FaceLandmarkerLike {
  detectForVideo(video: HTMLVideoElement, timestamp: number): {
    faceLandmarks?: unknown[];
    facialTransformationMatrixes?: Array<{ data: number[] }>;
  };
  close?: () => void;
}

export function useProctoring(
  active: boolean,
  armed: boolean,
  onWarning: (type: ProctoringEventType, detail: string) => void,
) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const landmarkerRef = useRef<FaceLandmarkerLike | null>(null);
  const warningRef = useRef(onWarning);
  const [cameraStatus, setCameraStatus] = useState<CameraStatus>("pending");
  const [faceCount, setFaceCount] = useState(0);

  useEffect(() => {
    warningRef.current = onWarning;
  }, [onWarning]);

  useEffect(() => {
    if (!active) {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      landmarkerRef.current?.close?.();
      landmarkerRef.current = null;
      setCameraStatus("pending");
      setFaceCount(0);
      return;
    }

    let cancelled = false;
    let animationFrame = 0;
    let lastFrameAt = 0;
    let awayState: SustainState = initialSustainState();
    let noFaceState: SustainState = initialSustainState();
    let multipleFaceState: SustainState = initialSustainState();

    const loadLandmarker = async () => {
      try {
        const vision = await import("@mediapipe/tasks-vision");
        const fileset = await vision.FilesetResolver.forVisionTasks("/wasm");
        let landmarker: FaceLandmarkerLike;
        try {
          landmarker = await vision.FaceLandmarker.createFromOptions(fileset, {
            baseOptions: { modelAssetPath: "/models/face_landmarker.task", delegate: "GPU" },
            runningMode: "VIDEO",
            numFaces: 2,
            outputFacialTransformationMatrixes: true,
          });
        } catch {
          landmarker = await vision.FaceLandmarker.createFromOptions(fileset, {
            baseOptions: { modelAssetPath: "/models/face_landmarker.task", delegate: "CPU" },
            runningMode: "VIDEO",
            numFaces: 2,
            outputFacialTransformationMatrixes: true,
          });
        }
        if (cancelled) {
          landmarker.close?.();
          return;
        }
        landmarkerRef.current = landmarker;
      } catch {
        if (!cancelled) setCameraStatus("unavailable");
      }
    };

    const start = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play().catch(() => undefined);
        }
        setCameraStatus("ready");
        await loadLandmarker();
      } catch {
        if (!cancelled) setCameraStatus("unavailable");
      }
    };

    const tick = (now: number) => {
      if (cancelled) return;
      if (now - lastFrameAt >= 100 && landmarkerRef.current && videoRef.current) {
        lastFrameAt = now;
        const result = landmarkerRef.current.detectForVideo(videoRef.current, now);
        const count = result.faceLandmarks?.length ?? 0;
        setFaceCount(count);
        const away = result.facialTransformationMatrixes?.[0]?.data
          ? isLookingAway(matrixToEuler(result.facialTransformationMatrixes[0].data))
          : false;
        const awayResult = trackSustain(awayState, away, now, 2500, 10000);
        awayState = awayResult.state;
        if (armed && awayResult.fired) warningRef.current("looking_away", "Head pose exceeded the allowed threshold.");

        const noFaceResult = trackSustain(noFaceState, count === 0, now, 4000, 10000);
        noFaceState = noFaceResult.state;
        if (armed && noFaceResult.fired) warningRef.current("no_face", "No face was visible for four seconds.");

        const multipleResult = trackSustain(multipleFaceState, count >= 2, now, 1500, 0);
        multipleFaceState = multipleResult.state;
        if (armed && multipleResult.fired) warningRef.current("multiple_faces", `${count} faces detected.`);
      }
      animationFrame = requestAnimationFrame(tick);
    };

    void start();
    animationFrame = requestAnimationFrame(tick);
    return () => {
      cancelled = true;
      cancelAnimationFrame(animationFrame);
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      landmarkerRef.current?.close?.();
      landmarkerRef.current = null;
    };
  }, [active, armed]);

  return { videoRef, cameraStatus, faceCount };
}
