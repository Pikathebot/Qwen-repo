"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  armFollowUpApi,
  listenChunkApi,
  sayApi,
  setVoiceStateApi,
  startHandsFreeApi,
  stopHandsFreeApi,
} from "@/lib/api";
import { VoiceState } from "@/lib/types";

/**
 * Hands-free voice loop.
 *
 * The browser owns the microphone; the backend owns the meaning of what it
 * hears. This hook does voice-activity detection locally so only whole
 * utterances are uploaded, then defers the "was that addressed to me?"
 * question to /api/voice/listen.
 */

export interface UseVoiceOptions {
  sessionId: string;
  /** Called with a request that Jarvis should actually answer. */
  onCommand: (query: string) => void;
  /** Silence, in ms, that ends an utterance. */
  silenceMs?: number;
  /** Hard cap on a single utterance so latency stays bounded. */
  maxUtteranceMs?: number;
  /** RMS level (0-1) above which we consider the user to be speaking. */
  speechThreshold?: number;
}

export interface UseVoiceReturn {
  isSupported: boolean;
  isActive: boolean;
  state: VoiceState;
  level: number;
  transcript: string;
  spokenText: string;
  error: string | null;
  start: () => Promise<void>;
  stop: () => void;
  toggle: () => Promise<void>;
  speak: (text: string) => Promise<void>;
  stopSpeaking: () => void;
  pushToTalk: () => Promise<void>;
  clearError: () => void;
}

const ANALYSER_FFT_SIZE = 512;
const LEVEL_POLL_MS = 80;
/** Sustained speech while Jarvis talks counts as an interruption. */
const BARGE_IN_MS = 240;
/** Ignore blobs too short to contain speech. */
const MIN_UTTERANCE_MS = 320;

