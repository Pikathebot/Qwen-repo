"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useAwareness } from "@/hooks/useAwareness";
import { useVoice } from "@/hooks/useVoice";
import { sendChatApi } from "@/lib/api";
import { PendingConfirmation, VoiceState } from "@/lib/types";
import { parseConfirmationIntent } from "@/lib/voice-intent";

/**
 * The always-on-top HUD.
 *
 * A separate Tauri window with its own webview, summoned by a global hotkey.
 * It is deliberately not the chat app in miniature: one ring of telemetry, the
 * voice state, and the last thing said in either direction.
 *
 * It keeps its own chat session so an ambient question asked at the HUD does
 * not interleave with whatever the main window is working through.
 */

const HUD_SESSION_ID = "jarvis-hud";

const STATE_COLOR: Record<VoiceState, string> = {
  idle: "#64748b",
  listening: "#22d3ee",
  armed: "#34d399",
  thinking: "#fbbf24",
  speaking: "#22d3ee",
};

const STATE_LABEL: Record<VoiceState, string> = {
  idle: "OFFLINE",
  listening: "LISTENING",
  armed: "GO AHEAD",
  thinking: "WORKING",
  speaking: "SPEAKING",
};

function Ring({
  percent,
  color,
  label,
  value,
}: {
  percent: number;
  color: string;
  label: string;
  value: string;
}) {
  const radius = 26;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, percent));
  const offset = circumference * (1 - clamped / 100);

  return (
    <div className="flex flex-col items-center gap-0.5">
      <div className="relative w-[64px] h-[64px]">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 64 64">
          <circle cx="32" cy="32" r={radius} fill="none" stroke="#1e293b" strokeWidth="5" />
          <circle
            cx="32"
            cy="32"
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth="5"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: "stroke-dashoffset 400ms ease" }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-[11px] font-mono text-slate-100">{value}</span>
        </div>
      </div>
      <span className="text-[9px] font-mono uppercase tracking-wider text-slate-500">{label}</span>
    </div>
  );
}

