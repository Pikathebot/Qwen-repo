"use client";

import React from "react";
import { ActivityStep } from "@/lib/types";

export interface AgentStepperProps {
  steps: ActivityStep[];
  runId?: string;
  modelName?: string;
  className?: string;
}

/**
 * AgentStepper — Vertical Live Agent Execution Timeline
 * Implements DESIGN.MD §7 (AgentStepper: pending/running/success/warning/failed/blocked).
 */
export function AgentStepper({
  steps,
  runId,
  modelName = "Qwen3-30B",
  className = "",
}: AgentStepperProps) {
  if (!steps || steps.length === 0) return null;

  return (
    <div className={`space-y-2 p-3 rounded-card bg-black/20 border border-white/5 backdrop-blur-md ${className}`}>
      <div className="flex items-center justify-between text-[11px] font-mono text-tertiary px-1 pb-1 border-b border-white/[0.04]">
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          <span className="font-semibold text-secondary">
            {runId ? `Run #${runId}` : "Agent Execution Flow"}
          </span>
        </div>
        <span className="text-[10px] text-tertiary">{modelName}</span>
      </div>

      <div className="relative pl-4 space-y-3 before:absolute before:left-1.5 before:top-2 before:bottom-2 before:w-px before:bg-white/10">
        {steps.map((step) => {
          let dotStyle = "bg-success border-success/40";
          if (step.status === "running") {
            dotStyle = "bg-accent border-accent/60 animate-ping";
          } else if (step.status === "warning") {
            dotStyle = "bg-warning border-warning/60";
          } else if (step.status === "failed" || step.status === "error") {
            dotStyle = "bg-danger border-danger/60";
          }

          return (
            <div key={step.id} className="relative group">
              <span
                className={`absolute -left-[19px] top-1.5 w-2 h-2 rounded-full border ${dotStyle}`}
              />
              <div className="flex items-start justify-between gap-2 text-xs">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-primary font-medium">
                      {step.tool || (step.type === "status" ? "Agent Status" : "Action")}
                    </span>
                    {step.latency_ms !== undefined && (
                      <span className="text-[10px] font-mono text-tertiary">
                        {step.latency_ms}ms
                      </span>
                    )}
                  </div>
                  {step.summary && (
                    <p className="text-[11px] text-secondary mt-0.5 font-sans leading-relaxed">
                      {step.summary}
                    </p>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
