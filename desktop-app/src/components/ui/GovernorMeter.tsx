"use client";

import React from "react";
import { GovernorTier } from "@/lib/types";

export interface GovernorMeterProps {
  tier?: GovernorTier;
  vramUsedMb?: number;
  vramTotalMb?: number;
  showLabels?: boolean;
  className?: string;
  onClick?: () => void;
}

const TIERS: Array<{
  id: GovernorTier;
  label: string;
  color: string;
  activeColor: string;
}> = [
  { id: "IDLE", label: "Idle", color: "bg-white/10", activeColor: "bg-neutral" },
  { id: "LIGHT", label: "Light", color: "bg-white/10", activeColor: "bg-memory" },
  { id: "MODERATE", label: "Moderate", color: "bg-white/10", activeColor: "bg-accent" },
  { id: "HEAVY", label: "Heavy", color: "bg-white/10", activeColor: "bg-reasoning" },
  { id: "CRITICAL", label: "Critical", color: "bg-white/10", activeColor: "bg-danger animate-pulse" },
  { id: "PAUSED", label: "Paused", color: "bg-white/10", activeColor: "bg-warning" },
];

/**
 * GovernorMeter — 6-Segment Resource Governor Hardware Monitor
 * Renders IDLE, LIGHT, MODERATE, HEAVY, CRITICAL, PAUSED states.
 */
export function GovernorMeter({
  tier = "IDLE",
  vramUsedMb,
  vramTotalMb = 24576,
  showLabels = false,
  className = "",
  onClick,
}: GovernorMeterProps) {
  const getActiveIndex = (t: GovernorTier) => {
    switch (t) {
      case "IDLE":
        return 0;
      case "LIGHT":
        return 1;
      case "MODERATE":
        return 2;
      case "HEAVY":
        return 3;
      case "CRITICAL":
        return 4;
      case "PAUSED":
        return 5;
    }
  };

  const activeIndex = getActiveIndex(tier);

  return (
    <div
      onClick={onClick}
      className={`inline-flex flex-col gap-1 ${
        onClick ? "cursor-pointer group" : ""
      } ${className}`}
      title={`Resource Governor: ${tier}${
        vramUsedMb ? ` · ${(vramUsedMb / 1024).toFixed(1)}GB VRAM` : ""
      }`}
    >
      <div className="flex items-center gap-1">
        {TIERS.slice(0, 5).map((t, idx) => {
          const isFilled = tier === "PAUSED" ? false : idx <= activeIndex;
          const barColor = isFilled ? t.activeColor : "bg-white/[0.08]";

          return (
            <div
              key={t.id}
              className={`h-1.5 w-3.5 rounded-full transition-all duration-std ease-liquid ${barColor}`}
            />
          );
        })}
        {tier === "PAUSED" && (
          <div className="h-1.5 w-6 rounded-full bg-warning animate-pulse" />
        )}
      </div>

      {showLabels && (
        <div className="flex items-center justify-between text-[10px] font-mono text-tertiary">
          <span>GOV: {tier}</span>
          {vramUsedMb !== undefined && (
            <span>
              {(vramUsedMb / 1024).toFixed(1)} / {(vramTotalMb / 1024).toFixed(0)} GB
            </span>
          )}
        </div>
      )}
    </div>
  );
}