export default function Hud() {
  const [lastReply, setLastReply] = useState("");
  const [pendingConfirmations, setPendingConfirmations] = useState<PendingConfirmation[]>([]);
  // The backend re-derives the pending tool calls from the original prompt,
  // so approving them resends it (with approved_action_ids) rather than "".
  const lastQueryRef = useRef("");

  // The shared layout paints an opaque background; the HUD window is
  // transparent, so its rounded card is the only thing that should show.
  useEffect(() => {
    const previous = document.body.style.backgroundColor;
    document.body.style.backgroundColor = "transparent";
    return () => {
      document.body.style.backgroundColor = previous;
    };
  }, []);

  // Submits a turn (a fresh command, or a re-submit with approved action
  // ids) and updates the reply/confirmation state from the result.
  const submitTurn = useCallback(
    async (message: string, approvedActionIds?: string[]) => {
      try {
        const result = await sendChatApi({
          message: message || lastQueryRef.current,
          session_id: HUD_SESSION_ID,
          chat_mode: "WORKSPACE",
          approved_action_ids: approvedActionIds,
        });
        setLastReply(result.spoken || result.response);
        setPendingConfirmations(result.pending_confirmations || []);
        void voice.speak(result.spoken || result.response);
      } catch (e) {
        const message = e instanceof Error ? e.message : "Request failed";
        setLastReply(message);
      }
    },
    // `voice` is created below; this only runs after mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const handleCommand = useCallback(
    async (query: string) => {
      if (pendingConfirmations.length > 0) {
        const intent = parseConfirmationIntent(query);
        if (intent === "yes") {
          const actionIds = pendingConfirmations.map((p) => p.action_id);
          setPendingConfirmations([]);
          await submitTurn("", actionIds);
          return;
        }
        if (intent === "no") {
          setPendingConfirmations([]);
          setLastReply("Cancelled.");
          void voice.speak("Understood, cancelled.");
          return;
        }
        void voice.speak("Sorry, was that a yes or a no?");
        return;
      }

      lastQueryRef.current = query;
      await submitTurn(query);
    },
    // `voice` is created below; this only runs after mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [pendingConfirmations, submitTurn]
  );

  const voice = useVoice({
    sessionId: HUD_SESSION_ID,
    onCommand: (query) => void handleCommand(query),
  });

  // The HUD shows what Jarvis notices but never speaks it: the main window
  // owns spoken alerts, so an open HUD does not double up on them.
  const awareness = useAwareness({ snapshotIntervalMs: 4000 });

  const snapshot = awareness.snapshot;
  const vramPercent = snapshot?.vram_util_percent ?? 0;
  const gpuPercent = snapshot?.gpu_util_percent ?? 0;
  const latest = awareness.observations[awareness.observations.length - 1];

  const caption =
    voice.state === "speaking" && voice.spokenText
      ? voice.spokenText
      : voice.transcript || lastReply || latest?.title || "";

  return (
    <div
      data-tauri-drag-region
      className="w-screen h-screen select-none cursor-grab active:cursor-grabbing"
      style={{ background: "transparent" }}
    >
      <div
        data-tauri-drag-region
        className="h-full w-full rounded-2xl border border-slate-700/60 bg-slate-950/85 backdrop-blur-xl shadow-2xl px-4 py-3 flex items-center gap-4"
      >
        {/* Voice state / activation */}
        <button
          onClick={() => (voice.state === "speaking" ? voice.stopSpeaking() : void voice.toggle())}
          className="relative w-[52px] h-[52px] rounded-full border-2 flex items-center justify-center shrink-0 transition-transform active:scale-95"
          style={{ borderColor: STATE_COLOR[voice.state] }}
          title={voice.error || STATE_LABEL[voice.state]}
        >
          {voice.isActive && (
            <span
              className="absolute inset-0 rounded-full opacity-25"
              style={{
                background: STATE_COLOR[voice.state],
                transform: `scale(${1 + Math.min(1, voice.level * 6) * 0.5})`,
                transition: "transform 80ms linear",
              }}
            />
          )}
          <svg
            className="w-5 h-5 relative"
            fill="none"
            stroke={STATE_COLOR[voice.state]}
            strokeWidth={2}
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 15a3 3 0 003-3V6a3 3 0 10-6 0v6a3 3 0 003 3z"
            />
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-14 0M12 18v3" />
            {!voice.isActive && <path strokeLinecap="round" d="M4 4l16 16" />}
          </svg>
        </button>

        {/* Status line */}
        <div className="flex-1 min-w-0">
          <div
            className="text-[10px] font-mono tracking-widest"
            style={{ color: STATE_COLOR[voice.state] }}
          >
            {voice.error ? "MIC ERROR" : STATE_LABEL[voice.state]}
            {!awareness.connected && <span className="text-slate-600 ml-2">· offline</span>}
          </div>
          <div className="text-[11px] text-slate-300 truncate mt-0.5" title={caption}>
            {caption || "Jarvis standing by."}
          </div>
          {snapshot && (
            <div className="text-[9px] font-mono text-slate-500 mt-0.5 truncate">
              {snapshot.governor_status}
              {snapshot.gpu_temp_c !== null && ` · ${snapshot.gpu_temp_c.toFixed(0)}°C`}
              {` · RAM ${snapshot.ram_percent.toFixed(0)}%`}
              {snapshot.model_unloaded && " · model evicted"}
            </div>
          )}
        </div>

        {/* Telemetry */}
        <div className="flex items-center gap-3 shrink-0">
          <Ring
            percent={vramPercent}
            color={vramPercent >= 88 ? "#f43f5e" : "#22d3ee"}
            label="vram"
            value={`${vramPercent.toFixed(0)}%`}
          />
          <Ring
            percent={gpuPercent}
            color={gpuPercent >= 90 ? "#fbbf24" : "#34d399"}
            label="gpu"
            value={`${gpuPercent.toFixed(0)}%`}
          />
        </div>
      </div>
    </div>
  );
}
