"use client";

import React, { useState } from "react";
import { UseGovernorReturn } from "@/hooks/useGovernor";

interface GovernorPillProps {
  governor: UseGovernorReturn;
  selectedModel?: string | null;
  onOpenSettings?: () => void;
}

export function GovernorPill({ governor, selectedModel, onOpenSettings }: GovernorPillProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const { status, throttled, activeBackend, configuredModel, pause, resume } = governor;

  // Determine dot color & label
  let dotColor = "bg-emerald-accent";
  let statusText = "Online";
  let ringColor = "ring-emerald-accent/20";

  if (status === "offline") {
    dotColor = "bg-rose-accent";
    statusText = "Offline";
    ringColor = "ring-rose-accent/20";
  } else if (throttled) {
    dotColor = "bg-amber-400";
    statusText = "Throttled";
    ringColor = "ring-amber-400/20";
  } else if (status === "degraded") {
    dotColor = "bg-amber-400";
    statusText = "Standby";
    ringColor = "ring-amber-400/20";
  }

  const activeModel = selectedModel || "main";
  let modelDisplayName = "Qwen3.5-9B";
  if (activeModel === "fast" || activeModel.toLowerCase().includes("4b")) {
    modelDisplayName = "Qwen3.5-4B (Fast)";
  } else if (activeModel === "main" || activeModel.toLowerCase().includes("9b")) {
    modelDisplayName = "Qwen3.5-9B (Main)";
  } else {
    modelDisplayName = activeModel.split("/").pop()?.replace(".gguf", "") || activeModel;
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface border border-subtle hover:border-white/20 transition-all text-xs text-text-main shadow-sm"
        title="Governor Resource & Runtime Status"
      >
        <span className="relative flex h-2 w-2">
          {status === "ok" && (
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-accent opacity-60"></span>
          )}
          <span className={`relative inline-flex rounded-full h-2 w-2 ${dotColor}`}></span>
        </span>
        <span className="font-medium text-text-muted">{statusText}</span>
        <span className="text-white/20">|</span>
        <span className="font-mono text-[11px] text-cyan-accent max-w-[150px] truncate font-medium">
          {modelDisplayName}
        </span>
        {throttled && (
          <span className="px-1.5 py-0.2 text-[9px] font-semibold bg-amber-500/20 text-amber-300 rounded border border-amber-500/40 animate-pulse">
            HIGH LOAD
          </span>
        )}
      </button>

      {isExpanded && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsExpanded(false)}
          />
          <div className="absolute right-0 mt-2 w-64 p-3 bg-surface rounded-xl border border-subtle shadow-xl z-50 text-xs space-y-2.5 backdrop-blur-lg">
            <div className="flex items-center justify-between border-b border-subtle pb-2">
              <span className="font-semibold text-text-main">Resource Governor</span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-mono ${ringColor} ${dotColor}/10 text-text-main`}>
                {activeBackend}
              </span>
            </div>

            <div className="space-y-1 text-text-muted">
              <div className="flex justify-between">
                <span>Model:</span>
                <span className="text-text-main font-mono text-[11px] truncate max-w-[130px]" title={configuredModel}>
                  {modelDisplayName}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Status:</span>
                <span className={status === "ok" ? "text-emerald-accent" : "text-amber-400"}>
                  {status.toUpperCase()}
                </span>
              </div>
              <div className="flex justify-between">
                <span>VRAM Throttle:</span>
                <span className={throttled ? "text-rose-accent font-bold" : "text-text-muted"}>
                  {throttled ? "Active" : "Normal"}
                </span>
              </div>
            </div>

            <div className="pt-2 border-t border-subtle flex gap-2">
              <button
                onClick={() => {
                  if (throttled) resume();
                  else pause("Manual pause via UI");
                }}
                className="flex-1 py-1 px-2 rounded bg-void hover:bg-white/5 border border-subtle text-[11px] text-text-muted hover:text-text-main transition-colors"
              >
                {throttled ? "Resume Governor" : "Pause Governor"}
              </button>
              {onOpenSettings && (
                <button
                  onClick={() => {
                    setIsExpanded(false);
                    onOpenSettings();
                  }}
                  className="py-1 px-2 rounded bg-void hover:bg-white/5 border border-subtle text-[11px] text-cyan-accent hover:underline"
                >
                  Settings
                </button>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
