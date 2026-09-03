"use client";

import React from "react";
import { VoiceState } from "@/lib/types";

interface VoiceOrbProps {
  isActive: boolean;
  isSupported: boolean;
  state: VoiceState;
  level: number;
  transcript: string;
  spokenText: string;
  error: string | null;
  onToggle: () => void;
  onStopSpeaking: () => void;
}

const STATE_COPY: Record<VoiceState, { label: string; hint: string }> = {
  idle: { label: "Voice off", hint: "Click to go hands-free" },
  listening: { label: "Listening", hint: 'Say "Jarvis" to get my attention' },
  armed: { label: "Go ahead", hint: "No wake word needed" },
  thinking: { label: "Working", hint: "" },
  speaking: { label: "Speaking", hint: "Talk over me to interrupt" },
};

const STATE_RING: Record<VoiceState, string> = {
  idle: "border-subtle text-text-muted",
  listening: "border-cyan-accent/50 text-cyan-accent",
  armed: "border-emerald-accent/60 text-emerald-accent",
  thinking: "border-amber-400/60 text-amber-400",
  speaking: "border-cyan-accent text-cyan-accent",
};

export function VoiceOrb({
  isActive,
  isSupported,
  state,
  level,
  transcript,
  spokenText,
  error,
  onToggle,
  onStopSpeaking,
}: VoiceOrbProps) {
  if (!isSupported) return null;

  const copy = STATE_COPY[state];
  // Mic level drives the halo; capped so a loud room cannot blow up the layout.
  const halo = Math.min(1, level * 6);
  const caption = state === "speaking" ? spokenText : transcript;

  return (
    <div className="flex items-center gap-3">
      {isActive && caption && (
        <div className="hidden md:block max-w-[280px] text-right">
          <div className="text-[11px] text-text-muted truncate" title={caption}>
            {state === "speaking" ? "“" : ""}
            {caption}
            {state === "speaking" ? "”" : ""}
          </div>
        </div>
      )}

      <div className="flex flex-col items-end">
        <button
          onClick={state === "speaking" ? onStopSpeaking : onToggle}
          title={error || copy.hint || copy.label}
          aria-label={isActive ? "Turn off hands-free voice" : "Turn on hands-free voice"}
          className={`relative w-9 h-9 rounded-full border flex items-center justify-center transition-all active:scale-95 ${
            error ? "border-rose-accent/60 text-rose-accent" : STATE_RING[state]
          } ${isActive ? "bg-void" : "bg-void/60 hover:border-white/25"}`}
        >
          {isActive && (
            <span
              className="absolute inset-0 rounded-full bg-current opacity-20 pointer-events-none transition-transform duration-75"
              style={{ transform: `scale(${1 + halo * 0.55})` }}
            />
          )}
          {state === "thinking" && (
            <span className="absolute inset-0 rounded-full border-2 border-transparent border-t-current animate-spin" />
          )}

          {state === "speaking" ? (
            <svg className="w-4 h-4 relative" fill="currentColor" viewBox="0 0 24 24">
              <rect x="6" y="5" width="4" height="14" rx="1.5" />
              <rect x="14" y="5" width="4" height="14" rx="1.5" />
            </svg>
          ) : (
            <svg
              className="w-4 h-4 relative"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 15a3 3 0 003-3V6a3 3 0 10-6 0v6a3 3 0 003 3z"
              />
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-14 0M12 18v3" />
              {!isActive && <path strokeLinecap="round" d="M4 4l16 16" />}
            </svg>
          )}
        </button>

        <span className="text-[10px] font-mono text-text-muted mt-1 hidden sm:block">
          {error ? "mic error" : copy.label}
        </span>
      </div>
    </div>
  );
}
