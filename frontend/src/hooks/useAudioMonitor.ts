import { useCallback, useEffect, useRef, useState } from "react";

import { initialSustainState, trackSustain, type SustainState } from "@/lib/proctorRules";
import type { ProctoringEventType } from "@/types";

const SAMPLE_INTERVAL_MS = 50;
const CALIBRATION_DURATION_MS = 3000;
const EXCESSIVE_NOISE_DELTA_DB = 18;
const EXCESSIVE_NOISE_SUSTAIN_MS = 3000;
const EXCESSIVE_NOISE_COOLDOWN_MS = 10000;
const BACKGROUND_VOICE_SUSTAIN_MS = 3000;
const BACKGROUND_VOICE_COOLDOWN_MS = 10000;
const SPEECH_BAND_LOW_HZ = 300;
const SPEECH_BAND_HIGH_HZ = 3400;
const SPEECH_BAND_PRESENCE_THRESHOLD = 30;

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
  const armedRef = useRef(armed);
  const answeringRef = useRef(answering);
  const sttSupportedRef = useRef(sttSupported);
  const contextRef = useRef<AudioContext | null>(null);
  const transcriptLengthRef = useRef(transcript.length);
  const transcriptGrowthAtRef = useRef(0);

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
    if (answering && !answeringRef.current) {
      transcriptLengthRef.current = transcript.length;
      transcriptGrowthAtRef.current = performance.now();
    }
  }, [answering, transcript]);
  useEffect(() => {
    armedRef.current = armed;
    answeringRef.current = answering;
    sttSupportedRef.current = sttSupported;
  }, [armed, answering, sttSupported]);

  const resume = useCallback(() => {
    void contextRef.current?.resume().catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!active) {
      setMicStatus("pending");
      statusRef.current = "pending";
      contextRef.current = null;
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
      if (now - lastSampleAt < SAMPLE_INTERVAL_MS) {
        raf = requestAnimationFrame(tick);
        return;
      }
      lastSampleAt = now;
      const level = rmsDb();
      if (statusRef.current !== "ready") noiseSamples.push(level);
      if (armedRef.current && statusRef.current === "ready") {
        const excessive = !answeringRef.current && level > noiseFloor + EXCESSIVE_NOISE_DELTA_DB;
        const excessiveResult = trackSustain(
          excessiveState,
          excessive,
          now,
          EXCESSIVE_NOISE_SUSTAIN_MS,
          EXCESSIVE_NOISE_COOLDOWN_MS,
        );
        excessiveState = excessiveResult.state;
        if (excessiveResult.fired) warningRef.current("excessive_noise", `Audio level ${level.toFixed(1)} dB.`);

        if (sttSupportedRef.current && answeringRef.current && analyser && context) {
          const frequencyData = new Uint8Array(analyser.frequencyBinCount);
          analyser.getByteFrequencyData(frequencyData);
          const binHz = context.sampleRate / analyser.fftSize;
          const startBin = Math.floor(SPEECH_BAND_LOW_HZ / binHz);
          const endBin = Math.min(frequencyData.length - 1, Math.ceil(SPEECH_BAND_HIGH_HZ / binHz));
          let speechBandSum = 0;
          for (let index = startBin; index <= endBin; index += 1) speechBandSum += frequencyData[index];
          const speechBandAverage = speechBandSum / Math.max(1, endBin - startBin + 1);

          if (transcriptRef.current.length !== transcriptLengthRef.current) {
            transcriptLengthRef.current = transcriptRef.current.length;
            transcriptGrowthAtRef.current = now;
          }
          const transcriptStalled = now - transcriptGrowthAtRef.current >= BACKGROUND_VOICE_SUSTAIN_MS;
          const voice = speechBandAverage > SPEECH_BAND_PRESENCE_THRESHOLD && transcriptStalled;
          const voiceResult = trackSustain(
            voiceState,
            voice,
            now,
            BACKGROUND_VOICE_SUSTAIN_MS,
            BACKGROUND_VOICE_COOLDOWN_MS,
          );
          voiceState = voiceResult.state;
          if (voiceResult.fired) warningRef.current("background_voice", "Speech-band energy detected without matching speech recognition output.");
        } else {
          voiceState = initialSustainState();
        }
      }
      raf = requestAnimationFrame(tick);
    };

    const start = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        context = new AudioContext();
        contextRef.current = context;
        // Permission is requested asynchronously, so the context can be
        // created after the user's click and start suspended. Resume it here
        // or the analyser will only observe silence.
        if (context.state === "suspended") await context.resume();
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
        }, CALIBRATION_DURATION_MS);
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
      contextRef.current = null;
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, [active]);

  return { micStatus, resume };
}
