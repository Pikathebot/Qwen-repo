"use client";

import React from "react";
import { LocalOnlyBadge, LocalPrivacyStatus } from "../ui/LocalOnlyBadge";
import { GovernorMeter } from "../ui/GovernorMeter";
import { GovernorTier } from "@/lib/types";

export interface StatusFooterProps {
  localStatus?: LocalPrivacyStatus;
  indexStatus?: string;
  chunksCount?: number;
  contextTokens?: {
    used: number;
    max: number;
  };
  governorTier?: GovernorTier;
  vramUsageMb?: number;
  className?: string;
  onOpenSystem?: () => void;
}

/**
 * StatusFooter — Floating M2 Glass Pill at canvas bottom
 * Renders: [🛡 Local only · ● Index ready · 12,403 chunks · Context 14k/32k] + Governor meter
 */
export function StatusFooter({
  localStatus = "local",
  indexStatus = "Index ready",
  chunksCount = 12403,
  contextTokens = { used: 14000, max: 32768 },
  governorTier = "IDLE",
  vramUsageMb,
  className = "",
  onOpenSystem,
}: StatusFooterProps) {
  const tokenRatio = (contextTokens.used / contextTokens.max) * 100;
  const tokenUsedK = (contextTokens.used / 1000).toFixed(0);
  const tokenMaxK = (contextTokens.max / 1000).toFixed(0);

  return (
    <footer
      onClick={onOpenSystem}
      className={`glass-pill px-4 py-1.5 flex items-center justify-between gap-4 text-[11px] font-mono select-none transition-all duration-std hover:bg-white/[0.10] cursor-pointer shadow-lg z-20 ${className}`}
      title="Click to view detailed System telemetry and model routing"
    >
      <div className="flex items-center gap-3">
        <LocalOnlyBadge status={localStatus} />

        <span className="text-white/20">|</span>

        <div className="flex items-center gap-1.5 text-secondary">
          <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
          <span className="font-medium text-primary">{indexStatus}</span>
          <span className="opacity-40">·</span>
          <span>{chunksCount.toLocaleString()} chunks</span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-secondary">
          <span className="opacity-60">Context:</span>
          <span className="text-primary font-semibold">
            {tokenUsedK}k / {tokenMaxK}k
          </span>
          <div className="w-12 h-1.5 rounded-full bg-white/10 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-std ${
                tokenRatio > 80
                  ? "bg-danger"
                  : tokenRatio > 60
                  ? "bg-warning"
                  : "bg-accent"
              }`}
              style={{ width: `${Math.min(tokenRatio, 100)}%` }}
            />
          </div>
        </div>

        <span className="text-white/20">|</span>

        <div className="flex items-center gap-2">
          <span className="text-tertiary text-[10px]">GOV</span>
          <GovernorMeter tier={governorTier} vramUsedMb={vramUsageMb} />
        </div>
      </div>
    </footer>
  );
}
