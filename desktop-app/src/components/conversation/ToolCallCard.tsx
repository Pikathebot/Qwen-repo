"use client";

import React, { useState } from "react";
import { ToolStep } from "@/lib/types";

export interface ToolCallCardProps {
  step: ToolStep;
  className?: string;
}

/**
 * ToolCallCard — Collapsible M2 Glass Tool Run Card
 * Features: live status indicators, argument formatting, execution latency, and output preview.
 */
export function ToolCallCard({ step, className = "" }: ToolCallCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  let statusBadge = (
    <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-accent/10 text-accent border border-accent/30">
      <span className="w-1.5 h-1.5 rounded-full bg-accent animate-ping" />
      Running
    </span>
  );

  if (step.status === "success") {
    statusBadge = (
      <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-success/10 text-success border border-success/30">
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
        </svg>
        Completed
      </span>
    );
  } else if (step.status === "warning") {
    statusBadge = (
      <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-warning/10 text-warning border border-warning/30">
        <span className="w-1.5 h-1.5 rounded-full bg-warning" />
        Needs Approval
      </span>
    );
  } else if (step.status === "error" || step.status === "blocked") {
    statusBadge = (
      <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-danger/10 text-danger border border-danger/30">
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
        </svg>
        Failed
      </span>
    );
  }

  const argsFormatted =
    step.args && typeof step.args === "object"
      ? JSON.stringify(step.args, null, 2)
      : String(step.args || "");

  const resultFormatted =
    typeof step.result === "string"
      ? step.result
      : JSON.stringify(step.result || {}, null, 2);

  return (
    <div
      className={`rounded-xl border border-white/[0.08] bg-black/25 backdrop-blur-md overflow-hidden text-xs transition-all ${className}`}
    >
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-white/[0.04] transition-colors text-left select-none"
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="p-1 rounded-lg bg-white/[0.06] border border-white/10 text-accent">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </div>
          <span className="font-mono text-primary font-semibold truncate">{step.tool}</span>
          {step.summary && (
            <span className="text-secondary text-[11px] truncate hidden sm:inline">
              · {step.summary}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {step.latency_ms !== undefined && (
            <span className="text-[10px] font-mono text-tertiary">{step.latency_ms}ms</span>
          )}
          {statusBadge}
          <svg
            className={`w-3.5 h-3.5 text-tertiary transition-transform duration-fast ${
              isExpanded ? "rotate-180" : ""
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {isExpanded && (
        <div className="px-3 pb-3 pt-1 border-t border-white/[0.06] bg-black/30 space-y-2">
          {step.args && Object.keys(step.args).length > 0 && (
            <div>
              <div className="text-[10px] uppercase font-mono font-semibold text-tertiary mb-1">
                Arguments
              </div>
              <pre className="p-2 rounded-lg bg-black/50 text-accent/90 font-mono text-[11px] border border-white/5 overflow-x-auto max-h-36">
                {argsFormatted}
              </pre>
            </div>
          )}

          {step.result !== undefined && (
            <div>
              <div className="text-[10px] uppercase font-mono font-semibold text-tertiary mb-1">
                Result Output
              </div>
              <pre className="p-2 rounded-lg bg-black/50 text-secondary font-mono text-[11px] border border-white/5 overflow-x-auto max-h-48 whitespace-pre-wrap">
                {resultFormatted}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
