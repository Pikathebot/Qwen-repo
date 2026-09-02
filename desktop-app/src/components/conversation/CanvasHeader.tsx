"use client";

import React from "react";
import { ModelBadge } from "../ui/ModelBadge";
import { GovernorMeter } from "../ui/GovernorMeter";
import { GovernorTier } from "@/lib/types";

export interface CanvasHeaderProps {
  sessionTitle: string;
  projectName?: string;
  chatMode: "WORKSPACE" | "SYSTEM";
  onToggleChatMode: (mode: "WORKSPACE" | "SYSTEM") => void;
  selectedModel: string;
  governorTier: GovernorTier;
  vramUsedMb?: number;
  rightPanelOpen: boolean;
  onToggleRightPanel: () => void;
  artifactsCount?: number;
  onOpenSettings: () => void;
  className?: string;
}

/**
 * CanvasHeader — Header for the central conversation canvas
 */
export function CanvasHeader({
  sessionTitle,
  projectName,
  chatMode,
  onToggleChatMode,
  selectedModel = "Qwen3-30B",
  governorTier = "IDLE",
  vramUsedMb,
  rightPanelOpen,
  onToggleRightPanel,
  artifactsCount = 0,
  onOpenSettings,
  className = "",
}: CanvasHeaderProps) {
  return (
    <header
      className={`h-14 px-6 flex items-center justify-between border-b border-white/[0.06] bg-black/20 backdrop-blur-md select-none z-10 ${className}`}
    >
      {/* Left: Project & Session Titles */}
      <div className="flex items-center gap-3 min-w-0">
        <div className="flex items-center gap-2 min-w-0">
          {projectName && (
            <span className="hidden sm:inline-flex px-2.5 py-0.5 rounded-full text-[11px] font-mono font-medium bg-white/[0.06] border border-white/10 text-secondary truncate max-w-[160px]">
              {projectName}
            </span>
          )}
          <span className="font-semibold text-xs text-primary truncate max-w-[220px]">
            {sessionTitle}
          </span>
        </div>

        {/* Mode Switcher */}
        <div className="hidden md:flex items-center bg-white/[0.04] rounded-pill p-0.5 border border-white/[0.06] text-[10px] font-mono">
          <button
            onClick={() => onToggleChatMode("WORKSPACE")}
            className={`px-2.5 py-0.5 rounded-pill transition-all ${
              chatMode === "WORKSPACE"
                ? "bg-accent/20 text-accent font-semibold shadow-xs"
                : "text-tertiary hover:text-secondary"
            }`}
          >
            WORKSPACE
          </button>
          <button
            onClick={() => onToggleChatMode("SYSTEM")}
            className={`px-2.5 py-0.5 rounded-pill transition-all ${
              chatMode === "SYSTEM"
                ? "bg-reasoning/20 text-reasoning font-semibold shadow-xs"
                : "text-tertiary hover:text-secondary"
            }`}
          >
            SYSTEM
          </button>
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-3">
        <ModelBadge role="MAIN" modelName={selectedModel} size="sm" />

        <div className="hidden lg:flex items-center px-2 py-1 rounded-pill bg-white/[0.04] border border-white/5">
          <GovernorMeter tier={governorTier} vramUsedMb={vramUsedMb} />
        </div>

        {/* Intelligence Panel Toggle Button */}
        <button
          onClick={onToggleRightPanel}
          className={`p-1.5 rounded-xl border transition-all flex items-center gap-1.5 text-xs shadow-sm ${
            rightPanelOpen
              ? "bg-accent/15 border-accent/40 text-accent"
              : "bg-white/[0.04] border-white/10 hover:border-white/20 text-secondary hover:text-primary"
          }`}
          title="Toggle Intelligence & Artifacts Panel"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          {artifactsCount > 0 && (
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-accent/20 text-accent font-mono font-bold">
              {artifactsCount}
            </span>
          )}
        </button>

        {/* Settings Button */}
        <button
          onClick={onOpenSettings}
          className="p-1.5 rounded-xl bg-white/[0.04] border border-white/10 hover:border-white/20 text-secondary hover:text-primary transition-colors shadow-sm"
          title="Settings"
          aria-label="Open settings"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
            />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>
      </div>
    </header>
  );
}