export function useVoice({
  sessionId,
  onCommand,
  silenceMs = 850,
  maxUtteranceMs = 12000,
  speechThreshold = 0.045,
}: UseVoiceOptions): UseVoiceReturn {
  const [isSupported, setIsSupported] = useState(false);
  const [isActive, setIsActive] = useState(false);
  const [state, setState] = useState<VoiceState>("idle");
  const [level, setLevel] = useState(0);
  const [transcript, setTranscript] = useState("");
  const [spokenText, setSpokenText] = useState("");
  const [error, setError] = useState<string | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const pollTimerRef = useRef<number | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const speakingSinceRef = useRef<number>(0);
  const silenceSinceRef = useRef<number>(0);
  const utteranceStartedRef = useRef<number>(0);
  const playbackRef = useRef<HTMLAudioElement | null>(null);
  const stateRef = useRef<VoiceState>("idle");
  const activeRef = useRef(false);
  // Keeps the latest callback without restarting the audio graph.
  const onCommandRef = useRef(onCommand);
  const sessionIdRef = useRef(sessionId);

  useEffect(() => {
    onCommandRef.current = onCommand;
  }, [onCommand]);

  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  useEffect(() => {
    setIsSupported(
      typeof window !== "undefined" &&
        typeof navigator !== "undefined" &&
        !!navigator.mediaDevices?.getUserMedia &&
        typeof MediaRecorder !== "undefined"
    );
  }, []);

  const applyState = useCallback((next: VoiceState) => {
    stateRef.current = next;
    setState(next);
  }, []);

  const reportState = useCallback(
    (next: VoiceState) => {
      applyState(next);
      void setVoiceStateApi(sessionIdRef.current, next).catch(() => {
        /* state reporting is advisory; the loop keeps running */
      });
    },
    [applyState]
  );

  // ------------------------------------------------------------- playback

  const stopSpeaking = useCallback(() => {
    const player = playbackRef.current;
    if (player) {
      player.pause();
      player.src = "";
      playbackRef.current = null;
    }
    if (stateRef.current === "speaking") {
      applyState(activeRef.current ? "listening" : "idle");
    }
  }, [applyState]);

  // ------------------------------------------------------------ recording

  const uploadUtterance = useCallback(
    async (blob: Blob) => {
      try {
        const result = await listenChunkApi(blob, sessionIdRef.current);

        if (result.transcript) {
          setTranscript(result.transcript);
        }

        if (result.speak_immediately) {
          await speakInternal(result.speak_immediately);
        }

        if (result.should_respond && result.query) {
          applyState("thinking");
          onCommandRef.current(result.query);
        } else if (activeRef.current && stateRef.current !== "speaking") {
          applyState(result.session.armed ? "armed" : "listening");
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Voice upload failed");
        if (activeRef.current) applyState("listening");
      }
    },
    // speakInternal is defined below and stable via ref indirection
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [applyState]
  );

  const speakInternalRef = useRef<(text: string) => Promise<void>>(async () => {});

  const speakInternal = useCallback(async (text: string) => {
    return speakInternalRef.current(text);
  }, []);

  useEffect(() => {
    speakInternalRef.current = async (text: string) => {
      if (!text.trim()) return;
      stopSpeaking();

      let result;
      try {
        result = await sayApi(text, sessionIdRef.current);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Speech synthesis failed");
        if (activeRef.current) applyState("listening");
        return;
      }

      setSpokenText(result.spoken_text);

      if (!result.audio_base64) {
        // No audio (engine unavailable) - still hand control back to the mic.
        if (activeRef.current) {
          await armFollowUpApi(sessionIdRef.current).catch(() => null);
          applyState("armed");
        }
        return;
      }

      const player = new Audio(
        `data:${result.audio_mime || "audio/mpeg"};base64,${result.audio_base64}`
      );
      playbackRef.current = player;
      applyState("speaking");

      player.onended = () => {
        playbackRef.current = null;
        if (activeRef.current) {
          void armFollowUpApi(sessionIdRef.current).catch(() => null);
          applyState("armed");
        } else {
          applyState("idle");
        }
      };
      player.onerror = () => {
        playbackRef.current = null;
        if (activeRef.current) applyState("listening");
      };

      try {
        await player.play();
      } catch {
        // Autoplay refused; treat it as finished rather than hanging.
        playbackRef.current = null;
        if (activeRef.current) applyState("listening");
      }
    };
  }, [applyState, stopSpeaking]);

  const finishUtterance = useCallback(() => {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === "inactive") return;
    recorder.stop();
  }, []);

  const beginUtterance = useCallback(() => {
    const stream = streamRef.current;
    if (!stream || recorderRef.current) return;

    let recorder: MediaRecorder;
    try {
      recorder = new MediaRecorder(stream);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Recorder unavailable");
      return;
    }

    chunksRef.current = [];
    utteranceStartedRef.current = Date.now();

    recorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) chunksRef.current.push(event.data);
    };
    recorder.onstop = () => {
      const elapsed = Date.now() - utteranceStartedRef.current;
      const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
      chunksRef.current = [];
      recorderRef.current = null;

      if (blob.size > 0 && elapsed >= MIN_UTTERANCE_MS) {
        void uploadUtterance(blob);
      } else if (activeRef.current && stateRef.current !== "speaking") {
        applyState("listening");
      }
    };

    recorderRef.current = recorder;
    recorder.start();
  }, [applyState, uploadUtterance]);

  // -------------------------------------------------------- level polling

  const pollLevel = useCallback(() => {
    const analyser = analyserRef.current;
    if (!analyser) return;

    const buffer = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(buffer);

    let sumSquares = 0;
    for (let i = 0; i < buffer.length; i += 1) {
      const centered = (buffer[i] - 128) / 128;
      sumSquares += centered * centered;
    }
    const rms = Math.sqrt(sumSquares / buffer.length);
    setLevel(rms);

    const now = Date.now();
    const isSpeech = rms >= speechThreshold;

    if (isSpeech) {
      silenceSinceRef.current = 0;
      if (!speakingSinceRef.current) speakingSinceRef.current = now;
    } else {
      speakingSinceRef.current = 0;
      if (!silenceSinceRef.current) silenceSinceRef.current = now;
    }

    // Barge-in: talking over a reply cuts it off immediately.
    if (
      stateRef.current === "speaking" &&
      speakingSinceRef.current &&
      now - speakingSinceRef.current >= BARGE_IN_MS
    ) {
      stopSpeaking();
      reportState("listening");
      return;
    }

    if (stateRef.current === "speaking" || stateRef.current === "thinking") return;

    if (!recorderRef.current) {
      if (isSpeech) beginUtterance();
      return;
    }

    const tooLong = now - utteranceStartedRef.current >= maxUtteranceMs;
    const silentLongEnough =
      silenceSinceRef.current > 0 && now - silenceSinceRef.current >= silenceMs;

    if (tooLong || silentLongEnough) {
      finishUtterance();
    }
  }, [
    beginUtterance,
    finishUtterance,
    maxUtteranceMs,
    reportState,
    silenceMs,
    speechThreshold,
    stopSpeaking,
  ]);

  // ------------------------------------------------------------ lifecycle

  const teardown = useCallback(() => {
    if (pollTimerRef.current !== null) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.onstop = null;
      recorderRef.current.stop();
    }
    recorderRef.current = null;
    chunksRef.current = [];

    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;

    void audioContextRef.current?.close().catch(() => null);
    audioContextRef.current = null;
    analyserRef.current = null;

    stopSpeaking();
    setLevel(0);
  }, [stopSpeaking]);

  const stop = useCallback(() => {
    activeRef.current = false;
    setIsActive(false);
    teardown();
    applyState("idle");
    void stopHandsFreeApi(sessionIdRef.current).catch(() => null);
  }, [applyState, teardown]);

  const start = useCallback(async () => {
    if (activeRef.current) return;
    setError(null);

    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Microphone capture is not available in this environment.");
      return;
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
    } catch (e) {
      setError(
        e instanceof Error && e.name === "NotAllowedError"
          ? "Microphone permission denied."
          : "Could not open the microphone."
      );
      return;
    }

    streamRef.current = stream;

    const AudioContextCtor =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const context = new AudioContextCtor();
    const analyser = context.createAnalyser();
    analyser.fftSize = ANALYSER_FFT_SIZE;
    context.createMediaStreamSource(stream).connect(analyser);

    audioContextRef.current = context;
    analyserRef.current = analyser;
    silenceSinceRef.current = 0;
    speakingSinceRef.current = 0;

    activeRef.current = true;
    setIsActive(true);
    applyState("listening");
    await startHandsFreeApi(sessionIdRef.current).catch(() => null);

    pollTimerRef.current = window.setInterval(pollLevel, LEVEL_POLL_MS);
  }, [applyState, pollLevel]);

  const toggle = useCallback(async () => {
    if (activeRef.current) {
      stop();
    } else {
      await start();
    }
  }, [start, stop]);

  /** Capture one request without needing the wake word. */
  const pushToTalk = useCallback(async () => {
    if (!activeRef.current) await start();
    await armFollowUpApi(sessionIdRef.current).catch(() => null);
    applyState("armed");
  }, [applyState, start]);

  useEffect(() => teardown, [teardown]);

  return {
    isSupported,
    isActive,
    state,
    level,
    transcript,
    spokenText,
    error,
    start,
    stop,
    toggle,
    speak: speakInternal,
    stopSpeaking,
    pushToTalk,
    clearError: useCallback(() => setError(null), []),
  };
}
