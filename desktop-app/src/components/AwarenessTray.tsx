"use client";

import React from "react";
import { Observation, ObservationSeverity } from "@/lib/types";

interface AwarenessTrayProps {
  observations: Observation[];
  onDismiss: (observationId: string) => void;
  onDismissAll: () => void;
}

const SEVERITY_STYLE: Record<ObservationSeverity, string> = {
  info: "border-subtle bg-surface/95 text-text-muted",
  notice: "border-cyan-accent/30 bg-surface/95 text-text-main",
  warning: "border-amber-400/40 bg-amber-400/10 text-amber-200",
  critical: "border-rose-accent/50 bg-rose-accent/10 text-rose-200",
};

const SEVERITY_DOT: Record<ObservationSeverity, string> = {
  info: "bg-text-muted",
  notice: "bg-cyan-accent",
  warning: "bg-amber-400",
  critical: "bg-rose-accent",
};

/**
 * Unprompted observations from the awareness monitor. Stacked bottom-up in
 * the corner so they never displace the conversation.
 */
export function AwarenessTray({ observations, onDismiss, onDismissAll }: AwarenessTrayProps) {
  if (observations.length === 0) return null;

  return (
    <div className="absolute bottom-28 right-6 z-20 flex flex-col items-end gap-2 pointer-events-none">
      {observations.length > 1 && (
        <button
          onClick={onDismissAll}
          className="pointer-events-auto text-[10px] font-mono text-text-muted hover:text-text-main transition-colors"
        >
          dismiss all ({observations.length})
        </button>
      )}

      {observations.map((observation) => (
        <div
          key={observation.id}
          className={`pointer-events-auto w-[320px] rounded-xl border px-3.5 py-2.5 shadow-lg backdrop-blur-md animate-in fade-in slide-in-from-right-2 duration-200 ${
            SEVERITY_STYLE[observation.severity]
          }`}
        >
          <div className="flex items-start gap-2.5">
            <span
              className={`mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 ${
                SEVERITY_DOT[observation.severity]
              }`}
            />
            <div className="min-w-0 flex-1">
              <div className="text-xs font-medium leading-snug">{observation.title}</div>
              {observation.detail && (
                <div className="text-[11px] opacity-75 mt-0.5 leading-snug">
                  {observation.detail}
                </div>
              )}
            </div>
            <button
              onClick={() => onDismiss(observation.id)}
              className="shrink-0 -mr-1 -mt-0.5 p-1 rounded-lg opacity-50 hover:opacity-100 transition-opacity"
              aria-label="Dismiss"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
