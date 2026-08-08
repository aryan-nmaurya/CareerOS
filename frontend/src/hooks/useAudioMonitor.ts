import { useEffect, useRef, useState } from "react";

import { initialSustainState, trackSustain, type SustainState } from "@/lib/proctorRules";
import type { ProctoringEventType } from "@/types";

export type MicStatus = "pending" | "calibrating" | "ready" | "unavailable";

export function useAudioMonitor(
  active: boolean,
  armed: boolean,
  answering: boolean,
  sttSupported: boolean,
  transcript: string,
  onWarning: (type: ProctoringEventType, detail: string) => void,
) {
  const [micStatus, setMicStatus] = useState<MicStatus>("pending");
  const statusRef = useRef<MicStatus>("pending");
  const warningRef = useRef(onWarning);
  const transcriptRef = useRef(transcript);

  useEffect(() => {
    warningRef.current = onWarning;
  }, [onWarning]);
  useEffect(() => {
    statusRef.current = micStatus;
  }, [micStatus]);
  useEffect(() => {
    transcriptRef.current = transcript;
  }, [transcript]);

  useEffect(() => {
    if (!active) {
      setMicStatus("pending");
      statusRef.current = "pending";
      return;
    }

    let cancelled = false;
    let raf = 0;
    let calibrationTimer = 0;
    let source: MediaStreamAudioSourceNode | null = null;
    let context: AudioContext | null = null;
    let stream: MediaStream | null = null;
    let analyser: AnalyserNode | null = null;
    let noiseFloor = -60;
    let lastSampleAt = -Infinity;
    let noiseSamples: number[] = [];
    let excessiveState: SustainState = initialSustainState();
    let voiceState: SustainState = initialSustainState();

    const rmsDb = () => {
      if (!analyser) return -60;
      const data = new Float32Array(analyser.fftSize);
      analyser.getFloatTimeDomainData(data);
      let sum = 0;
      for (const sample of data) sum += sample * sample;
      return 20 * Math.log10(Math.sqrt(sum / data.length) || 0.00001);
    };

    const tick = (now: number) => {
      if (cancelled || !analyser) return;
      if (now - lastSampleAt < 50) {
        raf = requestAnimationFrame(tick);
        return;
      }
      lastSampleAt = now;
      const level = rmsDb();
      if (statusRef.current !== "ready") noiseSamples.push(level);
      if (armed && statusRef.current === "ready") {
        const excessive = !answering && level > noiseFloor + 18;
        const voice = answering && sttSupported && level > noiseFloor + 8 && !transcriptRef.current.trim();
        const excessiveResult = trackSustain(excessiveState, excessive, now, 3000, 10000);
        excessiveState = excessiveResult.state;
        if (excessiveResult.fired) warningRef.current("excessive_noise", `Audio level ${level.toFixed(1)} dB.`);
        const voiceResult = trackSustain(voiceState, voice, now, 3000, 10000);
        voiceState = voiceResult.state;
        if (voiceResult.fired) warningRef.current("background_voice", "Speech-band energy detected outside the active transcript.");
      }
      raf = requestAnimationFrame(tick);
    };

    const start = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        context = new AudioContext();
        source = context.createMediaStreamSource(stream);
        analyser = context.createAnalyser();
        analyser.fftSize = 512;
        source.connect(analyser);
        setMicStatus("calibrating");
        calibrationTimer = window.setTimeout(() => {
          if (cancelled) return;
          noiseFloor = noiseSamples.length
            ? noiseSamples.reduce((sum, value) => sum + value, 0) / noiseSamples.length
            : -60;
          setMicStatus("ready");
          statusRef.current = "ready";
        }, 3000);
        raf = requestAnimationFrame(tick);
      } catch {
        if (!cancelled) setMicStatus("unavailable");
      }
    };

    void start();
    return () => {
      cancelled = true;
      window.clearTimeout(calibrationTimer);
      cancelAnimationFrame(raf);
      source?.disconnect();
      analyser?.disconnect();
      void context?.close();
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, [active, armed, answering, sttSupported]);

  return { micStatus };
}
