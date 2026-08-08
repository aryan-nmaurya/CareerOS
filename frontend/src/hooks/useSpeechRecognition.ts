import { useCallback, useRef, useState } from "react";

function getSpeechRecognitionCtor(): (new () => SpeechRecognition) | null {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

export function useSpeechRecognition() {
  const [transcript, setTranscript] = useState("");
  const [listening, setListening] = useState(false);
  const [supported, setSupported] = useState(getSpeechRecognitionCtor() !== null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const shouldListenRef = useRef(false);
  const listeningRef = useRef(false);

  const start = useCallback(() => {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) {
      setSupported(false);
      return;
    }
    if (listeningRef.current) return;

    setTranscript("");
    const recognition = new Ctor();
    shouldListenRef.current = true;
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.onresult = (event) => {
      let combined = "";
      for (let i = 0; i < event.results.length; i++) {
        combined += event.results[i][0].transcript;
      }
      setTranscript(combined);
    };
    recognition.onerror = (event) => {
      // `no-speech` and `aborted` are normal browser events. Only permission
      // and service errors mean this browser cannot provide speech input.
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        shouldListenRef.current = false;
        setSupported(false);
      }
      setListening(false);
      listeningRef.current = false;
    };
    recognition.onstart = () => {
      setListening(true);
      listeningRef.current = true;
    };
    recognition.onend = () => {
      setListening(false);
      listeningRef.current = false;
      if (recognitionRef.current === recognition) recognitionRef.current = null;
      // Chrome can end a continuous recognition session after a pause. Keep
      // listening while the answer phase is active instead of losing the mic.
      if (shouldListenRef.current) {
        window.setTimeout(() => {
          if (shouldListenRef.current) start();
        }, 250);
      }
    };
    recognitionRef.current = recognition;
    try {
      recognition.start();
    } catch {
      listeningRef.current = false;
      setListening(false);
    }
  }, []);

  const stop = useCallback(() => {
    shouldListenRef.current = false;
    try {
      recognitionRef.current?.stop();
    } catch {
      // The browser may already have ended the recognition session.
    }
    recognitionRef.current = null;
    listeningRef.current = false;
    setListening(false);
  }, []);

  return { start, stop, transcript, listening, supported };
}
