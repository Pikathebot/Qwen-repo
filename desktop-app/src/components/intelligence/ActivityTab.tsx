"use client";

import React from "react";
import { ActivityStep } from "@/lib/types";
import { EmptyState } from "../ui/EmptyState";

export interface ActivityTabProps {
  steps: ActivityStep[];
  runId?: string;
  modelName?: string;
  totalLatencyMs?: number;
  tokensUsed?: number;
  className?: string;
}

export function ActivityTab({
  steps,
  runId = "a41f",
  modelName = "MAIN · Qwen3-30B",
  totalLatencyMs = 6200,
  tokensUsed = 2410,
  className = "",
}: ActivityTabProps) {
  if (!steps || steps.length === 0) {
    return (
      <EmptyState
        title="No Recent Activity"
        description="Agent run telemetry, step latencies, tool execution logs, and token usage metrics will appear here in real-time."
      />
    );
  }

  return (
    <div className={`space-y-4 flex flex-col h-full ${className}`}>
      {/* Run Summary Header */}
      <div className="p-3.5 rounded-card bg-black/30 border border-white/[0.08] space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-bold text-primary">Run #{runId}</span>
            <span className="px-1.5 py-0.2 rounded font-mono text-[10px] bg-accent/20 text-accent font-semibold">
              Completed
            </span>
          </div>
          <span className="text-[11px] font-mono text-secondary">{modelName}</span>
        </div>

        <div className="grid grid-cols-3 gap-2 pt-1 border-t border-white/[0.06] text-[10px] font-mono text-tertiary">
          <div>
            <span className="opacity-60 block">STEPS</span>
            <span className="text-primary font-semibold">{steps.length} steps</span>
          </div>
          <div>
            <span className="opacity-60 block">LATENCY</span>
            <span className="text-primary font-semibold">{(totalLatencyMs / 1000).toFixed(1)}s</span>
          </div>
          <div>
            <span className="opacity-60 block">TOKENS</span>
            <span className="text-primary font-semibold">{(tokensUsed / 1000).toFixed(1)}k</span>
          </div>
        </div>
      </div>

      {/* Steps Timeline */}
      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        <span className="font-mono text-[11px] text-tertiary uppercase tracking-wider font-semibold px-1">
          Execution Timeline
        </span>

        <div className="relative pl-4 space-y-3 before:absolute before:left-1.5 before:top-2 before:bottom-2 before:w-px before:bg-white/10">
          {steps.map((step) => {
            let dotColor = "bg-success border-success/40";
            if (step.status === "warning") {
              dotColor = "bg-warning border-warning/40";
            } else if (step.status === "error" || step.status === "failed") {
              dotColor = "bg-danger border-danger/40";
            } else if (step.status === "running") {
              dotColor = "bg-accent border-accent/60 animate-ping";
            }

            const formattedResult =
              typeof step.result === "string"
                ? step.result
                : JSON.stringify(step.result || {}, null, 2);

            return (
              <div key={step.id} className="relative group">
                <span
                  className={`absolute -left-[19px] top-1.5 w-2 h-2 rounded-full border ${dotColor}`}
                />
                <div className="p-2.5 rounded-xl bg-black/25 border border-white/[0.06] space-y-1.5 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-semibold text-primary">
                      {step.tool || (step.type === "status" ? "Agent Status" : "Action")}
                    </span>
                    {step.latency_ms !== undefined && (
                      <span className="text-[10px] font-mono text-tertiary">
                        {step.latency_ms}ms
                      </span>
                    )}
                  </div>

                  {step.summary && (
                    <p className="text-[11px] text-secondary font-sans leading-relaxed">
                      {step.summary}
                    </p>
                  )}

                  {step.args && Object.keys(step.args).length > 0 && (
                    <pre className="p-2 rounded bg-black/50 text-[10px] font-mono text-accent/80 overflow-x-auto max-h-24">
                      {JSON.stringify(step.args, null, 2)}
                    </pre>
                  )}

                  {step.result !== undefined && (
                    <pre className="p-2 rounded bg-black/50 text-[10px] font-mono text-secondary overflow-x-auto max-h-24 whitespace-pre-wrap">
                      {formattedResult}
                    </pre>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
